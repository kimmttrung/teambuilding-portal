"""Email báo CBNV khi kỳ đổi trạng thái và khi BTC sửa mục họ đã chọn (ca, chặng, điểm đón, nơi xuất phát)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import EmailStatus, EventStatus, FlightDirection, RegistrationStatus, UserRole
from app.models.event import Event
from app.models.flight import Shift
from app.models.notification import EmailLog
from app.models.org import WorkLocation
from app.models.registration import Registration, RegistrationBusNeed
from app.models.transportation import PickupPoint, TripLeg

NOW = "2026-09-12T04:00:00+00:00"
MASTER = "/api/v1/master-data"
STATUS_TEMPLATE = "event_status_changed"
CHOICE_TEMPLATE = "registration_choice_changed"


@pytest.fixture
def world(db: Session, make_user) -> dict:
    """Kỳ đang phân bổ. An + Bình tham gia (ca 1, xe từ điểm đón P1, xuất phát HN);
    Cường chọn ca 2, không đi xe; Dung không tham gia; Én đã huỷ; Giang chưa đăng ký."""
    hanoi = WorkLocation(code="HN", name="Văn phòng Hà Nội", city="Hà Nội", airport_code="HAN")
    event = Event(
        code="TB2026", name="Team Building 2026", destination="Phú Quốc",
        start_date="2026-10-15", end_date="2026-10-17",
        status=EventStatus.ALLOCATION_PROCESSING, terms_version="v1", is_active=True,
    )
    db.add_all([hanoi, event])
    db.flush()
    ca1 = Shift(event_id=event.id, code="CA1", name="Ca 1", earliest_departure="06:00")
    ca2 = Shift(event_id=event.id, code="CA2", name="Ca 2", display_order=2)
    leg = TripLeg(
        event_id=event.id, code="CITY_TO_AIRPORT", name="HN → Sân bay",
        direction=FlightDirection.OUTBOUND, leg_date="2026-10-15", display_order=1,
    )
    db.add_all([ca1, ca2, leg])
    db.flush()
    p1 = PickupPoint(event_id=event.id, trip_leg_id=leg.id, name="Toà nhà A", address="1 Láng Hạ")
    p2 = PickupPoint(event_id=event.id, trip_leg_id=leg.id, name="Toà nhà B", address="2 Duy Tân")
    db.add_all([p1, p2])
    db.flush()

    make_user(email="btc@company.vn", full_name="Trưởng BTC", role=UserRole.ADMIN)
    people = {
        key: make_user(email=f"{key}@company.vn", full_name=key.title())
        for key in ("an", "binh", "cuong", "dung", "en", "giang")
    }
    make_user(email="nghi@company.vn", full_name="Đã nghỉ việc", is_active=False)

    def register(key, *, shift=None, participating=True, status=RegistrationStatus.SUBMITTED,
                 pickup=None):
        registration = Registration(
            event_id=event.id, user_id=people[key].id, is_participating=participating,
            status=status, submitted_at=NOW, shift_id=shift.id if shift else None,
            departure_location_id=hanoi.id if participating else None,
        )
        db.add(registration)
        db.flush()
        if participating:
            db.add(
                RegistrationBusNeed(
                    registration_id=registration.id, trip_leg_id=leg.id,
                    needs_bus=pickup is not None, pickup_point_id=pickup.id if pickup else None,
                )
            )

    register("an", shift=ca1, pickup=p1)
    register("binh", shift=ca1, pickup=p1)
    register("cuong", shift=ca2)
    register("dung", participating=False)
    register("en", shift=ca1, pickup=p1, status=RegistrationStatus.CANCELLED)
    db.commit()
    return {
        "event_id": event.id, "ca1": ca1.id, "ca2": ca2.id, "leg": leg.id,
        "p1": p1.id, "p2": p2.id, "hanoi": hanoi.id,
    }


@pytest.fixture
def admin(world, auth_headers):
    return auth_headers("btc@company.vn")


def _change(client, admin, world, status, **extra):
    return client.post(
        f"/api/v1/events/{world['event_id']}/status",
        headers=admin,
        json={"status": status, **extra},
    )


def _recipients(db: Session, template: str) -> set[str]:
    db.expire_all()
    return set(db.scalars(select(EmailLog.to_email).where(EmailLog.template == template)))


# --- Đổi trạng thái kỳ ---


def test_status_change_emails_every_participant_only(client: TestClient, world, admin, db):
    response = _change(client, admin, world, "information_published", notify=True)
    assert response.status_code == 200, response.text

    # Không gửi: người không tham gia, người đã huỷ, người chưa đăng ký, tài khoản đã khoá.
    assert _recipients(db, STATUS_TEMPLATE) == {
        "an@company.vn", "binh@company.vn", "cuong@company.vn",
    }
    entry = db.scalars(select(EmailLog).where(EmailLog.template == STATUS_TEMPLATE)).first()
    assert "Đã công bố thông tin" in entry.subject
    assert "/my-journey" in entry.body_preview
    assert entry.related_type == "audit_log"


def test_opening_registration_emails_every_active_account(
    client: TestClient, world, admin, db: Session
):
    event = db.get(Event, world["event_id"])
    event.status = EventStatus.DRAFT
    db.commit()

    assert _change(client, admin, world, "registration_open", notify=True).status_code == 200

    recipients = _recipients(db, STATUS_TEMPLATE)
    assert {"giang@company.vn", "dung@company.vn", "an@company.vn"} <= recipients
    assert "nghi@company.vn" not in recipients


def test_backward_step_without_reason_still_notifies(client: TestClient, world, admin, db):
    """Lùi không cần lý do; có lý do thì in vào thư dưới "Ghi chú của BTC"."""
    assert _change(client, admin, world, "registration_closed", notify=True).status_code == 200
    first = db.scalars(select(EmailLog).where(EmailLog.template == STATUS_TEMPLATE)).first()
    assert "Ghi chú của BTC" not in first.body_preview

    assert _change(
        client, admin, world, "allocation_processing", reason="Đã rà xong", notify=True
    ).status_code == 200
    db.expire_all()
    latest = db.scalars(
        select(EmailLog).where(EmailLog.template == STATUS_TEMPLATE).order_by(EmailLog.id.desc())
    ).first()
    assert "Ghi chú của BTC: Đã rà xong" in latest.body_preview


def test_status_change_sends_nothing_unless_ticked(client: TestClient, world, admin, db):
    """BTC không tích "Gửi email" (mặc định) thì không gửi — tránh spam khi thử nghiệm."""
    assert _change(client, admin, world, "registration_closed").status_code == 200
    assert _change(client, admin, world, "allocation_processing", notify=False).status_code == 200
    assert _recipients(db, STATUS_TEMPLATE) == set()


def test_failed_status_email_resends_only_while_status_holds(
    client: TestClient, world, admin, db: Session
):
    _change(client, admin, world, "information_published", notify=True)
    db.expire_all()
    rows = db.scalars(select(EmailLog).where(EmailLog.template == STATUS_TEMPLATE)).all()
    for row in rows:
        row.status = EmailStatus.FAILED
    db.commit()
    first_id, second_id = rows[0].id, rows[1].id

    resent = client.post(
        "/api/v1/admin/email-logs/resend", headers=admin, json={"ids": [first_id]}
    ).json()
    assert resent["queued"] == 1

    # Kỳ đã lùi về phân bổ: thư "đã công bố" giờ báo sai tình hình.
    _change(client, admin, world, "allocation_processing", notify=False)
    outdated = client.post(
        "/api/v1/admin/email-logs/resend", headers=admin, json={"ids": [second_id]}
    ).json()
    assert outdated["skipped"][0]["reason"] == "no_longer_relevant"


# --- BTC sửa mục CBNV đã chọn ---


def test_shift_change_emails_people_on_that_shift(client: TestClient, world, admin, db):
    response = client.patch(
        f"{MASTER}/shifts/{world['ca1']}?notify=true",
        headers=admin,
        json={"earliest_departure": "08:00", "name": "Ca sáng"},
    )
    assert response.status_code == 200, response.text

    assert _recipients(db, CHOICE_TEMPLATE) == {"an@company.vn", "binh@company.vn"}
    entry = db.scalars(select(EmailLog).where(EmailLog.template == CHOICE_TEMPLATE)).first()
    assert "Giờ bay sớm nhất: 06:00 → 08:00" in entry.body_preview
    assert "Tên ca: Ca 1 → Ca sáng" in entry.body_preview


def test_master_data_change_sends_nothing_unless_ticked(client: TestClient, world, admin, db):
    response = client.patch(
        f"{MASTER}/shifts/{world['ca1']}", headers=admin, json={"earliest_departure": "09:00"}
    )
    assert response.status_code == 200, response.text
    assert _recipients(db, CHOICE_TEMPLATE) == set()


def test_invisible_field_change_sends_nothing(client: TestClient, world, admin, db: Session):
    """Đổi thứ tự hiển thị thì CBNV không thấy gì khác — không làm phiền."""
    client.patch(f"{MASTER}/shifts/{world['ca1']}?notify=true", headers=admin, json={"display_order": 9})
    client.patch(f"{MASTER}/shifts/{world['ca1']}?notify=true", headers=admin, json={"name": "Ca 1"})
    assert _recipients(db, CHOICE_TEMPLATE) == set()


def test_pickup_point_change_emails_only_its_riders(client: TestClient, world, admin, db):
    client.patch(f"{MASTER}/pickup-points/{world['p2']}?notify=true", headers=admin, json={"address": "Mới"})
    assert _recipients(db, CHOICE_TEMPLATE) == set()  # không ai chọn điểm B

    client.patch(
        f"{MASTER}/pickup-points/{world['p1']}?notify=true", headers=admin, json={"address": "99 Trần Duy Hưng"}
    )
    assert _recipients(db, CHOICE_TEMPLATE) == {"an@company.vn", "binh@company.vn"}


def test_trip_leg_and_departure_location_changes_notify(client: TestClient, world, admin, db):
    client.patch(f"{MASTER}/trip-legs/{world['leg']}?notify=true", headers=admin, json={"leg_date": "2026-10-14"})
    assert _recipients(db, CHOICE_TEMPLATE) == {"an@company.vn", "binh@company.vn"}

    client.patch(
        f"{MASTER}/work-locations/{world['hanoi']}?notify=true", headers=admin, json={"airport_code": "VDO"}
    )
    db.expire_all()
    departure = db.scalars(
        select(EmailLog.to_email).where(
            EmailLog.template == CHOICE_TEMPLATE, EmailLog.subject.contains("địa điểm xuất phát")
        )
    ).all()
    assert set(departure) == {"an@company.vn", "binh@company.vn", "cuong@company.vn"}


def test_choice_email_resend_skips_people_who_switched(client: TestClient, world, admin, db):
    client.patch(f"{MASTER}/shifts/{world['ca1']}?notify=true", headers=admin, json={"name": "Ca sáng"})
    db.expire_all()
    rows = {
        row.to_email: row
        for row in db.scalars(select(EmailLog).where(EmailLog.template == CHOICE_TEMPLATE))
    }
    for row in rows.values():
        row.status = EmailStatus.FAILED
    # Bình đã đổi sang ca 2 — thư "ca 1 đổi giờ" không còn liên quan tới Bình.
    binh = db.scalars(
        select(Registration).join(Registration.user).where(Registration.user.has(email="binh@company.vn"))
    ).one()
    binh.shift_id = world["ca2"]
    db.commit()

    body = client.post("/api/v1/admin/email-logs/resend", headers=admin, json={}).json()
    assert body["queued"] == 1
    assert body["skipped"] == [
        {
            "id": rows["binh@company.vn"].id,
            "reason": "no_longer_relevant",
            "message": body["skipped"][0]["message"],
        }
    ]
