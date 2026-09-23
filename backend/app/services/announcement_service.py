"""Thông báo BTC gửi CBNV (announcements).

Vòng đời: nháp (`published_at` null, chỉ BTC thấy) → đăng (hiện trong My Journey đúng
nhóm đối tượng) → có thể gỡ về nháp hoặc xoá. Gửi email là tuỳ chọn lúc đăng, mỗi lần
đăng là một sự kiện riêng nên không chống trùng 24h như email nhắc việc.

Đối tượng nhận (`target_type` + `target_id`) tính theo cùng luật My Journey hiển thị
(`journey_service._targets`), chỉ khác chiều: ở đây liệt kê RA ai nhận, đằng kia kiểm
tra một người CÓ nhận không. Team và user là toàn cục (không gắn kỳ), còn chuyến
bay/xe phải thuộc kỳ đang chọn — không thì BTC kỳ này gửi nhầm sang dữ liệu kỳ khác.
"""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.database import immediate_transaction
from app.core.exceptions import AppError, NotFoundError
from app.core.timeutils import utcnow_iso
from app.models.content import Announcement
from app.models.enums import AnnouncementTarget
from app.models.event import Event
from app.models.flight import Flight, FlightAssignment
from app.models.notification import EmailLog
from app.models.org import Team
from app.models.registration import Registration
from app.models.transportation import Bus, BusAssignment
from app.models.user import User
from app.services import audit_service, email_service, email_templates

logger = logging.getLogger(__name__)

TEMPLATE = "announcement_notice"
# email_logs không có event_id: trỏ mềm về kỳ như email nhắc việc.
RELATED_TYPE = "event"
ENTITY_TYPE = "announcement"


def list_announcements(db: Session, event: Event) -> list[dict[str, Any]]:
    """Toàn bộ thông báo của kỳ, nháp trước rồi tới đã đăng mới nhất."""
    rows = db.scalars(
        select(Announcement).where(Announcement.event_id == event.id)
    ).all()
    drafts = sorted((row for row in rows if row.published_at is None), key=lambda row: -row.id)
    published = sorted(
        (row for row in rows if row.published_at is not None),
        key=lambda row: row.published_at,
        reverse=True,
    )
    return [_to_out(db, event, row) for row in (*drafts, *published)]


def create_announcement(db: Session, event: Event, data: dict, *, actor_id: int) -> Announcement:
    """Tạo bản nháp. Muốn CBNV thấy và muốn gửi mail thì đăng ở bước riêng."""
    payload = dict(data)
    label = _require_target(db, event, payload.get("target_type"), payload.get("target_id"))
    item = Announcement(
        event_id=event.id,
        title=payload["title"].strip(),
        content=payload["content"].strip(),
        severity=payload.get("severity"),
        target_type=payload.get("target_type"),
        target_id=payload.get("target_id"),
        created_by=actor_id,
        created_at=utcnow_iso(),
    )
    db.add(item)
    db.flush()
    logger.info("Tạo nháp thông báo '%s' (%s) trong kỳ %s", item.title, label, event.code)
    return item


def update_announcement(
    db: Session, event: Event, item_id: int, changes: dict
) -> Announcement:
    """Sửa nháp hay bản đã đăng đều được — sửa không tự đổi trạng thái đăng."""
    item = _scoped(db, event, item_id)
    merged = {
        "target_type": item.target_type,
        "target_id": item.target_id,
        **{key: value for key, value in changes.items() if value is not None},
    }
    _require_target(db, event, merged["target_type"], merged["target_id"])
    for field in ("title", "content", "severity", "target_type", "target_id"):
        if field in changes and changes[field] is not None:
            value = changes[field]
            setattr(item, field, value.strip() if field in ("title", "content") else value)
    db.flush()
    return item


def delete_announcement(db: Session, event: Event, item_id: int) -> Announcement:
    """Xoá cả nháp lẫn bản đã đăng — bản đã đăng biến mất khỏi My Journey."""
    item = _scoped(db, event, item_id)
    db.delete(item)
    db.flush()
    return item


def publish(
    db: Session,
    *,
    event: Event,
    item_id: int,
    actor: User,
    send_email: bool = False,
    ip_address: str | None = None,
) -> tuple[Announcement, dict[str, Any], list[dict[str, Any]]]:
    """Đăng thông báo: ghi giờ đăng, tuỳ chọn xếp email cho đúng nhóm nhận.

    Trả (thông báo, kết quả cho API, việc gửi cho BackgroundTask). Router xếp việc
    gửi SAU khi transaction đã commit — gửi trước mà rollback thì CBNV nhận mail
    còn nhật ký không có dòng nào.
    """
    event_id, actor_id = event.id, actor.id
    jobs: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    with immediate_transaction(db):
        event = db.get(Event, event_id)
        item = _scoped(db, event, item_id)
        item.published_at = utcnow_iso()
        item.send_email = send_email
        label = _target_label(db, event, item.target_type, item.target_id)

        queued: list[tuple[EmailLog, dict]] = []
        if send_email:
            recipients = resolve_recipients(db, event, item.target_type, item.target_id)
            for user in recipients:
                if not user.email:
                    skipped.append(
                        {"user_id": user.id, "full_name": user.full_name, "reason": "no_email"}
                    )
                    continue
                context = email_templates.announcement_context(
                    event=event, user=user, announcement=item, target_label=label
                )
                entry = email_service.enqueue(
                    db,
                    template=TEMPLATE,
                    to_email=user.email,
                    context=context,
                    event_id=event_id,
                    user_id=user.id,
                    related_type=RELATED_TYPE,
                    related_id=event_id,
                )
                queued.append((entry, context))

        db.flush()
        jobs = [{"log_id": entry.id, "context": context} for entry, context in queued]

        audit_service.log(
            db,
            action="announcement.published",
            entity_type=ENTITY_TYPE,
            entity_id=item.id,
            actor_id=actor_id,
            event_id=event_id,
            after={
                "title": item.title,
                "target_type": item.target_type,
                "target_id": item.target_id,
                "send_email": send_email,
                "queued": len(queued),
                "skipped": len(skipped),
            },
            ip_address=ip_address,
        )
        if queued:
            audit_service.log(
                db,
                action="announcement.emailed",
                entity_type=ENTITY_TYPE,
                entity_id=item.id,
                actor_id=actor_id,
                event_id=event_id,
                after={
                    "template": TEMPLATE,
                    "queued": len(queued),
                    "user_ids": [entry.user_id for entry, _context in queued],
                },
                ip_address=ip_address,
            )

    logger.info(
        "Đăng thông báo #%d '%s': xếp %d email, bỏ qua %d",
        item_id, item.title, len(jobs), len(skipped),
    )
    result = {"id": item_id, "published_at": item.published_at, "queued": len(jobs)}
    return item, result, jobs


def unpublish(db: Session, event: Event, item_id: int) -> Announcement:
    """Gỡ bản đã đăng về nháp — biến mất khỏi My Journey, email đã gửi không thu hồi."""
    item = _scoped(db, event, item_id)
    item.published_at = None
    db.flush()
    return item


def recipient_preview(
    db: Session, event: Event, target_type: str, target_id: int | None
) -> dict[str, Any]:
    """Ai sẽ nhận nếu đăng với đối tượng này — cho màn hình soạn xem trước."""
    label = _require_target(db, event, target_type, target_id)
    recipients = resolve_recipients(db, event, target_type, target_id)
    return {
        "target_type": target_type,
        "target_id": target_id,
        "target_label": label,
        "total": len(recipients),
        "email_enabled": settings.EMAIL_ENABLED,
        "recipients": [
            {
                "user_id": user.id,
                "full_name": user.full_name,
                "email": user.email,
                "team_name": user.team.name if user.team else None,
            }
            for user in recipients
        ],
    }


def resolve_recipients(
    db: Session, event: Event, target_type: str, target_id: int | None
) -> list[User]:
    """Liệt kê user nhận thông báo — cùng luật với `journey_service._targets`."""
    base = [User.is_active.is_(True)]
    if target_type == AnnouncementTarget.ALL:
        query = select(User).where(*base)
    elif target_type == AnnouncementTarget.TEAM:
        query = select(User).where(*base, User.team_id == target_id)
    elif target_type == AnnouncementTarget.USER:
        query = select(User).where(*base, User.id == target_id)
    elif target_type == AnnouncementTarget.FLIGHT:
        query = (
            select(User)
            .join(Registration, Registration.user_id == User.id)
            .join(FlightAssignment, FlightAssignment.registration_id == Registration.id)
            .where(
                *base,
                Registration.event_id == event.id,
                FlightAssignment.flight_id == target_id,
            )
        )
    elif target_type == AnnouncementTarget.BUS:
        query = (
            select(User)
            .join(Registration, Registration.user_id == User.id)
            .join(BusAssignment, BusAssignment.registration_id == Registration.id)
            .where(
                *base,
                Registration.event_id == event.id,
                BusAssignment.bus_id == target_id,
            )
        )
    else:  # pragma: no cover — CHECK ở DB và enum ở schema đã chặn trước
        return []
    rows = db.scalars(
        query.options(selectinload(User.team)).order_by(User.full_name)
    ).all()
    # Join qua assignment có thể trả trùng user (2 chiều bay) — gọn lại giữ thứ tự tên.
    return list(dict.fromkeys(rows))


def get_out(db: Session, event: Event, item_id: int) -> dict[str, Any]:
    """Một thông báo kèm nhãn đối tượng và số người nhận — cho response sau ghi."""
    return _to_out(db, event, _scoped(db, event, item_id))


def _to_out(db: Session, event: Event, item: Announcement) -> dict[str, Any]:
    return {
        "id": item.id,
        "event_id": item.event_id,
        "title": item.title,
        "content": item.content,
        "severity": item.severity,
        "target_type": item.target_type,
        "target_id": item.target_id,
        "target_label": _target_label(db, event, item.target_type, item.target_id),
        "published_at": item.published_at,
        "send_email": item.send_email,
        "recipient_count": len(
            resolve_recipients(db, event, item.target_type, item.target_id)
        ),
    }


def _scoped(db: Session, event: Event, item_id: int) -> Announcement:
    item = db.get(Announcement, item_id)
    if item is None or item.event_id != event.id:
        raise NotFoundError(
            f"Không tìm thấy thông báo #{item_id} trong kỳ này.",
            code="ANNOUNCEMENT_NOT_FOUND",
        )
    return item


def _require_target(db: Session, event: Event, target_type: str | None, target_id: int | None) -> str:
    """Đối tượng nhận phải có thật và thuộc kỳ đang chọn. Trả nhãn dễ đọc."""
    try:
        target = AnnouncementTarget(target_type)
    except ValueError:
        raise AppError(
            f"Đối tượng nhận '{target_type}' không hợp lệ.",
            code="ANNOUNCEMENT_TARGET_INVALID",
            status_code=422,
        )
    if target == AnnouncementTarget.ALL:
        if target_id is not None:
            raise AppError(
                "Thông báo gửi tất cả không cần chọn đối tượng cụ thể.",
                code="ANNOUNCEMENT_TARGET_INVALID",
                status_code=422,
            )
        return "Tất cả CBNV"
    if target_id is None:
        raise AppError(
            "Chưa chọn đối tượng nhận cụ thể cho thông báo này.",
            code="ANNOUNCEMENT_TARGET_INVALID",
            status_code=422,
        )
    if target == AnnouncementTarget.TEAM:
        team = db.get(Team, target_id)
        if team is None:
            raise AppError(
                f"Không tìm thấy team #{target_id}.",
                code="ANNOUNCEMENT_TARGET_INVALID",
                status_code=422,
            )
        return f"Team {team.name}"
    if target == AnnouncementTarget.USER:
        user = db.get(User, target_id)
        if user is None:
            raise AppError(
                f"Không tìm thấy CBNV #{target_id}.",
                code="ANNOUNCEMENT_TARGET_INVALID",
                status_code=422,
            )
        return f"Cá nhân: {user.full_name}"
    if target == AnnouncementTarget.FLIGHT:
        flight = db.get(Flight, target_id)
        if flight is None or flight.event_id != event.id:
            raise AppError(
                f"Chuyến bay #{target_id} không thuộc kỳ này.",
                code="ANNOUNCEMENT_TARGET_INVALID",
                status_code=422,
            )
        return f"Chuyến bay {flight.flight_code}"
    bus = db.get(Bus, target_id)
    if bus is None or bus.event_id != event.id:
        raise AppError(
            f"Xe #{target_id} không thuộc kỳ này.",
            code="ANNOUNCEMENT_TARGET_INVALID",
            status_code=422,
        )
    return f"Xe {bus.bus_code}"


def _target_label(db: Session, event: Event, target_type: str, target_id: int | None) -> str:
    """Nhãn đối tượng cho bản đã lưu — dữ liệu chuẩn nên không cần validate lại."""
    if target_type == AnnouncementTarget.ALL:
        return "Tất cả CBNV"
    if target_type == AnnouncementTarget.TEAM:
        team = db.get(Team, target_id)
        return f"Team {team.name}" if team else f"Team #{target_id}"
    if target_type == AnnouncementTarget.USER:
        user = db.get(User, target_id)
        return f"Cá nhân: {user.full_name}" if user else f"CBNV #{target_id}"
    if target_type == AnnouncementTarget.FLIGHT:
        flight = db.get(Flight, target_id)
        return f"Chuyến bay {flight.flight_code}" if flight else f"Chuyến bay #{target_id}"
    bus = db.get(Bus, target_id)
    return f"Xe {bus.bus_code}" if bus else f"Xe #{target_id}"
