"""Kiểm thử BTC quản lý thông báo: soạn nháp, đăng/gỡ/xoá, gửi email đúng nhóm nhận."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.content import Announcement
from app.models.enums import (
    AnnouncementSeverity,
    AnnouncementTarget,
    AssignmentMode,
    EventStatus,
    FlightDirection,
    RegistrationStatus,
    UserRole,
)
from app.models.event import Event
from app.models.flight import Flight, FlightAssignment, Shift
from app.models.notification import EmailLog
from app.models.org import Team
from app.models.registration import Registration
from app.models.transportation import Bus, BusAssignment, TripLeg
from app.services import email_service

BASE = "/api/v1/admin/announcements"
JOURNEY = "/api/v1/journey/me"
NOW = "2026-09-12T04:00:00+00:00"


@pytest.fixture
def world(db: Session, make_user) -> dict:
    """Kỳ đã công bố: Alice + Bob ở team A (Alice bay F1, Bob đi xe B1), Cara ở team B."""
    event = Event(
        code="TB2026", name="Team Building 2026", destination="Phú Quốc",
        start_date="2026-10-15", end_date="2026-10-17",
        status=EventStatus.INFORMATION_PUBLISHED, terms_version="v1", is_active=True,
    )
    other = Event(
        code="TB2027", name="Team Building 2027", destination="Đà Nẵng",
        start_date="2027-10-15", end_date="2027-10-17",
        status=EventStatus.DRAFT, terms_version="v1", is_active=False,
    )
    team_a = Team(code="IT-HN", name="Công nghệ Hà Nội")
    team_b = Team(code="SALES-HN", name="Kinh doanh Hà Nội")
    db.add_all([event, other, team_a, team_b])
    db.flush()

    ca1 = Shift(event_id=event.id, code="CA1", name="Ca 1", display_order=1)
    flight = Flight(
        event_id=event.id, flight_code="VN1234", direction=FlightDirection.OUTBOUND,
        shift_id=None, departure_airport="HAN", arrival_airport="PQC",
        departure_time="2026-10-15T06:30:00+00:00", arrival_time="2026-10-15T08:40:00+00:00",
        capacity=60,
    )
    strange_flight = Flight(
        event_id=other.id, flight_code="VN9999", direction=FlightDirection.OUTBOUND,
        shift_id=None, departure_airport="HAN", arrival_airport="DAD",
        departure_time="2027-10-15T06:30:00+00:00", arrival_time="2027-10-15T08:00:00+00:00",
        capacity=60,
    )
    leg = TripLeg(
        event_id=event.id, code="CITY_TO_AIRPORT", name="HN → Sân bay",
        direction=FlightDirection.OUTBOUND, leg_date="2026-10-15", is_airport_linked=True,
        display_order=1,
    )
    db.add_all([ca1, flight, strange_flight, leg])
    db.flush()
    bus = Bus(event_id=event.id, trip_leg_id=leg.id, bus_code="XE-01", capacity=45)
    db.add(bus)
    db.flush()

    make_user(email="btc@company.vn", full_name="Trưởng BTC", role=UserRole.ADMIN)
    alice = make_user(email="alice@company.vn", full_name="Alice Team A", team_id=team_a.id)
    bob = make_user(email="bob@company.vn", full_name="Bob Team A", team_id=team_a.id)
    cara = make_user(email="cara@company.vn", full_name="Cara Team B", team_id=team_b.id)
    dave = make_user(email="dave@company.vn", full_name="Dave Chưa Có Team")

    registrations = {}
    for user in (alice, bob, cara):
        registration = Registration(
            event_id=event.id, user_id=user.id, is_participating=True,
            status=RegistrationStatus.SUBMITTED, submitted_at=NOW,
        )
        db.add(registration)
        db.flush()
        registrations[user.email] = registration
    db.add(
        FlightAssignment(
            registration_id=registrations["alice@company.vn"].id, flight_id=flight.id,
            direction=FlightDirection.OUTBOUND, assignment_mode=AssignmentMode.AUTO,
            assigned_at=NOW,
        )
    )
    db.add(
        BusAssignment(
            registration_id=registrations["bob@company.vn"].id, bus_id=bus.id,
            trip_leg_id=leg.id, assignment_mode=AssignmentMode.AUTO, assigned_at=NOW,
        )
    )
    db.add(
        Announcement(
            event_id=other.id, title="Tin của kỳ khác", content="Không liên quan.",
            severity=AnnouncementSeverity.INFO, target_type=AnnouncementTarget.ALL,
            published_at=NOW, created_at=NOW,
        )
    )
    db.commit()
    return {
        "event_id": event.id,
        "team_a_id": team_a.id,
        "team_b_id": team_b.id,
        "flight_id": flight.id,
        "strange_flight_id": strange_flight.id,
        "bus_id": bus.id,
        "alice_id": alice.id,
    }


@pytest.fixture
def admin(world, auth_headers):
    return auth_headers("btc@company.vn")


@pytest.fixture
def alice_headers(world, auth_headers):
    return auth_headers("alice@company.vn")


@pytest.fixture
def bob_headers(world, auth_headers):
    return auth_headers("bob@company.vn")


@pytest.fixture
def cara_headers(world, auth_headers):
    return auth_headers("cara@company.vn")


def _draft(**overrides):
    body = {"title": "Đổi giờ bay", "content": "Bay sớm hơn **30 phút**.", "severity": "warning"}
    body.update(overrides)
    return body


def _journey_titles(client: TestClient, headers) -> list[str]:
    response = client.get(JOURNEY, headers=headers)
    assert response.status_code == 200, response.text
    return [item["title"] for item in response.json()["announcements"]]


# --- Soạn nháp ---


def test_create_draft_and_list_shows_it_first(client: TestClient, admin):
    created = client.post(BASE, headers=admin, json=_draft()).json()

    assert created["published_at"] is None
    assert created["send_email"] is False
    assert created["target_label"] == "Tất cả CBNV"
    # Mọi tài khoản đang hoạt động trong hệ thống đều nhận tin gửi tất cả.
    assert created["recipient_count"] == 5

    rows = client.get(BASE, headers=admin).json()
    assert rows[0]["title"] == "Đổi giờ bay"
    assert rows[0]["target_type"] == "all"


def test_update_draft_changes_target(client: TestClient, world, admin):
    created = client.post(BASE, headers=admin, json=_draft()).json()

    body = client.patch(
        f"{BASE}/{created['id']}",
        headers=admin,
        json={"target_type": "team", "target_id": world["team_a_id"]},
    ).json()

    assert body["target_label"] == "Team Công nghệ Hà Nội"
    assert body["recipient_count"] == 2


def test_target_must_exist_and_belong_to_event(client: TestClient, world, admin):
    assert client.post(
        BASE, headers=admin, json=_draft(target_id=1)
    ).status_code == 422  # all + target_id
    assert client.post(
        BASE, headers=admin, json=_draft(target_type="team")
    ).status_code == 422  # thiếu target_id
    response = client.post(
        BASE, headers=admin, json=_draft(target_type="team", target_id=9999)
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "ANNOUNCEMENT_TARGET_INVALID"
    # Chuyến bay của kỳ khác — chặn để khỏi gửi nhầm sang dữ liệu kỳ khác.
    response = client.post(
        BASE,
        headers=admin,
        json=_draft(target_type="flight", target_id=world["strange_flight_id"]),
    )
    assert response.status_code == 422


def test_other_event_announcement_is_isolated(client: TestClient, world, admin, db: Session):
    assert "Tin của kỳ khác" not in [row["title"] for row in client.get(BASE, headers=admin).json()]

    other_id = db.query(Announcement).filter_by(title="Tin của kỳ khác").one().id
    assert client.patch(f"{BASE}/{other_id}", headers=admin, json={"title": "X"}).status_code == 404
    assert client.delete(f"{BASE}/{other_id}", headers=admin).status_code == 404


def test_employee_cannot_manage(client: TestClient, world, admin, alice_headers):
    created = client.post(BASE, headers=admin, json=_draft()).json()

    assert client.get(BASE, headers=alice_headers).status_code == 403
    assert client.post(BASE, headers=alice_headers, json=_draft()).status_code == 403
    assert client.patch(
        f"{BASE}/{created['id']}", headers=alice_headers, json={"title": "X"}
    ).status_code == 403
    assert client.post(
        f"{BASE}/{created['id']}/publish", headers=alice_headers, json={}
    ).status_code == 403


# --- Đăng / gỡ / xoá ---


def test_draft_invisible_until_published(client: TestClient, world, admin, alice_headers, cara_headers):
    created = client.post(
        BASE, headers=admin,
        json=_draft(target_type="team", target_id=world["team_a_id"]),
    ).json()
    assert "Đổi giờ bay" not in _journey_titles(client, alice_headers)

    published = client.post(f"{BASE}/{created['id']}/publish", headers=admin, json={}).json()
    assert published["queued"] == 0
    assert published["published_at"] is not None

    assert "Đổi giờ bay" in _journey_titles(client, alice_headers)
    assert "Đổi giờ bay" not in _journey_titles(client, cara_headers)


def test_flight_and_bus_targets_follow_assignments(
    client: TestClient, world, admin, alice_headers, bob_headers
):
    flight = client.post(
        BASE, headers=admin,
        json=_draft(title="Tin chuyến VN1234", target_type="flight", target_id=world["flight_id"]),
    ).json()
    bus = client.post(
        BASE, headers=admin,
        json=_draft(title="Tin xe XE-01", target_type="bus", target_id=world["bus_id"]),
    ).json()
    client.post(f"{BASE}/{flight['id']}/publish", headers=admin, json={})
    client.post(f"{BASE}/{bus['id']}/publish", headers=admin, json={})

    bob = bob_headers
    assert _journey_titles(client, alice_headers) == ["Tin chuyến VN1234"]
    assert _journey_titles(client, bob) == ["Tin xe XE-01"]


def test_unpublish_hides_and_delete_removes(
    client: TestClient, world, admin, alice_headers, db: Session
):
    created = client.post(BASE, headers=admin, json=_draft()).json()
    client.post(f"{BASE}/{created['id']}/publish", headers=admin, json={})
    assert "Đổi giờ bay" in _journey_titles(client, alice_headers)

    assert client.post(f"{BASE}/{created['id']}/unpublish", headers=admin).json()["published_at"] is None
    assert "Đổi giờ bay" not in _journey_titles(client, alice_headers)

    assert client.delete(f"{BASE}/{created['id']}", headers=admin).status_code == 204
    assert client.get(BASE, headers=admin).json() == []
    actions = {row.action for row in db.query(AuditLog).all()}
    assert {
        "announcement.created", "announcement.published", "announcement.unpublished",
        "announcement.deleted",
    } <= actions


# --- Gửi email ---


def test_recipients_preview_matches_publish(
    client: TestClient, world, admin, alice_headers
):
    body = client.get(
        BASE + "/recipients",
        headers=admin,
        params={"target_type": "team", "target_id": world["team_a_id"]},
    ).json()
    assert body["target_label"] == "Team Công nghệ Hà Nội"
    assert [person["full_name"] for person in body["recipients"]] == ["Alice Team A", "Bob Team A"]

    single = client.get(
        BASE + "/recipients",
        headers=admin,
        params={"target_type": "user", "target_id": world["alice_id"]},
    ).json()
    assert single["total"] == 1

    assert client.get(
        BASE + "/recipients", headers=admin, params={"target_type": "team"}
    ).status_code == 422


def test_publish_with_email_writes_one_log_per_recipient(
    client: TestClient, world, admin, alice_headers, db: Session
):
    created = client.post(
        BASE, headers=admin,
        json=_draft(
            title="VN1234 đổi giờ", target_type="team", target_id=world["team_a_id"],
            severity="urgent",
        ),
    ).json()
    result = client.post(
        f"{BASE}/{created['id']}/publish", headers=admin, json={"send_email": True}
    ).json()

    assert result["queued"] == 2
    assert result["email_enabled"] is False

    db.expire_all()
    logs = db.query(EmailLog).order_by(EmailLog.id).all()
    assert [log.to_email for log in logs] == ["alice@company.vn", "bob@company.vn"]
    assert {(log.template, log.related_type, log.related_id) for log in logs} == {
        ("announcement_notice", "event", world["event_id"])
    }
    assert all(log.error_message == email_service.DEV_MODE_NOTE for log in logs)
    assert "VN1234 đổi giờ" in logs[0].body_preview

    emailed = db.query(AuditLog).filter_by(action="announcement.emailed").one()
    assert emailed.entity_id == created["id"]


def test_publish_without_email_writes_no_logs(client: TestClient, admin, db: Session):
    created = client.post(BASE, headers=admin, json=_draft()).json()
    client.post(f"{BASE}/{created['id']}/publish", headers=admin, json={"send_email": False})

    db.expire_all()
    assert db.query(EmailLog).count() == 0
    assert db.query(AuditLog).filter_by(action="announcement.emailed").count() == 0
