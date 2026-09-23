"""Kiểm thử dashboard BTC và nhật ký thay đổi (docs/04 §10)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.accommodation import Hotel, Room, RoomAssignment
from app.models.notification import EmailLog
from app.models.enums import (
    AssignmentMode,
    EmailStatus,
    EventStatus,
    FlightDirection,
    Gender,
    RegistrationStatus,
    RoomGenderPolicy,
    UserRole,
)
from app.models.event import Event
from app.models.flight import Flight, FlightAssignment, Shift
from app.models.org import Team
from app.models.registration import Registration, RegistrationBusNeed
from app.models.transportation import Bus, BusAssignment, TripLeg
from app.services.dashboard_service import build_checklist

URL = "/api/v1/admin/dashboard"
NOW = "2026-09-13T02:00:00+00:00"


@pytest.fixture
def world(db: Session, make_user) -> dict:
    """3 người tham gia, mỗi thứ mới xếp được một người.

    Team Công nghệ: 2 đi + 1 chưa đăng ký. Team Kinh doanh: 1 không đi + 1 huỷ.
    Không team: BTC + 1 người đi nhưng thiếu CCCD.
    """
    event = Event(
        code="TB2026", name="Team Building 2026", destination="Phú Quốc",
        start_date="2026-10-15", end_date="2026-10-17",
        status=EventStatus.REGISTRATION_CLOSED, terms_version="v1", is_active=True,
    )
    it = Team(code="IT-HN", name="Công nghệ", color="#7c3aed")
    sales = Team(code="SALES-HN", name="Kinh doanh")
    db.add_all([event, it, sales])
    db.flush()

    shift = Shift(event_id=event.id, code="CA1", name="Ca 1", display_order=1)
    leg = TripLeg(
        event_id=event.id, code="CITY_TO_AIRPORT", name="HN → Sân bay",
        direction=FlightDirection.OUTBOUND, display_order=1,
    )
    db.add_all([shift, leg])
    db.flush()

    admin = make_user(email="btc@company.vn", role=UserRole.ADMIN, full_name="Trưởng BTC")
    docs = {"date_of_birth": "1995-01-01", "id_card_number": "001095000001"}
    an = make_user(email="an@company.vn", team_id=it.id, gender=Gender.MALE, **docs)
    binh = make_user(email="binh@company.vn", team_id=it.id, gender=Gender.FEMALE, **docs)
    make_user(email="chua@company.vn", team_id=it.id)
    khong = make_user(email="khong@company.vn", team_id=sales.id)
    huy = make_user(email="huy@company.vn", team_id=sales.id)
    thieu = make_user(email="thieu@company.vn", gender=Gender.MALE, date_of_birth="1990-01-01")

    def register(user, *, participating=True, status=RegistrationStatus.SUBMITTED):
        row = Registration(
            event_id=event.id, user_id=user.id, is_participating=participating,
            shift_id=shift.id if participating else None, status=status, submitted_at=NOW,
        )
        db.add(row)
        return row

    reg_an, reg_binh = register(an), register(binh)
    register(thieu)
    register(khong, participating=False)
    register(huy, status=RegistrationStatus.CANCELLED)
    db.flush()

    db.add_all(
        [
            RegistrationBusNeed(registration_id=reg_an.id, trip_leg_id=leg.id, needs_bus=True),
            RegistrationBusNeed(registration_id=reg_binh.id, trip_leg_id=leg.id, needs_bus=True),
        ]
    )

    outbound = Flight(
        event_id=event.id, flight_code="VN1", direction=FlightDirection.OUTBOUND, shift_id=shift.id,
        departure_airport="HAN", arrival_airport="PQC",
        departure_time="2026-10-15T01:00:00+00:00", arrival_time="2026-10-15T03:00:00+00:00",
        capacity=2,
    )
    back = Flight(
        event_id=event.id, flight_code="VN2", direction=FlightDirection.RETURN,
        departure_airport="PQC", arrival_airport="HAN",
        departure_time="2026-10-17T10:00:00+00:00", arrival_time="2026-10-17T12:00:00+00:00",
        capacity=5,
    )
    bus = Bus(event_id=event.id, trip_leg_id=leg.id, bus_code="XE-01", capacity=1)
    hotel = Hotel(event_id=event.id, name="Sunset")
    db.add_all([outbound, back, bus, hotel])
    db.flush()

    room = Room(
        hotel_id=hotel.id, room_number="101", capacity=2, gender_policy=RoomGenderPolicy.MALE
    )
    db.add(room)
    db.flush()

    db.add_all(
        [
            FlightAssignment(
                registration_id=reg_an.id, flight_id=outbound.id, direction=FlightDirection.OUTBOUND,
                assignment_mode=AssignmentMode.AUTO, assigned_at=NOW,
            ),
            BusAssignment(
                registration_id=reg_an.id, bus_id=bus.id, trip_leg_id=leg.id,
                assignment_mode=AssignmentMode.AUTO, assigned_at=NOW,
            ),
            RoomAssignment(
                registration_id=reg_an.id, room_id=room.id,
                assignment_mode=AssignmentMode.MANUAL, assigned_at=NOW,
            ),
        ]
    )
    db.commit()
    return {"event": event, "admin": admin, "it": it}


@pytest.fixture
def admin_headers(world, auth_headers):
    return auth_headers("btc@company.vn")


# --- Quyền ---


def test_dashboard_is_admin_only(client: TestClient, world, auth_headers):
    assert client.get(URL).status_code == 401
    assert client.get(URL, headers=auth_headers("an@company.vn")).status_code == 403
    assert (
        client.get("/api/v1/admin/audit-logs", headers=auth_headers("an@company.vn")).status_code
        == 403
    )


# --- Số liệu ---


def test_registration_totals_and_team_breakdown(client: TestClient, admin_headers):
    body = client.get(URL, headers=admin_headers).json()

    stats = body["registrations"]
    assert stats["total_users"] == 7
    assert stats["participating"] == 3
    assert stats["missing_flight_documents"] == 1

    teams = {row["name"]: row for row in body["teams"]}
    assert (teams["Công nghệ"]["members"], teams["Công nghệ"]["participating"]) == (3, 2)
    assert teams["Công nghệ"]["not_submitted"] == 1
    assert teams["Công nghệ"]["participation_rate"] == pytest.approx(2 / 3, abs=1e-4)
    assert teams["Kinh doanh"]["not_participating"] == 1
    assert teams["Kinh doanh"]["cancelled"] == 1
    assert teams["Kinh doanh"]["response_rate"] == 1.0
    # Người không có team vẫn phải hiện, nếu không tổng các dòng lệch số tổng.
    assert teams["Chưa gán team"]["members"] == 2
    assert sum(row["members"] for row in body["teams"]) == stats["total_users"]


def test_allocation_progress(client: TestClient, admin_headers):
    body = client.get(URL, headers=admin_headers).json()

    flights = {row["direction"]: row for row in body["flights"]}
    assert flights["outbound"]["unassigned"] == 2
    assert flights["outbound"]["shortfall"] == 1
    assert flights["return"]["unassigned"] == 3
    assert flights["return"]["shortfall"] == 0

    leg = body["buses"][0]
    assert (leg["demand"], leg["capacity"], leg["assigned"], leg["unassigned"], leg["shortfall"]) == (
        2, 1, 1, 1, 1,
    )

    assert body["rooms"] == {
        "participants": 3, "assigned": 1, "unassigned": 2, "total_beds": 2, "uncovered": 1,
    }
    assert body["gala"]["configured"] is False


def test_checklist_lists_what_blocks_publishing(client: TestClient, admin_headers):
    body = client.get(URL, headers=admin_headers).json()
    items = {item["key"]: item for item in body["checklist"]}

    assert body["ready_to_publish"] is False
    assert items["registration_closed"]["done"] is True
    assert items["registration_closed"]["detail"] is None
    assert items["flight_documents"]["done"] is False
    assert items["flight_documents"]["link"] == "/admin/registrations?missing_documents=true"
    assert "Chiều đi thiếu 1 ghế" in items["flight_capacity"]["detail"]
    assert items["flights_assigned"]["detail"] == "Còn 5 lượt bay chưa có chuyến."
    assert items["buses_assigned"]["detail"] == "HN → Sân bay: còn 1 người"
    assert items["emails_ok"] == {
        "key": "emails_ok", "label": "Email gửi không lỗi", "done": True,
        "required": False, "detail": None, "link": "/admin/email-logs?status=failed",
    }


def test_failed_email_does_not_block_publishing():
    ok_flights = [
        {"direction": "outbound", "flights": 1, "unassigned": 0, "shortfall": 0},
        {"direction": "return", "flights": 1, "unassigned": 0, "shortfall": 0},
    ]
    items, ready = build_checklist(
        status=EventStatus.ALLOCATION_PROCESSING,
        registrations={"participating": 10, "missing_flight_documents": 0},
        flights=ok_flights,
        buses=[{"name": "HN → Sân bay", "unassigned": 0}],
        rooms={"unassigned": 0, "uncovered": 0},
        emails={"failed": 3},
    )

    assert ready is True
    assert [item["key"] for item in items if not item["done"]] == ["emails_ok"]


def test_bus_time_mismatch_blocks_publishing():
    """Mục này đi đôi với chặn cứng TRANSPORT_TIME_MISMATCH ở event_service."""
    items, ready = build_checklist(
        status=EventStatus.ALLOCATION_PROCESSING,
        registrations={"participating": 10, "missing_flight_documents": 0},
        flights=[
            {"direction": "outbound", "flights": 1, "unassigned": 0, "shortfall": 0},
            {"direction": "return", "flights": 1, "unassigned": 0, "shortfall": 0},
        ],
        buses=[{"name": "HN → Sân bay", "unassigned": 0}],
        rooms={"unassigned": 0, "uncovered": 0},
        emails={"failed": 0},
        transport_mismatches=2,
    )

    by_key = {item["key"]: item for item in items}
    assert ready is False
    assert by_key["transport_timing"]["done"] is False
    assert by_key["transport_timing"]["link"] == "/admin/buses"
    assert "2 lượt đi xe lệch giờ" in by_key["transport_timing"]["detail"]


def test_nothing_to_allocate_is_not_ready():
    _, ready = build_checklist(
        status=EventStatus.ALLOCATION_PROCESSING,
        registrations={"participating": 0, "missing_flight_documents": 0},
        flights=[],
        buses=[],
        rooms={"unassigned": 0, "uncovered": 0},
        emails={"failed": 0},
    )
    assert ready is False


def test_failed_emails_are_counted(client: TestClient, world, admin_headers, db: Session):
    db.add(
        EmailLog(
            event_id=world["event"].id,
            to_email="an@company.vn", template="registration_confirmed", subject="Xác nhận",
            status=EmailStatus.FAILED, error_message="535", retry_count=0, created_at=NOW,
        )
    )
    db.commit()

    body = client.get(URL, headers=admin_headers).json()
    items = {item["key"]: item for item in body["checklist"]}

    assert body["emails"]["failed"] == 1
    assert items["emails_ok"]["done"] is False


# --- Trạng thái & nhật ký ---


def test_next_statuses_put_forward_step_first(client: TestClient, admin_headers):
    event = client.get(URL, headers=admin_headers).json()["event"]

    assert event["status"] == "registration_closed"
    assert event["next_statuses"] == [
        {"status": "allocation_processing", "label": event["next_statuses"][0]["label"],
         "is_forward": True, "notify_scope": "participants"},
        {"status": "registration_open", "label": event["next_statuses"][1]["label"],
         "is_forward": False, "notify_scope": "everyone"},
    ]


def test_status_change_shows_in_recent_activity_and_audit_logs(
    client: TestClient, world, admin_headers
):
    changed = client.post(
        f"/api/v1/events/{world['event'].id}/status",
        headers=admin_headers,
        json={"status": "allocation_processing"},
    )
    assert changed.status_code == 200, changed.text

    activity = client.get(URL, headers=admin_headers).json()["recent_activity"]
    logs = client.get(
        "/api/v1/admin/audit-logs",
        headers=admin_headers,
        params={"action": "event.status_changed"},
    ).json()

    assert activity[0]["action"] == "event.status_changed"
    assert activity[0]["actor_name"] == "Trưởng BTC"
    assert logs["total"] == 1
    assert logs["items"][0]["before"] == {"status": "registration_closed"}
    assert logs["items"][0]["after"] == {"status": "allocation_processing"}
