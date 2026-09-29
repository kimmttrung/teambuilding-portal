"""Compact the operational schema to 24 tables without discarding legacy rows.

Revision ID: c24a29db2026
Revises: 5f3a91c7d420

This is a DB-only change: application services reading the removed tables need
the adapters documented in docs/16-schema-v2-handoff.md before serving traffic.
"""

import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c24a29db2026"
down_revision: Union[str, Sequence[str], None] = "5f3a91c7d420"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REMOVED = (
    "event_settings", "registration_bus_needs", "consents", "room_assignments",
    "gala_draw_orders", "gala_seat_holds", "gala_seat_assignments",
    "itinerary_items", "policy_documents", "announcements",
    "chat_messages", "chat_sessions",  # child first
)
NEW_COLUMNS = {
    "events": ("settings_json", "itinerary_json", "documents_json", "announcements_json"),
    "registrations": ("bus_needs_json", "consents_json", "room_assignment_json"),
    "gala_layouts": ("draw_orders_json",),
    "gala_seats": ("hold_json", "assignment_json"),
    "users": ("chat_history_json",),
}


def _rows(connection, table: str) -> list[dict]:
    # table only ever comes from the constants above.
    return [dict(row) for row in connection.execute(sa.text(f'SELECT * FROM "{table}"')).mappings()]


def _save_json(connection, table: str, row_id: int, column: str, data) -> None:
    connection.execute(
        sa.text(f'UPDATE "{table}" SET "{column}"=:value WHERE id=:id'),
        {"value": json.dumps(data, ensure_ascii=False, separators=(",", ":")), "id": row_id},
    )


def upgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name != "sqlite":
        raise RuntimeError("Schema v2 requires SQLite")
    if connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall():
        raise RuntimeError("Source database has foreign-key violations; fix before migration")
    old_count = connection.execute(sa.text(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' AND name != 'alembic_version'"
    )).scalar_one()
    if old_count != 35:
        raise RuntimeError(f"Schema v2 requires exactly 35 legacy tables, found {old_count}")

    op.create_table(
        "schema_archive",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_table", sa.String(64), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("archived_at", sa.String(32), nullable=False),
        sa.UniqueConstraint("source_table", "source_id", name="uq_schema_archive_source"),
    )
    for table, columns in NEW_COLUMNS.items():
        for column in columns:
            op.add_column(table, sa.Column(column, sa.Text(), nullable=True))
    # Do not rebuild registrations here: many retained tables reference its primary key.
    # SQLite cannot add a FK to an existing table with ALTER TABLE. room_id is
    # checked by application logic until a later controlled rebuild adds that FK.
    op.add_column("registrations", sa.Column("room_id", sa.Integer(), nullable=True))
    op.create_index("ix_registrations_room_id", "registrations", ["room_id"])

    rows = {table: _rows(connection, table) for table in REMOVED}
    now = datetime.now(timezone.utc).isoformat()
    for table, records in rows.items():
        if records:
            connection.execute(
                sa.text("INSERT INTO schema_archive (source_table,source_id,payload,archived_at) "
                        "VALUES (:table,:id,:payload,:now)"),
                [{"table": table, "id": row["id"],
                  "payload": json.dumps(row, ensure_ascii=False), "now": now}
                 for row in records],
            )
        archived = connection.execute(
            sa.text("SELECT COUNT(*) FROM schema_archive WHERE source_table=:table"), {"table": table}
        ).scalar_one()
        if archived != len(records):
            raise RuntimeError(f"Archive count mismatch for {table}")

    def grouped(table: str, key: str) -> dict[int, list[dict]]:
        result: dict[int, list[dict]] = defaultdict(list)
        for row in rows[table]:
            if row[key] is not None:
                result[row[key]].append(row)
        return result

    sources = (
        ("event_settings", "event_id", "events", "settings_json"),
        ("itinerary_items", "event_id", "events", "itinerary_json"),
        ("policy_documents", "event_id", "events", "documents_json"),
        ("announcements", "event_id", "events", "announcements_json"),
        ("registration_bus_needs", "registration_id", "registrations", "bus_needs_json"),
        ("gala_draw_orders", "layout_id", "gala_layouts", "draw_orders_json"),
        ("gala_seat_holds", "seat_id", "gala_seats", "hold_json"),
        ("gala_seat_assignments", "seat_id", "gala_seats", "assignment_json"),
    )
    for source, key, target, column in sources:
        for row_id, values in grouped(source, key).items():
            _save_json(connection, target, row_id, column,
                       values[0] if source in ("gala_seat_holds", "gala_seat_assignments") else values)

    # Retain the database-level guarantee that one registration occupies at most
    # one gala seat (the original assignments table had UNIQUE(registration_id)).
    op.execute(
        "CREATE UNIQUE INDEX uq_gala_seats_assigned_registration ON gala_seats "
        "(json_extract(assignment_json, '$.registration_id')) "
        "WHERE json_extract(assignment_json, '$.registration_id') IS NOT NULL"
    )

    for row in rows["room_assignments"]:
        if connection.execute(sa.text("SELECT 1 FROM rooms WHERE id=:id"),
                              {"id": row["room_id"]}).first() is None:
            raise RuntimeError(f"Legacy room assignment references missing room {row['room_id']}")
        connection.execute(sa.text("UPDATE registrations SET room_id=:room_id WHERE id=:id"),
                           {"room_id": row["room_id"], "id": row["registration_id"]})
        _save_json(connection, "registrations", row["registration_id"], "room_assignment_json", row)

    # Consent is keyed by (user,event,version); a registration may be missing in
    # legacy data. Such rows remain in the lossless archive, never silently reassigned.
    reg_ids = {(r[0], r[1]): r[2] for r in connection.execute(
        sa.text("SELECT user_id,event_id,id FROM registrations")
    )}
    consents: dict[int, list[dict]] = defaultdict(list)
    for row in rows["consents"]:
        reg_id = reg_ids.get((row["user_id"], row["event_id"]))
        if reg_id is not None:
            consents[reg_id].append(row)
    for reg_id, values in consents.items():
        _save_json(connection, "registrations", reg_id, "consents_json", values)

    messages = grouped("chat_messages", "session_id")
    histories: dict[int, list[dict]] = defaultdict(list)
    for session in rows["chat_sessions"]:
        histories[session["user_id"]].append({**session, "messages": messages.get(session["id"], [])})
    for user_id, history in histories.items():
        _save_json(connection, "users", user_id, "chat_history_json", history)

    # Do not remove data before every row has an immutable copy. No retained table
    # has an FK to any removed table; chat_messages must be dropped first.
    for table in REMOVED:
        op.drop_table(table)
    if connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall():
        raise RuntimeError("Foreign-key violations after schema compaction")
    count = connection.execute(sa.text(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' AND name != 'alembic_version'"
    )).scalar_one()
    if count != 24:
        raise RuntimeError(f"Schema v2 expected 24 tables, found {count}")


def downgrade() -> None:
    raise RuntimeError("Schema v2 downgrade requires restoring the pre-migration SQLite backup")