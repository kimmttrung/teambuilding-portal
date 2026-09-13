"""Kiểm thử quản lý tài khoản CBNV (docs/04 §10, docs/09 §3)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.enums import EventStatus, Gender, RegistrationStatus, UserRole
from app.models.event import Event
from app.models.org import Department, Team, WorkLocation
from app.models.registration import Registration

URL = "/api/v1/admin/users"
PASSWORD = "MatKhau123"


@pytest.fixture
def world(db: Session, make_user) -> dict:
    event = Event(
        code="TB2026", name="Team Building 2026", start_date="2026-10-15", end_date="2026-10-17",
        status=EventStatus.REGISTRATION_OPEN, terms_version="v1", is_active=True,
    )
    it = Team(code="IT", name="Công nghệ")
    sales = Team(code="SALE", name="Kinh doanh")
    department = Department(code="CN", name="Khối Công nghệ")
    location = WorkLocation(code="HN", name="Hà Nội")
    db.add_all([event, it, sales, department, location])
    db.flush()

    root = make_user(email="root@company.vn", role=UserRole.SUPER_ADMIN, full_name="Quản trị", employee_code="BTC000")
    admin = make_user(email="btc@company.vn", role=UserRole.ADMIN, full_name="Ban Tổ Chức", employee_code="BTC001")
    other_admin = make_user(email="btc2@company.vn", role=UserRole.ADMIN, full_name="BTC Hai", employee_code="BTC002")
    an = make_user(
        email="an@company.vn", full_name="An Nguyễn", employee_code="NV001", team_id=it.id,
        department_id=department.id, work_location_id=location.id, phone="0912000001",
        id_card_number="001095000001", date_of_birth="1995-01-01", gender=Gender.MALE,
    )
    binh = make_user(email="binh@company.vn", full_name="Bình Trần", employee_code="NV002", team_id=sales.id)
    locked = make_user(
        email="khoa@company.vn", full_name="Khoá Tạm", employee_code="NV003",
        failed_login_count=5, locked_until="2099-01-01T00:00:00+00:00",
    )
    db.add(
        Registration(
            event_id=event.id, user_id=an.id, is_participating=True,
            status=RegistrationStatus.SUBMITTED, submitted_at="2026-09-12T03:00:00+00:00",
        )
    )
    db.commit()
    return {
        "it": it.id, "sales": sales.id, "root": root.id, "admin": admin.id,
        "other_admin": other_admin.id, "an": an.id, "binh": binh.id, "locked": locked.id,
    }


@pytest.fixture
def admin(world, auth_headers):
    return auth_headers("btc@company.vn")


@pytest.fixture
def root(world, auth_headers):
    return auth_headers("root@company.vn")


def login(client: TestClient, email: str, password: str):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


# --- Quyền ---


def test_only_organizers_manage_users(client: TestClient, world, auth_headers):
    employee = auth_headers("an@company.vn")

    assert client.get(URL, headers=employee).status_code == 403
    assert client.get(f"{URL}/{world['binh']}", headers=employee).status_code == 403
    assert (
        client.post(URL, headers=employee, json={"employee_code": "NV9", "full_name": "X", "email": "x@company.vn"}).status_code
        == 403
    )


def test_only_super_admin_touches_organizer_accounts(client: TestClient, world, admin, root):
    payload = {"employee_code": "BTC010", "full_name": "BTC Mới", "email": "btc10@company.vn", "role": "admin"}
    other = f"{URL}/{world['other_admin']}"

    assert client.post(URL, headers=admin, json=payload).status_code == 403
    assert client.patch(other, headers=admin, json={"phone": "0900000009"}).status_code == 403
    assert client.post(f"{other}/reset-password", headers=admin).status_code == 403
    assert (
        client.patch(f"{other}/status", headers=admin, json={"is_active": False, "reason": "Nghỉ việc"}).status_code
        == 403
    )
    assert client.post(URL, headers=root, json=payload).status_code == 201
    assert client.patch(other, headers=root, json={"phone": "0900000009"}).status_code == 200


# --- Danh sách ---


def test_list_filters_and_hides_documents(client: TestClient, world, admin):
    def names(**params):
        return [row["full_name"] for row in client.get(URL, headers=admin, params=params).json()["items"]]

    assert names(q="NV00") == ["An Nguyễn", "Bình Trần", "Khoá Tạm"]
    assert names(team_id=world["it"]) == ["An Nguyễn"]
    assert names(registration="participating") == ["An Nguyễn"]
    assert "An Nguyễn" not in names(registration="none")
    assert names(role="admin") == ["BTC Hai", "Ban Tổ Chức"]
    assert names(q="NV", missing_documents="true") == ["Bình Trần", "Khoá Tạm"]

    row = client.get(URL, headers=admin, params={"q": "NV001"}).json()["items"][0]
    assert (row["registration_status"], row["is_participating"], row["can_fly"]) == ("submitted", True, True)
    assert (row["team_name"], row["department_name"], row["work_location_name"]) == ("Công nghệ", "Khối Công nghệ", "Hà Nội")
    assert "id_card_number" not in row
    assert "date_of_birth" not in row

    locked = client.get(URL, headers=admin, params={"q": "NV003"}).json()["items"][0]
    assert locked["is_locked"] is True


def test_detail_shows_full_profile_to_organizers(client: TestClient, world, admin):
    body = client.get(f"{URL}/{world['an']}", headers=admin).json()

    assert body["id_card_number"] == "001095000001"
    assert body["team"]["name"] == "Công nghệ"
    assert client.get(f"{URL}/99999", headers=admin).status_code == 404


# --- Tạo ---


def test_create_returns_one_time_password_and_forces_change(client: TestClient, world, admin, db: Session):
    response = client.post(
        URL,
        headers=admin,
        json={"employee_code": "NV100", "full_name": "Chi Lê", "email": " Chi.Le@Company.vn ", "team_id": world["it"], "gender": "female"},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    password = body["temporary_password"]
    assert len(password) == 12
    assert body["user"]["email"] == "chi.le@company.vn"
    assert body["user"]["must_change_password"] is True

    logged = login(client, "chi.le@company.vn", password)
    assert logged.status_code == 200
    assert logged.json()["user"]["must_change_password"] is True

    audit = db.query(AuditLog).filter_by(action="user.created").one()
    assert password not in (audit.after_data or "")


def test_create_rejects_duplicates_and_unknown_refs(client: TestClient, world, admin):
    base = {"employee_code": "NV200", "full_name": "Dũng", "email": "dung@company.vn"}

    def create(**overrides):
        return client.post(URL, headers=admin, json={**base, **overrides}).json()["error"]["code"]

    assert create(email="AN@company.vn") == "EMAIL_TAKEN"
    assert create(employee_code="NV001") == "EMPLOYEE_CODE_TAKEN"
    assert create(team_id=9999) == "TEAM_NOT_FOUND"


# --- Sửa ---


def test_update_profile_keeps_documents_out_of_audit(client: TestClient, world, admin, db: Session):
    url = f"{URL}/{world['binh']}"
    response = client.patch(
        url, headers=admin, json={"team_id": world["it"], "phone": "0987654321", "id_card_number": "001095999999"}
    )

    assert response.status_code == 200, response.text
    assert response.json()["team"]["name"] == "Công nghệ"
    audit = db.query(AuditLog).filter_by(action="user.updated").one()
    assert "001095999999" not in (audit.after_data or "")
    assert "001095999999" not in (audit.before_data or "")
    assert client.patch(url, headers=admin, json={"email": "an@company.vn"}).json()["error"]["code"] == "EMAIL_TAKEN"
    assert client.patch(url, headers=admin, json={"full_name": "   "}).status_code in (400, 422)


def test_role_change_is_super_admin_only(client: TestClient, world, admin, root, db: Session):
    url = f"{URL}/{world['an']}/role"

    assert client.patch(url, headers=admin, json={"role": "team_leader"}).status_code == 403
    changed = client.patch(url, headers=root, json={"role": "team_leader", "reason": "Trưởng nhóm mới"})
    assert changed.status_code == 200
    assert changed.json()["role"] == "team_leader"
    assert client.patch(url, headers=root, json={"role": "team_leader"}).json()["error"]["code"] == "ROLE_UNCHANGED"
    assert (
        client.patch(f"{URL}/{world['root']}/role", headers=root, json={"role": "admin"}).json()["error"]["code"]
        == "SELF_ROLE_CHANGE"
    )
    assert db.query(AuditLog).filter_by(action="user.role_changed").one().reason == "Trưởng nhóm mới"


# --- Khoá, mật khẩu ---


def test_deactivation_blocks_login_and_revokes_sessions(client: TestClient, world, admin):
    session = login(client, "binh@company.vn", PASSWORD).json()
    url = f"{URL}/{world['binh']}/status"

    assert client.patch(url, headers=admin, json={"is_active": False}).status_code == 422
    assert client.patch(url, headers=admin, json={"is_active": False, "reason": "Nghỉ việc"}).status_code == 200
    assert login(client, "binh@company.vn", PASSWORD).json()["error"]["code"] == "ACCOUNT_DISABLED"
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": session["refresh_token"]}).status_code == 401

    assert client.patch(url, headers=admin, json={"is_active": True, "reason": "Đi làm lại"}).status_code == 200
    assert login(client, "binh@company.vn", PASSWORD).status_code == 200


def test_no_self_lockout(client: TestClient, world, root):
    me = f"{URL}/{world['root']}"

    assert (
        client.patch(f"{me}/status", headers=root, json={"is_active": False, "reason": "Thử"}).json()["error"]["code"]
        == "SELF_DEACTIVATION"
    )
    assert client.post(f"{me}/reset-password", headers=root).json()["error"]["code"] == "SELF_PASSWORD_RESET"


def test_reset_password_unlocks_and_forces_change(client: TestClient, world, admin, db: Session):
    response = client.post(f"{URL}/{world['locked']}/reset-password", headers=admin)

    assert response.status_code == 200, response.text
    password = response.json()["temporary_password"]
    assert login(client, "khoa@company.vn", PASSWORD).status_code != 200
    logged = login(client, "khoa@company.vn", password)
    assert logged.status_code == 200
    assert logged.json()["user"]["must_change_password"] is True
    audit = db.query(AuditLog).filter_by(action="user.password_reset").one()
    assert password not in (audit.after_data or "")


def test_unlock_clears_lockout_without_changing_password(client: TestClient, world, admin):
    assert login(client, "khoa@company.vn", PASSWORD).status_code != 200

    unlocked = client.post(f"{URL}/{world['locked']}/unlock", headers=admin)

    assert unlocked.status_code == 200
    assert login(client, "khoa@company.vn", PASSWORD).status_code == 200
