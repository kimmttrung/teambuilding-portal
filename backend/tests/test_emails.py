"""Kiểm thử email service, template và nhật ký email."""

import smtplib
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Event, EmailLog, Registration, Shift, TripLeg, WorkLocation
from app.models.enums import EmailStatus, EventStatus, FlightDirection, Gender, UserRole
from app.services import email_service, email_templates


# --- Dữ liệu mẫu ---


@pytest.fixture
def setup(db: Session) -> dict:
    event = Event(
        code="TB2026",
        name="Team Building 2026",
        destination="Phú Quốc",
        start_date="2026-10-15",
        end_date="2026-10-17",
        status=EventStatus.REGISTRATION_OPEN,
        registration_closes_at="2026-12-25T17:00:00+00:00",
        terms_version="v1",
        terms_content="Quy định...",
        is_active=True,
    )
    location = WorkLocation(code="HN", name="Hà Nội", airport_code="HAN")
    db.add_all([event, location])
    db.flush()

    shift = Shift(event_id=event.id, code="CA1", name="Ca 1 – bay sáng", display_order=1)
    leg = TripLeg(
        event_id=event.id,
        code="CITY_TO_AIRPORT",
        name="HN → Sân bay",
        direction=FlightDirection.OUTBOUND,
        display_order=1,
    )
    db.add_all([shift, leg])
    db.commit()
    return {"event": event, "location": location, "shift": shift, "leg": leg}


@pytest.fixture
def employee(make_user, setup):
    return make_user(
        email="nv@company.vn",
        password="MatKhau123",
        work_location_id=setup["location"].id,
        phone="0912345678",
        gender=Gender.MALE,
        date_of_birth="1995-03-20",
        id_card_number="001095012345",
    )


@pytest.fixture
def registration(db: Session, setup, employee) -> Registration:
    row = Registration(
        event_id=setup["event"].id,
        user_id=employee.id,
        is_participating=True,
        shift_id=setup["shift"].id,
        wish_note="Mong được ở cùng phòng với anh Nam",
        submitted_at="2026-09-12T03:00:00+00:00",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def context_of(setup, employee, registration, **overrides) -> dict:
    data = email_templates.registration_context(
        event=setup["event"], user=employee, registration=registration
    )
    data.update(overrides)
    return data


# --- Template ---


def test_confirmed_template_has_event_shift_and_links(setup, employee, registration):
    rendered = email_templates.render(
        "registration_confirmed", context_of(setup, employee, registration)
    )

    assert "TB2026" in rendered.subject
    for expected in ("Team Building 2026", "Phú Quốc", "Ca 1 – bay sáng", "15/10/2026"):
        assert expected in rendered.text
    # Hạn đăng ký phải hiện theo giờ Việt Nam: 17:00 UTC = 00:00 ngày hôm sau.
    assert "26/12/2026 00:00" in rendered.text
    assert "/my-journey" in rendered.text
    assert "<html" in rendered.html


def test_template_never_leaks_personal_documents(setup, employee, registration):
    """CCCD, ngày sinh, ghi chú sức khoẻ không được đi qua email (docs/09-security.md §4)."""
    rendered = email_templates.render(
        "registration_confirmed", context_of(setup, employee, registration)
    )

    assert employee.id_card_number not in rendered.text
    assert employee.id_card_number not in rendered.html
    assert employee.date_of_birth not in rendered.text


def test_missing_profile_fields_are_named_not_valued(setup, employee, registration):
    rendered = email_templates.render(
        "registration_confirmed",
        context_of(setup, employee, registration, missing_profile_fields=["Số CCCD/Hộ chiếu"]),
    )

    assert "Số CCCD/Hộ chiếu" in rendered.text
    assert "/profile" in rendered.text


def test_user_input_is_escaped_in_html(setup, employee, registration, db: Session):
    """Ghi chú của CBNV là dữ liệu người dùng nhập — phải escape trước khi vào HTML."""
    registration.wish_note = '<script>alert("xss")</script>'
    db.commit()

    rendered = email_templates.render(
        "registration_confirmed", context_of(setup, employee, registration)
    )

    assert "<script>" not in rendered.html
    assert "&lt;script&gt;" in rendered.html


def test_cancelled_template_mentions_penalty_only_when_applied(setup, employee, registration):
    without = email_templates.render(
        "registration_cancelled",
        context_of(setup, employee, registration, cancel_reason="Trùng lịch công tác"),
    )
    with_penalty = email_templates.render(
        "registration_cancelled",
        context_of(
            setup, employee, registration, cancel_reason="Trùng lịch", penalty_applied=True
        ),
    )

    assert "chi phí" not in without.text.split("* ")[0]
    assert "chi phí vé máy bay" in with_penalty.text
    assert "Trùng lịch công tác" in without.text


def test_render_unknown_template_raises(setup, employee, registration):
    with pytest.raises(email_templates.UnknownTemplateError):
        email_templates.render("khong_ton_tai", context_of(setup, employee, registration))


# --- Gửi và ghi nhật ký ---


def test_dev_mode_logs_without_sending(
    db: Session, setup, employee, registration, monkeypatch
):
    """EMAIL_ENABLED=false: vẫn ghi nhật ký + nội dung, nhưng không gọi SMTP."""
    monkeypatch.setattr(settings, "EMAIL_ENABLED", False)

    def _explode(*_args, **_kwargs):
        raise AssertionError("Không được gọi SMTP khi EMAIL_ENABLED=false")

    monkeypatch.setattr(smtplib, "SMTP", _explode)

    entry = email_service.send(
        db,
        template="registration_confirmed",
        to_email=employee.email,
        context=context_of(setup, employee, registration),
        user_id=employee.id,
        related_type="registration",
        related_id=registration.id,
    )

    assert entry.status == EmailStatus.QUEUED
    assert entry.error_message == email_service.DEV_MODE_NOTE
    assert "Team Building 2026" in entry.body_preview
    assert entry.sent_at is None
    assert entry.related_id == registration.id


def test_sends_over_smtp_and_marks_sent(
    db: Session, setup, employee, registration, monkeypatch
):
    sent_messages = []

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            sent_messages.append({"host": host, "port": port})

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def ehlo(self):
            pass

        def starttls(self):
            sent_messages[-1]["starttls"] = True

        def login(self, user, password):
            sent_messages[-1]["login"] = user

        def send_message(self, message):
            sent_messages[-1]["message"] = message

    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.test.vn")
    monkeypatch.setattr(settings, "SMTP_PORT", 587)
    monkeypatch.setattr(settings, "SMTP_STARTTLS", True)
    monkeypatch.setattr(settings, "SMTP_USER", "btc@company.vn")
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)

    entry = email_service.send(
        db,
        template="registration_confirmed",
        to_email=employee.email,
        context=context_of(setup, employee, registration),
        user_id=employee.id,
    )

    assert entry.status == EmailStatus.SENT
    assert entry.sent_at is not None
    assert entry.error_message is None

    call = sent_messages[0]
    assert call["host"] == "smtp.test.vn"
    assert call["starttls"] is True
    assert call["login"] == "btc@company.vn"
    # Gửi cả bản text và bản HTML để client nào cũng đọc được.
    assert call["message"].get_content_type() == "multipart/alternative"
    assert call["message"]["To"] == employee.email


def test_starttls_can_be_disabled_for_local_smtp(
    db: Session, setup, employee, registration, monkeypatch
):
    """SMTP local (Mailpit/MailHog) và relay nội bộ cổng 25 không nói TLS —
    gọi STARTTLS là lỗi ngay lúc bắt tay, nên cờ này phải thực sự tắt được."""
    calls = []

    class FakeSMTP:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def ehlo(self):
            calls.append("ehlo")

        def starttls(self):
            calls.append("starttls")

        def send_message(self, _message):
            calls.append("send")

    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "SMTP_HOST", "127.0.0.1")
    monkeypatch.setattr(settings, "SMTP_PORT", 1025)
    monkeypatch.setattr(settings, "SMTP_STARTTLS", False)
    monkeypatch.setattr(settings, "SMTP_USER", "")
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)

    entry = email_service.send(
        db,
        template="registration_confirmed",
        to_email=employee.email,
        context=context_of(setup, employee, registration),
    )

    assert entry.status == EmailStatus.SENT
    assert "starttls" not in calls
    assert calls == ["ehlo", "send"]


def test_smtp_failure_is_recorded_not_raised(
    db: Session, setup, employee, registration, monkeypatch
):
    """SMTP hỏng không được thành exception — đăng ký đã thành công từ trước đó."""

    def _fail(*_args, **_kwargs):
        raise smtplib.SMTPConnectError(421, "Service not available")

    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.test.vn")
    monkeypatch.setattr(smtplib, "SMTP", _fail)

    entry = email_service.send(
        db,
        template="registration_confirmed",
        to_email=employee.email,
        context=context_of(setup, employee, registration),
    )

    assert entry.status == EmailStatus.FAILED
    assert "SMTPConnectError" in entry.error_message
    assert entry.sent_at is None


def test_auth_failure_explains_app_password(
    db: Session, setup, employee, registration, monkeypatch
):
    """535 của Gmail nói về tài khoản GỬI, không phải địa chỉ người nhận — lỗi thô
    dễ bị hiểu sai, nên dòng nhật ký phải kèm cách sửa."""

    def _reject_login(*_args, **_kwargs):
        raise smtplib.SMTPAuthenticationError(
            535, b"5.7.8 Username and Password not accepted. BadCredentials"
        )

    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setattr(smtplib, "SMTP", _reject_login)

    entry = email_service.send(
        db,
        template="registration_confirmed",
        to_email=employee.email,
        context=context_of(setup, employee, registration),
    )

    assert entry.status == EmailStatus.FAILED
    assert "App Password" in entry.error_message
    assert "người nhận" in entry.error_message


def test_connection_error_suggests_port_or_local_smtp():
    hint = email_service.explain_smtp_error(ConnectionRefusedError("refused"))
    assert "465" in hint


def test_unknown_smtp_error_has_no_invented_hint():
    assert email_service.explain_smtp_error(RuntimeError("chuyện gì đó khác")) is None


def test_enabled_without_host_is_marked_failed(
    db: Session, setup, employee, registration, monkeypatch
):
    monkeypatch.setattr(settings, "EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "SMTP_HOST", "")

    entry = email_service.send(
        db,
        template="registration_confirmed",
        to_email=employee.email,
        context=context_of(setup, employee, registration),
    )

    assert entry.status == EmailStatus.FAILED
    assert entry.error_message == email_service.NO_SMTP_HOST_NOTE


def test_send_skips_user_without_email(db: Session, setup, employee, registration):
    entry = email_service.send(
        db,
        template="registration_confirmed",
        to_email="",
        context=context_of(setup, employee, registration),
    )

    assert entry is None
    assert db.query(EmailLog).count() == 0


def test_send_async_swallows_errors(db: Session):
    """Background task không bao giờ được ném lỗi ra ngoài."""
    email_service.send_async(template="khong_ton_tai", to_email="a@b.vn", context={})

    assert db.query(EmailLog).count() == 0


# --- Gắn vào luồng đăng ký ---


def payload(setup) -> dict:
    return {
        "is_participating": True,
        "shift_id": setup["shift"].id,
        "bus_needs": [{"trip_leg_id": setup["leg"].id, "needs_bus": False}],
        "agreed_terms_version": "v1",
    }


def test_submit_registration_queues_confirmation_email(
    client: TestClient, setup, employee, auth_headers, db: Session
):
    headers = auth_headers("nv@company.vn")

    response = client.post("/api/v1/registrations", headers=headers, json=payload(setup))
    assert response.status_code == 201

    entry = db.query(EmailLog).one()
    assert entry.template == "registration_confirmed"
    assert entry.to_email == "nv@company.vn"
    assert entry.user_id == employee.id
    assert entry.related_type == "registration"
    assert "Ca 1 – bay sáng" in entry.body_preview


def test_update_and_cancel_queue_their_own_emails(
    client: TestClient, setup, employee, auth_headers, db: Session
):
    headers = auth_headers("nv@company.vn")
    client.post("/api/v1/registrations", headers=headers, json=payload(setup))

    client.patch("/api/v1/registrations/me", headers=headers, json={"wish_note": "Đổi ý"})
    client.post(
        "/api/v1/registrations/me/cancel", headers=headers, json={"reason": "Trùng lịch"}
    )

    templates = [row.template for row in db.query(EmailLog).order_by(EmailLog.id).all()]
    assert templates == [
        "registration_confirmed",
        "registration_updated",
        "registration_cancelled",
    ]


# --- Nhật ký cho BTC ---


def test_admin_lists_and_filters_email_logs(
    client: TestClient, setup, employee, make_user, auth_headers, db: Session
):
    make_user(email="btc@company.vn", password="MatKhau123", role=UserRole.ADMIN)
    employee_headers = auth_headers("nv@company.vn")
    client.post("/api/v1/registrations", headers=employee_headers, json=payload(setup))

    admin_headers = auth_headers("btc@company.vn")
    response = client.get("/api/v1/admin/email-logs", headers=admin_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["template_label"] == "Xác nhận đăng ký"
    assert body["items"][0]["status"] == "queued"

    filtered = client.get(
        "/api/v1/admin/email-logs?status=sent", headers=admin_headers
    )
    assert filtered.json()["total"] == 0

    stats = client.get("/api/v1/admin/email-logs/stats", headers=admin_headers)
    assert stats.json()["queued"] == 1
    assert stats.json()["by_template"] == {"registration_confirmed": 1}


def test_employee_cannot_read_email_logs(
    client: TestClient, setup, employee, auth_headers
):
    response = client.get("/api/v1/admin/email-logs", headers=auth_headers("nv@company.vn"))
    assert response.status_code == 403


def test_registration_context_has_no_orm_objects(setup, employee, registration):
    """Context phải là dict thuần: background task chạy sau khi session đã đóng."""
    context = email_templates.registration_context(
        event=setup["event"], user=employee, registration=registration
    )

    assert all(
        not hasattr(value, "_sa_instance_state")
        for value in context.values()
        if not isinstance(value, SimpleNamespace)
    )
    assert isinstance(context["bus_lines"], list)


def test_email_log_and_stats_follow_selected_event(
    client: TestClient, setup, employee, make_user, auth_headers, db: Session
):
    """Lỗi test tay: đổi sang kỳ khác, nhật ký và ô Email vẫn đếm thư của kỳ cũ."""
    make_user(email="btc@company.vn", password="MatKhau123", role=UserRole.ADMIN)
    client.post(
        "/api/v1/registrations", headers=auth_headers("nv@company.vn"), json=payload(setup)
    )

    other = Event(
        code="TB2027",
        name="Team Building 2027 – Đà Nẵng",
        start_date="2027-04-15",
        end_date="2027-04-17",
        status=EventStatus.REGISTRATION_OPEN,
        terms_version="v1",
        is_active=False,
    )
    db.add(other)
    db.commit()

    admin_headers = auth_headers("btc@company.vn")
    assert db.query(EmailLog).filter_by(event_id=setup["event"].id).count() == 1

    # Kỳ đang chọn = TB2026: thấy đúng thư của mình.
    current = client.get("/api/v1/admin/email-logs", headers=admin_headers)
    assert current.json()["total"] == 1
    stats = client.get("/api/v1/admin/email-logs/stats", headers=admin_headers)
    assert stats.json()["total"] == 1

    # Đổi sang TB2027: chưa phát sinh thư nào nên phải trống, không mượn thư của TB2026.
    switched = {**admin_headers, "X-Event-Id": str(other.id)}
    listed = client.get("/api/v1/admin/email-logs", headers=switched)
    assert listed.json()["total"] == 0
    assert listed.json()["items"] == []

    stats_other = client.get("/api/v1/admin/email-logs/stats", headers=switched)
    assert stats_other.json()["total"] == 0
    assert stats_other.json()["queued"] == 0
    assert stats_other.json()["by_template"] == {}

    dashboard = client.get("/api/v1/admin/dashboard", headers=switched)
    assert dashboard.json()["emails"]["total"] == 0


def test_resend_ignores_mail_of_another_event(
    client: TestClient, setup, employee, make_user, auth_headers, db: Session
):
    make_user(email="btc@company.vn", password="MatKhau123", role=UserRole.ADMIN)
    client.post(
        "/api/v1/registrations", headers=auth_headers("nv@company.vn"), json=payload(setup)
    )
    other = Event(
        code="TB2027",
        name="Team Building 2027 – Đà Nẵng",
        start_date="2027-04-15",
        end_date="2027-04-17",
        status=EventStatus.REGISTRATION_OPEN,
        terms_version="v1",
        is_active=False,
    )
    db.add(other)
    entry = db.query(EmailLog).one()
    entry.status = EmailStatus.FAILED
    db.commit()

    admin_headers = auth_headers("btc@company.vn")
    response = client.post(
        "/api/v1/admin/email-logs/resend",
        headers={**admin_headers, "X-Event-Id": str(other.id)},
        json={"ids": [entry.id]},
    )

    assert response.status_code == 200, response.text
    assert response.json()["queued"] == 0
    db.expire_all()
    assert db.get(EmailLog, entry.id).status == EmailStatus.FAILED
