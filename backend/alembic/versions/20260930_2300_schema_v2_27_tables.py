"""schema v2: 35 -> 27 tables

Revision ID: 7d2a9e41c027
Revises: 5f3a91c7d420
Create Date: 2026-09-30 23:00:00.000000

Gộp bảng theo ERD v2 (docs/03-data-model.md): chỉ gộp khi hai bảng cùng khoá hoặc quan hệ một-một,
và gộp thành CỘT THẬT (không dồn vào JSON) để giữ khoá ngoại, UNIQUE và lọc được bằng SQL.

| Bảng cũ                                   | Thành                                                    |
|-------------------------------------------|----------------------------------------------------------|
| event_settings                            | events.settings (JSON {khoá: giá trị đã parse})          |
| consents                                  | registrations.consent_* (bản mới nhất); bản cũ hơn -> audit_logs `consent.agreed` |
| room_assignments                          | registrations.room_id, is_room_captain, room_mode, room_assigned_by/at, room_note |
| registration_bus_needs + bus_assignments  | registration_legs (một dòng mỗi (đăng ký, chặng); bus_id NULL = chưa xếp) |
| gala_seat_holds + gala_seat_assignments   | gala_seats.status free/held/taken + cột giữ/chốt         |
| chat_sessions                             | chat_messages.user_id/event_id/conversation_id/conversation_title |
| announcements + policy_documents          | contents (kind = announcement | document); id thông báo giữ nguyên |

Kèm theo: khoá ngoại ghép registration_legs(bus_id, trip_leg_id) -> buses(id, trip_leg_id) và
flight_assignments(flight_id, direction) -> flights(id, direction); bỏ registrations.cancelled_at /
cancel_reason / penalty_applied (đọc từ registration_cancellations; đăng ký đã huỷ mà chưa có dòng huỷ
được duyệt thì migration tạo dòng đó); bỏ UNIQUE thừa uq_flights_event_code_direction_time;
UNIQUE(gala_layouts.event_id).

Cách dựng lại bảng: giống batch mode của Alembic (tạo bảng tạm -> chép -> drop -> đổi tên) nhưng DDL
viết tay, vì batch mode phản chiếu bảng SQLite sẽ làm MẤT các CHECK constraint. DDL dưới đây sinh từ
model lúc viết migration và đóng băng tại đây — sửa model sau này thì viết migration mới, không sửa file này.

Engine của Alembic không bật `PRAGMA foreign_keys` (listener chỉ gắn ở app), nên drop bảng cha không xoá
dây chuyền bảng con. Cuối migration chạy `PRAGMA foreign_key_check` và đếm lại dữ liệu; lệch là dừng.

Không có downgrade: quay lại thì khôi phục bản sao lưu (`scripts/backup_db.py`) chụp trước khi nâng cấp.
"""

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7d2a9e41c027"
down_revision: Union[str, Sequence[str], None] = "5f3a91c7d420"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DROPPED_TABLES = (
    "event_settings",
    "consents",
    "room_assignments",
    "bus_assignments",
    "registration_bus_needs",
    "gala_seat_holds",
    "gala_seat_assignments",
    "chat_sessions",
    "announcements",
    "policy_documents",
)
EXPECTED_TABLE_COUNT = 27

# --------------------------------------------------------------------------- DDL đóng băng

REGISTRATIONS = """
CREATE TABLE {name} (
    id INTEGER NOT NULL,
    event_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    is_participating BOOLEAN NOT NULL,
    not_participating_reason VARCHAR(512),
    shift_id INTEGER,
    is_shift_locked BOOLEAN NOT NULL,
    departure_location_id INTEGER,
    wish_note TEXT,
    companion_count INTEGER NOT NULL,
    status VARCHAR(16) NOT NULL,
    submitted_at VARCHAR(32),
    consent_version VARCHAR(16),
    consented_at VARCHAR(32),
    consent_ip VARCHAR(64),
    consent_user_agent VARCHAR(512),
    room_id INTEGER,
    is_room_captain BOOLEAN NOT NULL,
    room_mode VARCHAR(16),
    room_assigned_by INTEGER,
    room_assigned_at VARCHAR(32),
    room_note VARCHAR(512),
    created_at VARCHAR(32) DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at VARCHAR(32) DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT pk_registrations PRIMARY KEY (id),
    CONSTRAINT uq_registrations_event_user UNIQUE (event_id, user_id),
    CONSTRAINT ck_registrations_status_valid CHECK (status IN ('draft', 'submitted', 'cancelled')),
    CONSTRAINT ck_registrations_companion_non_negative CHECK (companion_count >= 0),
    CONSTRAINT ck_registrations_room_mode_valid CHECK (room_mode IS NULL OR room_mode IN ('auto', 'manual')),
    CONSTRAINT ck_registrations_captain_has_room CHECK (room_id IS NOT NULL OR is_room_captain = 0),
    CONSTRAINT ck_registrations_consent_complete CHECK ((consent_version IS NULL AND consented_at IS NULL) OR (consent_version IS NOT NULL AND consented_at IS NOT NULL)),
    CONSTRAINT fk_registrations_event_id_events FOREIGN KEY(event_id) REFERENCES events (id) ON DELETE CASCADE,
    CONSTRAINT fk_registrations_user_id_users FOREIGN KEY(user_id) REFERENCES users (id),
    CONSTRAINT fk_registrations_shift_id_shifts FOREIGN KEY(shift_id) REFERENCES shifts (id),
    CONSTRAINT fk_registrations_departure_location_id_work_locations FOREIGN KEY(departure_location_id) REFERENCES work_locations (id),
    CONSTRAINT fk_registrations_room_id_rooms FOREIGN KEY(room_id) REFERENCES rooms (id),
    CONSTRAINT fk_registrations_room_assigned_by_users FOREIGN KEY(room_assigned_by) REFERENCES users (id)
)"""
REGISTRATIONS_INDEXES = (
    "CREATE INDEX ix_registrations_event_id ON registrations (event_id)",
    "CREATE INDEX ix_registrations_room_id ON registrations (room_id)",
    "CREATE INDEX ix_registrations_shift_id ON registrations (shift_id)",
    "CREATE INDEX ix_registrations_status ON registrations (status)",
    "CREATE INDEX ix_registrations_user_id ON registrations (user_id)",
)

REGISTRATION_LEGS = """
CREATE TABLE registration_legs (
    id INTEGER NOT NULL,
    registration_id INTEGER NOT NULL,
    trip_leg_id INTEGER NOT NULL,
    needs_bus BOOLEAN NOT NULL,
    pickup_point_id INTEGER,
    note VARCHAR(512),
    bus_id INTEGER,
    assignment_mode VARCHAR(16),
    assigned_by INTEGER,
    assigned_at VARCHAR(32),
    assignment_note TEXT,
    CONSTRAINT pk_registration_legs PRIMARY KEY (id),
    CONSTRAINT uq_registration_legs_registration_leg UNIQUE (registration_id, trip_leg_id),
    CONSTRAINT ck_registration_legs_assigned_needs_bus CHECK (bus_id IS NULL OR needs_bus = 1),
    CONSTRAINT ck_registration_legs_mode_valid CHECK (assignment_mode IS NULL OR assignment_mode IN ('auto', 'manual')),
    CONSTRAINT fk_registration_legs_bus_leg FOREIGN KEY(bus_id, trip_leg_id) REFERENCES buses (id, trip_leg_id),
    CONSTRAINT fk_registration_legs_registration_id_registrations FOREIGN KEY(registration_id) REFERENCES registrations (id) ON DELETE CASCADE,
    CONSTRAINT fk_registration_legs_trip_leg_id_trip_legs FOREIGN KEY(trip_leg_id) REFERENCES trip_legs (id),
    CONSTRAINT fk_registration_legs_pickup_point_id_pickup_points FOREIGN KEY(pickup_point_id) REFERENCES pickup_points (id),
    CONSTRAINT fk_registration_legs_assigned_by_users FOREIGN KEY(assigned_by) REFERENCES users (id)
)"""
REGISTRATION_LEGS_INDEXES = (
    "CREATE INDEX ix_registration_legs_bus_id ON registration_legs (bus_id)",
    "CREATE INDEX ix_registration_legs_registration_id ON registration_legs (registration_id)",
    "CREATE INDEX ix_registration_legs_trip_leg_id ON registration_legs (trip_leg_id)",
)

FLIGHTS = """
CREATE TABLE {name} (
    id INTEGER NOT NULL,
    event_id INTEGER NOT NULL,
    flight_code VARCHAR(16) NOT NULL,
    airline VARCHAR(128),
    direction VARCHAR(16) NOT NULL,
    shift_id INTEGER,
    departure_airport VARCHAR(8) NOT NULL,
    arrival_airport VARCHAR(8) NOT NULL,
    departure_time VARCHAR(32) NOT NULL,
    arrival_time VARCHAR(32) NOT NULL,
    capacity INTEGER NOT NULL,
    reserved_slots INTEGER NOT NULL,
    note TEXT,
    is_active BOOLEAN NOT NULL,
    created_at VARCHAR(32) DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at VARCHAR(32) DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT pk_flights PRIMARY KEY (id),
    CONSTRAINT uq_flights_id_direction UNIQUE (id, direction),
    CONSTRAINT ck_flights_direction_valid CHECK (direction IN ('outbound', 'return')),
    CONSTRAINT ck_flights_capacity_non_negative CHECK (capacity >= 0),
    CONSTRAINT ck_flights_reserved_non_negative CHECK (reserved_slots >= 0),
    CONSTRAINT ck_flights_reserved_within_capacity CHECK (reserved_slots <= capacity),
    CONSTRAINT fk_flights_event_id_events FOREIGN KEY(event_id) REFERENCES events (id) ON DELETE CASCADE,
    CONSTRAINT fk_flights_shift_id_shifts FOREIGN KEY(shift_id) REFERENCES shifts (id)
)"""
FLIGHTS_INDEXES = (
    "CREATE INDEX ix_flights_direction ON flights (direction)",
    "CREATE INDEX ix_flights_event_id ON flights (event_id)",
    "CREATE INDEX ix_flights_shift_id ON flights (shift_id)",
    "CREATE UNIQUE INDEX uq_flights_event_code_direction ON flights (event_id, flight_code, direction)",
)

FLIGHT_ASSIGNMENTS = """
CREATE TABLE {name} (
    id INTEGER NOT NULL,
    registration_id INTEGER NOT NULL,
    flight_id INTEGER NOT NULL,
    direction VARCHAR(16) NOT NULL,
    seat_number VARCHAR(8),
    ticket_code VARCHAR(32),
    assignment_mode VARCHAR(16) NOT NULL,
    assigned_by INTEGER,
    assigned_at VARCHAR(32) NOT NULL,
    note TEXT,
    CONSTRAINT pk_flight_assignments PRIMARY KEY (id),
    CONSTRAINT uq_flight_assignments_registration_direction UNIQUE (registration_id, direction),
    CONSTRAINT ck_flight_assignments_direction_valid CHECK (direction IN ('outbound', 'return')),
    CONSTRAINT ck_flight_assignments_mode_valid CHECK (assignment_mode IN ('auto', 'manual')),
    CONSTRAINT fk_flight_assignments_flight_direction FOREIGN KEY(flight_id, direction) REFERENCES flights (id, direction),
    CONSTRAINT fk_flight_assignments_registration_id_registrations FOREIGN KEY(registration_id) REFERENCES registrations (id) ON DELETE CASCADE,
    CONSTRAINT fk_flight_assignments_assigned_by_users FOREIGN KEY(assigned_by) REFERENCES users (id)
)"""
FLIGHT_ASSIGNMENTS_INDEXES = (
    "CREATE INDEX ix_flight_assignments_flight_id ON flight_assignments (flight_id)",
    "CREATE INDEX ix_flight_assignments_registration_id ON flight_assignments (registration_id)",
)

BUSES = """
CREATE TABLE {name} (
    id INTEGER NOT NULL,
    event_id INTEGER NOT NULL,
    trip_leg_id INTEGER NOT NULL,
    bus_code VARCHAR(32) NOT NULL,
    plate_number VARCHAR(32),
    capacity INTEGER NOT NULL,
    pickup_point_id INTEGER,
    dropoff_point VARCHAR(255),
    gather_time VARCHAR(32),
    departure_time VARCHAR(32),
    leader_user_id INTEGER,
    leader_name VARCHAR(255),
    leader_phone VARCHAR(32),
    driver_name VARCHAR(255),
    driver_phone VARCHAR(32),
    linked_flight_id INTEGER,
    note TEXT,
    created_at VARCHAR(32) DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at VARCHAR(32) DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT pk_buses PRIMARY KEY (id),
    CONSTRAINT uq_buses_event_leg_code UNIQUE (event_id, trip_leg_id, bus_code),
    CONSTRAINT uq_buses_id_leg UNIQUE (id, trip_leg_id),
    CONSTRAINT ck_buses_capacity_positive CHECK (capacity > 0),
    CONSTRAINT fk_buses_event_id_events FOREIGN KEY(event_id) REFERENCES events (id) ON DELETE CASCADE,
    CONSTRAINT fk_buses_trip_leg_id_trip_legs FOREIGN KEY(trip_leg_id) REFERENCES trip_legs (id),
    CONSTRAINT fk_buses_pickup_point_id_pickup_points FOREIGN KEY(pickup_point_id) REFERENCES pickup_points (id),
    CONSTRAINT fk_buses_leader_user_id_users FOREIGN KEY(leader_user_id) REFERENCES users (id),
    CONSTRAINT fk_buses_linked_flight_id_flights FOREIGN KEY(linked_flight_id) REFERENCES flights (id)
)"""
BUSES_INDEXES = (
    "CREATE INDEX ix_buses_event_id ON buses (event_id)",
    "CREATE INDEX ix_buses_linked_flight_id ON buses (linked_flight_id)",
    "CREATE INDEX ix_buses_trip_leg_id ON buses (trip_leg_id)",
)

GALA_LAYOUTS = """
CREATE TABLE {name} (
    id INTEGER NOT NULL,
    event_id INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    venue VARCHAR(255),
    starts_at VARCHAR(32),
    stage_position VARCHAR(16) NOT NULL,
    grid_width INTEGER NOT NULL,
    grid_height INTEGER NOT NULL,
    selection_status VARCHAR(16) NOT NULL,
    turn_seconds INTEGER NOT NULL,
    hold_seconds INTEGER NOT NULL,
    draw_seed INTEGER,
    created_at VARCHAR(32) DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at VARCHAR(32) DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT pk_gala_layouts PRIMARY KEY (id),
    CONSTRAINT uq_gala_layouts_event UNIQUE (event_id),
    CONSTRAINT ck_gala_layouts_selection_status_valid CHECK (selection_status IN ('closed', 'drawing', 'open', 'finalized')),
    CONSTRAINT ck_gala_layouts_hold_seconds_positive CHECK (hold_seconds > 0),
    CONSTRAINT fk_gala_layouts_event_id_events FOREIGN KEY(event_id) REFERENCES events (id) ON DELETE CASCADE
)"""
GALA_LAYOUTS_INDEXES = ("CREATE INDEX ix_gala_layouts_event_id ON gala_layouts (event_id)",)

GALA_SEATS = """
CREATE TABLE {name} (
    id INTEGER NOT NULL,
    table_id INTEGER NOT NULL,
    seat_number INTEGER NOT NULL,
    is_available BOOLEAN NOT NULL,
    status VARCHAR(16) DEFAULT 'free' NOT NULL,
    team_id INTEGER,
    registration_id INTEGER,
    held_by INTEGER,
    held_at VARCHAR(32),
    hold_expires_at VARCHAR(32),
    confirmed_by INTEGER,
    confirmed_at VARCHAR(32),
    CONSTRAINT pk_gala_seats PRIMARY KEY (id),
    CONSTRAINT uq_gala_seats_table_number UNIQUE (table_id, seat_number),
    CONSTRAINT uq_gala_seats_registration UNIQUE (registration_id),
    CONSTRAINT ck_gala_seats_status_valid CHECK (status IN ('free', 'held', 'taken')),
    CONSTRAINT ck_gala_seats_state_consistent CHECK ((status = 'free' AND team_id IS NULL AND registration_id IS NULL AND held_by IS NULL AND hold_expires_at IS NULL AND confirmed_by IS NULL AND confirmed_at IS NULL) OR (status = 'held' AND team_id IS NOT NULL AND held_by IS NOT NULL AND hold_expires_at IS NOT NULL AND registration_id IS NULL AND confirmed_by IS NULL AND confirmed_at IS NULL) OR (status = 'taken' AND held_by IS NULL AND hold_expires_at IS NULL AND confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL)),
    CONSTRAINT fk_gala_seats_table_id_gala_tables FOREIGN KEY(table_id) REFERENCES gala_tables (id) ON DELETE CASCADE,
    CONSTRAINT fk_gala_seats_team_id_teams FOREIGN KEY(team_id) REFERENCES teams (id),
    CONSTRAINT fk_gala_seats_registration_id_registrations FOREIGN KEY(registration_id) REFERENCES registrations (id),
    CONSTRAINT fk_gala_seats_held_by_users FOREIGN KEY(held_by) REFERENCES users (id),
    CONSTRAINT fk_gala_seats_confirmed_by_users FOREIGN KEY(confirmed_by) REFERENCES users (id)
)"""
GALA_SEATS_INDEXES = (
    "CREATE INDEX ix_gala_seats_hold_expires_at ON gala_seats (hold_expires_at)",
    "CREATE INDEX ix_gala_seats_status ON gala_seats (status)",
    "CREATE INDEX ix_gala_seats_table_id ON gala_seats (table_id)",
    "CREATE INDEX ix_gala_seats_team_id ON gala_seats (team_id)",
)

CONTENTS = """
CREATE TABLE contents (
    id INTEGER NOT NULL,
    kind VARCHAR(16) NOT NULL,
    event_id INTEGER,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    severity VARCHAR(16) NOT NULL,
    target_type VARCHAR(16) NOT NULL,
    target_id INTEGER,
    published_at VARCHAR(32),
    send_email BOOLEAN NOT NULL,
    created_by INTEGER,
    created_at VARCHAR(32) NOT NULL,
    doc_type VARCHAR(16),
    version VARCHAR(16) NOT NULL,
    is_indexed BOOLEAN NOT NULL,
    updated_at VARCHAR(32) NOT NULL,
    CONSTRAINT pk_contents PRIMARY KEY (id),
    CONSTRAINT ck_contents_kind_valid CHECK (kind IN ('announcement', 'document')),
    CONSTRAINT ck_contents_severity_valid CHECK (severity IN ('info', 'warning', 'urgent')),
    CONSTRAINT ck_contents_target_valid CHECK (target_type IN ('all', 'team', 'flight', 'bus', 'user')),
    CONSTRAINT ck_contents_doc_type_valid CHECK (doc_type IS NULL OR doc_type IN ('terms', 'faq', 'guide', 'itinerary')),
    CONSTRAINT ck_contents_announcement_has_event CHECK (kind != 'announcement' OR event_id IS NOT NULL),
    CONSTRAINT ck_contents_document_has_type CHECK (kind != 'document' OR doc_type IS NOT NULL),
    CONSTRAINT fk_contents_event_id_events FOREIGN KEY(event_id) REFERENCES events (id) ON DELETE CASCADE,
    CONSTRAINT fk_contents_created_by_users FOREIGN KEY(created_by) REFERENCES users (id)
)"""
CONTENTS_INDEXES = (
    "CREATE INDEX ix_contents_doc_type ON contents (doc_type)",
    "CREATE INDEX ix_contents_event_id ON contents (event_id)",
    "CREATE INDEX ix_contents_is_indexed ON contents (is_indexed)",
    "CREATE INDEX ix_contents_kind ON contents (kind)",
    "CREATE INDEX ix_contents_published_at ON contents (published_at)",
)

CHAT_MESSAGES = """
CREATE TABLE {name} (
    id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    event_id INTEGER,
    conversation_id INTEGER NOT NULL,
    conversation_title VARCHAR(255),
    role VARCHAR(16) NOT NULL,
    content TEXT NOT NULL,
    sources TEXT,
    tokens_used INTEGER,
    latency_ms INTEGER,
    created_at VARCHAR(32) NOT NULL,
    CONSTRAINT pk_chat_messages PRIMARY KEY (id),
    CONSTRAINT ck_chat_messages_role_valid CHECK (role IN ('user', 'assistant')),
    CONSTRAINT fk_chat_messages_user_id_users FOREIGN KEY(user_id) REFERENCES users (id),
    CONSTRAINT fk_chat_messages_event_id_events FOREIGN KEY(event_id) REFERENCES events (id) ON DELETE CASCADE
)"""
CHAT_MESSAGES_INDEXES = (
    "CREATE INDEX ix_chat_messages_conversation_id ON chat_messages (conversation_id)",
    "CREATE INDEX ix_chat_messages_event_id ON chat_messages (event_id)",
    "CREATE INDEX ix_chat_messages_owner_conversation ON chat_messages (user_id, event_id, conversation_id)",
    "CREATE INDEX ix_chat_messages_user_id ON chat_messages (user_id)",
)

# --------------------------------------------------------------------------- dữ liệu

REGISTRATIONS_SELECT = """
SELECT r.id, r.event_id, r.user_id, r.is_participating, r.not_participating_reason, r.shift_id,
       r.is_shift_locked, r.departure_location_id, r.wish_note, r.companion_count, r.status,
       r.submitted_at,
       c.terms_version, c.agreed_at, c.ip_address, c.user_agent,
       ra.room_id, COALESCE(ra.is_room_captain, 0), ra.assignment_mode, ra.assigned_by,
       ra.assigned_at, ra.note,
       r.created_at, r.updated_at
FROM registrations r
LEFT JOIN (
    SELECT user_id, event_id, MAX(id) AS latest_id FROM consents GROUP BY user_id, event_id
) lc ON lc.user_id = r.user_id AND lc.event_id = r.event_id
LEFT JOIN consents c ON c.id = lc.latest_id
LEFT JOIN room_assignments ra ON ra.registration_id = r.id
"""

REGISTRATION_LEGS_INSERT = """
INSERT INTO registration_legs (registration_id, trip_leg_id, needs_bus, pickup_point_id, note,
                               bus_id, assignment_mode, assigned_by, assigned_at, assignment_note)
SELECT n.registration_id, n.trip_leg_id,
       CASE WHEN a.id IS NOT NULL THEN 1 ELSE n.needs_bus END,
       n.pickup_point_id, n.note, a.bus_id, a.assignment_mode, a.assigned_by, a.assigned_at, a.note
FROM registration_bus_needs n
LEFT JOIN bus_assignments a
       ON a.registration_id = n.registration_id AND a.trip_leg_id = n.trip_leg_id
UNION ALL
SELECT a.registration_id, a.trip_leg_id, 1, NULL, NULL,
       a.bus_id, a.assignment_mode, a.assigned_by, a.assigned_at, a.note
FROM bus_assignments a
WHERE NOT EXISTS (
    SELECT 1 FROM registration_bus_needs n
    WHERE n.registration_id = a.registration_id AND n.trip_leg_id = a.trip_leg_id
)
"""

GALA_SEATS_SELECT = """
SELECT s.id, s.table_id, s.seat_number, s.is_available,
       CASE WHEN a.id IS NOT NULL THEN 'taken' WHEN h.id IS NOT NULL THEN 'held' ELSE 'free' END,
       CASE WHEN a.id IS NOT NULL THEN a.team_id ELSE h.team_id END,
       a.registration_id,
       CASE WHEN a.id IS NULL THEN h.held_by END,
       CASE WHEN a.id IS NULL THEN h.held_at END,
       CASE WHEN a.id IS NULL THEN h.expires_at END,
       a.confirmed_by, a.confirmed_at
FROM gala_seats s
LEFT JOIN gala_seat_assignments a ON a.seat_id = s.id
LEFT JOIN gala_seat_holds h ON h.seat_id = s.id
"""

CHAT_MESSAGES_SELECT = """
SELECT m.id, s.user_id, s.event_id, m.session_id, s.title, m.role, m.content, m.sources,
       m.tokens_used, m.latency_ms, m.created_at
FROM chat_messages m
JOIN chat_sessions s ON s.id = m.session_id
"""

# Giữ nguyên id thông báo (audit_logs / email_logs trỏ tới bằng related_id); tài liệu nhận id mới.
CONTENTS_FROM_ANNOUNCEMENTS = """
INSERT INTO contents (id, kind, event_id, title, content, severity, target_type, target_id,
                      published_at, send_email, created_by, created_at, doc_type, version,
                      is_indexed, updated_at)
SELECT id, 'announcement', event_id, title, content, severity, target_type, target_id,
       published_at, send_email, created_by, created_at, NULL, 'v1', 0, created_at
FROM announcements
"""
CONTENTS_FROM_DOCUMENTS = """
INSERT INTO contents (kind, event_id, title, content, severity, target_type, target_id,
                      published_at, send_email, created_by, created_at, doc_type, version,
                      is_indexed, updated_at)
SELECT 'document', event_id, title, content, 'info', 'all', NULL,
       NULL, 0, NULL, updated_at, doc_type, version, is_indexed, updated_at
FROM policy_documents
ORDER BY id
"""


def _exec(sql: str, params: dict | None = None):
    return op.get_bind().execute(sa.text(sql), params or {})


def _scalar(sql: str, params: dict | None = None):
    return _exec(sql, params).scalar()


def _rebuild(name: str, ddl: str, indexes: Sequence[str], select_sql: str | None = None) -> None:
    """Dựng lại một bảng như batch mode: bảng tạm -> chép -> drop -> đổi tên -> index."""
    tmp = f"_v2_{name}"
    _exec(ddl.format(name=tmp))
    columns = _columns(tmp)
    # Không có câu SELECT riêng = bảng giữ nguyên cột, chép theo tên cột (không dựa vào thứ tự).
    source = select_sql if select_sql is not None else f"SELECT {columns} FROM {name}"
    _exec(f"INSERT INTO {tmp} ({columns}) {source}")
    _exec(f"DROP TABLE {name}")
    _exec(f"ALTER TABLE {tmp} RENAME TO {name}")
    for statement in indexes:
        _exec(statement)


def _columns(table: str) -> str:
    return ", ".join(row[1] for row in _exec(f"PRAGMA table_info({table})"))


def _check_preconditions() -> None:
    duplicated = _scalar(
        "SELECT COUNT(*) FROM (SELECT event_id FROM gala_layouts GROUP BY event_id HAVING COUNT(*) > 1)"
    )
    if duplicated:
        raise RuntimeError(
            f"{duplicated} kỳ có nhiều hơn một sơ đồ Gala; schema v2 chỉ cho một sơ đồ mỗi kỳ. "
            "Xoá sơ đồ thừa rồi chạy lại."
        )


def _move_event_settings() -> None:
    op.add_column(
        "events", sa.Column("settings", sa.JSON(), nullable=False, server_default="{}")
    )
    settings: dict[int, dict] = {}
    for event_id, key, value in _exec("SELECT event_id, key, value FROM event_settings ORDER BY id"):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            parsed = value
        settings.setdefault(event_id, {})[key] = parsed
    for event_id, values in settings.items():
        _exec(
            "UPDATE events SET settings = :settings WHERE id = :id",
            {"settings": json.dumps(values, ensure_ascii=False), "id": event_id},
        )


def _backfill_legacy_cancellations() -> None:
    """Đăng ký đã huỷ nhưng chưa có dòng huỷ `approved` (huỷ trước khi có bảng huỷ).

    Ba cột cancelled_at / cancel_reason / penalty_applied sắp bị bỏ, nên thông tin của những đăng ký
    này phải sang registration_cancellations trước, không thì mất.
    """
    _exec(
        """
        INSERT INTO registration_cancellations (
            event_id, registration_id, user_id, mode, status, reason, event_status, after_deadline,
            requested_at, decided_at, decision_note, penalty_applied, created_at, updated_at)
        SELECT r.event_id, r.id, r.user_id, 'admin', 'approved',
               COALESCE(NULLIF(r.cancel_reason, ''), 'Huỷ trước khi có bảng huỷ đăng ký'),
               e.status, r.penalty_applied,
               COALESCE(r.cancelled_at, r.updated_at), COALESCE(r.cancelled_at, r.updated_at),
               'Chuyển từ registrations.cancel_* khi nâng schema v2', r.penalty_applied,
               r.updated_at, r.updated_at
        FROM registrations r
        JOIN events e ON e.id = r.event_id
        WHERE r.status = 'cancelled'
          AND NOT EXISTS (
              SELECT 1 FROM registration_cancellations c
              WHERE c.registration_id = r.id AND c.status = 'approved'
          )
        """
    )


def _archive_older_consents() -> None:
    """Các lần đồng ý cũ hơn bản mới nhất (quy định lên version) -> audit_logs `consent.agreed`."""
    _exec(
        """
        INSERT INTO audit_logs (event_id, actor_id, action, entity_type, entity_id, before_data,
                                after_data, reason, ip_address, created_at)
        SELECT c.event_id, c.user_id, 'consent.agreed', 'registration', r.id, NULL,
               json_object('terms_version', c.terms_version, 'agreed_at', c.agreed_at,
                           'user_agent', c.user_agent),
               'Chuyển từ bảng consents khi nâng schema v2', c.ip_address, c.agreed_at
        FROM consents c
        LEFT JOIN registrations r ON r.user_id = c.user_id AND r.event_id = c.event_id
        WHERE c.id NOT IN (SELECT MAX(id) FROM consents GROUP BY user_id, event_id)
           OR r.id IS NULL
        """
    )


def _counts() -> dict[str, int]:
    return {
        "registrations": _scalar("SELECT COUNT(*) FROM registrations"),
        "room_assignments": _scalar("SELECT COUNT(*) FROM room_assignments"),
        "bus_assignments": _scalar("SELECT COUNT(*) FROM bus_assignments"),
        "bus_need_keys": _scalar(
            "SELECT COUNT(*) FROM (SELECT registration_id, trip_leg_id FROM registration_bus_needs "
            "UNION SELECT registration_id, trip_leg_id FROM bus_assignments)"
        ),
        "gala_assignments": _scalar("SELECT COUNT(*) FROM gala_seat_assignments"),
        "gala_holds": _scalar(
            "SELECT COUNT(*) FROM gala_seat_holds h WHERE NOT EXISTS "
            "(SELECT 1 FROM gala_seat_assignments a WHERE a.seat_id = h.seat_id)"
        ),
        "chat_messages": _scalar(
            "SELECT COUNT(*) FROM chat_messages m JOIN chat_sessions s ON s.id = m.session_id"
        ),
        "contents": _scalar("SELECT (SELECT COUNT(*) FROM announcements) + (SELECT COUNT(*) FROM policy_documents)"),
        "flight_assignments": _scalar("SELECT COUNT(*) FROM flight_assignments"),
    }


def _verify(before: dict[str, int]) -> None:
    after = {
        "registrations": _scalar("SELECT COUNT(*) FROM registrations"),
        "room_assignments": _scalar("SELECT COUNT(*) FROM registrations WHERE room_id IS NOT NULL"),
        "bus_assignments": _scalar("SELECT COUNT(*) FROM registration_legs WHERE bus_id IS NOT NULL"),
        "bus_need_keys": _scalar("SELECT COUNT(*) FROM registration_legs"),
        "gala_assignments": _scalar("SELECT COUNT(*) FROM gala_seats WHERE status = 'taken'"),
        "gala_holds": _scalar("SELECT COUNT(*) FROM gala_seats WHERE status = 'held'"),
        "chat_messages": _scalar("SELECT COUNT(*) FROM chat_messages"),
        "contents": _scalar("SELECT COUNT(*) FROM contents"),
        "flight_assignments": _scalar("SELECT COUNT(*) FROM flight_assignments"),
    }
    mismatched = {key: (before[key], after[key]) for key in before if before[key] != after[key]}
    if mismatched:
        raise RuntimeError(f"Số dòng lệch sau khi chuyển (trước, sau): {mismatched}")

    violations = _exec("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise RuntimeError(f"Vi phạm khoá ngoại sau khi chuyển: {violations[:10]}")

    tables = _scalar(
        "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' "
        "AND name NOT LIKE 'sqlite_%' AND name != 'alembic_version'"
    )
    if tables != EXPECTED_TABLE_COUNT:
        raise RuntimeError(f"Schema v2 phải có {EXPECTED_TABLE_COUNT} bảng, đang có {tables}")


def upgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        raise RuntimeError("Migration này viết cho SQLite")
    _check_preconditions()
    before = _counts()

    _move_event_settings()
    _backfill_legacy_cancellations()
    _archive_older_consents()

    # Bảng cha trước (flights, buses) để khoá ngoại ghép của bảng con có chỗ trỏ tới.
    _rebuild("flights", FLIGHTS, FLIGHTS_INDEXES)
    _rebuild("buses", BUSES, BUSES_INDEXES)
    _rebuild("registrations", REGISTRATIONS, REGISTRATIONS_INDEXES, REGISTRATIONS_SELECT)
    _rebuild("flight_assignments", FLIGHT_ASSIGNMENTS, FLIGHT_ASSIGNMENTS_INDEXES)
    _rebuild("gala_layouts", GALA_LAYOUTS, GALA_LAYOUTS_INDEXES)
    _rebuild("gala_seats", GALA_SEATS, GALA_SEATS_INDEXES, GALA_SEATS_SELECT)
    _rebuild("chat_messages", CHAT_MESSAGES, CHAT_MESSAGES_INDEXES, CHAT_MESSAGES_SELECT)

    _exec(REGISTRATION_LEGS)
    for statement in REGISTRATION_LEGS_INDEXES:
        _exec(statement)
    _exec(REGISTRATION_LEGS_INSERT)

    _exec(CONTENTS)
    for statement in CONTENTS_INDEXES:
        _exec(statement)
    _exec(CONTENTS_FROM_ANNOUNCEMENTS)
    _exec(CONTENTS_FROM_DOCUMENTS)

    for table in DROPPED_TABLES:
        _exec(f"DROP TABLE {table}")

    _verify(before)


def downgrade() -> None:
    raise RuntimeError(
        "Không hạ được từ schema v2. Khôi phục bản sao lưu chụp trước khi nâng cấp "
        "(scripts/backup_db.py)."
    )
