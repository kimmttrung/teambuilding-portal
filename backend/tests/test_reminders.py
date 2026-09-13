"""Kiểm thử email nhắc việc BTC gửi chủ động (thiếu giấy tờ, chưa đăng ký)."""

import json
import smtplib
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.timeutils import iso_in
from app.models.audit import AuditLog
from app.models.enums import EmailStatus, EventStatus, Gender, RegistrationStatus, UserRole
from app.models.event import Event
from app.models.notification import EmailLog
from app.models.org import Team
from app.models.registration import Registration
from app.services import email_service, email_templates

URL = "/api/v1/admin/reminders"
NOW = "2026-09-13T02:00:00+00:00"


@pytest.fixture
def world(db: Session, make_user) -> dict:
    """Kỳ đang mở đăng ký.

    Tham gia: An (đủ giấy tờ), Bình (thiếu CCCD), Cường (thiếu cả CCCD lẫn ngày sinh).
    Dũng không tham gia (thiếu giấy tờ cũng không cần nhắc). Giang đã huỷ (đã phản hồi).
    Hà chưa đăng ký. Khánh đã nghỉ việc (tài khoản khoá, không nhắc).
    """
    event = Event(
        code="TB2026", name="Team Building 2026", destination="Phú Quốc",
        start_date="2026-10-15", end_date="2026-10-17", status=EventStatus.REGISTRATION_OPEN,
        registration_closes_at="2026-12-25T17:00:00+00:00", terms_version="v1", is_active=True,
    )
    team = Team(code="IT-HN", name="Công nghệ")
    db.add_all([event, team])
    db.flush()

    contact = {"phone": "0912345678", "gender": Gender.MALE}
    make_user(email="btc@company.vn", role=UserRole.ADMIN, full_name="Trưởng BTC", **contact)
    users = {
        "an": make_user(
            email="an@company.vn", full_name="An Đủ Giấy", team_id=team.id,
            date_of_birth="1995-01-01", id_card_number="001095000001", **contact,
        ),
        "binh": make_user(
            email="binh@company.vn", full_name="Bình Thiếu CCCD", team_id=team.id,
            date_of_birth="1991-02-03", **contact,
        ),
        "cuong": make_user(email="cuong@company.vn", full_name="Cường Thiếu Hai", **contact),
        "dung": make_user(email="dung@company.vn", full_name="Dũng Không Đi", **contact),
        "giang": make_user(email="giang@company.vn", full_name="Giang Đã Huỷ", **contact),
        "ha": make_user(email="ha@company.vn", full_name="Hà Chưa Đăng Ký", **contact),
    }
    make_user(email="khanh@company.vn", full_name="Khánh Đã Nghỉ", is_active=False)

    for key, participating, status in [
        ("an", True, RegistrationStatus.SUBMITTED),
        ("binh", True, RegistrationStatus.SUBMITTED),
        ("cuong", True, RegistrationStatus.SUBMITTED),
        ("dung", False, RegistrationStatus.SUBMITTED),
        ("giang", True, RegistrationStatus.CANCELLED),
    ]:
        db.add(
            Registration(
                event_id=event.id, user_id=users[key].id, is_participating=participating,
                status=status, submitted_at=NOW,
            )
        )
    db.commit()
    return {"event_id": event.id, "ids": {key: user.id for key, user in users.items()}}


@pytest.fixture
def admin(world, auth_headers):
    return auth_headers("btc@company.vn")


def _reminder_log(world, key, *, status, created_at, related_id=None) -> EmailLog:
    return EmailLog(
        user_id=world["ids"][key], to_email=f"{key}@company.vn",
        template="reminder_missing_documents", subject="Nhắc", status=status, retry_count=0,
        related_type="event", related_id=related_id or world["event_id"], created_at=created_at,
    )


# --- Quyền ---


def test_reminders_are_admin_only(client: TestClient, world, auth_headers):
    employee = auth_headers("an@company.vn")

    assert client.get(f"{URL}/missing_documents", headers=employee).status_code == 403
    assert client.post(f"{URL}/missing_documents", headers=employee, json={}).status_code == 403


def test_unknown_kind_is_rejected(client: TestClient, admin):
    assert client.get(f"{URL}/everyone", headers=admin).status_code == 422


# --- Xem trước ---


def test_preview_missing_documents_matches_dashboard(client: TestClient, admin):
    body = client.get(f"{URL}/missing_documents", headers=admin).json()
    dashboard = client.get("/api/v1/admin/dashboard", headers=admin).json()

    assert [person["full_name"] for person in body["recipients"]] == [
        "Bình Thiếu CCCD",
        "Cường Thiếu Hai",
    ]
    assert body["recipients"][0]["missing_fields"] == ["Số CCCD/Hộ chiếu"]
    assert body["recipients"][1]["missing_fields"] == ["Ngày sinh", "Số CCCD/Hộ chiếu"]
    assert (body["can_send"], body["sendable"], body["email_enabled"]) == (True, 2, False)
    # Con số trên dashboard và số người trong hộp thoại gửi phải là một.
    assert body["total"] == dashboard["registrations"]["missing_flight_documents"]


def test_preview_not_registered_skips_cancelled_and_inactive(client: TestClient, admin):
    body = client.get(f"{URL}/not_registered", headers=admin).json()
    dashboard = client.get("/api/v1/admin/dashboard", headers=admin).json()

    assert [person["full_name"] for person in body["recipients"]] == ["Hà Chưa Đăng Ký", "Trưởng BTC"]
    assert body["recipients"][0]["missing_fields"] == []
    assert body["total"] == dashboard["registrations"]["not_submitted"]


# --- Gửi ---


def test_send_queues_one_email_per_person_and_audits(
    client: TestClient, world, admin, db: Session
):
    response = client.post(f"{URL}/missing_documents", headers=admin, json={})

    assert response.status_code == 200, response.text
    assert response.json() == {
        "kind": "missing_documents", "queued": 2, "skipped": [], "email_enabled": False,
    }

    db.expire_all()
    logs = db.query(EmailLog).order_by(EmailLog.id).all()
    assert [log.to_email for log in logs] == ["binh@company.vn", "cuong@company.vn"]
    assert {(log.template, log.related_type, log.related_id) for log in logs} == {
        ("reminder_missing_documents", "event", world["event_id"])
    }
    # BackgroundTask đã chạy sau response: chế độ dev ghi chú lại thay vì gửi thật.
    assert all(log.error_message == email_service.DEV_MODE_NOTE for log in logs)

    body = logs[0].body_preview
    assert "Số CCCD/Hộ chiếu" in body
    assert "/profile" in body
    # Chỉ nêu TÊN trường thiếu, không bao giờ nêu giá trị hồ sơ đang có.
    assert "1991" not in body

    audit = db.query(AuditLog).filter_by(action="reminder.sent").one()
    assert json.loads(audit.after_data)["queued"] == 2
    assert sorted(json.loads(audit.after_data)["user_ids"]) == sorted(
        [world["ids"]["binh"], world["ids"]["cuong"]]
    )


def test_second_click_within_cooldown_sends_nothing(client: TestClient, admin, db: Session):
    client.post(f"{URL}/missing_documents", headers=admin, json={})
    again = client.post(f"{URL}/missing_documents", headers=admin, json={}).json()
    preview = client.get(f"{URL}/missing_documents", headers=admin).json()

    assert again["queued"] == 0
    assert {item["reason"] for item in again["skipped"]} == {"recently_reminded"}
    assert preview["sendable"] == 0
    assert all(person["recently_reminded"] for person in preview["recipients"])

    forced = client.post(
        f"{URL}/missing_documents", headers=admin, json={"include_recently_reminded": True}
    ).json()

    assert forced["queued"] == 2
    db.expire_all()
    assert db.query(EmailLog).count() == 4
    # Lần bấm không gửi được gì thì không ghi audit — nhật ký chỉ ghi việc thật sự xảy ra.
    assert db.query(AuditLog).filter_by(action="reminder.sent").count() == 2


def test_failed_old_or_other_event_reminders_do_not_block(
    client: TestClient, world, admin, db: Session
):
    db.add_all(
        [
            _reminder_log(world, "binh", status=EmailStatus.FAILED, created_at=iso_in(hours=-1)),
            _reminder_log(
                world, "binh", status=EmailStatus.SENT, created_at=iso_in(hours=-1),
                related_id=world["event_id"] + 100,
            ),
            _reminder_log(world, "cuong", status=EmailStatus.SENT, created_at=iso_in(hours=-30)),
        ]
    )
    db.commit()

    preview = client.get(f"{URL}/missing_documents", headers=admin).json()
    people = {person["full_name"]: person for person in preview["recipients"]}

    assert people["Bình Thiếu CCCD"]["last_reminded_at"] is None
    assert people["Cường Thiếu Hai"]["last_reminded_at"] is not None
    assert people["Cường Thiếu Hai"]["recently_reminded"] is False
    assert preview["sendable"] == 2


def test_send_only_to_selected_people(client: TestClient, world, admin):
    ids = world["ids"]
    body = client.post(
        f"{URL}/missing_documents",
        headers=admin,
        json={"user_ids": [ids["binh"], ids["an"], ids["binh"]]},
    ).json()

    assert body["queued"] == 1
    # An đã đủ giấy tờ: không nằm trong nhóm cần nhắc, dù BTC gửi id lên.
    assert body["skipped"] == [{"user_id": ids["an"], "full_name": None, "reason": "not_eligible"}]


def test_not_registered_only_while_registration_open(
    client: TestClient, world, admin, db: Session
):
    db.get(Event, world["event_id"]).status = EventStatus.REGISTRATION_CLOSED
    db.commit()

    preview = client.get(f"{URL}/not_registered", headers=admin).json()
    response = client.post(f"{URL}/not_registered", headers=admin, json={})

    assert preview["can_send"] is False
    assert "mở đăng ký" in preview["blocked_reason"]
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "REMINDER_NOT_ALLOWED"
    db.expire_all()
    assert db.query(EmailLog).count() == 0


def test_queued_reminder_is_delivered_over_smtp(
    client: TestClient, world, admin, db: Session, monkeypatch
):
    sent = []

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def ehlo(self):
            pass

        def starttls(self):
            pass

        def login(self, user, password):
            pass

        def send_message(self, message):
            sent.append(message)

    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "SMTP_HOST", "127.0.0.1")
    monkeypatch.setattr(settings, "SMTP_PORT", 1025)
    monkeypatch.setattr(settings, "SMTP_STARTTLS", False)
    monkeypatch.setattr(settings, "SMTP_USER", "")
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)

    response = client.post(
        f"{URL}/missing_documents", headers=admin, json={"user_ids": [world["ids"]["binh"]]}
    )

    assert response.json()["email_enabled"] is True
    db.expire_all()
    log = db.query(EmailLog).one()
    assert log.status == EmailStatus.SENT
    assert log.sent_at is not None
    assert sent[0]["To"] == "binh@company.vn"
    html = sent[0].get_body(preferencelist=("html",)).get_content()
    assert "/profile" in html


def test_delivery_skips_rows_no_longer_queued(client: TestClient, world, db: Session):
    """Task gửi bị gọi lại (hoặc dòng đã xử lý) thì không gửi lần hai."""
    entry = _reminder_log(world, "binh", status=EmailStatus.SENT, created_at=NOW)
    entry.sent_at = NOW
    db.add(entry)
    db.commit()

    email_service.deliver_queued_async(log_id=entry.id, context={})

    db.expire_all()
    assert db.get(EmailLog, entry.id).sent_at == NOW


# --- Template ---


def test_reminder_templates_escape_input_and_show_vietnam_time():
    context = email_templates.reminder_context(
        event=SimpleNamespace(
            name="Team Building <2026>", code="TB2026", destination="Phú Quốc",
            start_date="2026-10-15", end_date="2026-10-17",
            registration_closes_at="2026-09-25T10:00:00+00:00",
        ),
        user=SimpleNamespace(display_name=None, full_name="Bình <script>"),
        missing_fields=["Số CCCD/Hộ chiếu"],
    )

    missing = email_templates.render("reminder_missing_documents", context)
    not_registered = email_templates.render("reminder_not_registered", context)

    assert "<script>" not in missing.html
    assert "&lt;script&gt;" in missing.html
    assert "Số CCCD/Hộ chiếu" in missing.text
    # Hạn đăng ký lưu UTC, email cho CBNV đọc phải là giờ Việt Nam (+7).
    assert "25/09/2026 17:00" in not_registered.text
    assert "/register-event" in not_registered.text
