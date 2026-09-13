"""Kiểm thử nhật ký email cho BTC và gửi lại thư lỗi."""

import json
import smtplib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.audit import AuditLog
from app.models.enums import EmailStatus, EventStatus, Gender, RegistrationStatus, UserRole
from app.models.event import Event
from app.models.notification import EmailLog
from app.models.registration import Registration
from app.services import email_service

URL = "/api/v1/admin/email-logs"
NOW = "2026-09-13T02:00:00+00:00"
CONNECTION_ERROR = "ConnectionRefusedError: refused | Không mở được kết nối tới SMTP_HOST:SMTP_PORT."


@pytest.fixture
def world(db: Session, make_user) -> dict:
    """SMTP từng sập: 5 thư lỗi, 1 thư đã gửi.

    - Nhắc Bình (thiếu CCCD) gửi tới địa chỉ cũ; hồ sơ Bình giờ đã đổi sang email thật.
    - Xác nhận đăng ký của An: một thư đã gửi, một thư lỗi (đăng ký vẫn còn) → gửi lại được.
    - Xác nhận đăng ký của Giang: Giang đã huỷ → thư "đã nhận đăng ký" không còn đúng.
    - Nhắc An thiếu giấy tờ: An đã bổ sung → không nhắc nữa.
    - Thư không gắn CBNV nào → không biết gửi cho ai.
    """
    event = Event(
        code="TB2026", name="Team Building 2026", destination="Phú Quốc",
        start_date="2026-10-15", end_date="2026-10-17", status=EventStatus.REGISTRATION_OPEN,
        registration_closes_at="2026-12-25T17:00:00+00:00", terms_version="v1", is_active=True,
    )
    db.add(event)
    db.flush()

    contact = {"phone": "0912345678", "gender": Gender.MALE}
    make_user(email="btc@company.vn", role=UserRole.ADMIN, full_name="Trưởng BTC")
    binh = make_user(
        email="vietmt231@gmail.com", full_name="Bình Thiếu CCCD", date_of_birth="1991-02-03", **contact
    )
    an = make_user(
        email="an@company.vn", full_name="An Đủ Giấy", date_of_birth="1995-01-01",
        id_card_number="001095000001", **contact,
    )
    giang = make_user(email="giang@company.vn", full_name="Giang Đã Huỷ", **contact)

    registrations = {}
    for key, user, status in [
        ("binh", binh, RegistrationStatus.SUBMITTED),
        ("an", an, RegistrationStatus.SUBMITTED),
        ("giang", giang, RegistrationStatus.CANCELLED),
    ]:
        row = Registration(
            event_id=event.id, user_id=user.id, is_participating=True, status=status, submitted_at=NOW
        )
        db.add(row)
        registrations[key] = row
    db.flush()

    def log(template, user, *, status=EmailStatus.FAILED, related_type="event", related_id=None, to_email=None):
        entry = EmailLog(
            user_id=user.id if user else None,
            to_email=to_email or (user.email if user else "ai-do@company.vn"),
            template=template, subject="Tiêu đề cũ", body_preview="Bản cũ", status=status,
            error_message=CONNECTION_ERROR if status == EmailStatus.FAILED else None,
            retry_count=0, related_type=related_type, related_id=related_id,
            sent_at=NOW if status == EmailStatus.SENT else None,
            created_at="2026-09-13T01:00:00+00:00",
        )
        db.add(entry)
        return entry

    logs = {
        "reminder_binh": log(
            "reminder_missing_documents", binh, related_id=event.id, to_email="binhd020@company.vn"
        ),
        "confirmed_an_sent": log(
            "registration_confirmed", an, status=EmailStatus.SENT,
            related_type="registration", related_id=registrations["an"].id,
        ),
        "confirmed_an_failed": log(
            "registration_confirmed", an, related_type="registration", related_id=registrations["an"].id
        ),
        "confirmed_giang": log(
            "registration_confirmed", giang,
            related_type="registration", related_id=registrations["giang"].id,
        ),
        "reminder_an": log("reminder_missing_documents", an, related_id=event.id),
        "orphan": log(
            "registration_confirmed", None, related_type="registration", related_id=registrations["an"].id
        ),
    }
    db.commit()
    return {"event_id": event.id, "logs": {key: entry.id for key, entry in logs.items()}}


@pytest.fixture
def admin(world, auth_headers):
    return auth_headers("btc@company.vn")


class FakeSMTP:
    sent: list = []

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
        FakeSMTP.sent.append(message)


# --- Quyền ---


def test_email_logs_are_admin_only(client: TestClient, world, auth_headers):
    employee = auth_headers("an@company.vn")

    assert client.get(URL, headers=employee).status_code == 403
    assert client.post(f"{URL}/resend", headers=employee, json={}).status_code == 403


# --- Xem ---


def test_list_filters_by_status_and_template(client: TestClient, admin):
    failed = client.get(URL, headers=admin, params={"status": "failed"}).json()
    reminders = client.get(URL, headers=admin, params={"template": "reminder_missing_documents"}).json()

    assert failed["total"] == 5
    assert all(item["is_dev_only"] is False for item in failed["items"])
    assert reminders["total"] == 2
    assert {item["template_label"] for item in reminders["items"]} == {"Nhắc bổ sung giấy tờ"}


def test_stats_list_every_template_label(client: TestClient, admin):
    stats = client.get(f"{URL}/stats", headers=admin).json()

    assert (stats["failed"], stats["sent"]) == (5, 1)
    # Loại chưa gửi lần nào vẫn phải có trong dropdown lọc.
    assert stats["template_labels"]["reminder_not_registered"] == "Nhắc gửi đăng ký"


def test_dev_only_rows_are_flagged(client: TestClient, admin, db: Session):
    db.add(
        EmailLog(
            to_email="a@company.vn", template="registration_confirmed", subject="x",
            status=EmailStatus.QUEUED, error_message=email_service.DEV_MODE_NOTE,
            retry_count=0, created_at=NOW,
        )
    )
    db.commit()

    items = client.get(URL, headers=admin, params={"status": "queued"}).json()["items"]

    assert items[0]["is_dev_only"] is True


# --- Gửi lại ---


def test_resend_all_failed_rebuilds_content_and_skips_outdated(
    client: TestClient, world, admin, db: Session
):
    logs = world["logs"]

    body = client.post(f"{URL}/resend", headers=admin, json={}).json()

    assert body["queued"] == 2
    assert {(item["id"], item["reason"]) for item in body["skipped"]} == {
        (logs["confirmed_giang"], "no_longer_relevant"),
        (logs["reminder_an"], "no_longer_relevant"),
        (logs["orphan"], "no_recipient"),
    }
    assert all(item["message"] for item in body["skipped"])

    db.expire_all()
    reminder = db.get(EmailLog, logs["reminder_binh"])
    # Gửi tới email HIỆN TẠI trong hồ sơ, không phải địa chỉ sai của lần gửi hỏng.
    assert reminder.to_email == "vietmt231@gmail.com"
    assert reminder.retry_count == 1
    assert "Số CCCD/Hộ chiếu" in reminder.body_preview
    # BackgroundTask đã chạy; chế độ dev chỉ ghi chú, không gửi thật.
    assert reminder.status == EmailStatus.QUEUED
    assert reminder.error_message == email_service.DEV_MODE_NOTE

    assert db.get(EmailLog, logs["confirmed_an_failed"]).retry_count == 1
    assert db.get(EmailLog, logs["confirmed_giang"]).status == EmailStatus.FAILED

    audit = db.query(AuditLog).filter_by(action="email.resent").one()
    assert json.loads(audit.after_data)["queued"] == 2


def test_resend_touches_only_failed_rows_once(client: TestClient, world, admin, db: Session):
    logs = world["logs"]

    first = client.post(
        f"{URL}/resend",
        headers=admin,
        json={"ids": [logs["reminder_binh"], logs["confirmed_an_sent"], 999999]},
    ).json()
    second = client.post(f"{URL}/resend", headers=admin, json={"ids": [logs["reminder_binh"]]}).json()

    assert first["queued"] == 1
    assert {(item["id"], item["reason"]) for item in first["skipped"]} == {
        (logs["confirmed_an_sent"], "not_failed"),
        (999999, "not_found"),
    }
    # Bấm gửi lại lần hai: dòng đã sang "queued" nên không gửi trùng.
    assert second["queued"] == 0
    assert second["skipped"][0]["reason"] == "not_failed"
    db.expire_all()
    assert db.query(AuditLog).filter_by(action="email.resent").count() == 1


def test_resend_delivers_over_smtp(client: TestClient, world, admin, db: Session, monkeypatch):
    FakeSMTP.sent = []
    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "SMTP_HOST", "127.0.0.1")
    monkeypatch.setattr(settings, "SMTP_PORT", 1025)
    monkeypatch.setattr(settings, "SMTP_STARTTLS", False)
    monkeypatch.setattr(settings, "SMTP_USER", "")
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)

    client.post(f"{URL}/resend", headers=admin, json={"ids": [world["logs"]["reminder_binh"]]})

    db.expire_all()
    entry = db.get(EmailLog, world["logs"]["reminder_binh"])
    assert entry.status == EmailStatus.SENT
    assert entry.sent_at is not None
    assert entry.error_message is None
    assert FakeSMTP.sent[0]["To"] == "vietmt231@gmail.com"


def test_resent_reminder_counts_for_cooldown(client: TestClient, world, admin):
    client.post(f"{URL}/resend", headers=admin, json={"ids": [world["logs"]["reminder_binh"]]})

    preview = client.get("/api/v1/admin/reminders/missing_documents", headers=admin).json()
    people = {person["full_name"]: person for person in preview["recipients"]}

    assert people["Bình Thiếu CCCD"]["recently_reminded"] is True


def test_too_many_ids_are_rejected(client: TestClient, admin):
    response = client.post(f"{URL}/resend", headers=admin, json={"ids": list(range(1, 502))})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "TOO_MANY_EMAILS"
