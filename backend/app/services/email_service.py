"""Gửi email và ghi nhật ký mọi lần gửi.

Nguyên tắc: **email không bao giờ được làm hỏng nghiệp vụ**. CBNV đã đăng ký thành công
thì SMTP hỏng cũng không được biến thành lỗi 500 — mọi thứ ở đây chạy trong BackgroundTask
và tự bắt lỗi, chỉ để lại một dòng `email_logs` trạng thái `failed`.

Vì sao ghi `email_logs` hai lần (queued rồi sent/failed): nếu tiến trình chết đúng lúc
đang nói chuyện với SMTP, vẫn còn dòng `queued` để BTC biết mail đó chưa tới đích.
"""

import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import session_scope
from app.core.timeutils import utcnow_iso
from app.models.enums import EmailStatus
from app.models.notification import EmailLog
from app.services import email_templates

logger = logging.getLogger(__name__)

# Cắt bản text để nhật ký không phình theo từng mail; đủ dài để BTC đọc lại nội dung.
BODY_PREVIEW_LIMIT = 4000
ERROR_MESSAGE_LIMIT = 500
SMTP_TIMEOUT_SECONDS = 15

# Ghi rõ lý do vào dòng log để BTC không nhầm "mail chưa gửi" với "mail gửi lỗi".
DEV_MODE_NOTE = "EMAIL_ENABLED=false: chỉ ghi log và lưu nội dung, chưa gửi thật."
NO_SMTP_HOST_NOTE = "EMAIL_ENABLED=true nhưng thiếu SMTP_HOST — kiểm tra lại .env."

# Lỗi SMTP thô rất khó hiểu với người vận hành: "535 BadCredentials" nghe như sai địa chỉ
# NGƯỜI NHẬN, trong khi thực ra là sai tài khoản GỬI. Dịch sẵn mấy ca hay gặp nhất để
# dòng trong /admin/email-logs đọc là biết phải sửa gì.
SMTP_ERROR_HINTS: tuple[tuple[str, str], ...] = (
    (
        "535",
        "Gmail từ chối đăng nhập của tài khoản GỬI (không liên quan địa chỉ người nhận). "
        "Phải dùng App Password 16 ký tự: bật xác minh 2 bước rồi tạo tại "
        "myaccount.google.com/apppasswords, dán vào SMTP_PASSWORD và bỏ hết dấu cách. "
        "Mật khẩu đăng nhập Google thường luôn bị chối.",
    ),
    (
        "534",
        "Tài khoản gửi bật xác minh 2 bước nhưng đang dùng mật khẩu thường — cần App Password.",
    ),
    (
        "553",
        "SMTP_FROM_EMAIL phải trùng SMTP_USER: nhà cung cấp không cho gửi hộ địa chỉ khác.",
    ),
    (
        "5.7.0",
        "Nhà cung cấp chối vì chưa xác thực hoặc thiếu quyền gửi — kiểm tra SMTP_USER/SMTP_PASSWORD.",
    ),
)

CONNECTION_HINT = (
    "Không mở được kết nối tới SMTP_HOST:SMTP_PORT. Mạng công ty thường chặn cổng 587 — "
    "thử SMTP_PORT=465, hoặc dùng SMTP local (Mailpit) với SMTP_STARTTLS=false."
)


def send(
    db: Session,
    *,
    template: str,
    to_email: str,
    context: dict,
    user_id: int | None = None,
    related_type: str | None = None,
    related_id: int | None = None,
) -> EmailLog | None:
    """Render, ghi nhật ký rồi gửi một email. Trả về dòng nhật ký đã ghi.

    Không ném lỗi khi SMTP thất bại: thất bại được ghi vào `email_logs.status`.
    """
    if not to_email:
        logger.warning("Bỏ qua email %s: người nhận không có địa chỉ", template)
        return None

    entry, rendered = _new_entry(
        template=template,
        to_email=to_email,
        context=context,
        user_id=user_id,
        related_type=related_type,
        related_id=related_id,
    )
    db.add(entry)
    db.commit()
    return _dispatch(db, entry, rendered)


def enqueue(
    db: Session,
    *,
    template: str,
    to_email: str,
    context: dict,
    user_id: int | None = None,
    related_type: str | None = None,
    related_id: int | None = None,
) -> EmailLog:
    """Thêm dòng `queued` vào session hiện tại — CHƯA commit, chưa gửi.

    Dùng khi quyết định "có gửi không" phải nằm cùng transaction với việc ghi nhật ký: email
    nhắc việc kiểm tra "đã nhắc trong 24 giờ chưa" rồi ghi dòng queued trong một BEGIN
    IMMEDIATE, để hai lần bấm đồng thời không cùng lọt qua. Gửi thật bằng
    `deliver_queued_async` sau khi commit.
    """
    entry, _rendered = _new_entry(
        template=template,
        to_email=to_email,
        context=context,
        user_id=user_id,
        related_type=related_type,
        related_id=related_id,
    )
    db.add(entry)
    return entry


def _new_entry(
    *,
    template: str,
    to_email: str,
    context: dict,
    user_id: int | None,
    related_type: str | None,
    related_id: int | None,
) -> tuple[EmailLog, email_templates.RenderedEmail]:
    rendered = email_templates.render(template, context)
    entry = EmailLog(
        user_id=user_id,
        to_email=to_email,
        template=template,
        subject=rendered.subject,
        body_preview=rendered.text[:BODY_PREVIEW_LIMIT],
        status=EmailStatus.QUEUED,
        related_type=related_type,
        related_id=related_id,
        created_at=utcnow_iso(),
    )
    return entry, rendered


def _dispatch(db: Session, entry: EmailLog, rendered: email_templates.RenderedEmail) -> EmailLog:
    """Gửi một dòng nhật ký đã commit và cập nhật trạng thái của nó."""
    if not settings.EMAIL_ENABLED:
        # Môi trường dev: in ra log để xem được nội dung mà không cần SMTP thật.
        entry.error_message = DEV_MODE_NOTE
        db.commit()
        logger.info(
            "[EMAIL-DEV] -> %s | %s\n%s", entry.to_email, rendered.subject, rendered.text
        )
        return entry

    if not settings.SMTP_HOST:
        return _mark_failed(db, entry, NO_SMTP_HOST_NOTE)

    try:
        _deliver(to_email=entry.to_email, rendered=rendered)
    except Exception as exc:  # smtplib ném nhiều loại lỗi khác nhau, gom về một chỗ
        hint = explain_smtp_error(exc)
        logger.warning(
            "Gửi email %s tới %s thất bại: %s%s",
            entry.template,
            entry.to_email,
            exc,
            f"\n  → {hint}" if hint else "",
        )
        detail = f"{type(exc).__name__}: {exc}"
        return _mark_failed(db, entry, f"{detail} | {hint}" if hint else detail)

    entry.status = EmailStatus.SENT
    entry.sent_at = utcnow_iso()
    db.commit()
    logger.info("Đã gửi email %s tới %s", entry.template, entry.to_email)
    return entry


def send_async(**kwargs) -> None:
    """Bản dùng cho `BackgroundTasks`: tự mở session riêng và không bao giờ ném lỗi.

    Session của request đã đóng khi background task chạy, nên không dùng lại được.
    Vì vậy `context` truyền vào phải là dict thuần, không phải ORM object.
    """
    try:
        with session_scope() as db:
            send(db, **kwargs)
    except Exception:
        # Đã tới đây là lỗi ngoài dự kiến (render sai template, DB hỏng). Ghi lại
        # và im lặng: người dùng đã nhận response thành công từ lâu.
        logger.exception(
            "Không ghi được email %s tới %s",
            kwargs.get("template"),
            kwargs.get("to_email"),
        )


def deliver_queued_async(*, log_id: int, context: dict) -> None:
    """Gửi một email đã `enqueue` + commit. Chạy trong BackgroundTask, không bao giờ ném lỗi.

    Dòng không còn `queued` (đã gửi, đã lỗi) thì bỏ qua — task có bị gọi lại cũng không gửi
    trùng. Render lại từ `context` vì bản HTML không được lưu trong nhật ký.
    """
    try:
        with session_scope() as db:
            entry = db.get(EmailLog, log_id)
            if entry is None or entry.status != EmailStatus.QUEUED:
                return
            rendered = email_templates.render(entry.template, context)
            _dispatch(db, entry, rendered)
    except Exception:
        logger.exception("Không gửi được email đã xếp hàng #%s", log_id)


# --- Truy vấn cho BTC ---


def list_logs(
    db: Session,
    *,
    status: str | None = None,
    template: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[EmailLog], int]:
    query = select(EmailLog)

    if status:
        query = query.where(EmailLog.status == status)
    if template:
        query = query.where(EmailLog.template == template)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(or_(EmailLog.to_email.like(pattern), EmailLog.subject.like(pattern)))

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = list(db.scalars(query.order_by(EmailLog.id.desc()).limit(limit).offset(offset)))
    return rows, total


def get_stats(db: Session) -> dict[str, object]:
    by_status = {
        status: count
        for status, count in db.execute(
            select(EmailLog.status, func.count(EmailLog.id)).group_by(EmailLog.status)
        ).all()
    }
    by_template = {
        template: count
        for template, count in db.execute(
            select(EmailLog.template, func.count(EmailLog.id)).group_by(EmailLog.template)
        ).all()
    }
    return {
        "total": sum(by_status.values()),
        "queued": by_status.get(EmailStatus.QUEUED, 0),
        "sent": by_status.get(EmailStatus.SENT, 0),
        "failed": by_status.get(EmailStatus.FAILED, 0),
        "by_template": by_template,
        "email_enabled": settings.EMAIL_ENABLED,
    }


def explain_smtp_error(exc: Exception) -> str | None:
    """Đổi lỗi SMTP thô thành câu người vận hành hiểu được. None nếu không nhận ra."""
    if isinstance(exc, (smtplib.SMTPConnectError, TimeoutError, OSError)) and not isinstance(
        exc, smtplib.SMTPResponseException
    ):
        return CONNECTION_HINT

    text = str(exc)
    for needle, hint in SMTP_ERROR_HINTS:
        if needle in text:
            return hint
    return None


# --- Nội bộ ---


def _mark_failed(db: Session, entry: EmailLog, message: str) -> EmailLog:
    entry.status = EmailStatus.FAILED
    entry.error_message = message[:ERROR_MESSAGE_LIMIT]
    db.commit()
    return entry


def _deliver(*, to_email: str, rendered: email_templates.RenderedEmail) -> None:
    """Gửi thật qua SMTP. Ném lỗi để nơi gọi ghi vào nhật ký."""
    message = EmailMessage()
    message["Subject"] = rendered.subject
    message["From"] = formataddr((settings.SMTP_FROM_NAME, settings.SMTP_FROM_EMAIL))
    message["To"] = to_email
    message.set_content(rendered.text)
    message.add_alternative(rendered.html, subtype="html")

    with _connect() as smtp:
        if settings.SMTP_USER:
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.send_message(message)


def _connect() -> smtplib.SMTP:
    """Mở kết nối SMTP.

    Cổng 465 dùng TLS ngay từ đầu (SMTPS). Các cổng khác (587, 25) nâng cấp bằng
    STARTTLS, trừ khi `SMTP_STARTTLS=false` — SMTP local để thử (Mailpit) và relay
    nội bộ không có TLS, cứ gọi STARTTLS là lỗi ngay lúc bắt tay.
    """
    if settings.SMTP_PORT == 465:
        return smtplib.SMTP_SSL(
            settings.SMTP_HOST, settings.SMTP_PORT, timeout=SMTP_TIMEOUT_SECONDS
        )

    smtp = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=SMTP_TIMEOUT_SECONDS)
    smtp.ehlo()
    if settings.SMTP_STARTTLS:
        smtp.starttls()
        smtp.ehlo()
    return smtp
