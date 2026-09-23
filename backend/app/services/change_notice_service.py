"""Email báo CBNV khi có thay đổi họ không tự làm.

Hai loại:
- **Kỳ đổi trạng thái** (mở / đóng đăng ký, phân bổ, công bố, diễn ra, kết thúc, cả bước lùi):
  gửi mọi người đang tham gia; riêng mở đăng ký (và thu hồi mở đăng ký) gửi mọi tài khoản
  đang hoạt động — lúc đó chưa ai đăng ký nên "người tham gia" là rỗng.
- **BTC sửa thông tin chung của kỳ** (tên, điểm đến, ngày, hạn đăng ký, bản quy định): gửi như
  đổi trạng thái — mở đăng ký thì mọi người, còn lại người tham gia.
- **BTC sửa một mục CBNV đã chọn** khi đăng ký: ca bay, chặng xe, điểm đón, địa điểm xuất phát.
  Chỉ gửi người đang dùng mục đó, và chỉ khi trường người dùng NHÌN THẤY đổi (đổi thứ tự hiển
  thị thì không ai cần biết).

Chỉ gửi khi BTC tích "Gửi email" (`notify`, mặc định tắt). Tất cả đều `enqueue` trong cùng transaction với thay đổi (rollback là không có thư nào), gửi thật
bằng `email_service.deliver_queued_async` sau commit. Mỗi đợt ghi một dòng audit và thư trỏ
`related_type="audit_log"` về dòng đó — gửi lại thư lỗi dựng lại nội dung từ chính dòng audit.
"""

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.timeutils import format_date_only, format_vn
from app.models.audit import AuditLog
from app.models.enums import EventStatus, RegistrationStatus
from app.models.event import Event
from app.models.registration import Registration, RegistrationBusNeed
from app.models.transportation import TripLeg
from app.models.user import User
from app.services import audit_service, email_service, email_templates

logger = logging.getLogger(__name__)

STATUS_TEMPLATE = "event_status_changed"
CHOICE_TEMPLATE = "registration_choice_changed"
EMAIL_TEMPLATES = {STATUS_TEMPLATE, CHOICE_TEMPLATE, "event_info_changed"}
RELATED_TYPE = "audit_log"
CHOICE_AUDIT_ACTION = "registration_choice.notified"

# Trường nào của mục master data mà CBNV nhìn thấy, kèm nhãn trong email.
WATCHED_FIELDS: dict[str, dict[str, str]] = {
    "shift": {
        "name": "Tên ca",
        "description": "Mô tả",
        "earliest_departure": "Giờ bay sớm nhất",
    },
    "trip_leg": {"name": "Tên chặng", "direction": "Chiều", "leg_date": "Ngày đi"},
    "pickup_point": {
        "name": "Tên điểm đón",
        "address": "Địa chỉ",
        "map_url": "Bản đồ",
        "trip_leg_id": "Chặng",
    },
    "work_location": {
        "name": "Tên địa điểm",
        "city": "Thành phố",
        "airport_code": "Sân bay",
        "is_active": "Còn sử dụng",
    },
}
SUBJECT_LABELS = {
    "shift": "Ca bay",
    "trip_leg": "Chặng xe",
    "pickup_point": "Điểm đón",
    "work_location": "Địa điểm xuất phát",
}
_DIRECTION_LABELS = {"outbound": "Chiều đi", "return": "Chiều về"}


# --- Đổi trạng thái kỳ ---


def notifies_everyone(previous: EventStatus, new: EventStatus) -> bool:
    """Mở đăng ký (và rút lại việc mở) liên quan cả người CHƯA đăng ký."""
    return new == EventStatus.REGISTRATION_OPEN or (
        previous == EventStatus.REGISTRATION_OPEN and new == EventStatus.DRAFT
    )


def status_recipients(
    db: Session, *, event_id: int, previous: EventStatus, new: EventStatus
) -> list[User]:
    if notifies_everyone(previous, new):
        query = select(User).where(User.is_active.is_(True))
    else:
        query = (
            select(User)
            .join(Registration, Registration.user_id == User.id)
            .where(
                Registration.event_id == event_id,
                Registration.status == RegistrationStatus.SUBMITTED,
                Registration.is_participating.is_(True),
                User.is_active.is_(True),
            )
        )
    return list(db.scalars(query.order_by(User.id)).unique())


def queue_status_change(
    db: Session, *, event: Event, previous: EventStatus, audit: AuditLog
) -> list[dict[str, Any]]:
    """Xếp email báo đổi trạng thái (chưa commit). Trả việc gửi cho BackgroundTask."""
    from app.services import event_service  # event_service gọi ngược vào đây

    new = EventStatus(event.status)
    queued = []
    for user in status_recipients(db, event_id=event.id, previous=previous, new=new):
        if not user.email:
            continue
        context = email_templates.event_status_context(
            event=event,
            user=user,
            previous_status=previous,
            previous_label=event_service.status_label(previous),
            new_label=event_service.status_label(new),
            is_forward=new.at_least(previous),
            reason=audit.reason,
        )
        queued.append((_enqueue(db, STATUS_TEMPLATE, user, context, audit), context))
    return _jobs(db, queued)


# --- BTC sửa thông tin chung của kỳ ---

EVENT_INFO_TEMPLATE = "event_info_changed"
EVENT_INFO_FIELDS = {
    "name": "Tên chương trình",
    "destination": "Điểm đến",
    "start_date": "Ngày bắt đầu",
    "end_date": "Ngày kết thúc",
    "registration_opens_at": "Mở đăng ký từ",
    "registration_closes_at": "Hạn đăng ký",
    "terms_version": "Quy định chương trình",
}


def queue_event_info_change(
    db: Session, *, event: Event, before: dict[str, Any], audit: AuditLog
) -> list[dict[str, Any]]:
    """Xếp email báo kỳ đổi thông tin chung (chưa commit). Chỉ gọi khi BTC tích "Gửi email"."""
    changes = _event_info_changes(event, before)
    if not changes:
        return []

    status = EventStatus(event.status)
    queued = []
    for user in status_recipients(db, event_id=event.id, previous=status, new=status):
        if not user.email:
            continue
        context = email_templates.event_info_context(event=event, user=user, changes=changes)
        queued.append((_enqueue(db, EVENT_INFO_TEMPLATE, user, context, audit), context))
    return _jobs(db, queued)


def _event_info_changes(event: Event, before: dict[str, Any]) -> list[list[str | None]]:
    changes = []
    for field, label in EVENT_INFO_FIELDS.items():
        if field not in before:
            continue
        old, new = before.get(field), getattr(event, field)
        if old == new:
            continue
        if field == "terms_version":
            changes.append([label, f"Bản {old}" if old else None, f"Bản {new} — vui lòng đọc lại"])
        elif field.endswith("_date"):
            changes.append([label, format_date_only(old) if old else None, format_date_only(new)])
        elif field.endswith("_at"):
            changes.append([label, format_vn(old) if old else None, format_vn(new) if new else None])
        else:
            changes.append([label, old, new])
    return changes


# --- BTC sửa mục CBNV đã chọn ---


def snapshot(entity_type: str, item: Any) -> dict[str, Any]:
    return {field: getattr(item, field) for field in WATCHED_FIELDS[entity_type]}


def queue_choice_change(
    db: Session,
    *,
    entity_type: str,
    item: Any,
    before: dict[str, Any],
    actor: User,
    notify: bool = False,
    ip_address: str | None = None,
) -> list[dict[str, Any]]:
    """So `before` với giá trị hiện tại của `item`; có trường nhìn thấy được đổi thì xếp email
    cho mọi người đang dùng mục đó. Gọi SAU khi đã gán giá trị mới, TRƯỚC commit.
    `notify=False` (BTC không tích "Gửi email") thì không làm gì.
    """
    if not notify:
        return []
    after = snapshot(entity_type, item)
    changed = [field for field in WATCHED_FIELDS[entity_type] if before[field] != after[field]]
    if not changed:
        return []

    registrations = _registrations_using(db, entity_type, item.id)
    if not registrations:
        return []

    labels = WATCHED_FIELDS[entity_type]
    changes = [
        [
            labels[field],
            _display(db, field, before[field]),
            _display(db, field, after[field]),
        ]
        for field in changed
    ]
    item_name = after.get("name") or before.get("name") or f"#{item.id}"
    audit = audit_service.log(
        db,
        action=CHOICE_AUDIT_ACTION,
        entity_type=entity_type,
        entity_id=item.id,
        actor_id=actor.id,
        # Địa điểm xuất phát dùng chung mọi kỳ nên không có event_id.
        event_id=getattr(item, "event_id", None),
        after={
            "item_name": item_name,
            "changes": changes,
            "user_ids": sorted({registration.user_id for registration in registrations}),
        },
        ip_address=ip_address,
    )
    db.flush()

    queued = []
    notified: set[tuple[int, int]] = set()
    for registration in registrations:
        user, event = registration.user, registration.event
        key = (user.id, event.id)
        if key in notified or not user.is_active or not user.email:
            continue
        notified.add(key)
        context = email_templates.choice_change_context(
            event=event,
            user=user,
            subject_label=SUBJECT_LABELS[entity_type],
            item_name=item_name,
            changes=changes,
        )
        queued.append((_enqueue(db, CHOICE_TEMPLATE, user, context, audit), context))

    jobs = _jobs(db, queued)
    logger.info(
        "%s #%s đổi %s: xếp %d email báo CBNV", entity_type, item.id, changed, len(jobs)
    )
    return jobs


def _registrations_using(db: Session, entity_type: str, item_id: int) -> list[Registration]:
    """Đăng ký còn hiệu lực đang dùng mục này, ở những kỳ chưa kết thúc."""
    query = (
        select(Registration)
        .join(Event, Event.id == Registration.event_id)
        .where(
            Registration.status == RegistrationStatus.SUBMITTED,
            Registration.is_participating.is_(True),
            Event.status != EventStatus.COMPLETED,
        )
        .options(selectinload(Registration.user), selectinload(Registration.event))
        .order_by(Registration.id)
    )
    if entity_type == "shift":
        query = query.where(Registration.shift_id == item_id)
    elif entity_type == "work_location":
        query = query.where(Registration.departure_location_id == item_id)
    else:
        column = (
            RegistrationBusNeed.trip_leg_id
            if entity_type == "trip_leg"
            else RegistrationBusNeed.pickup_point_id
        )
        query = query.where(
            Registration.id.in_(
                select(RegistrationBusNeed.registration_id).where(
                    column == item_id, RegistrationBusNeed.needs_bus.is_(True)
                )
            )
        )
    return list(db.scalars(query))


def _display(db: Session, field: str, value: Any) -> str | None:
    if value is None or value == "":
        return None
    if field == "trip_leg_id":
        leg = db.get(TripLeg, value)
        return leg.name if leg else f"#{value}"
    if field == "direction":
        return _DIRECTION_LABELS.get(str(value), str(value))
    if field == "leg_date":
        return format_date_only(value)
    if isinstance(value, bool):
        return "Có" if value else "Không"
    return str(value)


# --- Gửi lại thư lỗi ---


def rebuild_email_context(db: Session, *, template: str, audit: AuditLog, user: User) -> dict | None:
    """Dựng lại context cho một thư lỗi từ dòng audit gốc. None = thư không còn đúng nữa."""
    after = json.loads(audit.after_data or "{}")

    if template == STATUS_TEMPLATE:
        from app.services import event_service

        event = db.get(Event, audit.event_id) if audit.event_id else None
        before = json.loads(audit.before_data or "{}")
        # Kỳ đã sang trạng thái khác thì thư này báo sai tình hình.
        if event is None or not before.get("status") or event.status != after.get("status"):
            return None
        previous, new = EventStatus(before["status"]), EventStatus(event.status)
        return email_templates.event_status_context(
            event=event,
            user=user,
            previous_status=previous,
            previous_label=event_service.status_label(previous),
            new_label=event_service.status_label(new),
            is_forward=new.at_least(previous),
            reason=audit.reason,
        )

    if template == EVENT_INFO_TEMPLATE:
        event = db.get(Event, audit.event_id) if audit.event_id else None
        if event is None:
            return None
        # `after` của event.updated là diff {trường: {before, after}}: chỉ gửi lại khi kỳ vẫn
        # giữ đúng giá trị mới đó.
        if any(getattr(event, field) != change.get("after") for field, change in after.items()):
            return None
        changes = _event_info_changes(
            event, {field: change.get("before") for field, change in after.items()}
        )
        if not changes:
            return None
        return email_templates.event_info_context(event=event, user=user, changes=changes)

    # Thư đổi mục đã chọn: chỉ còn đúng khi người đó vẫn đang dùng mục ấy.
    if audit.entity_type not in WATCHED_FIELDS or audit.entity_id is None:
        return None
    using = [
        registration
        for registration in _registrations_using(db, audit.entity_type, audit.entity_id)
        if registration.user_id == user.id
    ]
    if not using:
        return None
    return email_templates.choice_change_context(
        event=using[0].event,
        user=user,
        subject_label=SUBJECT_LABELS[audit.entity_type],
        item_name=after.get("item_name") or "",
        changes=after.get("changes") or [],
    )


# --- Nội bộ ---


def _enqueue(db: Session, template: str, user: User, context: dict, audit: AuditLog):
    return email_service.enqueue(
        db,
        template=template,
        to_email=user.email,
        context=context,
        user_id=user.id,
        related_type=RELATED_TYPE,
        related_id=audit.id,
    )


def _jobs(db: Session, queued: list) -> list[dict[str, Any]]:
    db.flush()  # cần id của dòng nhật ký email
    return [{"log_id": entry.id, "context": context} for entry, context in queued]
