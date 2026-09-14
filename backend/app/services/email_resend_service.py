"""Gửi lại thư lỗi từ màn hình nhật ký email.

Nhật ký chỉ lưu bản text rút gọn, không lưu HTML hay dữ liệu dựng thư — nên gửi lại là DỰNG
LẠI nội dung từ dữ liệu hiện tại, không phát lại bản cũ. Đó cũng là điều mong muốn:
- Gửi tới email HIỆN TẠI của CBNV: lỗi vì sai địa chỉ thì sửa hồ sơ rồi gửi lại là xong.
- Nội dung không còn đúng thì không gửi: người đã bổ sung giấy tờ không nhận thư nhắc nữa,
  đăng ký đã huỷ không nhận lại thư "đã nhận đăng ký".

Cập nhật ngay dòng lỗi (failed → queued, retry_count + 1) thay vì thêm dòng mới: mỗi thư một
dòng, và điều kiện "chỉ dòng failed" trong BEGIN IMMEDIATE chặn luôn việc bấm gửi lại hai lần.
"""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import immediate_transaction
from app.core.exceptions import AppError
from app.core.timeutils import utcnow_iso
from app.models.enums import EmailStatus, RegistrationStatus, ReminderKind
from app.models.event import Event
from app.models.notification import EmailLog
from app.models.registration import Registration
from app.models.user import User
from app.services import (
    audit_service,
    email_service,
    email_templates,
    gala_service,
    registration_service,
    reminder_service,
)

logger = logging.getLogger(__name__)

MAX_BATCH = 500

SKIP_NOT_FOUND = "not_found"
SKIP_NOT_FAILED = "not_failed"
SKIP_NO_RECIPIENT = "no_recipient"
SKIP_NO_LONGER_RELEVANT = "no_longer_relevant"
SKIP_CANNOT_REBUILD = "cannot_rebuild"

SKIP_MESSAGES = {
    SKIP_NOT_FOUND: "Không tìm thấy thư này.",
    SKIP_NOT_FAILED: "Thư không ở trạng thái lỗi (đã gửi hoặc đang gửi).",
    SKIP_NO_RECIPIENT: "CBNV không còn tài khoản hoạt động hoặc chưa có email.",
    SKIP_NO_LONGER_RELEVANT: (
        "Nội dung không còn đúng: đăng ký đã đổi trạng thái hoặc CBNV không còn thuộc nhóm "
        "cần nhắc."
    ),
    SKIP_CANNOT_REBUILD: "Không dựng lại được nội dung thư vì thiếu bản ghi liên quan.",
}

# Thư về đăng ký chỉ còn đúng khi đăng ký vẫn ở trạng thái lúc gửi thư.
REGISTRATION_TEMPLATE_STATUS = {
    "registration_confirmed": RegistrationStatus.SUBMITTED,
    "registration_updated": RegistrationStatus.SUBMITTED,
    "registration_cancelled": RegistrationStatus.CANCELLED,
}


def resend(
    db: Session,
    *,
    actor: User,
    ids: list[int] | None = None,
    ip_address: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """`ids=None` = mọi thư đang lỗi (tối đa MAX_BATCH). Trả (kết quả, việc gửi cho BackgroundTask)."""
    if ids is not None and len(ids) > MAX_BATCH:
        raise AppError(
            f"Mỗi lần gửi lại tối đa {MAX_BATCH} thư.",
            code="TOO_MANY_EMAILS",
            details={"max": MAX_BATCH, "requested": len(ids)},
        )

    actor_id = actor.id
    skipped: list[dict[str, Any]] = []
    jobs: list[dict[str, Any]] = []

    with immediate_transaction(db):
        if ids is None:
            rows = db.scalars(
                select(EmailLog)
                .where(EmailLog.status == EmailStatus.FAILED)
                .order_by(EmailLog.id)
                .limit(MAX_BATCH)
            ).all()
            wanted = [row.id for row in rows]
        else:
            wanted = list(dict.fromkeys(ids))
            rows = db.scalars(select(EmailLog).where(EmailLog.id.in_(wanted))).all()
        by_id = {row.id: row for row in rows}
        eligible_cache: dict[tuple[int, ReminderKind], set[int]] = {}

        for log_id in wanted:
            entry = by_id.get(log_id)
            reason = None
            if entry is None:
                reason = SKIP_NOT_FOUND
            elif entry.status != EmailStatus.FAILED:
                reason = SKIP_NOT_FAILED
            else:
                outcome = _rebuild(db, entry, eligible_cache)
                if isinstance(outcome, str):
                    reason = outcome
            if reason:
                skipped.append({"id": log_id, "reason": reason, "message": SKIP_MESSAGES[reason]})
                continue

            user, context = outcome
            rendered = email_templates.render(entry.template, context)
            entry.to_email = user.email
            entry.subject = rendered.subject
            entry.body_preview = rendered.text[: email_service.BODY_PREVIEW_LIMIT]
            entry.status = EmailStatus.QUEUED
            entry.error_message = None
            entry.sent_at = None
            entry.retry_count += 1
            # Mốc lần thử gần nhất: khoảng chờ chống nhắc trùng tính theo mốc này.
            entry.created_at = utcnow_iso()
            jobs.append({"log_id": entry.id, "context": context})

        if jobs:
            audit_service.log(
                db,
                action="email.resent",
                entity_type="email_log",
                entity_id=jobs[0]["log_id"] if len(jobs) == 1 else None,
                actor_id=actor_id,
                after={
                    "ids": [job["log_id"] for job in jobs],
                    "queued": len(jobs),
                    "skipped": len(skipped),
                },
                ip_address=ip_address,
            )

    logger.info("Gửi lại email: xếp %d, bỏ qua %d", len(jobs), len(skipped))
    result = {"queued": len(jobs), "skipped": skipped, "email_enabled": settings.EMAIL_ENABLED}
    return result, jobs


def _rebuild(
    db: Session, entry: EmailLog, eligible_cache: dict[tuple[int, ReminderKind], set[int]]
) -> tuple[User, dict] | str:
    """Dựng lại (người nhận, context) cho một thư lỗi, hoặc trả mã lý do không gửi lại được."""
    user = db.get(User, entry.user_id) if entry.user_id else None
    if user is None or not user.is_active or not user.email:
        return SKIP_NO_RECIPIENT

    if entry.template in REGISTRATION_TEMPLATE_STATUS:
        if entry.related_type != "registration" or not entry.related_id:
            return SKIP_CANNOT_REBUILD
        registration = db.get(Registration, entry.related_id)
        if registration is None or registration.user_id != user.id:
            return SKIP_CANNOT_REBUILD
        if registration.status != REGISTRATION_TEMPLATE_STATUS[entry.template]:
            return SKIP_NO_LONGER_RELEVANT
        event = db.get(Event, registration.event_id)
        context = email_templates.registration_context(
            event=event,
            user=user,
            registration=registration,
            missing_profile_fields=registration_service.missing_profile_fields(user),
        )
        return user, context

    if entry.template == gala_service.TURN_TEMPLATE:
        # Chỉ gửi lại khi lượt đó vẫn đang diễn ra: báo "tới lượt" cho một lượt đã qua là sai.
        if entry.related_type != gala_service.TURN_RELATED_TYPE or not entry.related_id:
            return SKIP_CANNOT_REBUILD
        context = gala_service.rebuild_turn_email(db, order_id=entry.related_id, user=user)
        return (user, context) if context is not None else SKIP_NO_LONGER_RELEVANT

    kind = reminder_service.KIND_BY_TEMPLATE.get(entry.template)
    if kind is not None:
        if entry.related_type != reminder_service.RELATED_TYPE or not entry.related_id:
            return SKIP_CANNOT_REBUILD
        event = db.get(Event, entry.related_id)
        if event is None:
            return SKIP_CANNOT_REBUILD
        if reminder_service.blocked_reason(event, kind):
            return SKIP_NO_LONGER_RELEVANT
        key = (event.id, kind)
        if key not in eligible_cache:
            eligible_cache[key] = reminder_service.eligible_user_ids(db, event=event, kind=kind)
        if user.id not in eligible_cache[key]:
            return SKIP_NO_LONGER_RELEVANT
        missing = (
            registration_service.missing_profile_fields(user)
            if kind == ReminderKind.MISSING_DOCUMENTS
            else []
        )
        return user, email_templates.reminder_context(event=event, user=user, missing_fields=missing)

    return SKIP_CANNOT_REBUILD
