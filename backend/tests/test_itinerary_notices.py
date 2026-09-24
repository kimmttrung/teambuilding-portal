"""Email báo CBNV khi BTC sửa lịch trình SAU công bố — đúng người thấy mốc đó, chỉ khi tích "Gửi email"."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Shift
from app.models.content import ItineraryItem
from app.models.enums import (
    AssignmentMode,
    EmailStatus,
    EventStatus,
    FlightDirection,
    RegistrationStatus,
    UserRole,
)
from app.models.event import Event
from app.models.flight import Flight, FlightAssignment
from app.models.notification import EmailLog
from app.models.registration import Registration

NOW = "2026-09-12T04:00:00+00:00"
TEMPLATE = "itinerary_changed"
BASE = "/api/v1/itinerary"


@pytest.fixture
def world(db: Session, make_user) -> dict:
    """Kỳ đã công bố. An bay chuyến Ca 1, Bình bay chuyến Ca 2, Cường không tham gia."""
    event = Event(
        code="TB2026", name="Team Building 2026", destination="Phú Quốc",
        start_date="2026-10-15", end_date="2026-10-17",
        status=EventStatus.INFORMATION_PUBLISHED, terms_version="v1", is_active=True,
    )
    db.add(event)
    db.flush()
    shifts = [
        Shift(event_id=event.id, code=code, name=code, display_order=order)
        for order, code in enumerate(("CA1", "CA2"))
    ]
    db.add_all(shifts)
    db.flush()
    flights = [
        Flight(
            event_id=event.id, flight_code=code, direction=FlightDirection.OUTBOUND,
            shift_id=shift.id, departure_airport="HAN", arrival_airport="PQC",
            departure_time="2026-10-15T00:00:00+00:00",
            arrival_time="2026-10-15T02:00:00+00:00", capacity=60,
        )
        for code, shift in (("VN1", shifts[0]), ("VN2", shifts[1]))
    ]
    db.add_all(flights)
    db.flush()
    items = {
        "ca1": ItineraryItem(
            event_id=event.id, day_date="2026-10-16", start_time="08:00", end_time="09:00",
            title="Họp ca 1", audience="CA1", display_order=0,
        ),
        "all": ItineraryItem(
            event_id=event.id, day_date="2026-10-16", start_time="19:00", end_time="22:00",
            title="Gala Dinner", location="Sảnh A", audience="all", display_order=1,
        ),
    }
    db.add_all(items.values())

    make_user(email="btc@company.vn", full_name="Trưởng BTC", role=UserRole.ADMIN)
    for key, flight, participating in (
        ("an", flights[0], True),
        ("binh", flights[1], True),
        ("cuong", None, False),
    ):
        user = make_user(email=f"{key}@company.vn", full_name=key.title())
        registration = Registration(
            event_id=event.id, user_id=user.id, is_participating=participating,
            status=RegistrationStatus.SUBMITTED, submitted_at=NOW,
        )
        db.add(registration)
        db.flush()
        if flight is not None:
            db.add(FlightAssignment(
                registration_id=registration.id, flight_id=flight.id,
                direction=FlightDirection.OUTBOUND, assignment_mode=AssignmentMode.AUTO,
                assigned_at=NOW,
            ))
    db.commit()
    return {"event_id": event.id, **{key: item.id for key, item in items.items()}}


@pytest.fixture
def admin(world, auth_headers):
    return auth_headers("btc@company.vn")


def _mail(db: Session) -> dict[str, str]:
    db.expire_all()
    return {
        row.to_email: row.body_preview
        for row in db.scalars(select(EmailLog).where(EmailLog.template == TEMPLATE))
    }


def test_no_email_without_notify_flag(client: TestClient, world, admin, db):
    response = client.patch(f"{BASE}/{world['all']}", headers=admin, json={"start_time": "18:30"})
    assert response.status_code == 200, response.text
    assert _mail(db) == {}


def test_shared_item_change_emails_every_participant(client: TestClient, world, admin, db):
    response = client.patch(
        f"{BASE}/{world['all']}?notify=true", headers=admin, json={"location": "Sảnh B"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["location"] == "Sảnh B"

    mail = _mail(db)
    assert set(mail) == {"an@company.vn", "binh@company.vn"}  # Cường không tham gia
    assert "Gala Dinner · Địa điểm: Sảnh A → Sảnh B" in mail["an@company.vn"]


def test_shift_item_emails_only_that_shift(client: TestClient, world, admin, db):
    client.patch(f"{BASE}/{world['ca1']}?notify=true", headers=admin, json={"start_time": "07:30"})
    mail = _mail(db)
    assert set(mail) == {"an@company.vn"}
    assert "08:00 – 09:00 → 07:30 – 09:00" in mail["an@company.vn"]


def test_audience_change_emails_who_lost_and_who_gained(client: TestClient, world, admin, db):
    client.patch(f"{BASE}/{world['ca1']}?notify=true", headers=admin, json={"audience": "CA2"})
    mail = _mail(db)
    assert set(mail) == {"an@company.vn", "binh@company.vn"}
    assert "Mốc bị bỏ" in mail["an@company.vn"]
    assert "Mốc mới" in mail["binh@company.vn"]


def test_create_and_delete_follow_notify(client: TestClient, world, admin, db):
    created = client.post(
        f"{BASE}?notify=true",
        headers=admin,
        json={"day_date": "2026-10-17", "start_time": "09:00", "title": "Tham quan", "audience": "CA2"},
    )
    assert created.status_code == 201, created.text
    assert set(_mail(db)) == {"binh@company.vn"}

    deleted = client.delete(f"{BASE}/{world['all']}?notify=true", headers=admin)
    assert deleted.status_code == 204, deleted.text
    db.expire_all()
    rows = db.scalars(select(EmailLog).where(EmailLog.template == TEMPLATE)).all()
    assert len(rows) == 3
    assert all(row.event_id == world["event_id"] for row in rows)


def test_no_email_before_publish(client: TestClient, world, admin, db):
    event = db.get(Event, world["event_id"])
    event.status = EventStatus.ALLOCATION_PROCESSING
    db.commit()
    client.patch(f"{BASE}/{world['all']}?notify=true", headers=admin, json={"location": "Sảnh B"})
    assert _mail(db) == {}


def test_resend_skips_when_item_changed_again(client: TestClient, world, admin, db):
    client.patch(f"{BASE}/{world['all']}?notify=true", headers=admin, json={"location": "Sảnh B"})
    db.expire_all()
    rows = db.scalars(select(EmailLog).where(EmailLog.template == TEMPLATE)).all()
    for row in rows:
        row.status = EmailStatus.FAILED
    db.commit()

    first = client.post(
        "/api/v1/admin/email-logs/resend", headers=admin, json={"ids": [rows[0].id]}
    ).json()
    assert first["queued"] == 1

    client.patch(f"{BASE}/{world['all']}", headers=admin, json={"location": "Sảnh C"})
    second = client.post(
        "/api/v1/admin/email-logs/resend", headers=admin, json={"ids": [rows[1].id]}
    ).json()
    assert second["skipped"][0]["reason"] == "no_longer_relevant"
