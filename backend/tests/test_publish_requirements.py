"""Công bố là công bố trọn gói (F11 B8).

Luật của BTC: cấm tuyệt đối công bố khi còn người tham gia chưa có chuyến bay HAI chiều, xe ở chặng
họ đăng ký đi xe, phòng, hoặc ghế Gala. Trước bản sửa, kỳ công bố được cả khi chưa ai có chuyến bay.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import (
    Bus,
    Event,
    Flight,
    FlightAssignment,
    GalaLayout,
    GalaSeat,
    GalaTable,
    Registration,
    RegistrationLeg,
    TripLeg,
)
from app.models.accommodation import Hotel, Room
from app.models.enums import (
    AssignmentMode,
    EventStatus,
    FlightDirection,
    Gender,
    RegistrationStatus,
    UserRole,
)

NOW = "2026-10-01T03:00:00+00:00"


@pytest.fixture
def world(db: Session, make_user) -> dict:
    """Một người tham gia, kỳ đang phân bổ, hạ tầng có đủ nhưng CHƯA xếp gì cho người đó."""
    event = Event(
        code="TB2026", name="Team Building 2026", start_date="2026-10-15", end_date="2026-10-17",
        status=EventStatus.ALLOCATION_PROCESSING, terms_version="v1", is_active=True,
    )
    db.add(event)
    db.flush()
    admin = make_user(email="btc@company.vn", role=UserRole.ADMIN, full_name="Ban Tổ Chức")
    traveller = make_user(
        email="nv@company.vn", full_name="Nguyễn Văn Đi", gender=Gender.MALE,
        id_card_number="001095012345", date_of_birth="1995-05-05",
    )
    # Người không tham gia và người đã huỷ không được tính vào điều kiện công bố.
    stay_home = make_user(email="o-nha@company.vn", full_name="Trần Ở Nhà")
    quitter = make_user(email="huy@company.vn", full_name="Lê Đã Huỷ")

    outbound = Flight(
        event_id=event.id, flight_code="VN1234", direction=FlightDirection.OUTBOUND,
        departure_airport="HAN", arrival_airport="PQC",
        departure_time="2026-10-15T01:00:00+00:00", arrival_time="2026-10-15T03:10:00+00:00", capacity=60,
    )
    back = Flight(
        event_id=event.id, flight_code="VN4321", direction=FlightDirection.RETURN,
        departure_airport="PQC", arrival_airport="HAN",
        departure_time="2026-10-17T11:00:00+00:00", arrival_time="2026-10-17T13:10:00+00:00", capacity=60,
    )
    # Mã chặng không theo quy ước *_TO_AIRPORT để luật giờ xe–bay không xen vào bài này.
    leg = TripLeg(event_id=event.id, code="HOTEL_TO_GALA", name="Khách sạn → Gala", direction=FlightDirection.OUTBOUND)
    hotel = Hotel(event_id=event.id, name="Khách sạn Biển")
    layout = GalaLayout(event_id=event.id, name="Gala Dinner")
    db.add_all([outbound, back, leg, hotel, layout])
    db.flush()
    bus = Bus(event_id=event.id, trip_leg_id=leg.id, bus_code="XE-01", capacity=45)
    room = Room(hotel_id=hotel.id, room_number="101", capacity=2)
    table = GalaTable(layout_id=layout.id, table_code="B01", seat_count=2, pos_x=1, pos_y=1)
    db.add_all([bus, room, table])
    db.flush()
    seat = GalaSeat(table_id=table.id, seat_number=1)
    db.add(seat)

    registration = Registration(
        event_id=event.id, user_id=traveller.id, is_participating=True,
        status=RegistrationStatus.SUBMITTED, submitted_at=NOW,
    )
    db.add_all([
        registration,
        Registration(event_id=event.id, user_id=stay_home.id, is_participating=False,
                     status=RegistrationStatus.SUBMITTED, submitted_at=NOW),
        Registration(event_id=event.id, user_id=quitter.id, is_participating=True,
                     status=RegistrationStatus.CANCELLED, submitted_at=NOW),
    ])
    db.flush()
    db.add(RegistrationLeg(registration_id=registration.id, trip_leg_id=leg.id, needs_bus=True))
    db.commit()
    return {
        "event": event.id, "admin": admin.id, "registration": registration.id, "leg": leg.id,
        "outbound": outbound.id, "back": back.id, "bus": bus.id, "room": room.id, "seat": seat.id,
    }


@pytest.fixture
def admin(world, auth_headers):
    return auth_headers("btc@company.vn")


def publish(client: TestClient, world, headers):
    return client.post(
        f"/api/v1/events/{world['event']}/status", headers=headers, json={"status": "information_published"}
    )


def blocker_keys(response) -> list[str]:
    error = response.json()["error"]
    assert error["code"] == "PUBLISH_REQUIREMENTS_UNMET", error
    return [item["key"] for item in error["details"]["blockers"]]


def give(db: Session, world, *things: str) -> None:
    registration = db.get(Registration, world["registration"])
    for thing in things:
        if thing in ("outbound", "back"):
            direction = FlightDirection.OUTBOUND if thing == "outbound" else FlightDirection.RETURN
            db.add(FlightAssignment(
                registration_id=registration.id, flight_id=world[thing], direction=direction,
                assignment_mode=AssignmentMode.AUTO, assigned_at=NOW,
            ))
        elif thing == "bus":
            leg = db.query(RegistrationLeg).filter_by(registration_id=registration.id).one()
            leg.bus_id, leg.assignment_mode, leg.assigned_at = world["bus"], AssignmentMode.AUTO, NOW
        elif thing == "room":
            registration.room_id, registration.room_mode = world["room"], AssignmentMode.AUTO
            registration.room_assigned_at = NOW
        elif thing == "gala":
            seat = db.get(GalaSeat, world["seat"])
            seat.status, seat.registration_id = "taken", registration.id
            seat.confirmed_by, seat.confirmed_at = world["admin"], NOW
    db.commit()


def test_nothing_allocated_blocks_publishing_and_names_everything_missing(client, db: Session, world, admin):
    response = publish(client, world, admin)

    assert response.status_code == 409
    assert blocker_keys(response) == ["flight_outbound", "flight_return", "bus", "room", "gala"]
    first = response.json()["error"]["details"]["blockers"][0]
    assert first["count"] == 1 and first["names"] == ["Nguyễn Văn Đi"], "người ở nhà / đã huỷ không tính"
    assert first["link"] == "/admin/flights/board"
    assert db.get(Event, world["event"]).status == EventStatus.ALLOCATION_PROCESSING


@pytest.mark.parametrize(
    ("missing", "key"),
    [("outbound", "flight_outbound"), ("back", "flight_return"), ("bus", "bus"), ("room", "room"), ("gala", "gala")],
)
def test_any_single_gap_still_blocks(client, db: Session, world, admin, missing, key):
    """Chiều về hay bị quên nhất: xếp xong chiều đi là tưởng xong chuyến bay."""
    give(db, world, *[thing for thing in ("outbound", "back", "bus", "room", "gala") if thing != missing])

    response = publish(client, world, admin)

    assert response.status_code == 409
    assert blocker_keys(response) == [key]


def test_publishing_goes_through_once_everyone_has_everything(client, db: Session, world, admin):
    give(db, world, "outbound", "back", "bus", "room", "gala")

    response = publish(client, world, admin)

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "information_published"


def test_someone_who_did_not_ask_for_a_bus_needs_no_bus(client, db: Session, world, admin):
    leg = db.query(RegistrationLeg).filter_by(registration_id=world["registration"]).one()
    leg.needs_bus = False
    db.commit()
    give(db, world, "outbound", "back", "room", "gala")

    assert publish(client, world, admin).status_code == 200


def test_event_without_a_gala_layout_cannot_be_published(client, db: Session, world, admin):
    give(db, world, "outbound", "back", "bus", "room")
    db.delete(db.query(GalaLayout).one())
    db.commit()

    response = publish(client, world, admin)

    assert blocker_keys(response) == ["gala"]
    assert "sơ đồ Gala" in response.json()["error"]["message"]


def test_dashboard_checklist_reports_the_same_gala_gap(client, db: Session, world, admin):
    give(db, world, "outbound", "back", "bus", "room")
    checklist = client.get("/api/v1/admin/dashboard", headers=admin).json()["checklist"]
    gala = next(item for item in checklist if item["key"] == "gala_seated")
    assert gala["done"] is False and gala["required"] is True

    give(db, world, "gala")
    checklist = client.get("/api/v1/admin/dashboard", headers=admin).json()["checklist"]
    assert next(item for item in checklist if item["key"] == "gala_seated")["done"] is True


def test_stepping_back_from_published_is_never_blocked(client, db: Session, world, admin):
    """Thu hồi công bố để chỉnh sửa luôn phải làm được, kể cả khi dữ liệu đang thiếu."""
    db.get(Event, world["event"]).status = EventStatus.INFORMATION_PUBLISHED
    db.commit()
    back = client.post(
        f"/api/v1/events/{world['event']}/status", headers=admin, json={"status": "allocation_processing"}
    )
    assert back.status_code == 200, back.text
