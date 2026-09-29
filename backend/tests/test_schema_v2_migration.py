"""Database-only integration tests; run inside the backend Python environment."""

import os
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("alembic")

from scripts.preflight_schema_v2 import MERGED_TABLES, SOURCE_REVISION
from scripts.verify_schema_v2 import verify

ROOT = Path(__file__).resolve().parents[1]


def command(database: Path, *args: str) -> None:
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{database}"}
    subprocess.run(args, cwd=ROOT, env=env, check=True, capture_output=True, text=True)


def test_upgrade_empty_and_seed_both_events(tmp_path):
    database = tmp_path / "empty.db"
    command(database, "alembic", "upgrade", "head")
    command(database, sys.executable, "scripts/seed_v2.py", "--database", str(database), "--reset")
    command(database, sys.executable, "scripts/seed_v2.py", "--database", str(database), "--second-event")
    report = verify(database)
    assert report["table_count"] == 24
    assert report["events"] == 2
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT COUNT(*) FROM registrations").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 3
        seats = [row[0] for row in db.execute("SELECT id FROM gala_seats ORDER BY id LIMIT 2")]
        db.execute("UPDATE gala_seats SET assignment_json=? WHERE id=?",
                   (json.dumps({"registration_id": 1}), seats[0]))
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE gala_seats SET assignment_json=? WHERE id=?",
                       (json.dumps({"registration_id": 1}), seats[1]))
    command(database, sys.executable, "scripts/seed_v2.py", "--database", str(database), "--reset")
    assert verify(database)["events"] == 1


def test_upgrade_old_database_archives_every_row(tmp_path):
    database = tmp_path / "old.db"
    command(database, "alembic", "upgrade", SOURCE_REVISION)
    command(database, sys.executable, "scripts/seed.py", "--registration-rate", "0.1")
    with sqlite3.connect(database) as db:
        registration_id = db.execute("SELECT id FROM registrations LIMIT 1").fetchone()[0]
        user_id, event_id = db.execute(
            "SELECT user_id, event_id FROM registrations WHERE id=?", (registration_id,)
        ).fetchone()
        room_id = db.execute("SELECT id FROM rooms LIMIT 1").fetchone()[0]
        layout_id = db.execute("SELECT id FROM gala_layouts LIMIT 1").fetchone()[0]
        team_id = db.execute("SELECT id FROM teams LIMIT 1").fetchone()[0]
        seat_ids = [row[0] for row in db.execute("SELECT id FROM gala_seats ORDER BY id LIMIT 2")]
        db.execute(
            "INSERT INTO room_assignments (registration_id,room_id,is_room_captain,"
            "assignment_mode,assigned_at) VALUES (?,?,1,'manual','2026-09-29')",
            (registration_id, room_id),
        )
        db.execute(
            "INSERT INTO gala_draw_orders (layout_id,team_id,draw_position,quota,status) "
            "VALUES (?,?,1,1,'waiting')", (layout_id, team_id),
        )
        db.execute(
            "INSERT INTO gala_seat_holds (seat_id,team_id,held_by,held_at,expires_at) "
            "VALUES (?,?,?,'2026-09-29','2026-09-30')", (seat_ids[0], team_id, user_id),
        )
        db.execute(
            "INSERT INTO gala_seat_assignments (seat_id,team_id,registration_id,confirmed_by,confirmed_at) "
            "VALUES (?,?,?,?,'2026-09-29')", (seat_ids[1], team_id, registration_id, user_id),
        )
        session_id = db.execute(
            "INSERT INTO chat_sessions (user_id,event_id,title,created_at) VALUES (?,?,?,?)",
            (user_id, event_id, "Kiểm thử", "2026-09-29"),
        ).lastrowid
        db.execute(
            "INSERT INTO chat_messages (session_id,role,content,created_at) VALUES (?,?,?,?)",
            (session_id, "user", "Giờ xe?", "2026-09-29"),
        )
        db.execute(
            "INSERT INTO policy_documents (event_id,doc_type,title,content,version,is_indexed,updated_at) "
            "VALUES (NULL,'faq','Chung','Tài liệu chung','v1',0,'2026-09-29')"
        )
        db.commit()
        before = {
            table: db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in MERGED_TABLES
        }
        original_users = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    assert sum(before.values()) > 0
    command(database, "alembic", "upgrade", "head")
    report = verify(database)
    assert report["table_count"] == 24
    assert report["archived_rows"] == {key: count for key, count in before.items() if count}
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == original_users
        assert db.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1
        if before["policy_documents"]:
            assert db.execute(
                "SELECT COUNT(*) FROM schema_archive WHERE source_table='policy_documents'"
            ).fetchone()[0] == before["policy_documents"]
        assert db.execute("SELECT COUNT(*) FROM registrations WHERE bus_needs_json IS NOT NULL").fetchone()[0] > 0
        room, assignment = db.execute(
            "SELECT room_id,room_assignment_json FROM registrations WHERE id=?", (registration_id,)
        ).fetchone()
        assert room == room_id
        assert json.loads(assignment)["is_room_captain"] == 1
        assert json.loads(db.execute(
            "SELECT draw_orders_json FROM gala_layouts WHERE id=?", (layout_id,)
        ).fetchone()[0])[0]["team_id"] == team_id
        assert json.loads(db.execute(
            "SELECT hold_json FROM gala_seats WHERE id=?", (seat_ids[0],)
        ).fetchone()[0])["held_by"] == user_id
        assert json.loads(db.execute(
            "SELECT assignment_json FROM gala_seats WHERE id=?", (seat_ids[1],)
        ).fetchone()[0])["registration_id"] == registration_id
        history = json.loads(db.execute(
            "SELECT chat_history_json FROM users WHERE id=?", (user_id,)
        ).fetchone()[0])
        assert history[0]["messages"][0]["content"] == "Giờ xe?"
        assert db.execute(
            "SELECT COUNT(*) FROM schema_archive WHERE source_table='policy_documents' "
            "AND json_extract(payload,'$.event_id') IS NULL"
        ).fetchone()[0] == 1
    command(database, sys.executable, "scripts/seed_v2.py", "--database", str(database), "--second-event")
    assert verify(database)["events"] == 2
    with pytest.raises(subprocess.CalledProcessError):
        command(database, sys.executable, "scripts/seed_v2.py", "--database", str(database), "--reset")
    assert verify(database)["archived_rows"] == report["archived_rows"]