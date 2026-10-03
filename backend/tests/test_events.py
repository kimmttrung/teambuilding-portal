"""Kiểm thử vòng đời kỳ Team Building và cấu hình."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, Event, Registration, Shift, TripLeg
from app.models.enums import EventStatus, FlightDirection, UserRole


@pytest.fixture
def event(db: Session) -> Event:
    """Kỳ đang mở đăng ký, đã có master data tối thiểu."""
    row = Event(
        code="TB2026",
        name="Team Building 2026",
        start_date="2026-10-15",
        end_date="2026-10-17",
        status=EventStatus.REGISTRATION_OPEN,
        terms_version="v1",
        terms_content="## Quy định\nHuỷ sau hạn phải chịu phí.",
        is_active=True,
    )
    db.add(row)
    db.flush()
    db.add(Shift(event_id=row.id, code="CA1", name="Ca 1"))
    db.add(
        TripLeg(
            event_id=row.id,
            code="CITY_TO_AIRPORT",
            name="HN → Sân bay",
            direction=FlightDirection.OUTBOUND,
        )
    )
    db.commit()
    db.refresh(row)
    return row


@pytest.fixture
def admin(make_user):
    return make_user(email="btc@company.vn", password="Admin12345", role=UserRole.ADMIN)


@pytest.fixture
def admin_headers(admin, auth_headers):
    return auth_headers("btc@company.vn", "Admin12345")


def set_status(db: Session, event: Event, status: EventStatus) -> None:
    event.status = status
    db.commit()


# --- Đọc ---


def test_active_event_exposes_derived_flags(client: TestClient, event, make_user, auth_headers):
    make_user(email="nv@company.vn", password="MatKhau123")
    response = client.get("/api/v1/events/active", headers=auth_headers("nv@company.vn"))

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "TB2026"
    assert body["can_register"] is True
    assert body["is_published"] is False
    assert body["status_label"] == "Đang mở đăng ký"
    # Nội dung quy định lấy riêng ở /terms để response này nhẹ.
    assert "terms_content" not in body


def test_active_event_requires_login(client: TestClient, event):
    assert client.get("/api/v1/events/active").status_code == 401


def test_terms_returns_markdown(client: TestClient, event, make_user, auth_headers):
    make_user(email="nv@company.vn", password="MatKhau123")
    response = client.get(
        f"/api/v1/events/{event.id}/terms", headers=auth_headers("nv@company.vn")
    )
    assert response.status_code == 200
    assert "Huỷ sau hạn" in response.json()["content"]


def test_employee_cannot_list_all_events(client: TestClient, event, make_user, auth_headers):
    make_user(email="nv@company.vn", password="MatKhau123")
    response = client.get("/api/v1/events", headers=auth_headers("nv@company.vn"))
    assert response.status_code == 403


# --- Chuyển trạng thái ---


def test_valid_transition_is_accepted(client: TestClient, event, admin_headers):
    response = client.post(
        f"/api/v1/events/{event.id}/status",
        headers=admin_headers,
        json={"status": "registration_closed"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "registration_closed"
    assert response.json()["can_register"] is False


def test_cannot_skip_states(client: TestClient, event, admin_headers):
    """Không cho nhảy thẳng từ đang mở đăng ký sang đã công bố."""
    response = client.post(
        f"/api/v1/events/{event.id}/status",
        headers=admin_headers,
        json={"status": "information_published"},
    )
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "INVALID_STATUS_TRANSITION"
    assert "registration_closed" in error["details"]["allowed"]


def test_same_status_is_rejected(client: TestClient, event, admin_headers):
    response = client.post(
        f"/api/v1/events/{event.id}/status",
        headers=admin_headers,
        json={"status": "registration_open"},
    )
    assert response.json()["error"]["code"] == "STATUS_UNCHANGED"


def test_backward_transition_reason_is_optional(client: TestClient, event, admin_headers, db):
    """Lùi trạng thái không bắt nhập lý do (BTC cần thao tác nhanh); có lý do thì vào audit."""
    set_status(db, event, EventStatus.INFORMATION_PUBLISHED)

    without_reason = client.post(
        f"/api/v1/events/{event.id}/status",
        headers=admin_headers,
        json={"status": "allocation_processing"},
    )
    assert without_reason.status_code == 200, without_reason.text

    db.refresh(event)  # API đổi trạng thái ở session khác
    set_status(db, event, EventStatus.INFORMATION_PUBLISHED)
    with_reason = client.post(
        f"/api/v1/events/{event.id}/status",
        headers=admin_headers,
        json={"status": "allocation_processing", "reason": "  Hãng bay đổi giờ chuyến VN1234 "},
    )
    assert with_reason.status_code == 200
    audit = db.scalars(
        select(AuditLog)
        .where(AuditLog.action == "event.status_changed")
        .order_by(AuditLog.id.desc())
    ).first()
    assert audit.reason == "Hãng bay đổi giờ chuyến VN1234"


def test_cannot_open_registration_without_master_data(
    client: TestClient, admin_headers, db: Session
):
    """Mở đăng ký khi chưa có ca/chặng thì form đăng ký rỗng — chặn từ đầu."""
    bare = Event(
        code="TB2027",
        name="Kỳ chưa cấu hình",
        start_date="2027-10-15",
        end_date="2027-10-17",
        status=EventStatus.DRAFT,
        is_active=False,
    )
    db.add(bare)
    db.commit()

    response = client.post(
        f"/api/v1/events/{bare.id}/status",
        headers=admin_headers,
        json={"status": "registration_open"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "MASTER_DATA_MISSING"
    assert "ca bay (shifts)" in response.json()["error"]["details"]["missing"]


def test_cannot_start_allocation_without_participants(
    client: TestClient, event, admin_headers, db
):
    set_status(db, event, EventStatus.REGISTRATION_CLOSED)
    response = client.post(
        f"/api/v1/events/{event.id}/status",
        headers=admin_headers,
        json={"status": "allocation_processing"},
    )
    assert response.json()["error"]["code"] == "NO_PARTICIPANTS"


def test_allocation_allowed_with_participants(
    client: TestClient, event, admin_headers, db, make_user
):
    user = make_user(email="nv@company.vn", password="MatKhau123")
    db.add(Registration(event_id=event.id, user_id=user.id, is_participating=True))
    set_status(db, event, EventStatus.REGISTRATION_CLOSED)

    response = client.post(
        f"/api/v1/events/{event.id}/status",
        headers=admin_headers,
        json={"status": "allocation_processing"},
    )
    assert response.status_code == 200


def test_status_change_is_audited(client: TestClient, event, admin_headers, db: Session, admin):
    client.post(
        f"/api/v1/events/{event.id}/status",
        headers=admin_headers,
        json={"status": "registration_closed"},
    )
    entry = db.query(AuditLog).filter(AuditLog.action == "event.status_changed").one()
    assert entry.actor_id == admin.id
    assert "registration_open" in entry.before_data
    assert "registration_closed" in entry.after_data


def test_employee_cannot_change_status(client: TestClient, event, make_user, auth_headers):
    make_user(email="nv@company.vn", password="MatKhau123")
    response = client.post(
        f"/api/v1/events/{event.id}/status",
        headers=auth_headers("nv@company.vn"),
        json={"status": "registration_closed"},
    )
    assert response.status_code == 403


# --- Tạo & sửa ---


def test_create_event_seeds_default_settings(client: TestClient, admin_headers):
    response = client.post(
        "/api/v1/events",
        headers=admin_headers,
        json={
            "code": "TB2027",
            "name": "Team Building 2027",
            "start_date": "2027-09-10",
            "end_date": "2027-09-12",
        },
    )
    assert response.status_code == 201
    event_id = response.json()["id"]
    assert response.json()["status"] == "draft"

    settings = client.get(f"/api/v1/events/{event_id}/settings", headers=admin_headers).json()
    assert settings["allocation.team_weight"]["value"] == 10


def test_duplicate_event_code_is_rejected(client: TestClient, event, admin_headers):
    response = client.post(
        "/api/v1/events",
        headers=admin_headers,
        json={
            "code": "TB2026",
            "name": "Trùng mã",
            "start_date": "2026-11-01",
            "end_date": "2026-11-03",
        },
    )
    assert response.json()["error"]["code"] == "EVENT_CODE_DUPLICATED"


def test_end_date_before_start_date_is_rejected(client: TestClient, admin_headers):
    response = client.post(
        "/api/v1/events",
        headers=admin_headers,
        json={
            "code": "TB2028",
            "name": "Ngày sai",
            "start_date": "2028-10-17",
            "end_date": "2028-10-15",
        },
    )
    assert response.json()["error"]["code"] == "INVALID_DATE_RANGE"


def test_editing_terms_after_consent_requires_new_version(
    client: TestClient, event, admin_headers, db, make_user
):
    """Đã có người đồng ý v1 mà sửa nội dung v1 thì bản đồng ý cũ không còn đúng văn bản."""
    user = make_user(email="nv@company.vn", password="MatKhau123")
    db.add(
        Registration(
            event_id=event.id,
            user_id=user.id,
            is_participating=True,
            consent_version="v1",
            consented_at="2026-09-10T00:00:00+00:00",
        )
    )
    db.commit()

    blocked = client.patch(
        f"/api/v1/events/{event.id}",
        headers=admin_headers,
        json={"terms_content": "Nội dung mới", "terms_version": "v1"},
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "TERMS_VERSION_REQUIRED"

    allowed = client.patch(
        f"/api/v1/events/{event.id}",
        headers=admin_headers,
        json={"terms_content": "Nội dung mới", "terms_version": "v2"},
    )
    assert allowed.status_code == 200


def test_previous_terms_stay_readable_after_a_new_version(
    client: TestClient, event, admin_headers, db, make_user
):
    """Người đã đồng ý v1 phải còn văn bản v1 để đối chiếu — trước đây v2 ghi đè mất luôn."""
    user = make_user(email="nv@company.vn", password="MatKhau123")
    db.add(
        Registration(
            event_id=event.id, user_id=user.id, is_participating=True,
            consent_version="v1", consented_at="2026-09-10T00:00:00+00:00",
        )
    )
    db.commit()
    url = f"/api/v1/events/{event.id}"
    original = event.terms_content

    assert client.get(f"{url}/terms/versions", headers=admin_headers).json() == []

    client.patch(url, headers=admin_headers, json={"terms_content": "Bản hai", "terms_version": "v2"})
    client.patch(url, headers=admin_headers, json={"terms_content": "Bản ba", "terms_version": "v3"})

    versions = client.get(f"{url}/terms/versions", headers=admin_headers).json()
    assert [(row["version"], row["content"], row["consent_count"]) for row in versions] == [
        ("v2", "Bản hai", 0),
        ("v1", original, 1),
    ]
    assert client.get(f"{url}/terms", headers=admin_headers).json()["content"] == "Bản ba"

    # Dùng lại số phiên bản đã có người ký là chữ ký cũ trỏ sang văn bản khác.
    reused = client.patch(url, headers=admin_headers, json={"terms_content": "x", "terms_version": "v1"})
    assert reused.status_code == 409
    assert reused.json()["error"]["code"] == "TERMS_VERSION_REUSED"

    # Bản lưu trữ không lọt vào danh sách tài liệu của Tibi.
    assert client.get("/api/v1/admin/documents", headers=admin_headers).json() == []


def test_employees_cannot_read_terms_history(client: TestClient, event, make_user, auth_headers):
    make_user(email="nv@company.vn", password="MatKhau123")
    response = client.get(
        f"/api/v1/events/{event.id}/terms/versions", headers=auth_headers("nv@company.vn")
    )
    assert response.status_code == 403


def test_activate_event_deactivates_previous(client: TestClient, event, admin_headers, db):
    other = Event(
        code="TB2027",
        name="Kỳ sau",
        start_date="2027-10-15",
        end_date="2027-10-17",
        status=EventStatus.DRAFT,
        is_active=False,
    )
    db.add(other)
    db.commit()

    client.post(f"/api/v1/events/{other.id}/activate", headers=admin_headers)

    db.refresh(event)
    db.refresh(other)
    assert other.is_active is True
    assert event.is_active is False


# --- Cấu hình ---


def test_update_settings_changes_algorithm_weights(client: TestClient, event, admin_headers, db):
    event.settings = {"allocation.team_weight": 10}
    db.commit()

    response = client.put(
        f"/api/v1/events/{event.id}/settings",
        headers=admin_headers,
        json={"values": {"allocation.team_weight": 25}},
    )
    assert response.status_code == 200
    assert response.json()["allocation.team_weight"]["value"] == 25

    # Đọc lại từ DB: giá trị phải nằm trong `events.settings`.
    db.refresh(event)
    assert event.settings["allocation.team_weight"] == 25
    reloaded = client.get(f"/api/v1/events/{event.id}/settings", headers=admin_headers).json()
    assert reloaded["allocation.team_weight"]["value"] == 25


def test_settings_fill_in_defaults_for_keys_not_yet_in_the_table(
    client: TestClient, event, admin_headers, db
):
    """Kỳ tạo trước khi một khoá được thêm vào code sẽ thiếu khoá đó trong `events.settings`. Không
    trả về thì màn hình cấu hình hiện ô trống rồi lưu đè thành 0 — đổi lặng lẽ cách thuật toán xếp
    phòng chạy."""
    from app.models.event import DEFAULT_EVENT_SETTINGS

    event.settings = {"allocation.team_weight": 99}
    db.commit()

    settings = client.get(f"/api/v1/events/{event.id}/settings", headers=admin_headers).json()
    assert set(settings) == set(DEFAULT_EVENT_SETTINGS), "phải trả đủ mọi khoá cấu hình"
    assert settings["allocation.team_weight"]["value"] == 99, "giá trị đã lưu vẫn thắng mặc định"
    assert settings["rooms.team_weight"]["value"] == 10, "khoá chưa có dòng lấy giá trị mặc định"
    assert settings["rooms.team_weight"]["description"]


def test_unknown_setting_key_is_rejected(client: TestClient, event, admin_headers):
    """Gõ sai tên khoá mà vẫn lưu thì cấu hình không có tác dụng, rất khó phát hiện."""
    response = client.put(
        f"/api/v1/events/{event.id}/settings",
        headers=admin_headers,
        json={"values": {"allocation.team_weigth": 25}},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "UNKNOWN_SETTING_KEY"


def test_setting_value_must_be_a_whole_number(client: TestClient, event, admin_headers, db):
    """Nơi đọc cấu hình lặng lẽ lùi về mặc định khi giá trị hỏng — lưu được là BTC tưởng đã đổi."""
    for bad in ("abc", -1, 1.5, None, True):
        response = client.put(
            f"/api/v1/events/{event.id}/settings",
            headers=admin_headers,
            json={"values": {"gala.hold_seconds": bad}},
        )
        assert response.status_code == 422, bad
        assert response.json()["error"]["code"] == "INVALID_SETTING_VALUE"
    db.refresh(event)
    assert "gala.hold_seconds" not in (event.settings or {})


def test_new_event_starts_with_every_default_setting(client: TestClient, admin_headers, db):
    from app.models.event import DEFAULT_EVENT_SETTINGS

    created = client.post(
        "/api/v1/events",
        headers=admin_headers,
        json={"code": "TB2027", "name": "Kỳ mùa sau", "start_date": "2027-04-16", "end_date": "2027-04-18"},
    )
    assert created.status_code == 201, created.text
    stored = db.get(Event, created.json()["id"]).settings
    assert set(stored) == set(DEFAULT_EVENT_SETTINGS)
    assert stored["gala.turn_seconds"] == 300, "lưu dạng số, không phải chuỗi JSON"


# --- Khoá cấu hình khi chương trình đang diễn ra ---


@pytest.mark.parametrize("status", [EventStatus.EVENT_STARTED, EventStatus.COMPLETED])
def test_config_is_locked_once_the_event_has_started(
    client: TestClient, event, admin_headers, db, status
):
    set_status(db, event, status)

    info = client.patch(
        f"/api/v1/events/{event.id}", headers=admin_headers, json={"name": "Tên mới giữa chừng"}
    )
    assert info.status_code == 409
    assert info.json()["error"]["code"] == "EVENT_CONFIG_LOCKED"

    settings = client.put(
        f"/api/v1/events/{event.id}/settings",
        headers=admin_headers,
        json={"values": {"gala.hold_seconds": 60}},
    )
    assert settings.status_code == 409
    assert settings.json()["error"]["code"] == "EVENT_CONFIG_LOCKED"

    db.refresh(event)
    assert event.name == "Team Building 2026"
    assert client.get("/api/v1/events/active", headers=admin_headers).json()["config_locked"] is True


@pytest.mark.parametrize(
    "status", [EventStatus.ALLOCATION_PROCESSING, EventStatus.INFORMATION_PUBLISHED]
)
def test_config_stays_editable_until_the_event_starts(
    client: TestClient, event, admin_headers, db, status
):
    set_status(db, event, status)

    info = client.patch(
        f"/api/v1/events/{event.id}", headers=admin_headers, json={"destination": "Đà Nẵng"}
    )
    assert info.status_code == 200, info.text
    assert info.json()["config_locked"] is False
    assert client.put(
        f"/api/v1/events/{event.id}/settings",
        headers=admin_headers,
        json={"values": {"gala.hold_seconds": 60}},
    ).status_code == 200


def test_stepping_back_from_started_unlocks_config(client: TestClient, event, admin_headers, db):
    set_status(db, event, EventStatus.EVENT_STARTED)
    back = client.post(
        f"/api/v1/events/{event.id}/status",
        headers=admin_headers,
        json={"status": "information_published"},
    )
    assert back.status_code == 200, back.text
    assert client.patch(
        f"/api/v1/events/{event.id}", headers=admin_headers, json={"destination": "Đà Nẵng"}
    ).status_code == 200


def test_overview_reports_next_possible_statuses(client: TestClient, event, admin_headers):
    response = client.get(f"/api/v1/events/{event.id}/overview", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["can_register"] is True
    assert sorted(body["allowed_next_statuses"]) == ["draft", "registration_closed"]
