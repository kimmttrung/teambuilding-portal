"""Contract/integration tests cho đăng ký CBNV trên schema v2."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Department, Event, PickupPoint, Shift, Team, TripLeg, WorkLocation
from app.models.enums import EventStatus, FlightDirection, Gender, UserRole

REGISTRATIONS = "/api/v1/registrations"


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
    pickup = PickupPoint(
        event_id=event.id,
        trip_leg_id=leg.id,
        name="Toà Keangnam",
        address="Phạm Hùng, Hà Nội",
    )
    db.add(pickup)
    db.commit()

    employee = make_user(
        email="nv@company.vn",
        employee_code="NV001",
        full_name="Nguyễn Văn A",
        team_id=team.id,
        work_location_id=location.id,
        phone="0912345678",
        gender=Gender.MALE,
        date_of_birth="1995-03-20",
        id_card_number="001095012345",
    )
    other = make_user(
        email="nv2@company.vn",
        employee_code="NV002",
        full_name="Trần Văn B",
        team_id=team.id,
        work_location_id=location.id,
        phone="0912345679",
        gender=Gender.MALE,
        date_of_birth="1996-03-20",
        id_card_number="001095012346",
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


def registration_payload(world: dict, **overrides) -> dict:
    payload = {
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
        "wish_note": "Mong ở cùng team",
        "agreed_terms_version": "v1",
    }
    payload.update(overrides)
    return payload


def test_registration_returns_v2_json_and_admin_can_list(
    client: TestClient, world: dict, auth_headers
) -> None:
    employee_headers = auth_headers("nv@company.vn")
    response = client.post(REGISTRATIONS, headers=employee_headers, json=registration_payload(world))

    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == {
        "id",
        "event_id",
        "user_id",
        "is_participating",
        "not_participating_reason",
        "shift",
        "departure_location_id",
        "wish_note",
        "companion_count",
        "status",
        "submitted_at",
        "cancelled_at",
        "cancel_reason",
        "penalty_applied",
        "bus_needs",
        "can_edit",
        "agreed_terms_version",
        "cancel_policy",
        "latest_cancellation",
        "reregister_allowed",
    }
    assert body["status"] == "submitted"
    assert body["bus_needs"][0] == {
        "trip_leg_id": world["leg"].id,
        "trip_leg_code": "HN_AIRPORT",
        "trip_leg_name": "Hà Nội → Sân bay Nội Bài",
        "needs_bus": True,
        "pickup_point_id": world["pickup"].id,
        "pickup_point_name": "Toà Keangnam",
        "note": None,
    }

    admin_headers = auth_headers("btc@company.vn")
    admin_response = client.get(REGISTRATIONS, headers=admin_headers)
    assert admin_response.status_code == 200, admin_response.text
    admin_body = admin_response.json()
    assert admin_body["total"] == 1
    row = admin_body["items"][0]
    assert row["user"]["full_name"] == "Nguyễn Văn A"
    assert row["has_consent"] is True


def test_registration_rejects_incomplete_profile_and_invalid_pickup(
    client: TestClient, world: dict, make_user, auth_headers
) -> None:
    make_user(
        email="thieu@company.vn",
        employee_code="NV003",
        team_id=world["team"].id,
        work_location_id=world["location"].id,
        phone=None,
        gender=None,
        date_of_birth=None,
        id_card_number=None,
    )
    response = client.post(
        REGISTRATIONS,
        headers=auth_headers("thieu@company.vn"),
        json=registration_payload(world),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "MISSING_PROFILE_FIELDS"

    invalid_pickup = registration_payload(
        world, bus_needs=[{"trip_leg_id": world["leg"].id, "needs_bus": True}]
    )
    response = client.post(
        REGISTRATIONS,
        headers=auth_headers("nv@company.vn"),
        json=invalid_pickup,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "PICKUP_POINT_REQUIRED"


def test_registration_conflict_and_permission_are_json_errors(
    client: TestClient, world: dict, auth_headers
) -> None:
    employee_headers = auth_headers("nv@company.vn")
    created = client.post(REGISTRATIONS, headers=employee_headers, json=registration_payload(world))
    assert created.status_code == 201, created.text

    duplicate = client.post(REGISTRATIONS, headers=employee_headers, json=registration_payload(world))
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "ALREADY_REGISTERED"

    forbidden = client.get(REGISTRATIONS, headers=employee_headers)
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "PERMISSION_DENIED"

    other_headers = auth_headers("nv2@company.vn")
    forbidden_other = client.get(
        f"{REGISTRATIONS}/{world['employee'].id}", headers=other_headers
    )
    assert forbidden_other.status_code == 403
    assert forbidden_other.json()["error"]["code"] == "PERMISSION_DENIED"
