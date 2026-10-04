"""Rà những thứ đã xếp không còn khớp cấu hình kỳ.

BTC sửa ngày của kỳ, giờ sớm nhất của ca bay, ngày của chặng hay số phút đệm giữa xe và máy bay
thì chuyến bay / xe / lịch trình đã nhập trước đó có thể nằm lệch ra ngoài. Không chặn việc sửa —
cấu hình thường phải đổi trước rồi mới đi chỉnh từng chuyến — mà liệt kê đúng thứ đang lệch để BTC
biết phải phân bổ lại ở đâu.

Chỉ đọc, và tính lại mỗi lần gọi: lưu "có cần rà lại không" vào một cột là thứ sẽ lệch với thực tế
ngay sau lần sửa xe đầu tiên (CLAUDE.md cạm bẫy #19).
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timeutils import format_date_only, format_vn, to_vn
from app.models.accommodation import Hotel
from app.models.content import ItineraryItem
from app.models.enums import FlightDirection
from app.models.event import Event
from app.models.flight import Flight, Shift
from app.models.transportation import Bus, TripLeg
from app.services import transport_timing_service

MAX_DETAILS = 10


def check(db: Session, event: Event) -> dict[str, Any]:
    items = [
        item
        for item in (
            _flights_outside_dates(db, event),
            _buses_outside_dates(db, event),
            _legs_outside_dates(db, event),
            _itinerary_outside_dates(db, event),
            _hotels_outside_dates(db, event),
            _bus_flight_mismatches(db, event),
            _flights_before_shift(db, event),
        )
        if item is not None
    ]
    return {"needs_review": bool(items), "items": items}


# --- Ngoài khoảng ngày của kỳ ---


def _flights_outside_dates(db: Session, event: Event) -> dict[str, Any] | None:
    details = [
        f"{flight.flight_code}: cất cánh {format_vn(flight.departure_time)}, "
        f"hạ cánh {format_vn(flight.arrival_time)}"
        for flight in db.scalars(
            select(Flight).where(Flight.event_id == event.id).order_by(Flight.departure_time)
        )
        if _outside(event, flight.departure_time) or _outside(event, flight.arrival_time)
    ]
    return _item(
        "flight_outside_dates",
        f"Chuyến bay nằm ngoài ngày của kỳ ({_range_label(event)})",
        details,
        "/admin/flights",
    )


def _buses_outside_dates(db: Session, event: Event) -> dict[str, Any] | None:
    details = []
    first_leg_id = None
    for bus in db.scalars(select(Bus).where(Bus.event_id == event.id).order_by(Bus.bus_code)):
        moment = bus.departure_time or bus.gather_time
        if moment and _outside(event, moment):
            details.append(f"{bus.bus_code}: chạy lúc {format_vn(moment)}")
            first_leg_id = first_leg_id or bus.trip_leg_id
    return _item(
        "bus_outside_dates",
        f"Xe chạy ngoài ngày của kỳ ({_range_label(event)})",
        details,
        _buses_link(first_leg_id),
    )


def _legs_outside_dates(db: Session, event: Event) -> dict[str, Any] | None:
    details = [
        f"{leg.name}: {format_date_only(leg.leg_date)}"
        for leg in db.scalars(
            select(TripLeg).where(TripLeg.event_id == event.id).order_by(TripLeg.display_order)
        )
        if leg.leg_date and not _in_range(event, leg.leg_date)
    ]
    return _item(
        "leg_outside_dates",
        f"Chặng di chuyển có ngày nằm ngoài kỳ ({_range_label(event)})",
        details,
        "/admin/settings?tab=legs",
    )


def _itinerary_outside_dates(db: Session, event: Event) -> dict[str, Any] | None:
    details = [
        f"{format_date_only(row.day_date)} {row.start_time or ''} {row.title}".replace("  ", " ")
        for row in db.scalars(
            select(ItineraryItem)
            .where(ItineraryItem.event_id == event.id)
            .order_by(ItineraryItem.day_date, ItineraryItem.start_time)
        )
        if not _in_range(event, row.day_date)
    ]
    return _item(
        "itinerary_outside_dates",
        f"Mốc lịch trình nằm ngoài ngày của kỳ ({_range_label(event)})",
        details,
        "/admin/itinerary",
    )


def _hotels_outside_dates(db: Session, event: Event) -> dict[str, Any] | None:
    details = []
    for hotel in db.scalars(select(Hotel).where(Hotel.event_id == event.id).order_by(Hotel.name)):
        bad = [
            f"{label} {format_vn(moment)}"
            for label, moment in (("nhận phòng", hotel.check_in_at), ("trả phòng", hotel.check_out_at))
            if moment and _outside(event, moment)
        ]
        if bad:
            details.append(f"{hotel.name}: {', '.join(bad)}")
    return _item(
        "hotel_outside_dates",
        f"Giờ nhận / trả phòng khách sạn nằm ngoài kỳ ({_range_label(event)})",
        details,
        "/admin/rooms",
    )


# --- Giờ xe, giờ bay ---


def _bus_flight_mismatches(db: Session, event: Event) -> dict[str, Any] | None:
    issues = transport_timing_service.bus_timing_issues(db, event_id=event.id)
    if not issues:
        return None
    buses = {
        bus.id: bus for bus in db.scalars(select(Bus).where(Bus.id.in_(list(issues))))
    }
    ordered = sorted(issues, key=lambda bus_id: buses[bus_id].bus_code)
    details = [f"{buses[bus_id].bus_code}: {'; '.join(issues[bus_id])}" for bus_id in ordered]
    return _item(
        "bus_flight_mismatch",
        "Xe đưa đón lệch giờ chuyến bay",
        details,
        _buses_link(buses[ordered[0]].trip_leg_id),
    )


def _flights_before_shift(db: Session, event: Event) -> dict[str, Any] | None:
    """Chuyến chiều đi cất cánh sớm hơn giờ sớm nhất của ca nó thuộc về.

    Chỉ xét chiều đi: ca bay là thứ CBNV chọn cho lượt đi, chiều về không gắn với giờ này.
    """
    rows = db.execute(
        select(Flight, Shift)
        .join(Shift, Shift.id == Flight.shift_id)
        .where(
            Flight.event_id == event.id,
            Flight.direction == FlightDirection.OUTBOUND,
            Shift.earliest_departure.is_not(None),
        )
        .order_by(Flight.departure_time)
    ).all()
    details = [
        f"{flight.flight_code}: cất cánh {format_vn(flight.departure_time)}, "
        f"{shift.name} bay sớm nhất {shift.earliest_departure}"
        for flight, shift in rows
        if to_vn(flight.departure_time).strftime("%H:%M") < shift.earliest_departure
    ]
    return _item(
        "flight_before_shift",
        "Chuyến bay cất cánh sớm hơn giờ sớm nhất của ca",
        details,
        "/admin/flights",
    )


# --- Nội bộ ---


def _item(kind: str, title: str, details: list[str], link: str) -> dict[str, Any] | None:
    if not details:
        return None
    return {
        "kind": kind,
        "title": title,
        "count": len(details),
        "details": details[:MAX_DETAILS],
        "link": link,
    }


def _in_range(event: Event, day: str) -> bool:
    return event.start_date <= day[:10] <= event.end_date


def _outside(event: Event, moment: str) -> bool:
    """Mốc giờ UTC có rơi ra ngoài ngày của kỳ không — so theo NGÀY VIỆT NAM.

    Chuyến 00:30 ngày 15/10 giờ Việt Nam lưu thành 17:30 ngày 14/10 UTC; so chuỗi UTC là báo nhầm.
    """
    try:
        day = to_vn(moment).strftime("%Y-%m-%d")
    except ValueError:
        return False
    return not _in_range(event, day)


def _range_label(event: Event) -> str:
    return f"{format_date_only(event.start_date)} – {format_date_only(event.end_date)}"


def _buses_link(trip_leg_id: int | None) -> str:
    return f"/admin/buses?leg={trip_leg_id}" if trip_leg_id else "/admin/buses"
