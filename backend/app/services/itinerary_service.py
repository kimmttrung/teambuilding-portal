"""CRUD lịch trình chương trình (itinerary_items).

Lịch trình là xương sống của My Journey timeline: mỗi mốc có ngày, giờ, tiêu đề, địa điểm
và đối tượng (`all` hoặc mã ca/mã team). Giờ bay/xe thật vẫn nằm ở phân bổ — chỗ này chỉ
quản lý "chương trình chung", nên validation tập trung vào 3 thứ hay sai tay:

- ngày nằm ngoài kỳ (gõ 2026-11-15 trong khi kỳ chỉ 15–17/10),
- giờ kết thúc trước giờ bắt đầu,
- audience gõ sai mã ca/team (vd "Ca1" thay vì "CA1") khiến mốc biến mất với mọi người.
"""

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, NotFoundError
from app.models.content import ItineraryItem
from app.models.event import Event
from app.models.flight import Shift
from app.models.org import Team
from app.models.transportation import TripLeg

DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CLOCK_RE = re.compile(r"^([01][0-9]|2[0-3]):([0-5][0-9])$")


def list_items(db: Session, event: Event) -> list[ItineraryItem]:
    """Toàn bộ mốc của kỳ, đúng thứ tự My Journey hiển thị."""
    return list(
        db.scalars(
            select(ItineraryItem)
            .where(ItineraryItem.event_id == event.id)
            .order_by(ItineraryItem.day_date, ItineraryItem.display_order, ItineraryItem.start_time)
        ).all()
    )


def get_item(db: Session, event: Event, item_id: int) -> ItineraryItem:
    return _scoped(db, event, item_id)


def create_item(db: Session, event: Event, data: dict) -> ItineraryItem:
    """Thêm mốc mới. Không cho `display_order` thì nối vào cuối ngày đó."""
    payload = dict(data)
    _validate_item(db, event, payload)
    if payload.get("display_order") is None:
        payload["display_order"] = _next_order(db, event.id, payload["day_date"])
    item = ItineraryItem(event_id=event.id, is_indexed=False, **payload)
    db.add(item)
    db.flush()
    return item


def update_item(db: Session, event: Event, item_id: int, changes: dict) -> ItineraryItem:
    """Sửa mốc. Sửa gì cũng đánh dấu chưa nạp chatbot để Tibi không trả lời lịch cũ."""
    item = _scoped(db, event, item_id)
    merged = {
        "day_date": item.day_date,
        "start_time": item.start_time,
        "end_time": item.end_time,
        "title": item.title,
        "audience": item.audience,
        "trip_leg_id": item.trip_leg_id,
        **changes,
    }
    _validate_item(db, event, merged)
    for field, value in changes.items():
        setattr(item, field, value)
    item.is_indexed = False
    db.flush()
    return item


def delete_item(db: Session, event: Event, item_id: int) -> ItineraryItem:
    """Xoá mốc. Lịch trình không bị bảng nào tham chiếu nên xoá thẳng, có audit."""
    item = _scoped(db, event, item_id)
    db.delete(item)
    db.flush()
    return item


def reorder_day(
    db: Session, event: Event, day_date: str, ordered_ids: list[int]
) -> list[ItineraryItem]:
    """Xếp lại thứ tự các mốc trong một ngày theo đúng danh sách BTC kéo-thả."""
    _require_day_in_event(event, day_date)
    rows = db.scalars(
        select(ItineraryItem).where(
            ItineraryItem.event_id == event.id, ItineraryItem.day_date == day_date
        )
    ).all()
    by_id = {row.id: row for row in rows}
    unknown = [item_id for item_id in ordered_ids if item_id not in by_id]
    if unknown:
        raise NotFoundError(
            f"Ngày {day_date} không có các mốc #{', '.join(map(str, unknown))}.",
            code="ITINERARY_NOT_FOUND",
        )
    if set(ordered_ids) != set(by_id):
        raise AppError(
            f"Danh sách sắp xếp phải gồm đúng {len(by_id)} mốc của ngày {day_date} "
            f"(đang gửi {len(ordered_ids)}).",
            code="ITINERARY_REORDER_MISMATCH",
        )
    for order, item_id in enumerate(ordered_ids):
        by_id[item_id].display_order = order
        by_id[item_id].is_indexed = False
    db.flush()
    return [by_id[item_id] for item_id in ordered_ids]


def _scoped(db: Session, event: Event, item_id: int) -> ItineraryItem:
    item = db.get(ItineraryItem, item_id)
    if item is None or item.event_id != event.id:
        raise NotFoundError(
            f"Không tìm thấy mốc lịch trình #{item_id} trong kỳ này.",
            code="ITINERARY_NOT_FOUND",
        )
    return item


def _validate_item(db: Session, event: Event, payload: dict) -> None:
    _require_day_in_event(event, payload["day_date"])
    _require_valid_times(payload.get("start_time"), payload.get("end_time"))
    _require_audience(db, event, payload.get("audience") or "all")
    _require_trip_leg(db, event, payload.get("trip_leg_id"))


def _require_day_in_event(event: Event, day_date: str) -> None:
    if not DAY_RE.match(day_date or ""):
        raise AppError(
            f"Ngày '{day_date}' không đúng dạng YYYY-MM-DD.",
            code="ITINERARY_DAY_INVALID",
        )
    if not (event.start_date <= day_date <= event.end_date):
        raise AppError(
            f"Ngày {day_date} nằm ngoài kỳ ({event.start_date} – {event.end_date}).",
            code="ITINERARY_DAY_OUT_OF_RANGE",
            details={"start_date": event.start_date, "end_date": event.end_date},
        )


def _require_valid_times(start_time: str | None, end_time: str | None) -> None:
    for label, value in (("bắt đầu", start_time), ("kết thúc", end_time)):
        if value is not None and not CLOCK_RE.match(value):
            raise AppError(
                f"Giờ {label} '{value}' không đúng dạng HH:MM.",
                code="ITINERARY_TIME_INVALID",
            )
    if start_time and end_time and end_time <= start_time:
        raise AppError(
            f"Giờ kết thúc ({end_time}) phải sau giờ bắt đầu ({start_time}).",
            code="ITINERARY_TIME_INVALID",
        )


def _require_audience(db: Session, event: Event, audience: str) -> None:
    if audience == "all":
        return
    shift_codes = set(
        db.scalars(select(Shift.code).where(Shift.event_id == event.id)).all()
    )
    if audience in shift_codes:
        return
    team_codes = set(db.scalars(select(Team.code)).all())
    if audience in team_codes:
        return
    raise AppError(
        f"Đối tượng '{audience}' không tồn tại. Dùng 'all', mã ca "
        f"({', '.join(sorted(shift_codes)) or 'kỳ chưa có ca nào'}) hoặc mã team.",
        code="ITINERARY_AUDIENCE_UNKNOWN",
        details={"shifts": sorted(shift_codes), "teams": sorted(team_codes)},
    )


def _require_trip_leg(db: Session, event: Event, trip_leg_id: int | None) -> None:
    """Chặng phải thuộc chính kỳ này — gắn nhầm chặng của kỳ khác thì mốc biến mất với mọi
    người và không ai hiểu tại sao."""
    if trip_leg_id is None:
        return
    leg = db.get(TripLeg, trip_leg_id)
    if leg is None or leg.event_id != event.id:
        raise AppError(
            f"Chặng xe #{trip_leg_id} không thuộc kỳ này.",
            code="ITINERARY_TRIP_LEG_UNKNOWN",
        )


def _next_order(db: Session, event_id: int, day_date: str) -> int:
    current_max = db.scalar(
        select(func.max(ItineraryItem.display_order)).where(
            ItineraryItem.event_id == event_id, ItineraryItem.day_date == day_date
        )
    )
    return (current_max or 0) + 1 if current_max is not None else 0
