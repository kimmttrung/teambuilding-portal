"""Test chỉ định và hiển thị Trưởng nhóm trên schema v2."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Department, Event, Shift, Team, TripLeg, WorkLocation
from app.models.enums import EventStatus, FlightDirection, Gender, UserRole

REGISTRATIONS = "/api/v1/registrations"
TEAMS = "/api/v1/admin/teams"


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
    other_team = Team(code="SALES", name="Sales", department_id=department.id)
    shift = Shift(event_id=event.id, code="CA1", name="Ca 1", display_order=1)
    db.add_all([team, other_team, shift])
    db.commit()

    profile = {
        "work_location_id": location.id,
        "phone": "0912345678",
        "gender": Gender.MALE,
        "date_of_birth": "1995-03-20",
        "id_card_number": "001095012345",
    }
    candidate = make_user(
        email="lead@company.vn",
        employee_code="NV001",
        full_name="Trưởng Nhóm",
        team_id=team.id,
        **profile,
    )
    non_participant = make_user(
        email="absent@company.vn",
        employee_code="NV002",
        full_name="Chưa tham gia",
        team_id=team.id,
        **profile,
    )
    outsider = make_user(
        email="out@company.vn",
        employee_code="NV003",
        full_name="Người Ngoài Team",
        team_id=other_team.id,
        **profile,
    )
    admin = make_user(email="btc@company.vn", full_name="Ban Tổ Chức", role=UserRole.ADMIN)
    return {
        "event": event,
        "location": location,
        "team": team,
        "other_team": other_team,
        "shift": shift,
        "candidate": candidate,
        "non_participant": non_participant,
        "outsider": outsider,
        "admin": admin,
    }


def register(client: TestClient, headers: dict, world: dict) -> None:
    response = client.post(
        REGISTRATIONS,
        headers=headers,
        json={
            "is_participating": True,
            "shift_id": world["shift"].id,
            "departure_location_id": world["location"].id,
            "bus_needs": [],
            "agreed_terms_version": "v1",
        },
    )
    assert response.status_code == 201, response.text


def test_admin_assigns_and_dashboard_displays_leader(
    client: TestClient, world: dict, auth_headers
) -> None:
    register(client, auth_headers("lead@company.vn"), world)
    admin_headers = auth_headers("btc@company.vn")

    assigned = client.put(
        f"{TEAMS}/{world['team'].id}/leader",
        headers=admin_headers,
        json={"user_id": world["candidate"].id},
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json() == {
        "team_id": world["team"].id,
        "team_name": "Product",
        "leader_user_id": world["candidate"].id,
        "leader_name": "Trưởng Nhóm",
        "previous_leader_user_id": None,
    }

    dashboard = client.get("/api/v1/admin/dashboard", headers=admin_headers)
    assert dashboard.status_code == 200, dashboard.text
    row = next(item for item in dashboard.json()["teams"] if item["team_id"] == world["team"].id)
    assert row["leader_user_id"] == world["candidate"].id
    assert row["leader_name"] == "Trưởng Nhóm"
    assert row["needs_leader"] is False


def test_team_leader_assignment_forbidden_and_conflict_cases(
    client: TestClient, world: dict, auth_headers
) -> None:
    employee_headers = auth_headers("lead@company.vn")
    forbidden = client.put(
        f"{TEAMS}/{world['team'].id}/leader",
        headers=employee_headers,
        json={"user_id": world["candidate"].id},
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "PERMISSION_DENIED"

    admin_headers = auth_headers("btc@company.vn")
    not_participating = client.put(
        f"{TEAMS}/{world['team'].id}/leader",
        headers=admin_headers,
        json={"user_id": world["non_participant"].id},
    )
    assert not_participating.status_code == 409
    assert not_participating.json()["error"]["code"] == "LEADER_NOT_PARTICIPATING"

    outsider = client.put(
        f"{TEAMS}/{world['team'].id}/leader",
        headers=admin_headers,
        json={"user_id": world["outsider"].id},
    )
    assert outsider.status_code == 409
    assert outsider.json()["error"]["code"] == "LEADER_NOT_IN_TEAM"
