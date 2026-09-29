"""Verify a compacted SQLite database without importing the legacy ORM.

    python scripts/verify_schema_v2.py --database /path/to/migrated.db
"""

import argparse
import json
import sqlite3
from pathlib import Path

REVISION = "c24a29db2026"

REMOVED = frozenset({
    "event_settings", "registration_bus_needs", "consents", "room_assignments",
    "gala_draw_orders", "gala_seat_holds", "gala_seat_assignments",
    "itinerary_items", "policy_documents", "announcements", "chat_sessions", "chat_messages",
})


def verify(database: Path) -> dict:
    with sqlite3.connect(database.resolve(strict=True).as_uri() + "?mode=ro", uri=True) as db:
        version = db.execute("SELECT version_num FROM alembic_version").fetchone()
        if version != (REVISION,):
            raise ValueError(f"Expected Alembic {REVISION}; found {version}")
        tables = {row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' AND name <> 'alembic_version'"
        )}
        if len(tables) != 24 or REMOVED & tables or "schema_archive" not in tables:
            raise ValueError(f"Invalid 24-table schema: count={len(tables)}, stale={sorted(REMOVED & tables)}")
        errors = db.execute("PRAGMA foreign_key_check").fetchall()
        if errors:
            raise ValueError(f"Foreign key violations: {errors[:5]}")
        archive = dict(db.execute("SELECT source_table, COUNT(*) FROM schema_archive GROUP BY source_table"))
        if set(archive) - REMOVED:
            raise ValueError("Archive contains unexpected source tables")
        total_archived = sum(archive.values())
        scanned = 0
        for (table, row_id, payload) in db.execute(
            "SELECT source_table, source_id, payload FROM schema_archive"
        ):
            data = json.loads(payload)
            if not isinstance(data, dict) or data.get("id") != row_id:
                raise ValueError(f"Invalid archived row {table}#{row_id}")
            scanned += 1
        if scanned != total_archived:
            raise ValueError("Archive row count changed during verification")
        for table, column in (
            ("events", "settings_json"), ("events", "itinerary_json"),
            ("events", "documents_json"), ("events", "announcements_json"),
            ("registrations", "bus_needs_json"), ("registrations", "consents_json"),
            ("registrations", "room_assignment_json"), ("gala_layouts", "draw_orders_json"),
            ("gala_seats", "hold_json"), ("gala_seats", "assignment_json"),
            ("users", "chat_history_json"),
        ):
            for (value,) in db.execute(f'SELECT "{column}" FROM "{table}" WHERE "{column}" IS NOT NULL'):
                json.loads(value)
        return {"revision": REVISION, "table_count": len(tables), "foreign_key_errors": 0,
                "archived_rows": archive, "events": db.execute("SELECT COUNT(*) FROM events").fetchone()[0]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.database), ensure_ascii=True, indent=2))
    except (OSError, ValueError, sqlite3.Error) as exc:
        parser.exit(1, f"Schema v2 verification failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())