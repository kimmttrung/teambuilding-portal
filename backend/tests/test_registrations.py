"""Kiểm thử Module 1 – Đăng ký tham gia Team Building."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    Consent,
    Department,
    Event,
    PickupPoint,
    Registration,
    RegistrationBusNeed,
    Shift,
    Team,
    TripLeg,
    WorkLocation,
)
from app.models.enums import EventStatus, FlightDirection, Gender, UserRole


@pytest.fixture
def setup(db: Session) -> dict:
    """Kỳ đang mở đăng ký với 2 ca, 2 chặng, 1 điểm đón."""
    event = Event(
        code="TB2026",
        name="Team Building 2026",
        start_date="2026-10-15",
        end_date="2026-10-17",
        status=EventStatus.REGISTRATION_OPEN,
        registration_closes_at="2026-12-25T17:00:00+00:00",  # còn hạn
        terms_version="v1",
        terms_content="Quy định...",
        is_active=True,
    )
    location = WorkLocation(code="HN", name="Hà Nội", airport_code="HAN")
    department = Department(code="CN", name="Khối Công nghệ")
    db.add_all([event, location, department])
    db.flush()

    team = Team(code="IT-HN", name="Công nghệ Hà Nội", department_id=department.id)
    shift1 = Shift(event_id=event.id, code="CA1", name="Ca 1", display_order=1)
    shift2 = Shift(event_id=event.id, code="CA2", name="Ca 2", display_order=2)
    leg1 = TripLeg(
        event_id=event.id,
        code="CITY_TO_AIRPORT",
        name="HN → Sân bay",
        direction=FlightDirection.OUTBOUND,
        display_order=1,
    )
    leg2 = TripLeg(
        event_id=event.id,
        code="AIRPORT_TO_CITY",
        name="Sân bay → HN",
        direction=FlightDirection.RETURN,
        display_order=2,
    )
    db.add_all([team, shift1, shift2, leg1, leg2])
    db.flush()

    pickup = PickupPoint(
        event_id=event.id, trip_leg_id=leg1.id, name="Toà nhà Keangnam"
    )
    db.add(pickup)
    db.commit()

    return {
        "event": event,
        "team": team,
        "location": location,
        "shift1": shift1,
        "shift2": shift2,
        "leg1": leg1,
        "leg2": leg2,
        "pickup": pickup,
    }


@pytest.fixture
def employee(make_user, setup):
    """CBNV đã có đủ giấy tờ để đăng ký được ngay."""
    return make_user(
        email="nv@company.vn",
        password="MatKhau123",
        team_id=setup["team"].id,
        work_location_id=setup["location"].id,
        phone="0912345678",
        gender=Gender.MALE,
        date_of_birth="1995-03-20",
        id_card_number="001095012345",
    )


@pytest.fixture
def headers(employee, auth_headers):
    return auth_headers("nv@company.vn")


def payload(setup, **overrides) -> dict:
    data = {
        "is_participating": True,
        "shift_id": setup["shift2"].id,
        "departure_location_id": setup["location"].id,
        "bus_needs": [
            {
                "trip_leg_id": setup["leg1"].id,
                "needs_bus": True,
                "pickup_point_id": setup["pickup"].id,
            },
            {"trip_leg_id": setup["leg2"].id, "needs_bus": False},
        ],
        "wish_note": "Mong có hoạt động ngoài trời",
        "agreed_terms_version": "v1",
    }
    data.update(overrides)
    return data


# --- Gửi đăng ký ---


def test_submit_creates_registration_bus_needs_and_consent(
    client: TestClient, setup, employee, headers, db: Session
):
    """Ba mảnh dữ liệu phải cùng được ghi: đăng ký, nhu cầu xe, bằng chứng đồng ý."""
    response = client.post("/api/v1/registrations", headers=headers, json=payload(setup))

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "submitted"
    assert body["shift"]["code"] == "CA2"
    assert body["can_edit"] is True
    assert len(body["bus_needs"]) == 2
    assert body["bus_needs"][0]["pickup_point_name"] == "Toà nhà Keangnam"

    assert db.query(RegistrationBusNeed).count() == 2
    consent = db.query(Consent).one()
    assert consent.terms_version == "v1"
    assert consent.agreed_at is not None


def test_not_participating_skips_shift_and_bus(
    client: TestClient, setup, employee, headers, db: Session
):
    response = client.post(
        "/api/v1/registrations",
        headers=headers,
        json={
            "is_participating": False,
            "not_participating_reason": "Bận việc gia đình",
        },
    )
    assert response.status_code == 201
    assert response.json()["shift"] is None
    assert db.query(Consent).count() == 0  # không tham gia thì không cần đồng ý quy định


def test_participating_requires_terms_agreement(client: TestClient, setup, employee, headers):
    response = client.post(
        "/api/v1/registrations", headers=headers, json=payload(setup, agreed_terms_version=None)
    )
    assert response.status_code == 422


def test_outdated_terms_version_is_rejected(client: TestClient, setup, employee, headers, db):
    """Người dùng mở form từ hôm qua, BTC vừa sửa quy định — phải đọc lại bản mới."""
    setup["event"].terms_version = "v2"
    db.commit()

    response = client.post(
        "/api/v1/registrations", headers=headers, json=payload(setup, agreed_terms_version="v1")
    )
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "TERMS_VERSION_MISMATCH"
    assert error["details"]["current_version"] == "v2"


def test_missing_id_card_blocks_participation(
    client: TestClient, setup, make_user, auth_headers
):
    """Thiếu CCCD/ngày sinh thì BTC không xuất được vé — chặn ngay lúc đăng ký."""
    make_user(email="thieu@company.vn", password="MatKhau123", team_id=setup["team"].id)

    response = client.post(
        "/api/v1/registrations",
        headers=auth_headers("thieu@company.vn"),
        json=payload(setup),
    )
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "MISSING_PROFILE_FIELDS"
    assert "Số CCCD/Hộ chiếu" in error["details"]["missing_fields"]


def test_profile_patch_is_saved_with_registration(
    client: TestClient, setup, make_user, auth_headers, db: Session
):
    """CBNV bổ sung giấy tờ ngay trong form đăng ký, không phải sang trang hồ sơ."""
    user = make_user(email="thieu@company.vn", password="MatKhau123", team_id=setup["team"].id)

    response = client.post(
        "/api/v1/registrations",
        headers=auth_headers("thieu@company.vn"),
        json=payload(
            setup,
            profile_patch={
                "phone": "0987654321",
                "gender": "female",
                "date_of_birth": "1998-07-15",
                "id_card_number": "001198001234",
                "shirt_size": "M",
            },
        ),
    )
    assert response.status_code == 201

    db.refresh(user)
    assert user.phone == "0987654321"
    assert user.can_fly is True


def test_duplicate_submission_is_rejected(client: TestClient, setup, employee, headers):
    client.post("/api/v1/registrations", headers=headers, json=payload(setup))
    again = client.post("/api/v1/registrations", headers=headers, json=payload(setup))

    assert again.status_code == 409
    assert again.json()["error"]["code"] == "ALREADY_REGISTERED"


def test_cannot_submit_when_registration_closed(
    client: TestClient, setup, employee, headers, db
):
    setup["event"].status = EventStatus.REGISTRATION_CLOSED
    db.commit()

    response = client.post("/api/v1/registrations", headers=headers, json=payload(setup))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "REGISTRATION_CLOSED"


def test_shift_from_another_event_is_rejected(
    client: TestClient, setup, employee, headers, db: Session
):
    other_event = Event(
        code="TB2027",
        name="Kỳ khác",
        start_date="2027-10-15",
        end_date="2027-10-17",
        status=EventStatus.DRAFT,
    )
    db.add(other_event)
    db.flush()
    foreign_shift = Shift(event_id=other_event.id, code="CAX", name="Ca lạ")
    db.add(foreign_shift)
    db.commit()

    response = client.post(
        "/api/v1/registrations", headers=headers, json=payload(setup, shift_id=foreign_shift.id)
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SHIFT_NOT_FOUND"


def test_duplicate_trip_leg_is_rejected(client: TestClient, setup, employee, headers):
    response = client.post(
        "/api/v1/registrations",
        headers=headers,
        json=payload(
            setup,
            bus_needs=[
                {"trip_leg_id": setup["leg1"].id, "needs_bus": True},
                {"trip_leg_id": setup["leg1"].id, "needs_bus": False},
            ],
        ),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DUPLICATE_TRIP_LEG"


def test_pickup_point_cleared_when_not_taking_bus(
    client: TestClient, setup, employee, headers, db: Session
):
    """Không đi xe mà vẫn gửi điểm đón — dữ liệu mâu thuẫn, phải dọn."""
    client.post(
        "/api/v1/registrations",
        headers=headers,
        json=payload(
            setup,
            bus_needs=[
                {
                    "trip_leg_id": setup["leg1"].id,
                    "needs_bus": False,
                    "pickup_point_id": setup["pickup"].id,
                }
            ],
        ),
    )
    need = db.query(RegistrationBusNeed).one()
    assert need.needs_bus is False
    assert need.pickup_point_id is None


# --- Sửa đăng ký ---


def test_update_replaces_bus_needs(client: TestClient, setup, employee, headers, db: Session):
    """Bỏ tick một chặng thì dòng cũ phải biến mất, không chỉ đổi cờ."""
    client.post("/api/v1/registrations", headers=headers, json=payload(setup))
    assert db.query(RegistrationBusNeed).count() == 2

    response = client.patch(
        "/api/v1/registrations/me",
        headers=headers,
        json={"bus_needs": [{"trip_leg_id": setup["leg1"].id, "needs_bus": True}]},
    )
    assert response.status_code == 200
    assert len(response.json()["bus_needs"]) == 1
    assert db.query(RegistrationBusNeed).count() == 1


def test_switching_to_not_participating_clears_shift_and_bus(
    client: TestClient, setup, employee, headers, db: Session
):
    client.post("/api/v1/registrations", headers=headers, json=payload(setup))

    response = client.patch(
        "/api/v1/registrations/me",
        headers=headers,
        json={"is_participating": False, "not_participating_reason": "Trùng lịch công tác"},
    )
    assert response.status_code == 200
    assert response.json()["shift"] is None
    assert response.json()["bus_needs"] == []
    assert db.query(RegistrationBusNeed).count() == 0


def test_cannot_edit_after_registration_closed(
    client: TestClient, setup, employee, headers, db
):
    client.post("/api/v1/registrations", headers=headers, json=payload(setup))
    setup["event"].status = EventStatus.ALLOCATION_PROCESSING
    db.commit()

    read_back = client.get("/api/v1/registrations/me", headers=headers)
    assert read_back.status_code == 200
    assert read_back.json()["can_edit"] is False

    edit = client.patch(
        "/api/v1/registrations/me", headers=headers, json={"wish_note": "Đổi ý"}
    )
    assert edit.status_code == 409


# --- Huỷ ---


def test_cancel_before_deadline_has_no_penalty(
    client: TestClient, setup, employee, headers, db: Session
):
    client.post("/api/v1/registrations", headers=headers, json=payload(setup))

    response = client.post(
        "/api/v1/registrations/me/cancel",
        headers=headers,
        json={"reason": "Có việc đột xuất"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "cancelled"
    assert body["penalty_applied"] is False
    assert db.query(RegistrationBusNeed).count() == 0


def test_cancel_after_deadline_flags_penalty(
    client: TestClient, setup, employee, headers, db: Session
):
    """Huỷ sau hạn thì đánh cờ phí phạt — hệ thống đánh dấu, BTC quyết định thu."""
    client.post("/api/v1/registrations", headers=headers, json=payload(setup))
    setup["event"].registration_closes_at = "2026-09-01T17:00:00+00:00"  # đã qua
    db.commit()

    response = client.post(
        "/api/v1/registrations/me/cancel", headers=headers, json={"reason": "Bận đột xuất"}
    )
    assert response.json()["penalty_applied"] is True


def test_can_register_again_after_cancel(client: TestClient, setup, employee, headers, db):
    client.post("/api/v1/registrations", headers=headers, json=payload(setup))
    client.post(
        "/api/v1/registrations/me/cancel", headers=headers, json={"reason": "Đổi ý"}
    )

    again = client.post("/api/v1/registrations", headers=headers, json=payload(setup))
    assert again.status_code == 201
    body = again.json()
    assert body["status"] == "submitted"
    assert body["penalty_applied"] is False
    assert body["cancel_reason"] is None
    assert db.query(Registration).count() == 1  # cùng một bản ghi, không tạo thêm


# --- Phân quyền & danh sách BTC ---


def test_employee_cannot_list_all_registrations(client: TestClient, setup, employee, headers):
    assert client.get("/api/v1/registrations", headers=headers).status_code == 403


def test_employee_cannot_read_other_registration(
    client: TestClient, setup, employee, headers, make_user
):
    """Đổi id trên URL để xem đăng ký người khác — phải bị chặn (IDOR)."""
    other = make_user(email="khac@company.vn", team_id=setup["team"].id)
    response = client.get(f"/api/v1/registrations/{other.id}", headers=headers)
    assert response.status_code == 403


def test_admin_can_filter_and_paginate(
    client: TestClient, setup, employee, headers, make_user, auth_headers
):
    make_user(email="btc@company.vn", password="Admin12345", role=UserRole.ADMIN)
    client.post("/api/v1/registrations", headers=headers, json=payload(setup))
    admin_headers = auth_headers("btc@company.vn", "Admin12345")

    listing = client.get(
        "/api/v1/registrations?page=1&page_size=10", headers=admin_headers
    ).json()
    assert listing["total"] == 1
    assert listing["items"][0]["user"]["full_name"] == "Nguyễn Văn A"
    # Danh sách hiển thị rộng nên không kèm dữ liệu nhạy cảm
    assert "id_card_number" not in listing["items"][0]["user"]

    by_shift = client.get(
        f"/api/v1/registrations?shift_id={setup['shift1'].id}", headers=admin_headers
    ).json()
    assert by_shift["total"] == 0


def test_admin_can_filter_missing_documents(
    client: TestClient, setup, make_user, auth_headers, db: Session
):
    make_user(email="btc@company.vn", password="Admin12345", role=UserRole.ADMIN)
    incomplete = make_user(email="thieu@company.vn", team_id=setup["team"].id)
    db.add(
        Registration(
            event_id=setup["event"].id, user_id=incomplete.id, is_participating=True
        )
    )
    db.commit()

    result = client.get(
        "/api/v1/registrations?missing_documents=true",
        headers=auth_headers("btc@company.vn", "Admin12345"),
    ).json()
    assert result["total"] == 1
    assert result["items"][0]["user"]["can_fly"] is False


def test_stats_summarise_registration_state(
    client: TestClient, setup, employee, headers, make_user, auth_headers
):
    make_user(email="btc@company.vn", password="Admin12345", role=UserRole.ADMIN)
    client.post("/api/v1/registrations", headers=headers, json=payload(setup))

    stats = client.get(
        "/api/v1/registrations/stats", headers=auth_headers("btc@company.vn", "Admin12345")
    ).json()
    assert stats["participating"] == 1
    assert stats["by_shift"] == {"CA2": 1}
    assert stats["bus_demand_by_leg"] == {"CITY_TO_AIRPORT": 1}
    assert stats["missing_flight_documents"] == 0


def test_registration_actions_are_audited(
    client: TestClient, setup, employee, headers, db: Session
):
    client.post("/api/v1/registrations", headers=headers, json=payload(setup))
    client.patch("/api/v1/registrations/me", headers=headers, json={"wish_note": "Sửa"})
    client.post(
        "/api/v1/registrations/me/cancel", headers=headers, json={"reason": "Đổi ý"}
    )

    actions = [row.action for row in db.query(AuditLog).all()]
    assert actions == [
        "registration.submitted",
        "registration.updated",
        "registration.cancelled",
    ]
