"""Kiểm thử master data: dropdown cho form đăng ký và bảo vệ toàn vẹn khi xoá."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Department, Event, Shift, Team, TripLeg, WorkLocation
from app.models.enums import EventStatus, FlightDirection, UserRole


@pytest.fixture
def event(db: Session) -> Event:
    row = Event(
        code="TB2026",
        name="Team Building 2026",
        start_date="2026-10-15",
        end_date="2026-10-17",
        status=EventStatus.REGISTRATION_OPEN,
        is_active=True,
    )
    db.add(row)
    db.flush()
    db.add_all(
        [
            Shift(event_id=row.id, code="CA1", name="Ca 1 – bay sáng", display_order=1),
            Shift(event_id=row.id, code="CA2", name="Ca 2 – bay tối", display_order=2),
            TripLeg(
                event_id=row.id,
                code="CITY_TO_AIRPORT",
                name="HN → Sân bay",
                direction=FlightDirection.OUTBOUND,
                display_order=1,
            ),
        ]
    )
    db.commit()
    db.refresh(row)
    return row


@pytest.fixture
def org(db: Session) -> dict:
    department = Department(code="CN", name="Khối Công nghệ")
    location = WorkLocation(code="HN", name="Hà Nội", airport_code="HAN")
    db.add_all([department, location])
    db.flush()
    team = Team(code="IT-HN", name="Công nghệ Hà Nội", department_id=department.id)
    db.add(team)
    db.commit()
    return {"department": department, "location": location, "team": team}


@pytest.fixture
def admin_headers(make_user, auth_headers):
    make_user(email="btc@company.vn", password="Admin12345", role=UserRole.ADMIN)
    return auth_headers("btc@company.vn", "Admin12345")


@pytest.fixture
def employee_headers(make_user, auth_headers):
    make_user(email="nv@company.vn", password="MatKhau123")
    return auth_headers("nv@company.vn")


# --- Đọc ---


def test_registration_form_returns_every_dropdown_in_one_call(
    client: TestClient, event, org, employee_headers
):
    """Form đăng ký là màn hình vào nhiều nhất — gộp 6 danh sách vào 1 request."""
    response = client.get("/api/v1/master-data/registration-form", headers=employee_headers)

    assert response.status_code == 200
    body = response.json()
    assert {"teams", "departments", "work_locations", "shifts", "trip_legs", "pickup_points"} <= body.keys()
    assert [shift["code"] for shift in body["shifts"]] == ["CA1", "CA2"]
    assert body["trip_legs"][0]["code"] == "CITY_TO_AIRPORT"


def test_employee_can_read_master_data(client: TestClient, event, org, employee_headers):
    for path in ("teams", "departments", "work-locations", "shifts", "trip-legs"):
        response = client.get(f"/api/v1/master-data/{path}", headers=employee_headers)
        assert response.status_code == 200, path


def test_employee_cannot_write_master_data(client: TestClient, employee_headers):
    response = client.post(
        "/api/v1/master-data/departments",
        headers=employee_headers,
        json={"code": "XX", "name": "Phòng ban lậu"},
    )
    assert response.status_code == 403


def test_team_list_includes_member_count(
    client: TestClient, event, org, admin_headers, make_user
):
    make_user(email="a@company.vn", team_id=org["team"].id)
    make_user(email="b@company.vn", team_id=org["team"].id)

    teams = client.get("/api/v1/master-data/teams", headers=admin_headers).json()
    assert teams[0]["member_count"] == 2


# --- Ghi ---


def test_create_and_update_shift(client: TestClient, event, admin_headers):
    created = client.post(
        "/api/v1/master-data/shifts",
        headers=admin_headers,
        json={
            "code": "CA3",
            "name": "Ca 3 – bay trưa",
            "earliest_departure": "12:00",
            "display_order": 3,
        },
    )
    assert created.status_code == 201
    shift_id = created.json()["id"]
    assert created.json()["event_id"] == event.id

    updated = client.patch(
        f"/api/v1/master-data/shifts/{shift_id}",
        headers=admin_headers,
        json={"name": "Ca 3 – bay đầu giờ chiều"},
    )
    assert updated.json()["name"] == "Ca 3 – bay đầu giờ chiều"


def test_duplicate_code_within_event_is_rejected(client: TestClient, event, admin_headers):
    response = client.post(
        "/api/v1/master-data/shifts",
        headers=admin_headers,
        json={"code": "CA1", "name": "Trùng mã"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CODE_DUPLICATED"


def test_invalid_code_format_is_rejected(client: TestClient, event, admin_headers):
    """Mã phải viết hoa không dấu — để hiển thị và import Excel đồng nhất."""
    response = client.post(
        "/api/v1/master-data/departments",
        headers=admin_headers,
        json={"code": "ca 1", "name": "Sai định dạng"},
    )
    assert response.status_code == 422


def test_team_color_must_be_hex(client: TestClient, org, admin_headers):
    response = client.post(
        "/api/v1/master-data/teams",
        headers=admin_headers,
        json={"code": "NEW", "name": "Team mới", "color": "xanh"},
    )
    assert response.status_code == 422


def test_team_leader_must_exist(client: TestClient, org, admin_headers):
    """teams.leader_user_id không có FOREIGN KEY nên phải tự kiểm tra."""
    response = client.post(
        "/api/v1/master-data/teams",
        headers=admin_headers,
        json={"code": "NEW", "name": "Team mới", "leader_user_id": 9999},
    )
    assert response.status_code == 404


# --- Bảo vệ khi xoá ---


def test_cannot_delete_team_with_members(
    client: TestClient, org, admin_headers, make_user
):
    make_user(email="a@company.vn", team_id=org["team"].id)

    response = client.delete(
        f"/api/v1/master-data/teams/{org['team'].id}", headers=admin_headers
    )
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "ENTITY_IN_USE"
    assert error["details"]["CBNV"] == 1
    assert "is_active" in error["message"]  # gợi ý cách ẩn thay vì xoá


def test_cannot_delete_department_with_teams(client: TestClient, org, admin_headers):
    response = client.delete(
        f"/api/v1/master-data/departments/{org['department'].id}", headers=admin_headers
    )
    assert response.status_code == 409
    assert response.json()["error"]["details"]["team"] == 1


def test_cannot_delete_shift_in_use(client: TestClient, event, admin_headers, db, make_user):
    from app.models import Registration

    user = make_user(email="a@company.vn")
    shift = db.query(Shift).filter(Shift.code == "CA1").one()
    db.add(
        Registration(
            event_id=event.id, user_id=user.id, is_participating=True, shift_id=shift.id
        )
    )
    db.commit()

    response = client.delete(f"/api/v1/master-data/shifts/{shift.id}", headers=admin_headers)
    assert response.status_code == 409
    assert response.json()["error"]["details"]["đăng ký"] == 1


def test_unused_entity_can_be_deleted(client: TestClient, event, admin_headers):
    created = client.post(
        "/api/v1/master-data/shifts",
        headers=admin_headers,
        json={"code": "CA9", "name": "Ca thử"},
    ).json()

    response = client.delete(
        f"/api/v1/master-data/shifts/{created['id']}", headers=admin_headers
    )
    assert response.status_code == 204
    remaining = client.get("/api/v1/master-data/shifts", headers=admin_headers).json()
    assert "CA9" not in [shift["code"] for shift in remaining]


def test_delete_is_audited(client: TestClient, event, admin_headers, db):
    from app.models import AuditLog

    created = client.post(
        "/api/v1/master-data/shifts",
        headers=admin_headers,
        json={"code": "CA9", "name": "Ca thử"},
    ).json()
    client.delete(f"/api/v1/master-data/shifts/{created['id']}", headers=admin_headers)

    actions = [row.action for row in db.query(AuditLog).all()]
    assert "shift.created" in actions
    assert "shift.deleted" in actions


def test_pickup_point_crud(client: TestClient, event, org, admin_headers, db):
    leg = db.query(TripLeg).one()
    created = client.post(
        "/api/v1/master-data/pickup-points",
        headers=admin_headers,
        json={
            "name": "Toà nhà Keangnam",
            "address": "Phạm Hùng, Nam Từ Liêm",
            "trip_leg_id": leg.id,
            "work_location_id": org["location"].id,
        },
    )
    assert created.status_code == 201
    assert created.json()["event_id"] == event.id

    listed = client.get("/api/v1/master-data/pickup-points", headers=admin_headers).json()
    assert listed[0]["name"] == "Toà nhà Keangnam"
