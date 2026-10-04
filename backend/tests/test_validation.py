"""Dữ liệu sai phải bị từ chối — bộ ca tìm ra ở đợt kiểm thử F11 (4/10).

Mỗi nhóm ứng với một mục trong thẻ Trello F11. Trước bản sửa, mọi ca dưới đây trả 2xx (hoặc 500).
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Event, Shift, TripLeg, User
from app.models.auth import RefreshToken
from app.models.enums import EventStatus, FlightDirection, UserRole
from app.models.org import Team

API = "/api/v1"
ADULT = f"{date.today().year - 30}-05-05"
PROFILE = {
    "gender": "male", "date_of_birth": ADULT, "phone": "0912345678",
    "id_card_type": "cccd", "id_card_number": "001095012345", "id_card_issue_date": "2021-01-01",
}


@pytest.fixture
def world(db: Session, make_user) -> dict:
    event = Event(
        code="TB2026", name="Team Building 2026", start_date="2026-10-15", end_date="2026-10-17",
        status=EventStatus.REGISTRATION_OPEN, terms_version="v1", terms_content="# Quy định", is_active=True,
    )
    other = Event(
        code="TB2027", name="Team Building 2027", start_date="2027-04-16", end_date="2027-04-18",
        status=EventStatus.REGISTRATION_OPEN, terms_version="v1", is_active=False,
    )
    draft = Event(
        code="TB2028", name="Kỳ nháp", start_date="2028-04-16", end_date="2028-04-18",
        status=EventStatus.DRAFT, terms_version="v1", terms_content="# Bí mật", is_active=False,
    )
    db.add_all([event, other, draft])
    db.flush()
    shift = Shift(event_id=event.id, code="CA1", name="Ca 1")
    leg = TripLeg(event_id=event.id, code="CITY_TO_AIRPORT", name="HN → Sân bay", direction=FlightDirection.OUTBOUND)
    other_leg = TripLeg(event_id=other.id, code="CITY_TO_AIRPORT", name="ĐN → Sân bay", direction=FlightDirection.OUTBOUND)
    db.add_all([shift, leg, other_leg])
    make_user(email="btc@company.vn", role=UserRole.ADMIN, full_name="Ban Tổ Chức")
    make_user(email="sa@company.vn", role=UserRole.SUPER_ADMIN, full_name="Quản Trị")
    employee = make_user(email="nv@company.vn", full_name="Nguyễn Văn A", **PROFILE)
    db.commit()
    return {
        "event": event.id, "other": other.id, "draft": draft.id, "shift": shift.id,
        "leg": leg.id, "other_leg": other_leg.id, "employee": employee.id,
    }


@pytest.fixture
def admin(world, auth_headers):
    return auth_headers("btc@company.vn")


@pytest.fixture
def employee(world, auth_headers):
    return auth_headers("nv@company.vn")


def code(response) -> str:
    return response.json()["error"]["code"]


# --- A1: BTC tạo / sửa CBNV ---


@pytest.mark.parametrize(
    "extra",
    [
        {"phone": "khong-phai-so"},
        {"phone": "09123"},
        {"join_date": "2999-01-01"},
        {"full_name": "     "},
    ],
)
def test_admin_cannot_create_user_with_bad_data(client: TestClient, admin, extra):
    payload = {"employee_code": "AUD001", "full_name": "Người Thử", "email": "audit@company.vn", **extra}
    assert client.post(f"{API}/admin/users", headers=admin, json=payload).status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {"phone": "abc"},
        {"emergency_contact_phone": "xyz"},
        {"id_card_type": "cccd", "id_card_number": "khong-phai-so"},
        {"id_card_number": "abc!!!"},  # không gửi loại giấy tờ: phải so với loại đang lưu (cccd)
        {"date_of_birth": "2999-01-01"},
        {"date_of_birth": "1800-01-01"},
        {"id_card_issue_date": "2999-01-01"},
        {"id_card_issue_date": "1980-01-01"},  # trước ngày sinh đang lưu
    ],
)
def test_admin_cannot_save_bad_profile_data(client: TestClient, db: Session, admin, world, body):
    response = client.patch(f"{API}/admin/users/{world['employee']}", headers=admin, json=body)
    assert response.status_code == 422, response.text
    stored = db.get(User, world["employee"])
    assert (stored.phone, stored.id_card_number, stored.date_of_birth) == (
        PROFILE["phone"], PROFILE["id_card_number"], PROFILE["date_of_birth"],
    )


# --- A3, A4, A5: hồ sơ cá nhân ---


@pytest.mark.parametrize(
    "body",
    [
        {"id_card_number": "abc!!!"},
        {"date_of_birth": "1800-01-01"},
        {"date_of_birth": f"{date.today().year - 10}-01-01"},
        {"id_card_issue_date": "1980-01-01"},
        {"phone": "abcdefghij"},
        {"avatar_url": "javascript:alert(1)"},
        {"avatar_url": "https://evil.example/track.png"},
        {"avatar_url": "/uploads/avatar_1_abc.png"},
    ],
)
def test_employee_cannot_save_bad_profile_data(client: TestClient, db: Session, employee, world, body):
    response = client.patch(f"{API}/auth/me", headers=employee, json=body)
    assert response.status_code == 422, response.text
    stored = db.get(User, world["employee"])
    assert stored.id_card_number == PROFILE["id_card_number"]
    assert stored.avatar_url is None


def test_passport_number_is_accepted_when_type_says_passport(client: TestClient, employee):
    response = client.patch(
        f"{API}/auth/me", headers=employee, json={"id_card_type": "passport", "id_card_number": "C1234567"}
    )
    assert response.status_code == 200, response.text


def test_uploading_an_avatar_never_deletes_someone_elses_file(client: TestClient, db: Session, employee, world, tmp_path):
    """`avatar_url` từng nhận chuỗi tự do: trỏ sang ảnh người khác rồi tải ảnh mới là xoá ảnh của họ."""
    victim = tmp_path / "uploads" / "avatar_999_victim.png"
    victim.write_bytes(b"anh cua nguoi khac")
    db.get(User, world["employee"]).avatar_url = "/uploads/avatar_999_victim.png"
    db.commit()

    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    uploaded = client.post(f"{API}/auth/me/avatar", headers=employee, files={"file": ("a.png", png, "image/png")})
    assert uploaded.status_code == 201, uploaded.text
    assert victim.exists(), "không được xoá file không phải của mình"


# --- A6, B10: master data theo kỳ ---


def test_pickup_point_needs_a_leg_of_the_selected_event(client: TestClient, admin, world):
    url = f"{API}/master-data/pickup-points"
    missing = client.post(url, headers=admin, json={"name": "Điểm A", "trip_leg_id": 99999})
    assert (missing.status_code, code(missing)) == (404, "TRIP_LEG_NOT_FOUND")  # từng là lỗi 500
    foreign = client.post(url, headers=admin, json={"name": "Điểm A", "trip_leg_id": world["other_leg"]})
    assert (foreign.status_code, code(foreign)) == (404, "TRIP_LEG_NOT_FOUND")
    assert client.post(url, headers=admin, json={"name": "Điểm A", "trip_leg_id": world["leg"]}).status_code == 201


def test_cannot_edit_another_events_master_data_by_id(client: TestClient, db: Session, admin, world):
    url = f"{API}/master-data/trip-legs/{world['other_leg']}"
    assert client.patch(url, headers=admin, json={"name": "Đổi tên"}).status_code == 404
    assert client.delete(url, headers=admin).status_code == 404
    assert db.get(TripLeg, world["other_leg"]).name == "ĐN → Sân bay"
    # Chọn đúng kỳ thì sửa được.
    scoped = {**admin, "X-Event-Id": str(world["other"])}
    assert client.patch(url, headers=scoped, json={"name": "Đổi tên"}).status_code == 200


# --- B1: tên toàn dấu cách ---


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/events", {"code": "TBX1", "name": "      ", "start_date": "2027-03-01", "end_date": "2027-03-02"}),
        ("/master-data/shifts", {"code": "CAX1", "name": "   "}),
        ("/master-data/teams", {"code": "TMX1", "name": "   "}),
        ("/master-data/pickup-points", {"name": "   "}),
        ("/hotels", {"name": "   "}),
        ("/itinerary", {"day_date": "2026-10-15", "title": "    "}),
        ("/admin/announcements", {"title": "   ", "content": "x"}),
        ("/admin/documents", {"doc_type": "faq", "title": "   ", "content": "x"}),
        ("/admin/documents", {"doc_type": "faq", "title": "Tài liệu", "content": "    "}),
    ],
)
def test_blank_names_are_rejected(client: TestClient, admin, path, body):
    assert client.post(f"{API}{path}", headers=admin, json=body).status_code == 422


# --- B2, B3: tạo kỳ ---


@pytest.mark.parametrize(
    "extra",
    [
        {"start_date": "2027-02-31", "end_date": "2027-03-02"},
        {"registration_opens_at": "hom nay"},
        {"registration_opens_at": "2027-02-10T00:00:00"},  # thiếu múi giờ
        {"registration_opens_at": "2027-02-10T00:00:00+00:00", "registration_closes_at": "2027-02-01T00:00:00+00:00"},
        {"registration_closes_at": "2027-04-01T00:00:00+00:00"},  # sau ngày bắt đầu kỳ
        {"banner_url": "javascript:alert(1)"},
    ],
)
def test_event_rejects_bad_dates_and_links(client: TestClient, admin, extra):
    payload = {"code": "TBX2", "name": "Kỳ thử", "start_date": "2027-03-01", "end_date": "2027-03-02", **extra}
    assert client.post(f"{API}/events", headers=admin, json=payload).status_code == 422


def test_editing_one_registration_deadline_is_checked_against_the_stored_one(client: TestClient, db: Session, admin, world):
    event = db.get(Event, world["event"])
    event.registration_opens_at = "2026-09-10T00:00:00+00:00"
    db.commit()
    response = client.patch(
        f"{API}/events/{world['event']}", headers=admin, json={"registration_closes_at": "2026-09-01T00:00:00+00:00"}
    )
    assert (response.status_code, code(response)) == (422, "INVALID_REGISTRATION_WINDOW")


# --- B3, B4, B6: link, ca, chặng, số điện thoại ---


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/master-data/shifts", {"code": "CAX1", "name": "Ca thử", "earliest_departure": "25:99"}),
        ("/master-data/shifts", {"code": "CAX2", "name": "Ca thử", "display_order": -5}),
        ("/master-data/trip-legs", {"code": "LEGX1", "name": "Chặng thử", "direction": "outbound", "leg_date": "2026-13-45"}),
        ("/master-data/pickup-points", {"name": "Điểm thử", "map_url": "javascript:alert(1)"}),
        ("/hotels", {"name": "KS thử", "map_url": "javascript:alert(1)"}),
        ("/hotels", {"name": "KS thử", "phone": "goi-le-tan"}),
    ],
)
def test_master_data_rejects_bad_values(client: TestClient, admin, path, body):
    assert client.post(f"{API}{path}", headers=admin, json=body).status_code == 422


def test_hotel_accepts_a_landline_and_bus_rejects_a_text_driver_phone(client: TestClient, admin, world):
    hotel = client.post(f"{API}/hotels", headers=admin, json={"name": "KS Biển", "phone": "0297 3999 888"})
    assert hotel.status_code == 201, hotel.text
    bus = {"trip_leg_id": world["leg"], "bus_code": "XE-01", "capacity": 45}
    assert client.post(f"{API}/buses", headers=admin, json={**bus, "driver_phone": "khong co"}).status_code == 422
    assert client.post(f"{API}/buses", headers=admin, json={**bus, "driver_phone": "0912 345 678"}).status_code == 201


# --- B5: chuyến bay ---

FLIGHT = {
    "flight_code": "VN9001", "direction": "outbound", "departure_airport": "HAN", "arrival_airport": "PQC",
    "departure_time": "2026-10-15T01:00:00+00:00", "arrival_time": "2026-10-15T03:00:00+00:00", "capacity": 50,
}


@pytest.mark.parametrize(
    ("extra", "expected"),
    [
        ({"departure_time": "2026-10-15T01:00:00"}, "VALIDATION_ERROR"),  # thiếu múi giờ
        ({"arrival_time": "2026-10-18T03:00:00+00:00"}, "VALIDATION_ERROR"),  # bay 3 ngày
        ({"departure_time": "1990-01-01T01:00:00+00:00", "arrival_time": "1990-01-01T03:00:00+00:00"}, "FLIGHT_OUTSIDE_EVENT"),
    ],
)
def test_flight_times_must_make_sense(client: TestClient, admin, extra, expected):
    response = client.post(f"{API}/flights", headers=admin, json={**FLIGHT, **extra})
    assert (response.status_code, code(response)) == (422, expected)


def test_flight_may_leave_the_evening_before_the_event(client: TestClient, admin):
    night_before = {"departure_time": "2026-10-14T21:00:00+07:00", "arrival_time": "2026-10-14T23:10:00+07:00"}
    assert client.post(f"{API}/flights", headers=admin, json={**FLIGHT, **night_before}).status_code == 201


# --- B7: cấu hình kỳ ---


@pytest.mark.parametrize(
    "values",
    [
        {"gala.hold_seconds": 0},
        {"gala.turn_seconds": 1},
        {"gala.turn_seconds": 10_000_000_000},
        {"allocation.shift_split_percent": 500},
        {"allocation.min_chunk_size": 0},
        {"allocation.max_split_per_team": 0},
        {"transport.from_airport_min_wait_minutes": 60, "transport.from_airport_max_wait_minutes": 10},
    ],
)
def test_settings_outside_their_range_are_rejected(client: TestClient, db: Session, admin, world, values):
    response = client.put(f"{API}/events/{world['event']}/settings", headers=admin, json={"values": values})
    assert (response.status_code, code(response)) == (422, "INVALID_SETTING_VALUE")
    assert not (db.get(Event, world["event"]).settings or {})


def test_pickup_wait_of_zero_means_unlimited(client: TestClient, admin, world):
    values = {"transport.from_airport_min_wait_minutes": 30, "transport.from_airport_max_wait_minutes": 0}
    assert client.put(f"{API}/events/{world['event']}/settings", headers=admin, json={"values": values}).status_code == 200


# --- B9: hạ vai trò gỡ chức Trưởng nhóm ---


def test_demoting_a_team_leader_also_removes_the_team_leadership(client: TestClient, db: Session, world, make_user, auth_headers):
    leader = make_user(email="truong@company.vn", role=UserRole.TEAM_LEADER, full_name="Trưởng Nhóm")
    team = Team(code="KD", name="Kinh doanh", leader_user_id=leader.id)
    db.add(team)
    db.commit()
    team_id = team.id

    response = client.patch(
        f"{API}/admin/users/{leader.id}/role", headers=auth_headers("sa@company.vn"), json={"role": "employee"}
    )
    assert response.status_code == 200, response.text
    db.expire_all()
    assert db.get(Team, team_id).leader_user_id is None, "còn chức Trưởng nhóm là vẫn xếp được ghế Gala"


# --- B11: quy định của kỳ nháp ---


def test_draft_event_terms_are_hidden_from_employees(client: TestClient, admin, employee, world):
    url = f"{API}/events/{world['draft']}/terms"
    hidden = client.get(url, headers=employee)
    assert (hidden.status_code, code(hidden)) == (404, "EVENT_NOT_FOUND")
    assert client.get(url, headers=admin).json()["content"] == "# Bí mật"
    assert client.get(f"{API}/events/{world['event']}/terms", headers=employee).status_code == 200


# --- C1, C2: phiên đăng nhập ---


def login(client: TestClient, email="nv@company.vn", password="MatKhau123") -> dict:
    response = client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_access_token_dies_at_logout(client: TestClient, world):
    session = login(client)
    headers = bearer(session["access_token"])
    assert client.get(f"{API}/auth/me", headers=headers).status_code == 200

    client.post(f"{API}/auth/logout", headers=headers, json={"refresh_token": session["refresh_token"]})

    after = client.get(f"{API}/auth/me", headers=headers)
    assert (after.status_code, code(after)) == (401, "SESSION_REVOKED")


def test_logging_out_one_device_keeps_the_other(client: TestClient, world):
    phone, laptop = login(client), login(client)
    client.post(f"{API}/auth/logout", headers=bearer(phone["access_token"]), json={"refresh_token": phone["refresh_token"]})
    assert client.get(f"{API}/auth/me", headers=bearer(phone["access_token"])).status_code == 401
    assert client.get(f"{API}/auth/me", headers=bearer(laptop["access_token"])).status_code == 200


def test_session_survives_refresh_and_old_access_token_stays_tied_to_it(client: TestClient, world):
    session = login(client)
    renewed = client.post(f"{API}/auth/refresh", json={"refresh_token": session["refresh_token"]}).json()
    # Cùng một phiên: access token cũ còn hạn vẫn dùng được cho tới khi phiên bị thu hồi.
    assert client.get(f"{API}/auth/me", headers=bearer(session["access_token"])).status_code == 200
    client.post(f"{API}/auth/logout", headers=bearer(renewed["access_token"]), json={"refresh_token": renewed["refresh_token"]})
    assert client.get(f"{API}/auth/me", headers=bearer(session["access_token"])).status_code == 401
    assert client.get(f"{API}/auth/me", headers=bearer(renewed["access_token"])).status_code == 401


def test_reusing_a_rotated_refresh_token_kills_the_whole_session(client: TestClient, db: Session, world):
    session = login(client)
    renewed = client.post(f"{API}/auth/refresh", json={"refresh_token": session["refresh_token"]}).json()

    # Trong 10 giây đầu: coi như hai tab refresh cùng lúc — chỉ từ chối, phiên vẫn sống.
    early = client.post(f"{API}/auth/refresh", json={"refresh_token": session["refresh_token"]})
    assert (early.status_code, code(early)) == (401, "SESSION_REVOKED")
    assert client.get(f"{API}/auth/me", headers=bearer(renewed["access_token"])).status_code == 200

    # Quá 10 giây: có người giữ bản sao token cũ → thu hồi cả phiên.
    rotated = db.query(RefreshToken).filter(RefreshToken.revoked_reason == "rotated").one()
    rotated.revoked_at = "2026-01-01T00:00:00+00:00"
    db.commit()
    late = client.post(f"{API}/auth/refresh", json={"refresh_token": session["refresh_token"]})
    assert late.status_code == 401
    assert client.get(f"{API}/auth/me", headers=bearer(renewed["access_token"])).status_code == 401
    assert client.post(f"{API}/auth/refresh", json={"refresh_token": renewed["refresh_token"]}).status_code == 401


def test_admin_password_reset_ends_live_sessions(client: TestClient, admin, world):
    session = login(client)
    assert client.post(f"{API}/admin/users/{world['employee']}/reset-password", headers=admin).status_code == 200
    assert client.get(f"{API}/auth/me", headers=bearer(session["access_token"])).status_code == 401


# --- C3: /health ---


def test_health_does_not_expose_the_database_path(client: TestClient):
    body = client.get(f"{API}/health").json()
    assert body["status"] == "ok"
    assert body["database"] == {"connected": True, "foreign_keys": True}
