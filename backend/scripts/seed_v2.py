"""Seed a migrated v2 SQLite database without importing legacy ORM models.

    python scripts/seed_v2.py --database /tmp/v2.db --reset
    python scripts/seed_v2.py --database /tmp/v2.db --second-event

Development/demo only. --reset deletes existing business data and refuses to run
if the archive contains migrated rows; never use it on real data.
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.security import hash_password

REVISION = "c24a29db2026"
NOW = "2026-09-29T00:00:00+00:00"


def _insert(db: sqlite3.Connection, table: str, **values) -> int:
    names = ", ".join(f'"{name}"' for name in values)
    marks = ", ".join("?" for _ in values)
    return db.execute(f'INSERT INTO "{table}" ({names}) VALUES ({marks})', tuple(values.values())).lastrowid


def _clear(db: sqlite3.Connection) -> None:
    """Delete children before parents with FK enforcement enabled."""
    tables = [name for (name,) in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
        "AND name != 'alembic_version'"
    )]
    seen: set[str] = set()
    ordered: list[str] = []

    def visit(table: str) -> None:
        if table in seen:
            return
        seen.add(table)
        for (_, _, parent, *_) in db.execute(f'PRAGMA foreign_key_list("{table}")'):
            if parent in tables:
                visit(parent)
        ordered.append(table)

    for table in tables:
        visit(table)
    for table in reversed(ordered):
        db.execute(f'DELETE FROM "{table}"')


def _ensure_user(db: sqlite3.Connection, email: str, role: str, name: str) -> int:
    row = db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    if row:
        return row[0]
    return _insert(
        db, "users", email=email, full_name=name, role=role,
        password_hash=hash_password("Admin12345" if role != "employee" else "Matkhau123"),
        phone="0912345678", id_card_number="001099012345", date_of_birth="1999-01-01",
        gender="male", is_active=1, must_change_password=0, failed_login_count=0,
        created_at=NOW, updated_at=NOW,
    )


def seed_event(db: sqlite3.Connection, *, year: int, active: bool) -> int:
    event_id = _insert(
        db, "events", code=f"TB{year}", name=f"Team Building {year}",
        destination="Phú Quốc" if year == 2026 else "Đà Nẵng",
        start_date=f"{year}-10-15", end_date=f"{year}-10-17",
        status="registration_open", terms_version="v1",
        terms_content="Quy định tham gia Team Building (dữ liệu mẫu).",
        is_active=int(active), created_at=NOW, updated_at=NOW,
        settings_json=json.dumps([{"key": "allocation.team_weight", "value": "10"}]),
        itinerary_json=json.dumps([{"id": 1, "day_date": f"{year}-10-15", "title": "Đến nơi"}]),
        documents_json="[]", announcements_json="[]",
    )
    shift_id = _insert(db, "shifts", event_id=event_id, code="CA1", name="Ca 1", display_order=1)
    leg_id = _insert(db, "trip_legs", event_id=event_id, code="CITY_TO_AIRPORT",
                     name="Thành phố → sân bay", direction="outbound",
                     is_airport_linked=1, display_order=1)
    hotel_id = _insert(db, "hotels", event_id=event_id, name=f"Khách sạn mẫu {year}",
                       created_at=NOW, updated_at=NOW)
    room_id = _insert(db, "rooms", hotel_id=hotel_id, room_number="101", capacity=2,
                      gender_policy="any")
    layout_id = _insert(db, "gala_layouts", event_id=event_id, name="Gala Dinner",
                        stage_position="top", grid_width=12, grid_height=10,
                        selection_status="closed", turn_seconds=300, hold_seconds=120,
                        created_at=NOW, updated_at=NOW, draw_orders_json="[]")
    table_id = _insert(db, "gala_tables", layout_id=layout_id, table_code="B01",
                       seat_count=2, pos_x=1, pos_y=1, is_vip=0, is_available=1)
    for seat_number in (1, 2):
        _insert(db, "gala_seats", table_id=table_id, seat_number=seat_number, is_available=1)
    flight_id = _insert(db, "flights", event_id=event_id, flight_code=f"VN{year}",
                        direction="outbound", shift_id=shift_id, departure_airport="HAN",
                        arrival_airport="PQC" if year == 2026 else "DAD",
                        departure_time=f"{year}-10-15T00:00:00+00:00",
                        arrival_time=f"{year}-10-15T02:00:00+00:00",
                        capacity=20, reserved_slots=0, is_active=1,
                        created_at=NOW, updated_at=NOW)
    bus_id = _insert(db, "buses", event_id=event_id, trip_leg_id=leg_id,
                     bus_code="XE-01", capacity=20, linked_flight_id=flight_id,
                     created_at=NOW, updated_at=NOW)

    # Existing users are shared across events; the second event must not duplicate them.
    _ensure_user(db, "superadmin@company.vn", "super_admin", "Quản trị hệ thống")
    _ensure_user(db, "btc@company.vn", "admin", "Ban tổ chức")
    user_id = _ensure_user(db, "demo@company.vn", "employee", "Nhân viên mẫu")
    registration_id = _insert(
        db, "registrations", event_id=event_id, user_id=user_id,
        is_participating=1, is_shift_locked=0, shift_id=shift_id,
        companion_count=0, status="submitted", penalty_applied=0,
        submitted_at=NOW, created_at=NOW, updated_at=NOW,
        room_id=room_id,
        room_assignment_json=json.dumps({"room_id": room_id, "assignment_mode": "manual", "assigned_at": NOW}),
        bus_needs_json=json.dumps([{"trip_leg_id": leg_id, "needs_bus": True}]),
        consents_json=json.dumps([{"terms_version": "v1", "agreed_at": NOW}]),
    )
    _insert(db, "flight_assignments", registration_id=registration_id,
            flight_id=flight_id, direction="outbound", assignment_mode="auto", assigned_at=NOW)
    _insert(db, "bus_assignments", registration_id=registration_id, bus_id=bus_id,
            trip_leg_id=leg_id, assignment_mode="auto", assigned_at=NOW)
    return event_id


def seed(database: Path, *, reset: bool = False, second_event: bool = False) -> list[int]:
    database = database.resolve(strict=True)
    with sqlite3.connect(database) as db:
        db.execute("PRAGMA foreign_keys=ON")
        revision = db.execute("SELECT version_num FROM alembic_version").fetchone()
        if revision != (REVISION,):
            raise ValueError(f"Database must first be upgraded to {REVISION}; found {revision}")
        if reset:
            if db.execute("SELECT 1 FROM schema_archive LIMIT 1").fetchone():
                raise ValueError("Refusing --reset: schema_archive contains migrated data. "
                                 "Use a new disposable database instead")
            _clear(db)
        first_exists = db.execute("SELECT id FROM events WHERE code='TB2026'").fetchone()
        if first_exists and not second_event and not reset:
            raise ValueError("TB2026 already exists. Pass --second-event or --reset")
        ids = []
        if not first_exists or reset:
            ids.append(seed_event(db, year=2026, active=True))
        if second_event and not db.execute("SELECT id FROM events WHERE code='TB2027'").fetchone():
            ids.append(seed_event(db, year=2027, active=False))
        violations = db.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(f"Foreign key violations: {violations}")
        count = db.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' AND name <> 'alembic_version'"
        ).fetchone()[0]
        if count != 24:
            raise RuntimeError(f"Expected 24 business tables, found {count}")
        db.commit()
        return ids


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--second-event", action="store_true")
    args = parser.parse_args()
    try:
        ids = seed(args.database, reset=args.reset, second_event=args.second_event)
    except (ValueError, OSError, sqlite3.Error, RuntimeError) as exc:
        parser.exit(1, f"Seed v2 failed: {exc}\n")
    print(f"Seed v2 complete; created event IDs: {ids}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())