"""Email báo CBNV khi BTC thêm / sửa / xoá mốc lịch trình SAU khi đã công bố.

Cùng cách làm với `journey_notice_service`: chụp lịch trình mỗi người tham gia đang thấy
**trước** và **sau** thao tác rồi so. Luật "ai thấy mốc nào" (audience = all / mã ca được xếp /
mã team, mốc gắn chặng chỉ cho người đi xe chặng đó, ẩn mốc chung đã xong trước giờ hạ cánh)
lấy nguyên từ `journey_service.published_itinerary` — nên thư đến đúng người thấy mốc đó,
kể cả khi BTC đổi đối tượng của mốc (người mất mốc và người được thêm mốc đều nhận thư).

Chỉ chạy khi kỳ đã công bố và BTC tích "Gửi email" (`notify`). Trước công bố CBNV chưa thấy
lịch theo ca, báo "đổi" là thừa.

Tách khỏi `journey_notice_service` có chủ đích: sửa giờ bay / xe cũng làm mốc gắn chặng đổi
giờ theo, nếu gộp chung thì mỗi lần sửa chuyến bay CBNV nhận thư hai lần cho cùng một việc.
"""

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.timeutils import format_date_only
from app.models.audit import AuditLog
from app.models.enums import EventStatus, RegistrationStatus
from app.models.event import Event
from app.models.registration import Registration
from app.models.user import User
from app.services import audit_service, email_service, email_templates, journey_service

logger = logging.getLogger(__name__)

TEMPLATE = "itinerary_changed"
RELATED_TYPE = "audit_log"
AUDIT_ACTION = "itinerary.notified"

Row = dict[str, str]  # nhãn -> giá trị đã dịch sang chữ
Snapshot = dict[int, dict[int, Row]]  # user_id -> itinerary_id -> mốc

FIELDS = ("Ngày", "Giờ", "Tiêu đề", "Địa điểm", "Mô tả")


class ItineraryTracker:
    """Dùng trong router quanh một thao tác sửa lịch trình:

        tracker = ItineraryTracker(db, event, notify=notify)   # chụp TRƯỚC
        ... gọi service + audit + commit ...
        jobs = tracker.finish(actor=actor, action="itinerary.updated")  # chụp SAU, xếp thư, commit

    Không bật (`notify=False` hoặc kỳ chưa công bố) thì cả hai bước là no-op.
    """

    def __init__(self, db: Session, event: Event, *, notify: bool) -> None:
        self.db = db
        self.event_id = event.id
        self.enabled = bool(notify) and EventStatus(event.status).at_least(
            EventStatus.INFORMATION_PUBLISHED
        )
        self.before: Snapshot = snapshot(db, event) if self.enabled else {}

    def finish(
        self, *, actor: User, action: str, ip_address: str | None = None
    ) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        self.db.expire_all()  # service vừa commit
        event = self.db.get(Event, self.event_id)
        after = snapshot(self.db, event)
        jobs = queue_changes(
            self.db, event=event, before=self.before, after=after, actor=actor,
            action=action, ip_address=ip_address,
        )
        self.db.commit()
        return jobs


# --- Chụp ---


def snapshot(db: Session, event: Event, *, user_ids: set[int] | None = None) -> Snapshot:
    """Lịch trình từng người đang tham gia thấy. Mốc sinh thêm (id None — "tự ra sân bay")
    không do BTC gõ nên bỏ qua."""
    query = (
        select(Registration)
        .where(
            Registration.event_id == event.id,
            Registration.status == RegistrationStatus.SUBMITTED,
            Registration.is_participating.is_(True),
        )
        .options(selectinload(Registration.user).selectinload(User.team))
    )
    if user_ids is not None:
        query = query.where(Registration.user_id.in_(user_ids))

    result: Snapshot = {}
    for registration in db.scalars(query):
        rows = journey_service.published_itinerary(
            db, event=event, registration=registration, user=registration.user
        )
        result[registration.user_id] = {
            row["id"]: _row(row) for row in rows if row.get("id") is not None
        }
    return result


def _row(item: dict[str, Any]) -> Row:
    clock = " – ".join(filter(None, [item.get("start_time"), item.get("end_time")]))
    return {
        "Ngày": format_date_only(item["day_date"]),
        "Giờ": clock or "Cả ngày",
        "Tiêu đề": item.get("title") or "",
        "Địa điểm": item.get("location") or "",
        "Mô tả": item.get("description") or "",
    }


def _summary(row: Row) -> str:
    return " · ".join(filter(None, [f"{row['Ngày']} {row['Giờ']}", row["Tiêu đề"], row["Địa điểm"]]))


# --- So và xếp thư ---


def diff(before: dict[int, Row], after: dict[int, Row]) -> list[list[str | None]]:
    """[[nhãn, cũ, mới], …] cho MỘT người. Rỗng = lịch trình của người đó không đổi."""
    changes: list[list[str | None]] = []
    ordered = sorted(
        set(before) | set(after),
        key=lambda item_id: _sort_key(after.get(item_id) or before[item_id], item_id),
    )
    for item_id in ordered:
        old, new = before.get(item_id), after.get(item_id)
        if old == new:
            continue
        if old is None:
            changes.append(["Mốc mới", None, _summary(new)])
        elif new is None:
            changes.append(["Mốc bị bỏ", _summary(old), "Không còn trong lịch trình của bạn"])
        else:
            title = old["Tiêu đề"]
            for label in FIELDS:
                if old.get(label) != new.get(label):
                    changes.append([f"{title} · {label}", old.get(label) or None, new.get(label) or None])
    return changes


def queue_changes(
    db: Session, *, event: Event, before: Snapshot, after: Snapshot, actor: User,
    action: str, ip_address: str | None = None,
) -> list[dict[str, Any]]:
    per_user: dict[int, list] = {}
    touched: dict[int, dict[str, Row | None]] = {}
    for user_id in set(before) | set(after):
        old, new = before.get(user_id, {}), after.get(user_id, {})
        changes = diff(old, new)
        if not changes:
            continue
        per_user[user_id] = changes
        touched[user_id] = {
            str(item_id): new.get(item_id)
            for item_id in set(old) | set(new)
            if old.get(item_id) != new.get(item_id)
        }
    if not per_user:
        return []

    audit = audit_service.log(
        db,
        action=AUDIT_ACTION,
        entity_type="event",
        entity_id=event.id,
        actor_id=actor.id,
        event_id=event.id,
        after={
            "trigger": action,
            "changes": {str(user_id): changes for user_id, changes in per_user.items()},
            # Trạng thái "sau" của từng mốc đã đổi — gửi lại thư lỗi so với cái này.
            "items": {str(user_id): items for user_id, items in touched.items()},
        },
        ip_address=ip_address,
    )
    db.flush()

    queued = []
    for user_id in sorted(per_user):
        user = db.get(User, user_id)
        if user is None or not user.is_active or not user.email:
            continue
        context = email_templates.itinerary_change_context(
            event=event, user=user, changes=per_user[user_id]
        )
        entry = email_service.enqueue(
            db, template=TEMPLATE, to_email=user.email, context=context, event_id=event.id,
            user_id=user.id, related_type=RELATED_TYPE, related_id=audit.id,
        )
        queued.append((entry, context))
    db.flush()
    logger.info("%s: xếp %d email báo đổi lịch trình", action, len(queued))
    return [{"log_id": entry.id, "context": context} for entry, context in queued]


def rebuild_email_context(db: Session, *, audit: AuditLog, user: User) -> dict | None:
    """Gửi lại thư lỗi: chỉ khi lịch trình hiện tại của người đó vẫn đúng như "sau thay đổi"."""
    event = db.get(Event, audit.event_id) if audit.event_id else None
    if event is None or not EventStatus(event.status).at_least(EventStatus.INFORMATION_PUBLISHED):
        return None
    after = json.loads(audit.after_data or "{}")
    changes = (after.get("changes") or {}).get(str(user.id))
    expected = (after.get("items") or {}).get(str(user.id))
    if not changes or expected is None:
        return None
    current = snapshot(db, event, user_ids={user.id}).get(user.id)
    if current is None:
        return None  # không còn tham gia
    for item_id, row in expected.items():
        if current.get(int(item_id)) != row:
            return None  # đã đổi tiếp sau thư này — nội dung thư không còn đúng
    return email_templates.itinerary_change_context(event=event, user=user, changes=changes)


def _sort_key(row: Row, item_id: int) -> tuple:
    # "dd/mm/yyyy" -> yyyy-mm-dd để sắp theo ngày thật.
    day, month, year = (row["Ngày"].split("/") + ["", "", ""])[:3]
    return (year, month, day, row["Giờ"], item_id)
