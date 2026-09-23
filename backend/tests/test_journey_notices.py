"""Email báo CBNV khi BTC đổi hành trình đã công bố — đúng người, đúng dịch vụ, chỉ khi tích "Gửi email"."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.accommodation import Hotel, Room, RoomAssignment
from app.models.enums import (
    AssignmentMode,
    EmailStatus,
    EventStatus,
    FlightDirection,
    RegistrationStatus,
    RoomGenderPolicy,
    UserRole,
)
from app.models.event import Event
from app.models.flight import Flight, FlightAssignment
from app.models.notification import EmailLog
from app.models.registration import Registration
from app.models.transportation import Bus, BusAssignment, TripLeg

NOW = "2026-09-12T04:00:00+00:00"
TEMPLATE = "journey_changed"


@pytest.fixture
def world(db: Session, make_user) -> dict:
    """Kỳ đã công bố. An + Bình bay F1, Cường bay F2. An + Bình đi xe XE-01. An + Cường ở phòng 301,
    Bình ở phòng 302."""
    event = Event(
        code="TB2026", name="Team Building 2026", destination="Phú Quốc",
        start_date="2026-10-15", end_date="2026-10-17",
        status=EventStatus.INFORMATION_PUBLISHED, terms_version="v1", is_active=True,
    )
    db.add(event)
    db.flush()
    flights = [
        Flight(
            event_id=event.id, flight_code=code, direction=FlightDirection.OUTBOUND,
            departure_airport="HAN", arrival_airport="PQC", departure_time=departs,
            arrival_time="2026-10-15T08:40:00+00:00", capacity=60,
        )
        for code, departs in (("VN1234", "2026-10-14T23:30:00+00:00"), ("VJ456", "2026-10-15T02:00:00+00:00"))
    ]
    leg = TripLeg(
        event_id=event.id, code="CITY_TO_AIRPORT", name="HN → Sân bay",
        direction=FlightDirection.OUTBOUND, leg_date="2026-10-15", display_order=1,
    )
    hotel = Hotel(event_id=event.id, name="Resort Biển Xanh", address="Bãi Trường")
    db.add_all([*flights, leg, hotel])
    db.flush()
    bus = Bus(event_id=event.id, trip_leg_id=leg.id, bus_code="XE-01", plate_number="29B-11111", capacity=45)
    rooms = [
        Room(hotel_id=hotel.id, room_number=number, capacity=3, gender_policy=RoomGenderPolicy.MALE)
        for number in ("301", "302")
    ]
    db.add_all([bus, *rooms])
    db.flush()

    make_user(email="btc@company.vn", full_name="Trưởng BTC", role=UserRole.ADMIN)
    registrations = {}
    for key, flight, rides, room in (
        ("an", flights[0], True, rooms[0]),
        ("binh", flights[0], True, rooms[1]),
        ("cuong", flights[1], False, rooms[0]),
    ):
        user = make_user(email=f"{key}@company.vn", full_name=key.title(), gender="male")
        registration = Registration(
            event_id=event.id, user_id=user.id, is_participating=True,
            status=RegistrationStatus.SUBMITTED, submitted_at=NOW,
        )
        db.add(registration)
        db.flush()
        registrations[key] = registration.id
        db.add(FlightAssignment(
            registration_id=registration.id, flight_id=flight.id,
            direction=FlightDirection.OUTBOUND, assignment_mode=AssignmentMode.AUTO, assigned_at=NOW,
        ))
        if rides:
            db.add(BusAssignment(
                registration_id=registration.id, bus_id=bus.id, trip_leg_id=leg.id,
                assignment_mode=AssignmentMode.AUTO, assigned_at=NOW,
            ))
        db.add(RoomAssignment(
            registration_id=registration.id, room_id=room.id,
            assignment_mode=AssignmentMode.AUTO, assigned_at=NOW,
        ))
    db.commit()
    return {
        "event_id": event.id, "f1": flights[0].id, "f2": flights[1].id, "bus": bus.id,
        "hotel": hotel.id, "room_301": rooms[0].id, "room_302": rooms[1].id,
        "registrations": registrations,
    }


@pytest.fixture
def admin(world, auth_headers):
    return auth_headers("btc@company.vn")


def _mail(db: Session) -> dict[str, str]:
    db.expire_all()
    return {
        row.to_email: row.body_preview
        for row in db.scalars(select(EmailLog).where(EmailLog.template == TEMPLATE))
    }


def test_flight_time_change_emails_only_its_passengers(client: TestClient, world, admin, db):
    response = client.patch(
        f"/api/v1/flights/{world['f1']}?notify=true",
        headers=admin,
        json={"departure_time": "2026-10-15T00:30:00+00:00"},
    )
    assert response.status_code == 200, response.text

    mail = _mail(db)
    assert set(mail) == {"an@company.vn", "binh@company.vn"}  # Cường bay chuyến khác
    body = mail["an@company.vn"]
    assert "Chuyến bay chiều đi · Cất cánh: 15/10/2026 06:30 → 15/10/2026 07:30" in body
    # Chỉ phần đổi: không kể lại xe hay phòng.
    assert "Xe HN" not in body and "Phòng khách sạn" not in body


def test_nothing_sent_unless_ticked(client: TestClient, world, admin, db: Session):
    client.patch(f"/api/v1/flights/{world['f1']}", headers=admin, json={"departure_time": "2026-10-15T00:30:00+00:00"})
    client.patch(f"/api/v1/buses/{world['bus']}?notify=false", headers=admin, json={"plate_number": "30A-2"})
    assert _mail(db) == {}


def test_before_publish_nothing_is_sent_even_if_ticked(client: TestClient, world, admin, db):
    """CBNV chưa thấy phân bổ thì báo "đổi" là lộ dữ liệu dở dang (cạm bẫy #6)."""
    event = db.get(Event, world["event_id"])
    event.status = EventStatus.ALLOCATION_PROCESSING
    db.commit()
    client.patch(f"/api/v1/buses/{world['bus']}?notify=true", headers=admin, json={"plate_number": "30A-2"})
    assert _mail(db) == {}


def test_bus_change_emails_riders_only(client: TestClient, world, admin, db: Session):
    response = client.patch(
        f"/api/v1/buses/{world['bus']}?notify=true", headers=admin, json={"plate_number": "30A-22222"}
    )
    assert response.status_code == 200, response.text
    mail = _mail(db)
    assert set(mail) == {"an@company.vn", "binh@company.vn"}
    assert "Xe HN → Sân bay · Xe: XE-01 · 29B-11111 → XE-01 · 30A-22222" in mail["binh@company.vn"]


def test_moving_one_person_emails_that_person_not_roommates(client: TestClient, world, admin, db):
    """Bình chuyển sang phòng 301: chỉ Bình nhận thư. An và Cường có thêm bạn cùng phòng nhưng
    phòng của họ không đổi."""
    response = client.post(
        "/api/v1/room-assignments?notify=true",
        headers=admin,
        json={
            "registration_id": world["registrations"]["binh"], "room_id": world["room_301"],
            "replace_existing": True, "reason": "Đổi phòng",
        },
    )
    assert response.status_code == 200, response.text
    mail = _mail(db)
    assert set(mail) == {"binh@company.vn"}
    assert "Phòng khách sạn · Phòng: 302 → 301" in mail["binh@company.vn"]


def test_flight_move_emails_moved_person(client: TestClient, world, admin, db: Session):
    assignment_id = db.scalar(
        select(FlightAssignment.id).where(
            FlightAssignment.registration_id == world["registrations"]["cuong"]
        )
    )
    response = client.patch(
        f"/api/v1/flight-assignments/{assignment_id}?notify=true",
        headers=admin,
        json={"flight_id": world["f1"], "reason": "Gom cùng team"},
    )
    assert response.status_code == 200, response.text
    mail = _mail(db)
    assert set(mail) == {"cuong@company.vn"}
    assert "VJ456 → VN1234" in mail["cuong@company.vn"]
    # Lý do nội bộ của BTC không lọt vào thư CBNV.
    assert "Gom cùng team" not in mail["cuong@company.vn"]


def test_resend_skips_when_journey_changed_again(client: TestClient, world, admin, db):
    client.patch(f"/api/v1/buses/{world['bus']}?notify=true", headers=admin, json={"plate_number": "30A-2"})
    db.expire_all()
    rows = db.scalars(select(EmailLog).where(EmailLog.template == TEMPLATE)).all()
    for row in rows:
        row.status = EmailStatus.FAILED
    db.commit()

    first = client.post(
        "/api/v1/admin/email-logs/resend", headers=admin, json={"ids": [rows[0].id]}
    ).json()
    assert first["queued"] == 1

    # Biển số đổi tiếp: thư "→ 30A-2" giờ sai.
    client.patch(f"/api/v1/buses/{world['bus']}", headers=admin, json={"plate_number": "30A-3"})
    second = client.post(
        "/api/v1/admin/email-logs/resend", headers=admin, json={"ids": [rows[1].id]}
    ).json()
    assert second["skipped"][0]["reason"] == "no_longer_relevant"


# --- Thông tin kỳ + master data: cũng theo ô tích ---


def test_event_info_change_follows_notify_flag(client: TestClient, world, admin, db: Session):
    url = f"/api/v1/events/{world['event_id']}"
    client.patch(url, headers=admin, json={"destination": "Nha Trang"})
    assert not db.scalars(select(EmailLog).where(EmailLog.template == "event_info_changed")).all()

    client.patch(f"{url}?notify=true", headers=admin, json={"end_date": "2026-10-18"})
    db.expire_all()
    rows = db.scalars(select(EmailLog).where(EmailLog.template == "event_info_changed")).all()
    assert {row.to_email for row in rows} == {"an@company.vn", "binh@company.vn", "cuong@company.vn"}
    assert "Ngày kết thúc: 17/10/2026 → 18/10/2026" in rows[0].body_preview
