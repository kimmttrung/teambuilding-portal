"""Tạo và nạp DB v2 độc lập từ 27 ORM models, KHÔNG chạy migration v1.

    python scripts/seed_v2.py
    python scripts/seed_v2.py --database data/sqlite/teambuilding_v2.db --reset
    python scripts/seed_v2.py --database data/sqlite/teambuilding_v2.db --second-event

Mặc định dùng file teambuilding_v2.db riêng, không đọc DATABASE_URL của backend.
--reset chỉ xoá dữ liệu của DB đã khớp schema v2; không sửa/drop schema cũ.
Dữ liệu demo có cả đăng ký nháp/huỷ, nhu cầu xe chưa xếp, ghế free/held/taken,
thông báo nháp/công khai, tài liệu chung/theo kỳ và lịch sử consent trong audit_logs.
Backend v1 chưa tương thích với models này: script không import service hay app.main.
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from alembic.autogenerate import compare_metadata  # noqa: E402
from alembic.migration import MigrationContext  # noqa: E402
from sqlalchemy import create_engine, delete, event, func, inspect, select, text  # noqa: E402
from sqlalchemy.engine import URL, Engine  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.core.timeutils import VN_TZ, to_iso, utcnow, utcnow_iso  # noqa: E402
from app.models import (  # noqa: E402
    DEFAULT_EVENT_SETTINGS,
    AuditLog,
    Base,
    Bus,
    ChatMessage,
    Content,
    Department,
    EmailLog,
    Event,
    Flight,
    FlightAssignment,
    GalaDrawOrder,
    GalaLayout,
    GalaSeat,
    GalaTable,
    Hotel,
    ItineraryItem,
    LoginAttempt,
    PickupPoint,
    RefreshToken,
    Registration,
    RegistrationCancellation,
    RegistrationLeg,
    Room,
    Shift,
    Team,
    TripLeg,
    User,
    WorkLocation,
)

DEFAULT_DATABASE = BACKEND_DIR / "data" / "sqlite" / "teambuilding_v2.db"
EXPECTED_TABLES = frozenset(
    {
        "audit_logs",
        "buses",
        "chat_messages",
        "contents",
        "departments",
        "email_logs",
        "events",
        "flight_assignments",
        "flights",
        "gala_draw_orders",
        "gala_layouts",
        "gala_seats",
        "gala_tables",
        "hotels",
        "itinerary_items",
        "login_attempts",
        "pickup_points",
        "refresh_tokens",
        "registration_cancellations",
        "registration_legs",
        "registrations",
        "rooms",
        "shifts",
        "teams",
        "trip_legs",
        "users",
        "work_locations",
    }
)
DEMO_PASSWORD = "Matkhau123"
ADMIN_PASSWORD = "Admin12345"


def _pragmas(connection, _record) -> None:
    cursor = connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
    finally:
        cursor.close()


def _prepare_schema(engine: Engine) -> None:
    """Reject v1/compact schemas even with --reset: never silently migrate a DB."""
    if frozenset(Base.metadata.tables) != EXPECTED_TABLES:
        raise RuntimeError("ORM metadata phải chứa đúng 27 bảng v2 đã xác định.")
    with engine.connect() as connection:
        tables = set(inspect(connection).get_table_names())
        if tables:
            if tables != EXPECTED_TABLES:
                raise ValueError(
                    "DB không phải schema v2 27 bảng. Hãy chọn file DB mới; "
                    "--reset không chuyển schema v1/compact sang v2. "
                    f"Thiếu: {sorted(EXPECTED_TABLES - tables)}; "
                    f"Thừa: {sorted(tables - EXPECTED_TABLES)}"
                )
            context = MigrationContext.configure(
                connection, opts={"compare_type": True, "compare_server_default": True}
            )
            differences = compare_metadata(context, Base.metadata)
            if differences:
                raise ValueError(
                    "DB có 27 bảng nhưng cấu trúc khác ORM v2. Chọn file DB mới; "
                    f"không tự sửa schema hiện có. Khác biệt: {differences}"
                )
    Base.metadata.create_all(engine)


def _time(year: int, day: int, hour: int, minute: int = 0) -> str:
    return to_iso(datetime(year, 10, day, hour, minute, tzinfo=VN_TZ))


def _master_data(db: Session) -> tuple[User, list[User], list[Team], WorkLocation]:
    """Shared company data: create once, reuse for the second event."""
    existing = db.scalar(select(User).where(User.email == "btc@company.vn"))
    if existing:
        employees = list(
            db.scalars(
                select(User).where(User.employee_code.like("V2NV%")).order_by(User.employee_code)
            )
        )
        teams = list(
            db.scalars(select(Team).where(Team.code.in_(["V2-IT", "V2-OPS"])).order_by(Team.code))
        )
        location = db.scalar(select(WorkLocation).where(WorkLocation.code == "V2-HN"))
        if len(employees) != 12 or len(teams) != 2 or location is None:
            raise ValueError("Master data demo v2 không đầy đủ. Dùng --reset trên DB demo.")
        return existing, employees, teams, location

    department = Department(code="V2-CN", name="Khối Công nghệ", display_order=1)
    location = WorkLocation(code="V2-HN", name="Hà Nội", city="Hà Nội", airport_code="HAN")
    db.add_all([department, location])
    db.flush()
    teams = [
        Team(code="V2-IT", name="Team Công nghệ", department_id=department.id, color="#2563eb"),
        Team(code="V2-OPS", name="Team Vận hành", department_id=department.id, color="#059669"),
    ]
    db.add_all(teams)
    db.flush()
    admin_hash, employee_hash = hash_password(ADMIN_PASSWORD), hash_password(DEMO_PASSWORD)
    admin = User(
        email="btc@company.vn",
        full_name="Ban tổ chức",
        role="admin",
        password_hash=admin_hash,
        department_id=department.id,
    )
    superadmin = User(
        email="superadmin@company.vn",
        full_name="Quản trị hệ thống",
        role="super_admin",
        password_hash=admin_hash,
    )
    names = [
        "Nguyễn Văn An",
        "Trần Thu Anh",
        "Lê Minh Việt",
        "Phạm Ngọc Linh",
        "Hoàng Đức Nam",
        "Vũ Thị Mai",
        "Đặng Quang Hải",
        "Bùi Thanh Hà",
        "Đỗ Minh Sơn",
        "Ngô Thu Trang",
        "Dương Văn Long",
        "Lý Ngọc Chi",
    ]
    employees = [
        User(
            employee_code=f"V2NV{index + 1:03}",
            email=f"nv{index + 1:02}@company.vn",
            full_name=name,
            password_hash=employee_hash,
            role="team_leader" if index in (0, 6) else "employee",
            team_id=None if index == 7 else teams[0 if index < 6 else 1].id,
            department_id=department.id,
            work_location_id=location.id,
            gender="male" if index % 2 == 0 else "female",
            phone=f"090000{index + 1:04}",
            date_of_birth=f"1995-01-{index + 1:02}",
            id_card_number=f"001095{index + 1:06}",
            id_card_type="cccd",
            shirt_size="M" if index % 2 else "L",
            must_change_password=index == 11,
        )
        for index, name in enumerate(names)
    ]
    db.add_all([admin, superadmin, *employees])
    db.flush()
    teams[0].leader_user_id, teams[1].leader_user_id = employees[0].id, employees[6].id
    now = utcnow_iso()
    # Expired, revoked demo token — not a usable login credential.
    db.add(
        RefreshToken(
            user_id=admin.id,
            jti="seed-v2-revoked",
            token_hash=hashlib.sha256(b"seed-v2-not-a-real-token").hexdigest(),
            issued_at=to_iso(utcnow() - timedelta(days=2)),
            expires_at=to_iso(utcnow() - timedelta(days=1)),
            revoked_at=now,
            revoked_reason="logout",
            ip_address="127.0.0.1",
            user_agent="seed_v2",
        )
    )
    db.add(
        LoginAttempt(email=admin.email, ip_address="127.0.0.1", succeeded=True, attempted_at=now)
    )
    return admin, employees, teams, location


def _seed_event(
    db: Session,
    *,
    year: int,
    active: bool,
    admin: User,
    employees: list[User],
    teams: list[Team],
    location: WorkLocation,
) -> int:
    now = utcnow_iso()
    event_row = Event(
        code=f"TB{year}",
        name=f"Team Building {year}",
        destination="Phú Quốc" if year == 2026 else "Đà Nẵng",
        start_date=f"{year}-10-15",
        end_date=f"{year}-10-17",
        status="information_published" if active else "registration_open",
        is_active=active,
        registration_opens_at=_time(year, 1, 8),
        registration_closes_at=_time(year, 10, 17),
        terms_version="v2",
        terms_content="## Quy định\nHuỷ sau hạn có thể chịu phí theo BTC.",
        settings={key: json.loads(value) for key, (value, _) in DEFAULT_EVENT_SETTINGS.items()},
    )
    db.add(event_row)
    db.flush()
    event_id = event_row.id
    shift = Shift(event_id=event_id, code="CA1", name="Ca sáng", earliest_departure="08:00")
    db.add(shift)
    db.flush()
    destination_airport = "PQC" if year == 2026 else "DAD"
    flights = [
        Flight(
            event_id=event_id,
            flight_code=f"VN{year}A",
            direction="outbound",
            shift_id=shift.id,
            departure_airport="HAN",
            arrival_airport=destination_airport,
            departure_time=_time(year, 15, 8),
            arrival_time=_time(year, 15, 10),
            capacity=20,
        ),
        Flight(
            event_id=event_id,
            flight_code=f"VN{year}B",
            direction="return",
            departure_airport=destination_airport,
            arrival_airport="HAN",
            departure_time=_time(year, 17, 16),
            arrival_time=_time(year, 17, 18),
            capacity=20,
        ),
    ]
    legs = [
        TripLeg(
            event_id=event_id,
            code=code,
            name=name,
            direction=direction,
            leg_date=f"{year}-10-{day}",
            is_airport_linked=True,
            display_order=index,
        )
        for index, (code, name, direction, day) in enumerate(
            [
                ("CITY_TO_AIRPORT", "Thành phố → Sân bay", "outbound", 15),
                ("AIRPORT_TO_HOTEL", "Sân bay → Khách sạn", "outbound", 15),
                ("HOTEL_TO_AIRPORT", "Khách sạn → Sân bay", "return", 17),
                ("AIRPORT_TO_CITY", "Sân bay → Thành phố", "return", 17),
            ],
            start=1,
        )
    ]
    db.add_all([*flights, *legs])
    db.flush()
    pickup = PickupPoint(
        event_id=event_id,
        trip_leg_id=legs[0].id,
        work_location_id=location.id,
        name="Văn phòng Hà Nội",
        address="Hà Nội",
        map_url="https://maps.google.com/?q=Hanoi",
    )
    hotel = Hotel(
        event_id=event_id,
        name=f"Khách sạn demo {year}",
        phone="02970000000",
        check_in_at=_time(year, 15, 14),
        check_out_at=_time(year, 17, 12),
    )
    db.add_all([pickup, hotel])
    db.flush()
    rooms = [
        Room(
            hotel_id=hotel.id,
            room_number="101",
            capacity=6,
            floor="1",
            room_type="triple",
            gender_policy="male",
        ),
        Room(
            hotel_id=hotel.id,
            room_number="102",
            capacity=6,
            floor="1",
            room_type="triple",
            gender_policy="female",
        ),
    ]
    buses = [
        Bus(
            event_id=event_id,
            trip_leg_id=leg.id,
            bus_code=f"XE{index + 1}",
            capacity=20,
            pickup_point_id=pickup.id if index == 0 else None,
            gather_time=_time(year, 15 if index < 2 else 17, [5, 10, 13, 18][index], 0),
            departure_time=_time(year, 15 if index < 2 else 17, [5, 10, 13, 18][index], 40),
            linked_flight_id=flights[0 if index < 2 else 1].id,
            leader_user_id=employees[0].id,
            driver_name=f"Tài xế {index + 1}",
            driver_phone=f"091234000{index}",
        )
        for index, leg in enumerate(legs)
    ]
    db.add_all([*rooms, *buses])
    db.flush()
    registrations = []
    for index, user in enumerate(employees):
        status = "cancelled" if index == 10 else "draft" if index == 11 else "submitted"
        participating = index != 9
        assigned = index < 8
        room = rooms[index % 2]
        registration = Registration(
            event_id=event_id,
            user_id=user.id,
            is_participating=participating,
            status=status,
            not_participating_reason="Bận việc gia đình" if not participating else None,
            shift_id=shift.id if participating else None,
            departure_location_id=location.id,
            submitted_at=now if status != "draft" else None,
            consent_version="v2" if participating and status != "draft" else None,
            consented_at=now if participating and status != "draft" else None,
            consent_ip="127.0.0.1" if participating and status != "draft" else None,
            consent_user_agent="seed_v2" if participating and status != "draft" else None,
            room_id=room.id if assigned else None,
            is_room_captain=index in (0, 1),
            room_mode="manual" if assigned else None,
            room_assigned_by=admin.id if assigned else None,
            room_assigned_at=now if assigned else None,
        )
        db.add(registration)
        db.flush()
        registrations.append(registration)
        if registration.consent_version:
            for version in ("v1", "v2"):
                db.add(
                    AuditLog(
                        event_id=event_id,
                        actor_id=user.id,
                        action="consent.agreed",
                        entity_type="registration",
                        entity_id=registration.id,
                        after_data=json.dumps(
                            {
                                "terms_version": version,
                                "agreed_at": now,
                                "ip_address": "127.0.0.1",
                                "user_agent": "seed_v2",
                            }
                        ),
                        ip_address="127.0.0.1",
                        created_at=now,
                    )
                )
        if participating and status == "submitted":
            for leg_index, leg in enumerate(legs):
                db.add(
                    RegistrationLeg(
                        registration_id=registration.id,
                        trip_leg_id=leg.id,
                        needs_bus=not (index == 8 and leg_index == 3),
                        pickup_point_id=pickup.id if leg_index == 0 else None,
                        bus_id=buses[leg_index].id if assigned else None,
                        assignment_mode="manual" if index == 0 else "auto" if assigned else None,
                        assigned_by=admin.id if assigned else None,
                        assigned_at=now if assigned else None,
                    )
                )
            if assigned:
                for flight in flights:
                    db.add(
                        FlightAssignment(
                            registration_id=registration.id,
                            flight_id=flight.id,
                            direction=flight.direction,
                            assignment_mode="manual" if index == 0 else "auto",
                            assigned_by=admin.id,
                            assigned_at=now,
                        )
                    )
        if status == "cancelled":
            db.add(
                RegistrationCancellation(
                    event_id=event_id,
                    registration_id=registration.id,
                    user_id=user.id,
                    mode="admin",
                    status="approved",
                    reason="Bận công tác",
                    event_status=event_row.status,
                    requested_at=now,
                    decided_at=now,
                    decided_by=admin.id,
                    after_deadline=True,
                    penalty_applied=True,
                    penalty_note="Phí demo",
                    released_items="{}",
                )
            )
    _gala(db, event_id, year, admin, employees, teams, registrations, now)
    _content(db, event_id, year, admin, employees[0], legs, now)
    return event_id


def _gala(
    db: Session,
    event_id: int,
    year: int,
    admin: User,
    employees: list[User],
    teams: list[Team],
    registrations: list[Registration],
    now: str,
) -> None:
    layout = GalaLayout(
        event_id=event_id,
        name=f"Gala {year}",
        venue="Sảnh tiệc",
        starts_at=_time(year, 16, 18),
        selection_status="open",
        draw_seed=year,
    )
    db.add(layout)
    db.flush()
    tables = [
        GalaTable(
            layout_id=layout.id,
            table_code=f"B{index + 1:02}",
            seat_count=8,
            pos_x=index * 3,
            pos_y=1,
        )
        for index in range(2)
    ]
    db.add_all(tables)
    db.flush()
    for index, team in enumerate(teams):
        quota = sum(
            row.is_active_participant and user.team_id == team.id
            for row, user in zip(registrations, employees, strict=True)
        )
        db.add(
            GalaDrawOrder(
                layout_id=layout.id,
                team_id=team.id,
                draw_position=index + 1,
                quota=quota,
                status="done" if index == 0 else "active",
                turn_started_at=now if index == 1 else None,
                turn_ends_at=to_iso(utcnow() + timedelta(minutes=5)) if index == 1 else None,
            )
        )
    for table_index, table in enumerate(tables):
        for seat_number in range(1, 9):
            seat = GalaSeat(table_id=table.id, seat_number=seat_number, status="free")
            if table_index == 0:
                registration = registrations[seat_number - 1]
                seat.status = "taken"
                seat.team_id = employees[seat_number - 1].team_id
                seat.registration_id = registration.id
                seat.confirmed_by, seat.confirmed_at = admin.id, now
            elif seat_number == 1:
                seat.status, seat.team_id = "held", teams[1].id
                seat.held_by, seat.held_at = employees[6].id, now
                seat.hold_expires_at = to_iso(utcnow() + timedelta(seconds=120))
            db.add(seat)


def _content(
    db: Session, event_id: int, year: int, admin: User, user: User, legs: list[TripLeg], now: str
) -> None:
    db.add_all(
        [
            ItineraryItem(
                event_id=event_id,
                day_date=f"{year}-10-15",
                start_time="05:00",
                title="Tập trung ra sân bay",
                trip_leg_id=legs[0].id,
                display_order=1,
            ),
            ItineraryItem(
                event_id=event_id,
                day_date=f"{year}-10-16",
                start_time="18:00",
                end_time="21:00",
                title="Gala Dinner",
                location="Sảnh tiệc",
                display_order=2,
            ),
            Content(
                kind="announcement",
                event_id=event_id,
                title="Thông báo lịch trình",
                content="BTC đã công bố thông tin hành trình.",
                published_at=now,
                created_by=admin.id,
            ),
            Content(
                kind="announcement",
                event_id=event_id,
                title="Bản nháp BTC",
                content="Nội dung chưa công khai.",
                created_by=admin.id,
            ),
            Content(
                kind="document",
                event_id=event_id,
                doc_type="terms",
                version="v2",
                title=f"Quy định {year}",
                content="Quy định tham gia kỳ Team Building.",
            ),
            EmailLog(
                event_id=event_id,
                user_id=user.id,
                to_email=user.email,
                template="journey_published",
                subject=f"Hành trình {year}",
                status="sent",
                sent_at=now,
                created_at=now,
            ),
            EmailLog(
                event_id=event_id,
                user_id=user.id,
                to_email=user.email,
                template="registration_reminder",
                subject="Email lỗi mẫu",
                status="failed",
                error_message="SMTP demo unavailable",
                created_at=now,
            ),
            ChatMessage(
                user_id=user.id,
                event_id=event_id,
                conversation_id=year,
                conversation_title="Lịch trình Gala",
                role="user",
                content="Gala tổ chức lúc nào?",
                created_at=now,
            ),
            ChatMessage(
                user_id=user.id,
                event_id=event_id,
                conversation_id=year,
                conversation_title="Lịch trình Gala",
                role="assistant",
                content=f"Gala bắt đầu lúc 18:00 ngày 16/10/{year} tại sảnh tiệc.",
                sources=json.dumps([{"title": "Lịch trình Gala", "source_type": "itinerary"}]),
                tokens_used=30,
                latency_ms=25,
                created_at=now,
            ),
        ]
    )


def seed(database: Path, *, reset: bool = False, second_event: bool = False) -> list[int]:
    database = database.expanduser().resolve()
    database.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(URL.create("sqlite", database=str(database)))
    event.listen(engine, "connect", _pragmas)
    try:
        _prepare_schema(engine)
        with Session(engine) as db, db.begin():
            db.execute(text("BEGIN IMMEDIATE"))
            if reset:
                # No FK disabling, no schema drops, child-to-parent deletion.
                for table in reversed(Base.metadata.sorted_tables):
                    db.execute(delete(table))
            first = db.scalar(select(Event).where(Event.code == "TB2026"))
            if first and not reset and not second_event:
                raise ValueError(
                    "TB2026 đã tồn tại. Dùng --second-event hoặc --reset trên DB demo."
                )
            admin, employees, teams, location = _master_data(db)
            ids = []
            if not first:
                ids.append(
                    _seed_event(
                        db,
                        year=2026,
                        active=True,
                        admin=admin,
                        employees=employees,
                        teams=teams,
                        location=location,
                    )
                )
            if second_event and not db.scalar(select(Event.id).where(Event.code == "TB2027")):
                ids.append(
                    _seed_event(
                        db,
                        year=2027,
                        active=False,
                        admin=admin,
                        employees=employees,
                        teams=teams,
                        location=location,
                    )
                )
            if not db.scalar(select(Content.id).where(Content.event_id.is_(None))):
                db.add(
                    Content(
                        kind="document",
                        doc_type="faq",
                        title="FAQ dùng chung",
                        content="Liên hệ BTC để được hỗ trợ.",
                    )
                )
            db.flush()
            violations = db.execute(text("PRAGMA foreign_key_check")).all()
            if violations:
                raise RuntimeError(f"Khoá ngoại không hợp lệ: {violations}")
            integrity = db.execute(text("PRAGMA integrity_check")).scalar()
            if integrity != "ok":
                raise RuntimeError(f"SQLite integrity_check: {integrity}")
        return ids
    finally:
        engine.dispose()


def main() -> int:
    # Windows consoles can default to cp1252; Vietnamese output must not fail after commit.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--reset", action="store_true", help="Xoá dữ liệu, chỉ dùng với DB demo v2")
    parser.add_argument(
        "--second-event", action="store_true", help="Thêm TB2027, giữ nguyên TB2026"
    )
    args = parser.parse_args()
    try:
        ids = seed(args.database, reset=args.reset, second_event=args.second_event)
        engine = create_engine(URL.create("sqlite", database=str(args.database.resolve())))
        try:
            with engine.connect() as connection:
                counts = {
                    table.name: connection.scalar(select(func.count()).select_from(table))
                    for table in Base.metadata.sorted_tables
                }
        finally:
            engine.dispose()
    except (ValueError, OSError, SQLAlchemyError, RuntimeError) as exc:
        parser.exit(1, f"Seed v2 thất bại: {exc}\n")
    print(f"DB v2: {args.database.resolve()} — 27 bảng; kỳ vừa tạo: {ids}")
    for name, count in sorted(counts.items()):
        print(f"  {name}: {count}")
    print(f"BTC: btc@company.vn / {ADMIN_PASSWORD}")
    print(f"Super Admin: superadmin@company.vn / {ADMIN_PASSWORD}")
    print(f"CBNV: nv01@company.vn … nv12@company.vn / {DEMO_PASSWORD}")
    print("Dữ liệu demo; backend v1 chưa tương thích DB v2. Không chạy alembic upgrade head.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
