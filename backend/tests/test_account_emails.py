"""Email tài khoản chỉ gửi sau khi ghi thật và không để mật khẩu trong nhật ký."""

from io import BytesIO

import pytest
from openpyxl import Workbook
from sqlalchemy import select

from app.core.config import settings
from app.models import EmailLog, Event, User
from app.models.enums import EmailStatus, EventStatus, UserRole
from app.services import email_service

URL = "/api/v1/admin/users"


@pytest.fixture
def account_world(db, make_user, auth_headers, monkeypatch):
    make_user(email="btc@company.vn", role=UserRole.ADMIN)
    employee = make_user(email="old@company.vn", employee_code="NV_OLD")
    event = Event(
        code="EMAIL_TEST",
        name="Email test",
        start_date="2026-10-15",
        end_date="2026-10-17",
        status=EventStatus.REGISTRATION_OPEN,
        is_active=True,
    )
    db.add(event)
    db.commit()
    sent = []
    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "SMTP_HOST", "mailpit")
    monkeypatch.setattr(email_service, "_deliver", lambda **kwargs: sent.append(kwargs))
    return auth_headers("btc@company.vn"), employee.id, sent


def import_file():
    book = Workbook()
    book.active.append(["Mã NV", "Họ tên", "Email"])
    book.active.append(["NV_OLD", "Cập nhật", "old@company.vn"])
    book.active.append(["NV_NEW", "Người mới", "new@company.vn"])
    stream = BytesIO()
    book.save(stream)
    return {
        "file": (
            "users.xlsx",
            stream.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }


@pytest.mark.parametrize("operation", ["create", "reset", "import"])
def test_credentials_email_and_redacted_logs(client, db, account_world, operation, caplog):
    headers, user_id, sent = account_world
    if operation == "create":
        response = client.post(
            URL,
            headers=headers,
            json={"employee_code": "NV_NEW", "full_name": "Người mới", "email": "new@company.vn"},
        )
        assert response.status_code == 201, response.text
        password = response.json()["temporary_password"]
    elif operation == "reset":
        response = client.post(f"{URL}/{user_id}/reset-password", headers=headers)
        assert response.status_code == 200, response.text
        password = response.json()["temporary_password"]
    else:
        preview = client.post(f"{URL}/import", headers=headers, files=import_file())
        assert preview.status_code == 200
        assert not sent and not db.scalars(select(EmailLog)).all()
        response = client.post(
            f"{URL}/import", headers=headers, params={"dry_run": "false"}, files=import_file()
        )
        assert response.status_code == 200, response.text
        password = response.json()["created_accounts"][0]["temporary_password"]
    assert len(sent) == 1
    assert password in sent[0]["rendered"].text
    assert "/login" in sent[0]["rendered"].text
    assert "đổi mật khẩu" in sent[0]["rendered"].text
    entry = db.scalars(select(EmailLog)).one()
    assert entry.status == EmailStatus.SENT
    assert password not in entry.body_preview
    assert password not in caplog.text
    logs = client.get("/api/v1/admin/email-logs", headers=headers).json()
    assert logs["total"] == 1
    assert password not in str(logs)
    # Cập nhật tài khoản đã có không phát thêm thư mật khẩu.
    if operation == "import":
        client.post(
            f"{URL}/import", headers=headers, params={"dry_run": "false"}, files=import_file()
        )
        assert len(sent) == 1


def test_smtp_failure_keeps_created_user_and_instructs_password_reset(
    client, db, account_world, monkeypatch
):
    headers, _, _ = account_world

    def fail(**kwargs):
        raise OSError("SMTP unavailable")

    monkeypatch.setattr(email_service, "_deliver", fail)
    response = client.post(
        URL,
        headers=headers,
        json={"employee_code": "NV_NEW", "full_name": "Người mới", "email": "new@company.vn"},
    )
    assert response.status_code == 201
    assert db.scalar(select(User).where(User.email == "new@company.vn")) is not None
    entry = db.scalars(select(EmailLog)).one()
    assert entry.status == EmailStatus.FAILED
    resend = client.post(
        "/api/v1/admin/email-logs/resend", headers=headers, json={"ids": [entry.id]}
    )
    assert resend.status_code == 200, resend.text
    assert resend.json()["skipped"][0]["reason"] == "credentials_not_stored"


def test_dev_mode_does_not_log_plaintext_password(client, db, account_world, monkeypatch, caplog):
    headers, _, sent = account_world
    monkeypatch.setattr(settings, "EMAIL_ENABLED", False)
    response = client.post(
        URL,
        headers=headers,
        json={"employee_code": "NV_NEW", "full_name": "Người mới", "email": "new@company.vn"},
    )
    assert response.status_code == 201
    password = response.json()["temporary_password"]
    assert not sent
    assert password not in caplog.text
    assert password not in db.scalars(select(EmailLog)).one().body_preview
