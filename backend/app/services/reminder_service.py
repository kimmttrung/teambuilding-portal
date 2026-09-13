"""Email nhắc việc BTC chủ động gửi cho một nhóm CBNV.

Hai nhóm, định nghĩa khớp với số liệu dashboard (`registration_service.get_stats`) để con
số BTC thấy trên thẻ và số người trong hộp thoại gửi là một:
- `missing_documents`: đã xác nhận tham gia nhưng thiếu CCCD hoặc ngày sinh → không xuất vé.
- `not_registered`: chưa gửi đăng ký (không tính người đã huỷ — họ đã phản hồi).

Chống gửi trùng: ai đã được nhắc CÙNG loại trong `REMINDER_COOLDOWN_HOURS` thì mặc định bỏ
qua. Việc kiểm tra và ghi dòng `queued` nằm chung một BEGIN IMMEDIATE, nên hai lần bấm đồng
thời cũng không lọt qua cả hai. Email gửi lỗi không tính là "đã nhắc".
"""

import logging
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.database import immediate_transaction
from app.core.exceptions import ConflictError
from app.core.timeutils import iso_in
from app.models.enums import EmailStatus, EventStatus, RegistrationStatus, ReminderKind
from app.models.event import Event
from app.models.notification import EmailLog
from app.models.registration import Registration
from app.models.user import User
from app.services import audit_service, email_service, email_templates, registration_service

logger = logging.getLogger(__name__)

REMINDER_COOLDOWN_HOURS = 24
# email_logs không có event_id: trỏ mềm về kỳ để sang kỳ mới thì khoảng chờ tính lại từ đầu.
RELATED_TYPE = "event"

TEMPLATES = {
    ReminderKind.MISSING_DOCUMENTS: "reminder_missing_documents",
    ReminderKind.NOT_REGISTERED: "reminder_not_registered",
}

SKIP_RECENTLY_REMINDED = "recently_reminded"
SKIP_NOT_ELIGIBLE = "not_eligible"


def blocked_reason(event: Event, kind: ReminderKind) -> str | None:
    """Lúc này có nên gửi loại nhắc này không. None = được gửi."""
    status = EventStatus(event.status)
    if kind == ReminderKind.NOT_REGISTERED and status != EventStatus.REGISTRATION_OPEN:
        return (
            "Chỉ nhắc gửi đăng ký khi kỳ đang mở đăng ký — lúc này CBNV nhận email cũng không "
            "đăng ký được."
        )
    if kind == ReminderKind.MISSING_DOCUMENTS and status.at_least(EventStatus.EVENT_STARTED):
        return "Chương trình đã bắt đầu, bổ sung giấy tờ lúc này không còn tác dụng xuất vé."
    return None


def preview(db: Session, *, event: Event, kind: ReminderKind) -> dict[str, Any]:
    rows = _collect(db, event=event, kind=kind)
    recipients = [info for _user, info in rows]
    reason = blocked_reason(event, kind)
    template = TEMPLATES[kind]
    return {
        "kind": kind,
        "label": email_templates.TEMPLATE_LABELS[template],
        "template": template,
        "can_send": reason is None,
        "blocked_reason": reason,
        "cooldown_hours": REMINDER_COOLDOWN_HOURS,
        "email_enabled": settings.EMAIL_ENABLED,
        "total": len(recipients),
        "sendable": sum(1 for info in recipients if not info["recently_reminded"]),
        "recipients": recipients,
    }


def send(
    db: Session,
    *,
    event: Event,
    kind: ReminderKind,
    actor: User,
    user_ids: list[int] | None = None,
    include_recently_reminded: bool = False,
    ip_address: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Ghi các dòng `queued` + audit log, trả (kết quả cho API, việc gửi cho BackgroundTask).

    Router tự xếp việc gửi SAU khi transaction đã commit: gửi trước khi commit thì lỡ
    rollback là CBNV đã nhận mail mà nhật ký không có dòng nào.
    """
    reason = blocked_reason(event, kind)
    if reason:
        raise ConflictError(
            reason,
            code="REMINDER_NOT_ALLOWED",
            details={"kind": kind.value, "event_status": event.status},
        )

    template = TEMPLATES[kind]
    event_id, actor_id = event.id, actor.id
    skipped: list[dict[str, Any]] = []
    jobs: list[dict[str, Any]] = []

    with immediate_transaction(db):
        event = db.get(Event, event_id)
        by_id = {user.id: (user, info) for user, info in _collect(db, event=event, kind=kind)}
        wanted = list(by_id) if user_ids is None else list(dict.fromkeys(user_ids))

        queued: list[tuple[EmailLog, dict]] = []
        for user_id in wanted:
            found = by_id.get(user_id)
            if found is None:
                # Đã bổ sung giấy tờ / đã đăng ký kể từ lúc BTC mở hộp thoại, hoặc id lạ.
                skipped.append({"user_id": user_id, "full_name": None, "reason": SKIP_NOT_ELIGIBLE})
                continue
            user, info = found
            if info["recently_reminded"] and not include_recently_reminded:
                skipped.append(
                    {"user_id": user_id, "full_name": user.full_name, "reason": SKIP_RECENTLY_REMINDED}
                )
                continue

            context = email_templates.reminder_context(
                event=event, user=user, missing_fields=info["missing_fields"]
            )
            entry = email_service.enqueue(
                db,
                template=template,
                to_email=user.email,
                context=context,
                user_id=user.id,
                related_type=RELATED_TYPE,
                related_id=event_id,
            )
            queued.append((entry, context))

        db.flush()
        jobs = [{"log_id": entry.id, "context": context} for entry, context in queued]

        if queued:
            audit_service.log(
                db,
                action="reminder.sent",
                entity_type="event",
                entity_id=event_id,
                actor_id=actor_id,
                event_id=event_id,
                after={
                    "kind": kind.value,
                    "template": template,
                    "queued": len(queued),
                    "user_ids": [entry.user_id for entry, _context in queued],
                    "skipped": len(skipped),
                },
                ip_address=ip_address,
            )

    logger.info("Nhắc %s: xếp %d email, bỏ qua %d", kind.value, len(jobs), len(skipped))
    result = {
        "kind": kind,
        "queued": len(jobs),
        "skipped": skipped,
        "email_enabled": settings.EMAIL_ENABLED,
    }
    return result, jobs


# --- Nội bộ ---


def _collect(db: Session, *, event: Event, kind: ReminderKind) -> list[tuple[User, dict[str, Any]]]:
    users = _candidates(db, event=event, kind=kind)
    template = TEMPLATES[kind]
    last = _last_reminded(db, event_id=event.id, template=template, user_ids=[user.id for user in users])
    cutoff = iso_in(hours=-REMINDER_COOLDOWN_HOURS)

    rows = []
    for user in users:
        last_at = last.get(user.id)
        rows.append(
            (
                user,
                {
                    "user_id": user.id,
                    "full_name": user.full_name,
                    "email": user.email,
                    "employee_code": user.employee_code,
                    "team_name": user.team.name if user.team else None,
                    "missing_fields": (
                        registration_service.missing_profile_fields(user)
                        if kind == ReminderKind.MISSING_DOCUMENTS
                        else []
                    ),
                    "last_reminded_at": last_at,
                    # Chuỗi ISO UTC cùng định dạng nên so sánh chuỗi là so sánh thời gian.
                    "recently_reminded": bool(last_at and last_at >= cutoff),
                },
            )
        )
    return rows


def _candidates(db: Session, *, event: Event, kind: ReminderKind) -> list[User]:
    if kind == ReminderKind.MISSING_DOCUMENTS:
        query = (
            select(User)
            .join(Registration, Registration.user_id == User.id)
            .where(
                Registration.event_id == event.id,
                Registration.status == RegistrationStatus.SUBMITTED,
                Registration.is_participating.is_(True),
                User.is_active.is_(True),
                or_(
                    User.id_card_number.is_(None),
                    User.id_card_number == "",
                    User.date_of_birth.is_(None),
                ),
            )
        )
    else:
        responded = select(Registration.user_id).where(
            Registration.event_id == event.id,
            Registration.status.in_([RegistrationStatus.SUBMITTED, RegistrationStatus.CANCELLED]),
        )
        query = select(User).where(User.is_active.is_(True), User.id.not_in(responded))

    return list(db.scalars(query.options(selectinload(User.team)).order_by(User.full_name)))


def _last_reminded(
    db: Session, *, event_id: int, template: str, user_ids: list[int]
) -> dict[int, str]:
    if not user_ids:
        return {}
    return dict(
        db.execute(
            select(EmailLog.user_id, func.max(EmailLog.created_at))
            .where(
                EmailLog.template == template,
                EmailLog.related_type == RELATED_TYPE,
                EmailLog.related_id == event_id,
                EmailLog.status != EmailStatus.FAILED,
                EmailLog.user_id.in_(user_ids),
            )
            .group_by(EmailLog.user_id)
        ).all()
    )
