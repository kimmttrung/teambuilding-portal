"""Trưởng nhóm huỷ → mất chức ngay, BTC chỉ định người thay. Người đã huỷ đăng ký lại → BTC được báo."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.exceptions import PermissionDeniedError
from app.models import (
    AuditLog,
    Department,
    EmailLog,
    Event,
    GalaLayout,
    Registration,
    RegistrationCancellation,
    Shift,
    Team,
    User,
    WorkLocation,
)
from app.models.enums import EventStatus, Gender, UserRole
from app.services import gala_service

REG = "/api/v1/registrations"
ADMIN = "/api/v1/admin/cancellations"


@pytest.fixture
def world(db: Session, make_user) -> dict:
    event = Event(
        code="TB2026",
        name="Team Building 2026",
        start_date="2026-10-15",
        end_date="2026-10-17",
        status=EventStatus.REGISTRATION_OPEN,
        registration_closes_at="2026-12-25T17:00:00+00:00",
        terms_version="v1",
        terms_content="Quy định...",
        is_active=True,
    )
    location = WorkLocation(code="HN", name="Hà Nội", airport_code="HAN")
    department = Department(code="CN", name="Khối Công nghệ")
    db.add_all([event, location, department])
    db.flush()
    team = Team(code="IT-HN", name="Công nghệ Hà Nội", department_id=department.id)
    other = Team(code="MKT", name="Marketing", department_id=department.id)
    shift = Shift(event_id=event.id, code="CA1", name="Ca 1", display_order=1)
    db.add_all([team, other, shift])
    db.commit()

    profile = {
        "work_location_id": location.id,
        "phone": "0912345678",
        "gender": Gender.MALE,
        "date_of_birth": "1995-03-20",
        "id_card_number": "001095012345",
    }
    leader = make_user(email="lead@company.vn", full_name="Trưởng Nhóm", role=UserRole.TEAM_LEADER, team_id=team.id, **profile)
    member = make_user(email="mem@company.vn", full_name="Thành Viên", team_id=team.id, **profile)
    outsider = make_user(email="out@company.vn", full_name="Người Ngoài", team_id=other.id, **profile)
    admin = make_user(email="btc@company.vn", full_name="Ban Tổ Chức", role=UserRole.ADMIN)
    team.leader_user_id = leader.id
    db.commit()
    return {"event": event, "team": team, "shift": shift, "location": location, "leader": leader, "member": member, "outsider": outsider, "admin": admin}


@pytest.fixture
def login(world, auth_headers):
    cache: dict[str, dict] = {}

    def _login(email: str) -> dict:
        if email not in cache:
            cache[email] = auth_headers(email)
        return cache[email]

    return _login


def register(client: TestClient, headers: dict, world: dict) -> int:
    response = client.post(
        REG,
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
    return response.json()["id"]


def set_status(db: Session, world: dict, status: EventStatus) -> None:
    world["event"].status = status
    db.commit()


def team_row(client: TestClient, headers: dict, world: dict) -> dict:
    teams = client.get("/api/v1/admin/dashboard", headers=headers).json()["teams"]
    return next(row for row in teams if row["team_id"] == world["team"].id)


def code(response) -> str:
    return response.json()["error"]["code"]


def test_leader_self_cancel_demotes_role_and_flags_team(client: TestClient, db: Session, world, login):
    register(client, login("lead@company.vn"), world)
    register(client, login("mem@company.vn"), world)
    btc = login("btc@company.vn")
    assert team_row(client, btc, world)["needs_leader"] is False

    client.post(f"{REG}/me/cancel", headers=login("lead@company.vn"), json={"reason": "Trùng lịch"})

    db.expire_all()
    assert db.get(Team, world["team"].id).leader_user_id is None
    assert db.get(User, world["leader"].id).role == UserRole.EMPLOYEE
    row = team_row(client, btc, world)
    assert row["needs_leader"] is True
    assert row["leader_name"] is None


def test_organizer_assigns_new_leader_and_roles_follow(client: TestClient, db: Session, world, login):
    register(client, login("lead@company.vn"), world)
    register(client, login("mem@company.vn"), world)
    client.post(f"{REG}/me/cancel", headers=login("lead@company.vn"), json={"reason": "Trùng lịch"})
    btc = login("btc@company.vn")

    response = client.put(
        f"/api/v1/admin/teams/{world['team'].id}/leader", headers=btc, json={"user_id": world["member"].id}
    )

    assert response.status_code == 200, response.text
    assert response.json()["leader_name"] == "Thành Viên"
    db.expire_all()
    assert db.get(Team, world["team"].id).leader_user_id == world["member"].id
    assert db.get(User, world["member"].id).role == UserRole.TEAM_LEADER
    assert db.query(AuditLog).filter_by(action="team.leader_changed").count() == 1
    assert team_row(client, btc, world)["needs_leader"] is False
    # Trưởng nhóm mới có quyền Gala ngay.
    assert gala_service.led_team(db, world["member"].id).id == world["team"].id


def test_assign_leader_validations(client: TestClient, db: Session, world, login):
    register(client, login("lead@company.vn"), world)
    register(client, login("out@company.vn"), world)
    btc = login("btc@company.vn")
    url = f"/api/v1/admin/teams/{world['team'].id}/leader"

    assert code(client.put(url, headers=btc, json={"user_id": world["outsider"].id})) == "LEADER_NOT_IN_TEAM"
    # Thành viên chưa đăng ký tham gia thì không làm Trưởng nhóm được.
    assert code(client.put(url, headers=btc, json={"user_id": world["member"].id})) == "LEADER_NOT_PARTICIPATING"
    assert code(client.put(url, headers=btc, json={"user_id": world["leader"].id})) == "LEADER_UNCHANGED"
    assert code(client.put(url, headers=btc, json={"user_id": world["admin"].id})) == "LEADER_IS_ORGANIZER"
    assert client.put(url, headers=login("lead@company.vn"), json={"user_id": world["leader"].id}).status_code == 403


def test_approve_leader_request_with_replacement_in_same_transaction(
    client: TestClient, db: Session, world, login
):
    registration_id = register(client, login("lead@company.vn"), world)
    register(client, login("mem@company.vn"), world)
    set_status(db, world, EventStatus.INFORMATION_PUBLISHED)
    client.post(f"{REG}/me/cancellation-request", headers=login("lead@company.vn"), json={"reason": "Ốm nặng"})
    cancellation_id = db.query(RegistrationCancellation).one().id
    btc = login("btc@company.vn")

    item = client.get(f"{ADMIN}?status=pending", headers=btc).json()["items"][0]
    assert item["user"]["is_team_leader"] is True
    assert item["user"]["team_id"] == world["team"].id

    # Người thay không hợp lệ → cả việc duyệt huỷ bị huỷ theo.
    bad = client.post(f"{ADMIN}/{cancellation_id}/approve", headers=btc, json={"new_leader_user_id": world["outsider"].id})
    assert code(bad) == "LEADER_NOT_IN_TEAM"
    db.expire_all()
    assert db.get(Registration, registration_id).status == "submitted"
    assert db.get(RegistrationCancellation, cancellation_id).status == "pending"
    assert db.get(Team, world["team"].id).leader_user_id == world["leader"].id

    good = client.post(f"{ADMIN}/{cancellation_id}/approve", headers=btc, json={"new_leader_user_id": world["member"].id})
    assert good.status_code == 200, good.text
    db.expire_all()
    assert db.get(Registration, registration_id).status == "cancelled"
    assert db.get(Team, world["team"].id).leader_user_id == world["member"].id
    assert db.get(User, world["member"].id).role == UserRole.TEAM_LEADER
    assert db.get(User, world["leader"].id).role == UserRole.EMPLOYEE


def test_replacement_for_non_leader_is_rejected(client: TestClient, db: Session, world, login):
    register(client, login("lead@company.vn"), world)
    register(client, login("mem@company.vn"), world)
    set_status(db, world, EventStatus.INFORMATION_PUBLISHED)
    client.post(f"{REG}/me/cancellation-request", headers=login("mem@company.vn"), json={"reason": "Bận việc"})
    cancellation_id = db.query(RegistrationCancellation).one().id

    response = client.post(
        f"{ADMIN}/{cancellation_id}/approve", headers=login("btc@company.vn"), json={"new_leader_user_id": world["leader"].id}
    )
    assert code(response) == "NOT_TEAM_LEADER"


def test_cancelled_leader_cannot_auto_assign_members(client: TestClient, db: Session, world, login):
    """Phòng thủ sâu cho lối "xếp ngẫu nhiên thành viên": sót chức cũng không làm được."""
    register(client, login("lead@company.vn"), world)
    client.post(f"{REG}/me/cancel", headers=login("lead@company.vn"), json={"reason": "Đổi ý"})
    db.add(GalaLayout(event_id=world["event"].id, name="Gala"))
    world["team"].leader_user_id = world["leader"].id  # giả lập sót dữ liệu
    db.commit()
    db.expire_all()

    with pytest.raises(PermissionDeniedError):
        gala_service.auto_assign_members(db, event=db.get(Event, world["event"].id), actor=db.get(User, world["leader"].id))


# --- Đăng ký lại ---


def test_reregister_after_close_notifies_organizers(client: TestClient, db: Session, world, login):
    headers = login("mem@company.vn")
    register(client, headers, world)
    client.post(f"{REG}/me/cancel", headers=headers, json={"reason": "Việc gia đình"})
    set_status(db, world, EventStatus.ALLOCATION_PROCESSING)

    register(client, headers, world)

    db.expire_all()
    notices = [row.to_email for row in db.query(EmailLog).filter_by(template="registration_reregistered_admin")]
    assert notices == ["btc@company.vn"]
    assert db.query(AuditLog).filter_by(action="registration.reregistered").count() == 1

    btc = login("btc@company.vn")
    assert client.get("/api/v1/admin/dashboard", headers=btc).json()["cancellations"]["reregistered_recent"] == 1
    row = client.get(f"{ADMIN}?status=approved", headers=btc).json()["items"][0]
    assert row["reregistered_at"] is not None


def test_reregister_while_open_is_ordinary(client: TestClient, db: Session, world, login):
    headers = login("mem@company.vn")
    register(client, headers, world)
    client.post(f"{REG}/me/cancel", headers=headers, json={"reason": "Đổi ý"})

    register(client, headers, world)

    db.expire_all()
    assert db.query(EmailLog).filter_by(template="registration_reregistered_admin").count() == 0
