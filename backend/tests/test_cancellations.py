"""Integration tests cho huỷ/đăng ký lại và dọn allocation schema v2."""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Bus,
    Department,
    Event,
    Flight,
    FlightAssignment,
    GalaLayout,
    GalaSeat,
    GalaTable,
    Hotel,
    PickupPoint,
    Registration,
    RegistrationCancellation,
    RegistrationLeg,
    Room,
    Shift,
    Team,
    TripLeg,
    WorkLocation,
)
from app.models.enums import AssignmentMode, EventStatus, FlightDirection, Gender, UserRole

REGISTRATIONS = "/api/v1/registrations"
CANCELLATIONS = "/api/v1/admin/cancellations"


@pytest.fixture
def world(db: Session, make_user) -> dict:
    event = Event(
        code="TB2026",
        name="Team Building 2026",
        destination="Phú Quốc",
        start_date="2026-10-15",
        end_date="2026-10-17",
        status=EventStatus.REGISTRATION_OPEN,
        registration_closes_at="2026-12-25T17:00:00+00:00",
        terms_version="v1",
        terms_content="Quy định chương trình",
        is_active=True,
    )
    location = WorkLocation(code="HN", name="Hà Nội", airport_code="HAN")
    department = Department(code="TECH", name="Công nghệ")
    db.add_all([event, location, department])
    db.flush()
    team = Team(code="PRODUCT", name="Product", department_id=department.id)
    shift = Shift(event_id=event.id, code="CA1", name="Ca 1 · sáng", display_order=1)
    leg = TripLeg(
        event_id=event.id,
        code="HN_AIRPORT",
        name="Hà Nội → Sân bay Nội Bài",
        direction=FlightDirection.OUTBOUND,
        display_order=1,
    )
    db.add_all([team, shift, leg])
    db.flush()
    pickup = PickupPoint(event_id=event.id, trip_leg_id=leg.id, name="Keangnam")
    db.add(pickup)
    db.commit()

    profile = {
        "team_id": team.id,
        "work_location_id": location.id,
        "phone": "0912345678",
        "gender": Gender.MALE,
        "date_of_birth": "1995-03-20",
        "id_card_number": "001095012345",
    }
    employee = make_user(
        email="nv@company.vn", employee_code="NV001", full_name="Nguyễn Văn A", **profile
    )
    other = make_user(
        email="nv2@company.vn", employee_code="NV002", full_name="Trần Văn B", **profile
    )
    admin = make_user(email="btc@company.vn", full_name="Ban Tổ Chức", role=UserRole.ADMIN)
    return {
        "event": event,
        "location": location,
        "team": team,
        "shift": shift,
        "leg": leg,
        "pickup": pickup,
        "employee": employee,
        "other": other,
        "admin": admin,
    }


def registration_payload(world: dict) -> dict:
    return {
        "is_participating": True,
        "shift_id": world["shift"].id,
        "departure_location_id": world["location"].id,
        "bus_needs": [
            {
                "trip_leg_id": world["leg"].id,
                "needs_bus": True,
                "pickup_point_id": world["pickup"].id,
            }
        ],
        "agreed_terms_version": "v1",
    }


def register(client: TestClient, headers: dict, world: dict) -> int:
    response = client.post(REGISTRATIONS, headers=headers, json=registration_payload(world))
    assert response.status_code == 201, response.text
    return response.json()["id"]


def add_allocations(db: Session, world: dict, registration_id: int) -> dict:
    """Tạo đủ bốn loại allocation v2 để chứng minh đường huỷ dọn sạch."""
    registration = db.get(Registration, registration_id)
    flight = Flight(
        event_id=world["event"].id,
        flight_code="VN123",
        direction=FlightDirection.OUTBOUND,
        departure_airport="HAN",
        arrival_airport="PQC",
        departure_time="06:30",
        arrival_time="08:30",
        capacity=120,
    )
    bus = Bus(
        event_id=world["event"].id,
        trip_leg_id=world["leg"].id,
        bus_code="XE03",
        capacity=45,
        pickup_point_id=world["pickup"].id,
    )
    hotel = Hotel(event_id=world["event"].id, name="Sea Star Resort")
    db.add_all([flight, bus, hotel])
    db.flush()
    room = Room(hotel_id=hotel.id, room_number="1208", capacity=2)
    db.add(room)
    layout = GalaLayout(event_id=world["event"].id, name="Gala Dinner")
    db.add(layout)
    db.flush()
    table = GalaTable(
        layout_id=layout.id,
        table_code="B07",
        table_name="Bàn 07",
        seat_count=10,
        pos_x=1,
        pos_y=1,
    )
    db.add(table)
    db.flush()
    seat = GalaSeat(
        table_id=table.id,
        seat_number=4,
        is_available=False,
        status="taken",
        team_id=world["team"].id,
        registration_id=registration_id,
        confirmed_by=world["admin"].id,
        confirmed_at="2026-09-20T10:00:00+00:00",
    )
    db.add(seat)
    db.flush()

    registration.room_id = room.id
    registration.room_mode = "manual"
    leg = db.scalar(
        select(RegistrationLeg).where(RegistrationLeg.registration_id == registration_id)
    )
    assert leg is not None
    leg.bus_id = bus.id
    leg.assignment_mode = AssignmentMode.MANUAL
    leg.assigned_at = "2026-09-20T10:00:00+00:00"
    assignment = FlightAssignment(
        registration_id=registration_id,
        flight_id=flight.id,
        direction=FlightDirection.OUTBOUND,
        seat_number="12A",
        assignment_mode=AssignmentMode.MANUAL,
        assigned_at="2026-09-20T10:00:00+00:00",
    )
    db.add(assignment)
    db.commit()
    return {"flight": flight.id, "bus": bus.id, "room": room.id, "seat": seat.id}


def test_self_cancel_releases_flight_bus_room_and_gala_without_ghost_seat(
    client: TestClient, db: Session, world: dict, auth_headers
) -> None:
    employee_headers = auth_headers("nv@company.vn")
    registration_id = register(client, employee_headers, world)
    ids = add_allocations(db, world, registration_id)

    response = client.post(
        f"{REGISTRATIONS}/me/cancel",
        headers=employee_headers,
        json={"reason": "Việc gia đình"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "cancelled"

    assert db.scalar(select(FlightAssignment).where(FlightAssignment.registration_id == registration_id)) is None
    leg = db.scalar(select(RegistrationLeg).where(RegistrationLeg.registration_id == registration_id))
    assert leg is None, "Huỷ phải dọn cả dòng nhu cầu xe để không còn liên kết phân bổ"
    cancelled = db.get(Registration, registration_id)
    assert cancelled is not None
    assert cancelled.room_id is None
    seat = db.get(GalaSeat, ids["seat"])
    assert seat is not None
    assert seat.status == "free"
    assert seat.registration_id is None
    assert seat.is_available is True

    admin_headers = auth_headers("btc@company.vn")
    rows = client.get(CANCELLATIONS, headers=admin_headers)
    assert rows.status_code == 200, rows.text
    cancellation_row = rows.json()["items"][0]
    assert set(cancellation_row) == {
        "id",
        "mode",
        "status",
        "reason",
        "requested_at",
        "decided_at",
        "decision_note",
        "penalty_applied",
        "penalty_note",
        "registration_id",
        "event_status",
        "event_status_label",
        "after_deadline",
        "decided_by_name",
        "released",
        "reregistered_at",
        "user",
    }
    released = cancellation_row["released"]
    assert set(released) >= {"flights", "buses", "room", "gala"}
    assert all(ids[key] for key in ("flight", "bus", "room", "seat"))


def test_request_approve_keeps_allocation_until_btc_decides(
    client: TestClient, db: Session, world: dict, auth_headers
) -> None:
    employee_headers = auth_headers("nv@company.vn")
    registration_id = register(client, employee_headers, world)
    ids = add_allocations(db, world, registration_id)
    world["event"].status = EventStatus.INFORMATION_PUBLISHED
    db.commit()

    request = client.post(
        f"{REGISTRATIONS}/me/cancellation-request",
        headers=employee_headers,
        json={"reason": "Việc gia đình"},
    )
    assert request.status_code == 201, request.text
    assert request.json()["latest_cancellation"]["status"] == "pending"
    assert db.scalar(select(FlightAssignment).where(FlightAssignment.registration_id == registration_id)) is not None
    assert db.get(GalaSeat, ids["seat"]).registration_id == registration_id

    employee_forbidden = client.get(CANCELLATIONS, headers=employee_headers)
    assert employee_forbidden.status_code == 403
    assert employee_forbidden.json()["error"]["code"] == "PERMISSION_DENIED"

    admin_headers = auth_headers("btc@company.vn")
    pending = client.get(CANCELLATIONS, headers=admin_headers)
    cancellation_id = pending.json()["items"][0]["id"]
    approved = client.post(
        f"{CANCELLATIONS}/{cancellation_id}/approve",
        headers=admin_headers,
        json={"penalty_applied": False, "decision_note": "Đã duyệt"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert approved.json()["released"]
    assert db.scalar(select(FlightAssignment).where(FlightAssignment.registration_id == registration_id)) is None
    assert db.get(GalaSeat, ids["seat"]).registration_id is None


def test_reject_keeps_registration_and_reregister_after_self_cancel(
    client: TestClient, db: Session, world: dict, auth_headers
) -> None:
    employee_headers = auth_headers("nv@company.vn")
    registration_id = register(client, employee_headers, world)
    world["event"].status = EventStatus.INFORMATION_PUBLISHED
    db.commit()
    request = client.post(
        f"{REGISTRATIONS}/me/cancellation-request",
        headers=employee_headers,
        json={"reason": "Đổi kế hoạch"},
    )
    cancellation_id = request.json()["latest_cancellation"]["id"]
    admin_headers = auth_headers("btc@company.vn")
    rejected = client.post(
        f"{CANCELLATIONS}/{cancellation_id}/reject",
        headers=admin_headers,
        json={"decision_note": "Chưa đủ căn cứ"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert client.get(f"{REGISTRATIONS}/me", headers=employee_headers).json()["status"] == "submitted"
    assert db.get(Registration, registration_id).status == "submitted"

    world["event"].status = EventStatus.REGISTRATION_OPEN
    db.commit()
    cancelled = client.post(
        f"{REGISTRATIONS}/me/cancel",
        headers=employee_headers,
        json={"reason": "Huỷ lần hai"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["reregister_allowed"] is True
    reregis = client.post(REGISTRATIONS, headers=employee_headers, json=registration_payload(world))
    assert reregis.status_code == 201, reregis.text
    assert reregis.json()["status"] == "submitted"
    assert reregis.json()["reregister_allowed"] is False
