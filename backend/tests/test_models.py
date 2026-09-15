"""Kiểm chứng schema: bảng, khoá ngoại, UNIQUE, CHECK thực sự có hiệu lực.

Test chạy trên database tạm trong file riêng, không đụng DB dev.
"""

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Base,
    Department,
    Event,
    Flight,
    FlightAssignment,
    GalaLayout,
    GalaSeat,
    GalaSeatAssignment,
    GalaTable,
    Registration,
    Shift,
    Team,
    User,
    utcnow_iso,
)
from app.models.enums import EventStatus, FlightDirection


@pytest.fixture
def db(tmp_path) -> Session:
    """DB SQLite tạm, có bật foreign_keys giống môi trường thật."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")

    @event.listens_for(engine, "connect")
    def _pragma(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def make_event(db: Session, **kwargs) -> Event:
    event_obj = Event(
        code=kwargs.get("code", "TB2026"),
        name="Team Building 2026",
        start_date="2026-10-15",
        end_date="2026-10-17",
        status=kwargs.get("status", EventStatus.REGISTRATION_OPEN),
    )
    db.add(event_obj)
    db.commit()
    return event_obj


def make_user(db: Session, email="a@company.vn", **kwargs) -> User:
    user = User(email=email, full_name=kwargs.get("full_name", "Nguyễn Văn A"), **kwargs)
    db.add(user)
    db.commit()
    return user


def make_registration(db: Session, event_obj: Event, user: User) -> Registration:
    registration = Registration(
        event_id=event_obj.id, user_id=user.id, is_participating=True
    )
    db.add(registration)
    db.commit()
    return registration


# --- Cấu trúc ---


def test_all_expected_tables_exist():
    assert len(Base.metadata.tables) == 34
    for table in (
        "events",
        "users",
        "registrations",
        "registration_cancellations",
        "flights",
        "gala_seat_assignments",
        "refresh_tokens",
    ):
        assert table in Base.metadata.tables


# --- Toàn vẹn tham chiếu ---


def test_foreign_key_is_enforced(db: Session):
    """Không cho tạo đăng ký trỏ tới event không tồn tại."""
    db.add(Registration(event_id=9999, user_id=9999, is_participating=True))
    with pytest.raises(IntegrityError):
        db.commit()


def test_cascade_delete_removes_children(db: Session):
    event_obj = make_event(db)
    db.add(Shift(event_id=event_obj.id, code="CA1", name="Ca 1"))
    db.commit()

    db.delete(event_obj)
    db.commit()
    assert db.query(Shift).count() == 0


# --- Quy tắc nghiệp vụ ở mức database ---


def test_one_registration_per_user_per_event(db: Session):
    event_obj = make_event(db)
    user = make_user(db)
    make_registration(db, event_obj, user)

    db.add(Registration(event_id=event_obj.id, user_id=user.id, is_participating=True))
    with pytest.raises(IntegrityError):
        db.commit()


def test_one_flight_per_registration_per_direction(db: Session):
    """Một người chỉ có một chuyến cho mỗi chiều — chặn ngay ở DB."""
    event_obj = make_event(db)
    user = make_user(db)
    registration = make_registration(db, event_obj, user)

    flights = []
    for code in ("VN1234", "VN5678"):
        flight = Flight(
            event_id=event_obj.id,
            flight_code=code,
            direction=FlightDirection.OUTBOUND,
            departure_airport="HAN",
            arrival_airport="PQC",
            departure_time="2026-10-15T06:00:00+00:00",
            arrival_time="2026-10-15T08:00:00+00:00",
            capacity=180,
        )
        db.add(flight)
        flights.append(flight)
    db.commit()

    db.add(
        FlightAssignment(
            registration_id=registration.id,
            flight_id=flights[0].id,
            direction=FlightDirection.OUTBOUND,
            assigned_at=utcnow_iso(),
        )
    )
    db.commit()

    db.add(
        FlightAssignment(
            registration_id=registration.id,
            flight_id=flights[1].id,
            direction=FlightDirection.OUTBOUND,
            assigned_at=utcnow_iso(),
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()


def test_same_registration_can_have_both_directions(db: Session):
    """Ngược lại, đi và về là hai bản ghi hợp lệ."""
    event_obj = make_event(db)
    registration = make_registration(db, event_obj, make_user(db))

    for direction in (FlightDirection.OUTBOUND, FlightDirection.RETURN):
        flight = Flight(
            event_id=event_obj.id,
            flight_code=f"VN-{direction}",
            direction=direction,
            departure_airport="HAN",
            arrival_airport="PQC",
            departure_time="2026-10-15T06:00:00+00:00",
            arrival_time="2026-10-15T08:00:00+00:00",
            capacity=180,
        )
        db.add(flight)
        db.commit()
        db.add(
            FlightAssignment(
                registration_id=registration.id,
                flight_id=flight.id,
                direction=direction,
                assigned_at=utcnow_iso(),
            )
        )
        db.commit()

    assert db.query(FlightAssignment).count() == 2


def test_one_team_per_gala_seat(db: Session):
    """Hai team không thể cùng giữ một ghế — lớp bảo vệ cuối ở mức DB."""
    event_obj = make_event(db)
    admin = make_user(db, email="admin@company.vn")
    layout = GalaLayout(event_id=event_obj.id, name="Gala 2026")
    db.add(layout)
    db.commit()

    table = GalaTable(
        layout_id=layout.id, table_code="B01", seat_count=10, pos_x=1, pos_y=1
    )
    db.add(table)
    db.commit()

    seat = GalaSeat(table_id=table.id, seat_number=1)
    db.add(seat)

    teams = [Team(code=f"T{i}", name=f"Team {i}") for i in (1, 2)]
    db.add_all(teams)
    db.commit()

    db.add(
        GalaSeatAssignment(
            seat_id=seat.id,
            team_id=teams[0].id,
            confirmed_by=admin.id,
            confirmed_at=utcnow_iso(),
        )
    )
    db.commit()

    db.add(
        GalaSeatAssignment(
            seat_id=seat.id,
            team_id=teams[1].id,
            confirmed_by=admin.id,
            confirmed_at=utcnow_iso(),
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()


def test_check_constraint_rejects_invalid_status(db: Session):
    db.add(
        Event(
            code="BAD",
            name="Kỳ sai trạng thái",
            start_date="2026-10-15",
            end_date="2026-10-17",
            status="trang_thai_khong_ton_tai",
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()


def test_flight_capacity_must_not_be_negative(db: Session):
    event_obj = make_event(db)
    db.add(
        Flight(
            event_id=event_obj.id,
            flight_code="VN0001",
            direction=FlightDirection.OUTBOUND,
            departure_airport="HAN",
            arrival_airport="PQC",
            departure_time="2026-10-15T06:00:00+00:00",
            arrival_time="2026-10-15T08:00:00+00:00",
            capacity=-5,
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()


def test_reserved_slots_cannot_exceed_capacity(db: Session):
    event_obj = make_event(db)
    db.add(
        Flight(
            event_id=event_obj.id,
            flight_code="VN0002",
            direction=FlightDirection.OUTBOUND,
            departure_airport="HAN",
            arrival_airport="PQC",
            departure_time="2026-10-15T06:00:00+00:00",
            arrival_time="2026-10-15T08:00:00+00:00",
            capacity=10,
            reserved_slots=20,
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()


# --- Logic trên model ---


def test_event_status_ordering():
    """My Journey chỉ mở từ information_published trở đi."""
    published = EventStatus.INFORMATION_PUBLISHED
    assert EventStatus.EVENT_STARTED.at_least(published)
    assert published.at_least(published)
    assert not EventStatus.ALLOCATION_PROCESSING.at_least(published)


def test_user_can_fly_requires_id_documents(db: Session):
    user = make_user(db)
    assert user.can_fly is False

    user.id_card_number = "001099012345"
    user.date_of_birth = "1999-01-01"
    db.commit()
    assert user.can_fly is True


def test_timestamps_are_set_automatically(db: Session):
    department = Department(code="IT", name="Công nghệ thông tin")
    db.add(department)
    db.commit()

    team = Team(code="IT1", name="Team IT 1", department_id=department.id)
    db.add(team)
    db.commit()
    assert team.created_at and team.updated_at


def test_default_pragmas_present_in_test_db(db: Session):
    assert db.execute(text("PRAGMA foreign_keys")).scalar() == 1
