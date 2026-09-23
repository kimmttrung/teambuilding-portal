"""Huỷ đăng ký theo giai đoạn kỳ.

Trước công bố: CBNV tự huỷ, hệ thống gỡ mọi chỗ đã xếp và báo BTC.
Sau công bố: CBNV gửi yêu cầu, chỗ giữ nguyên tới khi BTC duyệt (gỡ chỗ, quyết phí phạt) hoặc từ chối.
Từ khi chương trình bắt đầu: CBNV không tự huỷ được, BTC huỷ ngoại lệ.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    Bus,
    BusAssignment,
    Department,
    EmailLog,
    Event,
    Flight,
    FlightAssignment,
    GalaLayout,
    GalaSeat,
    GalaSeatAssignment,
    GalaTable,
    Hotel,
    PickupPoint,
    Registration,
    RegistrationBusNeed,
    RegistrationCancellation,
    Room,
    RoomAssignment,
    Shift,
    Team,
    TripLeg,
    WorkLocation,
)
from app.models.enums import AssignmentMode, EmailStatus, EventStatus, FlightDirection, Gender, UserRole
from app.services import email_resend_service

REG = "/api/v1/registrations"
ADMIN = "/api/v1/admin/cancellations"
STAMP = "2026-09-12T04:00:00+00:00"
PAST = "2026-09-01T10:00:00+00:00"


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
    shift = Shift(event_id=event.id, code="CA1", name="Ca 1", display_order=1)
    leg = TripLeg(
        event_id=event.id,
        code="CITY_TO_AIRPORT",
        name="HN → Sân bay",
        direction=FlightDirection.OUTBOUND,
        display_order=1,
    )
    db.add_all([team, shift, leg])
    db.flush()
    pickup = PickupPoint(event_id=event.id, trip_leg_id=leg.id, name="Toà nhà Keangnam")
    db.add(pickup)
    db.commit()

    employee = make_user(
        email="nv@company.vn",
        full_name="Trần Văn Huỷ",
        employee_code="NV001",
        team_id=team.id,
        work_location_id=location.id,
        phone="0912345678",
        gender=Gender.MALE,
        date_of_birth="1995-03-20",
        id_card_number="001095012345",
    )
    admin = make_user(email="btc@company.vn", full_name="Ban Tổ Chức", role=UserRole.ADMIN)
    make_user(email="super@company.vn", full_name="Quản trị", role=UserRole.SUPER_ADMIN)
    # BTC đã nghỉ việc không được nhận thư báo.
    make_user(email="nghi@company.vn", full_name="BTC cũ", role=UserRole.ADMIN, is_active=False)
    return {
        "event": event,
        "team": team,
        "location": location,
        "shift": shift,
        "leg": leg,
        "pickup": pickup,
        "employee": employee,
        "admin": admin,
    }


@pytest.fixture
def nv(world, auth_headers) -> dict:
    return auth_headers("nv@company.vn")


@pytest.fixture
def btc(world, auth_headers) -> dict:
    return auth_headers("btc@company.vn")


def payload(world, **overrides) -> dict:
    data = {
        "is_participating": True,
        "shift_id": world["shift"].id,
        "departure_location_id": world["location"].id,
        "bus_needs": [
            {"trip_leg_id": world["leg"].id, "needs_bus": True, "pickup_point_id": world["pickup"].id}
        ],
        "agreed_terms_version": "v1",
    }
    data.update(overrides)
    return data


def register(client: TestClient, nv: dict, world: dict, **overrides) -> int:
    response = client.post(REG, headers=nv, json=payload(world, **overrides))
    assert response.status_code == 201, response.text
    return response.json()["id"]


def set_event(db: Session, world: dict, status: EventStatus, closes_at: str | None = None) -> None:
    world["event"].status = status
    if closes_at:
        world["event"].registration_closes_at = closes_at
    db.commit()


def allocate_everything(db: Session, world: dict, registration_id: int) -> dict:
    """Xếp đủ vé bay, xe (kèm vai trò Trưởng xe), phòng (trưởng phòng) và ghế Gala cho một người."""
    event_id = world["event"].id
    flight = Flight(
        event_id=event_id,
        flight_code="VN1234",
        direction=FlightDirection.OUTBOUND,
        shift_id=world["shift"].id,
        departure_airport="HAN",
        arrival_airport="PQC",
        departure_time="2026-10-15T01:00:00+00:00",
        arrival_time="2026-10-15T03:00:00+00:00",
        capacity=10,
    )
    bus = Bus(
        event_id=event_id,
        trip_leg_id=world["leg"].id,
        bus_code="XE-01",
        capacity=16,
        leader_user_id=world["employee"].id,
        leader_name="Trần Văn Huỷ",
        leader_phone="0912345678",
    )
    hotel = Hotel(event_id=event_id, name="Sunset Beach Resort")
    layout = GalaLayout(event_id=event_id, name="Đêm hội")
    db.add_all([flight, bus, hotel, layout])
    db.flush()

    room = Room(hotel_id=hotel.id, room_number="801", capacity=2)
    table = GalaTable(layout_id=layout.id, table_code="B01", seat_count=10, pos_x=0, pos_y=0)
    db.add_all([room, table])
    db.flush()
    seat = GalaSeat(table_id=table.id, seat_number=3)
    db.add(seat)
    db.flush()

    db.add_all(
        [
            FlightAssignment(
                registration_id=registration_id,
                flight_id=flight.id,
                direction=FlightDirection.OUTBOUND,
                assignment_mode=AssignmentMode.AUTO,
                assigned_at=STAMP,
            ),
            BusAssignment(
                registration_id=registration_id,
                bus_id=bus.id,
                trip_leg_id=world["leg"].id,
                assignment_mode=AssignmentMode.AUTO,
                assigned_at=STAMP,
            ),
            RoomAssignment(
                registration_id=registration_id,
                room_id=room.id,
                is_room_captain=True,
                assignment_mode=AssignmentMode.AUTO,
                assigned_at=STAMP,
            ),
            GalaSeatAssignment(
                seat_id=seat.id,
                team_id=world["team"].id,
                registration_id=registration_id,
                confirmed_by=world["admin"].id,
                confirmed_at=STAMP,
            ),
        ]
    )
    db.commit()
    return {"bus_id": bus.id, "flight_id": flight.id}


def allocations_of(db: Session, registration_id: int) -> int:
    db.expire_all()
    return sum(
        db.query(model).filter_by(registration_id=registration_id).count()
        for model in (FlightAssignment, BusAssignment, RoomAssignment, GalaSeatAssignment)
    )


def emails(db: Session) -> list[tuple[str, str]]:
    db.expire_all()
    return [(row.template, row.to_email) for row in db.query(EmailLog).order_by(EmailLog.id)]


def error_code(response) -> str:
    return response.json()["error"]["code"]


# --- Trước công bố: tự huỷ ---


def test_self_cancel_before_publish_releases_everything_and_notifies_organizers(
    client: TestClient, db: Session, world, nv
):
    registration_id = register(client, nv, world)
    refs = allocate_everything(db, world, registration_id)
    set_event(db, world, EventStatus.ALLOCATION_PROCESSING, closes_at=PAST)
    assert client.get(f"{REG}/me", headers=nv).json()["cancel_policy"] == "self"

    response = client.post(f"{REG}/me/cancel", headers=nv, json={"reason": "Trùng lịch công tác"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "cancelled"
    # Huỷ sau hạn đăng ký → thuộc diện phí phạt theo quy định đã đồng ý.
    assert body["penalty_applied"] is True
    assert body["cancel_policy"] is None
    assert body["latest_cancellation"]["mode"] == "self"
    assert body["latest_cancellation"]["status"] == "approved"

    assert allocations_of(db, registration_id) == 0
    assert db.query(RegistrationBusNeed).count() == 0
    bus = db.get(Bus, refs["bus_id"])
    assert (bus.leader_user_id, bus.leader_name, bus.leader_phone) == (None, None, None)

    cancellation = db.query(RegistrationCancellation).one()
    assert cancellation.event_status == EventStatus.ALLOCATION_PROCESSING
    assert cancellation.after_deadline is True
    assert set(cancellation.released) == {"flights", "buses", "room", "gala", "roles"}
    assert cancellation.released["room"] == ["Phòng 801 – Sunset Beach Resort (trưởng phòng)"]

    sent = emails(db)
    assert ("registration_cancelled", "nv@company.vn") in sent
    notices = sorted(to for template, to in sent if template == "cancellation_notice_admin")
    assert notices == ["btc@company.vn", "super@company.vn"]  # không gửi BTC đã khoá tài khoản

    audit = db.query(AuditLog).filter_by(action="registration.cancelled").one()
    assert audit.reason == "Trùng lịch công tác"
    assert "flights" in audit.after_data


def test_self_cancel_while_registration_open_is_free(client: TestClient, db: Session, world, nv):
    register(client, nv, world)

    body = client.post(f"{REG}/me/cancel", headers=nv, json={"reason": "Có việc gia đình"}).json()

    assert body["status"] == "cancelled"
    assert body["penalty_applied"] is False
    assert db.query(RegistrationCancellation).one().released == {}


def test_non_participant_cancels_directly_even_after_publish(client: TestClient, db: Session, world, nv):
    """Người đã báo không tham gia không có vé / phòng để giữ — không cần BTC duyệt."""
    register(client, nv, world, is_participating=False, not_participating_reason="Bận", bus_needs=[], shift_id=None, agreed_terms_version=None)
    set_event(db, world, EventStatus.INFORMATION_PUBLISHED)

    assert client.get(f"{REG}/me", headers=nv).json()["cancel_policy"] == "self"
    assert client.post(f"{REG}/me/cancel", headers=nv, json={"reason": "Đổi ý"}).status_code == 200


# --- Sau công bố: yêu cầu huỷ ---


def test_after_publish_employee_must_request_and_keeps_seats_while_pending(
    client: TestClient, db: Session, world, nv, btc
):
    registration_id = register(client, nv, world)
    allocate_everything(db, world, registration_id)
    set_event(db, world, EventStatus.INFORMATION_PUBLISHED, closes_at=PAST)
    assert client.get(f"{REG}/me", headers=nv).json()["cancel_policy"] == "request"

    direct = client.post(f"{REG}/me/cancel", headers=nv, json={"reason": "Bận đột xuất"})
    assert direct.status_code == 409
    assert error_code(direct) == "CANCELLATION_REQUIRES_APPROVAL"

    response = client.post(f"{REG}/me/cancellation-request", headers=nv, json={"reason": "  Bận đột xuất  "})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "submitted"
    assert body["latest_cancellation"]["status"] == "pending"
    assert body["latest_cancellation"]["reason"] == "Bận đột xuất"
    assert allocations_of(db, registration_id) == 4  # chưa gỡ gì khi BTC chưa duyệt

    again = client.post(f"{REG}/me/cancellation-request", headers=nv, json={"reason": "Bấm lại"})
    assert again.status_code == 409
    assert error_code(again) == "CANCELLATION_PENDING"

    sent = emails(db)
    assert ("cancellation_requested", "nv@company.vn") in sent
    assert sorted(to for template, to in sent if template == "cancellation_notice_admin") == [
        "btc@company.vn",
        "super@company.vn",
    ]

    dashboard = client.get("/api/v1/admin/dashboard", headers=btc).json()
    assert dashboard["cancellations"]["pending"] == 1

    listed = client.get(f"{ADMIN}?status=pending", headers=btc).json()
    assert listed["total"] == 1
    item = listed["items"][0]
    assert item["user"]["full_name"] == "Trần Văn Huỷ"
    assert item["user"]["team_name"] == "Công nghệ Hà Nội"
    assert item["event_status_label"]
    assert item["after_deadline"] is True


def test_employee_withdraws_then_can_request_again(client: TestClient, db: Session, world, nv):
    register(client, nv, world)
    set_event(db, world, EventStatus.INFORMATION_PUBLISHED)
    client.post(f"{REG}/me/cancellation-request", headers=nv, json={"reason": "Bận"})

    withdrawn = client.delete(f"{REG}/me/cancellation-request", headers=nv)
    assert withdrawn.status_code == 200
    assert withdrawn.json()["latest_cancellation"]["status"] == "withdrawn"
    assert withdrawn.json()["status"] == "submitted"
    assert client.delete(f"{REG}/me/cancellation-request", headers=nv).status_code == 409

    assert client.post(f"{REG}/me/cancellation-request", headers=nv, json={"reason": "Bận thật"}).status_code == 201


def test_organizer_approves_with_penalty_and_seats_are_released(
    client: TestClient, db: Session, world, nv, btc
):
    registration_id = register(client, nv, world)
    allocate_everything(db, world, registration_id)
    set_event(db, world, EventStatus.INFORMATION_PUBLISHED, closes_at=PAST)
    client.post(f"{REG}/me/cancellation-request", headers=nv, json={"reason": "Ốm nặng"})
    cancellation_id = db.query(RegistrationCancellation).one().id

    response = client.post(
        f"{ADMIN}/{cancellation_id}/approve",
        headers=btc,
        json={"penalty_applied": True, "penalty_note": "Chịu vé máy bay và phòng", "decision_note": "Đã báo quản lý"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "approved"
    assert body["decided_by_name"] == "Ban Tổ Chức"
    assert body["penalty_note"] == "Chịu vé máy bay và phòng"
    assert body["released"]["flights"] == ["VN1234 (Chiều đi)"]

    db.expire_all()
    registration = db.get(Registration, registration_id)
    assert registration.status == "cancelled"
    assert registration.penalty_applied is True
    assert allocations_of(db, registration_id) == 0
    assert ("cancellation_decided", "nv@company.vn") in emails(db)
    assert db.query(AuditLog).filter_by(action="registration.cancellation_approved").count() == 1

    twice = client.post(f"{ADMIN}/{cancellation_id}/approve", headers=btc, json={})
    assert twice.status_code == 409
    assert error_code(twice) == "CANCELLATION_NOT_PENDING"


def test_organizer_rejects_with_reason_and_registration_stays(
    client: TestClient, db: Session, world, nv, btc
):
    registration_id = register(client, nv, world)
    allocate_everything(db, world, registration_id)
    set_event(db, world, EventStatus.INFORMATION_PUBLISHED)
    client.post(f"{REG}/me/cancellation-request", headers=nv, json={"reason": "Không muốn đi"})
    cancellation_id = db.query(RegistrationCancellation).one().id

    assert client.post(f"{ADMIN}/{cancellation_id}/reject", headers=btc, json={}).status_code == 422

    response = client.post(
        f"{ADMIN}/{cancellation_id}/reject", headers=btc, json={"decision_note": "Vé đã xuất, không hoàn được"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert allocations_of(db, registration_id) == 4

    mine = client.get(f"{REG}/me", headers=nv).json()
    assert mine["status"] == "submitted"
    assert mine["latest_cancellation"]["decision_note"] == "Vé đã xuất, không hoàn được"
    assert mine["cancel_policy"] == "request"  # vẫn xin lại được nếu có lý do khác
    assert ("cancellation_decided", "nv@company.vn") in emails(db)


# --- Từ khi chương trình bắt đầu ---


def test_event_started_blocks_employee_but_organizer_cancels_as_exception(
    client: TestClient, db: Session, world, nv, btc
):
    registration_id = register(client, nv, world)
    allocate_everything(db, world, registration_id)
    set_event(db, world, EventStatus.EVENT_STARTED)
    assert client.get(f"{REG}/me", headers=nv).json()["cancel_policy"] == "contact_btc"

    for method, url, body in (
        ("post", f"{REG}/me/cancel", {"reason": "Ốm nặng"}),
        ("post", f"{REG}/me/cancellation-request", {"reason": "Ốm nặng"}),
    ):
        blocked = getattr(client, method)(url, headers=nv, json=body)
        assert blocked.status_code == 409
        assert error_code(blocked) == "EVENT_ALREADY_STARTED"

    response = client.post(
        ADMIN,
        headers=btc,
        json={"registration_id": registration_id, "reason": "Nhập viện, có giấy xác nhận", "penalty_applied": False},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["mode"], body["status"]) == ("admin", "approved")
    assert allocations_of(db, registration_id) == 0
    assert ("cancellation_decided", "nv@company.vn") in emails(db)

    again = client.post(ADMIN, headers=btc, json={"registration_id": registration_id, "reason": "Lần hai"})
    assert error_code(again) == "ALREADY_CANCELLED"


def test_organizer_cancel_closes_pending_request_instead_of_adding_another(
    client: TestClient, db: Session, world, nv, btc
):
    registration_id = register(client, nv, world)
    set_event(db, world, EventStatus.INFORMATION_PUBLISHED)
    client.post(f"{REG}/me/cancellation-request", headers=nv, json={"reason": "Bận"})

    client.post(ADMIN, headers=btc, json={"registration_id": registration_id, "reason": "Đã gọi xác nhận"})

    db.expire_all()
    row = db.query(RegistrationCancellation).one()
    assert (row.mode, row.status, row.decision_note) == ("request", "approved", "Đã gọi xác nhận")


# --- Phân quyền & gửi lại thư ---


def test_cancellation_admin_endpoints_are_organizer_only(client: TestClient, world, nv):
    assert client.get(ADMIN, headers=nv).status_code == 403
    assert client.post(f"{ADMIN}/1/approve", headers=nv, json={}).status_code == 403


# --- Trưởng nhóm huỷ: tự gỡ chức, BTC gán sau ---


def test_team_leader_self_cancel_releases_leadership(client: TestClient, db: Session, world, nv):
    """Trưởng nhóm tự huỷ trước công bố: huỷ ngay, mất chức, không đổi được ghế Gala nữa."""
    register(client, nv, world)
    world["team"].leader_user_id = world["employee"].id
    db.commit()

    response = client.post(f"{REG}/me/cancel", headers=nv, json={"reason": "Trùng lịch công tác"})
    assert response.status_code == 200, response.text

    db.expire_all()
    assert db.get(Team, world["team"].id).leader_user_id is None
    cancellation = db.query(RegistrationCancellation).one()
    assert cancellation.released["roles"] == ["Trưởng nhóm Công nghệ Hà Nội"]

    from app.services import gala_service

    assert gala_service.led_team(db, world["employee"].id) is None


def test_approve_request_of_team_leader_releases_leadership(
    client: TestClient, db: Session, world, nv, btc
):
    """BTC duyệt yêu cầu của Trưởng nhóm: gỡ chỗ và gỡ chức; danh sách gắn cờ để BTC thấy."""
    register(client, nv, world)
    world["team"].leader_user_id = world["employee"].id
    db.commit()
    set_event(db, world, EventStatus.INFORMATION_PUBLISHED)
    client.post(f"{REG}/me/cancellation-request", headers=nv, json={"reason": "Bận đột xuất"})
    cancellation_id = db.query(RegistrationCancellation).one().id

    listed = client.get(f"{ADMIN}?status=pending", headers=btc).json()
    assert listed["items"][0]["user"]["is_team_leader"] is True

    response = client.post(f"{ADMIN}/{cancellation_id}/approve", headers=btc, json={})
    assert response.status_code == 200, response.text

    db.expire_all()
    assert db.get(Team, world["team"].id).leader_user_id is None
    assert db.query(RegistrationCancellation).one().released["roles"] == [
        "Trưởng nhóm Công nghệ Hà Nội"
    ]


def test_cancelled_user_cannot_operate_gala_even_if_still_flagged(
    client: TestClient, db: Session, world, nv
):
    """Phòng thủ sâu: kể cả khi sót chức Trưởng nhóm, người đã huỷ vẫn không xem ghế team được."""
    from app.core.exceptions import PermissionDeniedError
    from app.models import User
    from app.services import gala_service

    register(client, nv, world)
    client.post(f"{REG}/me/cancel", headers=nv, json={"reason": "Đổi ý"})
    # Giả lập sót dữ liệu: chức chưa kịp gỡ.
    world["team"].leader_user_id = world["employee"].id
    db.commit()
    db.expire_all()

    viewer = db.get(User, world["employee"].id)
    with pytest.raises(PermissionDeniedError):
        gala_service.team_members(db, event=world["event"], viewer=viewer)


def test_failed_notice_is_resent_only_while_still_relevant(client: TestClient, db: Session, world, nv, btc):
    register(client, nv, world)
    set_event(db, world, EventStatus.INFORMATION_PUBLISHED)
    client.post(f"{REG}/me/cancellation-request", headers=nv, json={"reason": "Bận"})

    db.expire_all()
    notice = db.query(EmailLog).filter_by(template="cancellation_notice_admin", to_email="btc@company.vn").one()
    notice.status = EmailStatus.FAILED
    db.commit()
    admin = world["admin"]

    result, _jobs = email_resend_service.resend(db, event=world["event"], actor=admin, ids=[notice.id])
    assert result["queued"] == 1

    cancellation_id = db.query(RegistrationCancellation).one().id
    client.post(f"{ADMIN}/{cancellation_id}/reject", headers=btc, json={"decision_note": "Không duyệt"})
    db.expire_all()
    notice = db.get(EmailLog, notice.id)
    notice.status = EmailStatus.FAILED
    db.commit()

    # BTC đã xử lý xong → thư "cần duyệt" không còn đúng, không gửi lại.
    result, _jobs = email_resend_service.resend(db, event=world["event"], actor=admin, ids=[notice.id])
    assert result["queued"] == 0
