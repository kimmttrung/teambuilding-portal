# backend/app/rag/knowledge.py
"""Knowledge base của trợ lý: CHỈ thông tin chung, công khai với mọi CBNV (ADR-004).

Nguồn được phép:
    - kỳ Team Building: tên, điểm đến, thời gian, hạn đăng ký, trạng thái
    - policy_documents: quy định, FAQ, hướng dẫn
    - itinerary_items: lịch trình từng ngày
    - announcements: thông báo gửi TẤT CẢ đã công bố
    - CHỈ KHI BTC ĐÃ CÔNG BỐ: danh sách chuyến bay, xe từng chặng + điểm đón, khách sạn, địa điểm Gala

KHÔNG BAO GIỜ đọc: users, registrations, *_assignments, tên/SĐT Trưởng xe và tài xế, người ở cùng phòng,
ghế Gala của ai. Muốn thêm nguồn phải sửa file này — và `tests/test_rag_knowledge.py` sẽ đỏ nếu dữ liệu
cá nhân lọt vào.

Hàm trả về dataclass thuần (không ORM) để dùng được sau khi session đóng.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.timeutils import format_date_only, format_vn
from app.models.accommodation import Hotel
from app.models.content import Announcement, ItineraryItem, PolicyDocument
from app.models.enums import AnnouncementTarget, EventStatus, FlightDirection
from app.models.event import Event
from app.models.flight import Flight
from app.models.gala import GalaLayout, GalaSeat, GalaTable
from app.models.transportation import Bus, PickupPoint, TripLeg
from app.services.event_service import status_label

WEEKDAYS = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"]
DIRECTION_LABELS = {FlightDirection.OUTBOUND: "chiều đi", FlightDirection.RETURN: "chiều về"}


@dataclass(frozen=True)
class KnowledgeDoc:
    source_type: str  # terms | faq | guide | itinerary | announcement | event | flight | bus | hotel | gala
    source_id: str  # định danh ổn định để re-index: "policy:3", "itinerary:2026-10-16"
    title: str
    text: str  # markdown


def build_documents(db: Session, event: Event) -> list[KnowledgeDoc]:
    published = EventStatus(event.status).at_least(EventStatus.INFORMATION_PUBLISHED)
    docs = [_event_overview(event, published)]
    docs += _policies(db, event.id)
    docs += _itinerary(db, event.id)
    docs += _announcements(db, event.id)
    if published:
        docs += _flights(db, event.id)
        docs += _buses(db, event.id)
        docs += _hotels(db, event.id)
        docs += _gala(db, event.id)
    return [doc for doc in docs if doc.text.strip()]


# --- Thông tin chung ---


def _event_overview(event: Event, published: bool) -> KnowledgeDoc:
    lines = [
        f"## {event.name}",
        f"- Điểm đến: {event.destination or 'chưa công bố'}",
        f"- Thời gian: {_day_label(event.start_date)} đến {_day_label(event.end_date)}",
        f"- Trạng thái chương trình: {status_label(EventStatus(event.status))}",
    ]
    if event.registration_closes_at:
        lines.append(f"- Hạn đăng ký: {format_vn(event.registration_closes_at)} (giờ Việt Nam)")
    lines.append(
        "- Ban tổ chức ĐÃ công bố chuyến bay, xe, khách sạn. Mỗi CBNV xem chuyến bay, xe, phòng, ghế của mình ở mục Hành trình của tôi."
        if published
        else "- Ban tổ chức CHƯA công bố phân bổ chuyến bay, xe, phòng. Thông tin sẽ hiện ở mục Hành trình của tôi khi công bố."
    )
    return KnowledgeDoc("event", f"event:{event.id}", "Thông tin chương trình", "\n".join(lines))


def _policies(db: Session, event_id: int) -> list[KnowledgeDoc]:
    rows = db.scalars(
        select(PolicyDocument)
        .where(or_(PolicyDocument.event_id == event_id, PolicyDocument.event_id.is_(None)))
        .order_by(PolicyDocument.id)
    )
    return [KnowledgeDoc(row.doc_type, f"policy:{row.id}", row.title, row.content) for row in rows]


def _itinerary(db: Session, event_id: int) -> list[KnowledgeDoc]:
    by_day: dict[str, list[ItineraryItem]] = defaultdict(list)
    for item in db.scalars(
        select(ItineraryItem)
        .where(ItineraryItem.event_id == event_id)
        .order_by(ItineraryItem.day_date, ItineraryItem.start_time, ItineraryItem.display_order)
    ):
        by_day[item.day_date].append(item)

    docs = []
    last = len(by_day)
    for number, (day, items) in enumerate(sorted(by_day.items()), start=1):
        # Người hỏi "sáng ngày đầu tiên làm gì?" không biết đó là 15/10 — ghi rõ thứ tự ngày.
        nickname = " (ngày đầu tiên)" if number == 1 else " (ngày cuối)" if number == last else ""
        title = f"Lịch trình ngày {number}{nickname} – {_day_label(day)}"
        lines = [f"## {title}"]
        for item in items:
            time = "–".join(part for part in (item.start_time, item.end_time) if part) or "Cả ngày"
            line = f"- {time}: {item.title}"
            if item.location:
                line += f" — tại {item.location}"
            if item.audience and item.audience != "all":
                line += f" (dành cho nhóm {item.audience})"
            lines.append(line)
            if item.description:
                lines.append(f"  {item.description}")
        docs.append(KnowledgeDoc("itinerary", f"itinerary:{day}", title, "\n".join(lines)))
    return docs


def _announcements(db: Session, event_id: int) -> list[KnowledgeDoc]:
    rows = db.scalars(
        select(Announcement)
        .where(
            Announcement.event_id == event_id,
            Announcement.target_type == AnnouncementTarget.ALL,  # thông báo nhóm/cá nhân không vào KB
            Announcement.published_at.is_not(None),
        )
        .order_by(Announcement.published_at.desc())
    )
    return [
        KnowledgeDoc(
            "announcement",
            f"announcement:{row.id}",
            row.title,
            f"## Thông báo: {row.title}\nĐăng lúc {format_vn(row.published_at)}\n\n{row.content}",
        )
        for row in rows
    ]


# --- Hậu cần chung (chỉ khi đã công bố) ---


def _flights(db: Session, event_id: int) -> list[KnowledgeDoc]:
    flights = db.scalars(
        select(Flight)
        .where(Flight.event_id == event_id, Flight.is_active.is_(True))
        .options(selectinload(Flight.shift))
        .order_by(Flight.direction, Flight.departure_time)
    ).all()
    docs = []
    for direction in FlightDirection:
        items = [flight for flight in flights if flight.direction == direction]
        if not items:
            continue
        lines = [f"## Các chuyến bay {DIRECTION_LABELS[direction]}"]
        for flight in items:
            line = (
                f"- {flight.flight_code}"
                f"{f' ({flight.airline})' if flight.airline else ''}: {flight.departure_airport} → {flight.arrival_airport}, "
                f"cất cánh {format_vn(flight.departure_time)}, hạ cánh {format_vn(flight.arrival_time)}"
            )
            if flight.shift:
                line += f" — {flight.shift.name}"
            lines.append(line)
        lines.append("Giờ theo giờ Việt Nam. Chuyến bay của từng người xem ở mục Hành trình của tôi.")
        docs.append(
            KnowledgeDoc("flight", f"flights:{direction.value}", f"Chuyến bay {DIRECTION_LABELS[direction]}", "\n".join(lines))
        )
    return docs


def _buses(db: Session, event_id: int) -> list[KnowledgeDoc]:
    legs = db.scalars(select(TripLeg).where(TripLeg.event_id == event_id).order_by(TripLeg.display_order)).all()
    docs = []
    for leg in legs:
        points = db.scalars(select(PickupPoint).where(PickupPoint.trip_leg_id == leg.id).order_by(PickupPoint.display_order)).all()
        buses = db.scalars(
            select(Bus)
            .where(Bus.trip_leg_id == leg.id)
            .options(selectinload(Bus.pickup_point), selectinload(Bus.linked_flight))
            .order_by(Bus.gather_time, Bus.bus_code)
        ).all()
        if not points and not buses:
            continue
        lines = [f"## Xe đưa đón chặng {leg.name}" + (f" ({_day_label(leg.leg_date)})" if leg.leg_date else "")]
        for point in points:
            lines.append(f"- Điểm đón: {point.name}" + (f" — {point.address}" if point.address else ""))
        for bus in buses:
            # Cố ý KHÔNG có tên/SĐT Trưởng xe, tài xế: đó là dữ liệu cá nhân, CBNV xem ở Hành trình.
            parts = [f"- Xe {bus.bus_code}"]
            if bus.pickup_point:
                parts.append(f"đón tại {bus.pickup_point.name}")
            if bus.gather_time:
                parts.append(f"tập trung {format_vn(bus.gather_time)}")
            if bus.departure_time:
                parts.append(f"xe chạy {format_vn(bus.departure_time)}")
            if bus.linked_flight:
                parts.append(f"đưa khách chuyến {bus.linked_flight.flight_code}")
            if bus.dropoff_point:
                parts.append(f"trả khách tại {bus.dropoff_point}")
            lines.append(", ".join(parts))
        lines.append("Có mặt trước giờ xe chạy 15 phút. Xe của từng người và SĐT Trưởng xe xem ở mục Hành trình của tôi.")
        docs.append(KnowledgeDoc("bus", f"bus-leg:{leg.id}", f"Xe đưa đón: {leg.name}", "\n".join(lines)))
    return docs


def _hotels(db: Session, event_id: int) -> list[KnowledgeDoc]:
    docs = []
    for hotel in db.scalars(select(Hotel).where(Hotel.event_id == event_id).order_by(Hotel.id)):
        lines = [f"## Khách sạn {hotel.name}"]
        if hotel.address:
            lines.append(f"- Địa chỉ: {hotel.address}")
        if hotel.phone:
            lines.append(f"- Điện thoại lễ tân: {hotel.phone}")
        if hotel.check_in_at:
            lines.append(f"- Nhận phòng (check-in): từ {format_vn(hotel.check_in_at)}")
        if hotel.check_out_at:
            lines.append(f"- Trả phòng (check-out): trước {format_vn(hotel.check_out_at)}")
        if hotel.map_url:
            lines.append(f"- Bản đồ: {hotel.map_url}")
        lines.append("Số phòng và người ở cùng phòng của từng người xem ở mục Hành trình của tôi.")
        docs.append(KnowledgeDoc("hotel", f"hotel:{hotel.id}", f"Khách sạn {hotel.name}", "\n".join(lines)))
    return docs


def _gala(db: Session, event_id: int) -> list[KnowledgeDoc]:
    docs = []
    for layout in db.scalars(select(GalaLayout).where(GalaLayout.event_id == event_id)):
        tables = db.scalar(select(func.count(GalaTable.id)).where(GalaTable.layout_id == layout.id)) or 0
        seats = db.scalar(
            select(func.count(GalaSeat.id)).join(GalaTable, GalaTable.id == GalaSeat.table_id).where(GalaTable.layout_id == layout.id)
        ) or 0
        lines = [f"## {layout.name}"]
        if layout.venue:
            lines.append(f"- Địa điểm: {layout.venue}")
        if layout.starts_at:
            lines.append(f"- Bắt đầu: {format_vn(layout.starts_at)} (giờ Việt Nam)")
        lines.append(f"- Sơ đồ: {tables} bàn, {seats} ghế")
        lines.append(
            "- Cách chọn chỗ: hệ thống bốc thăm thứ tự các team; tới lượt, Trưởng nhóm chọn ghế cho cả team rồi xếp "
            "thành viên vào ghế. Chỗ ngồi của từng người xem ở mục Hành trình của tôi."
        )
        docs.append(KnowledgeDoc("gala", f"gala:{layout.id}", layout.name, "\n".join(lines)))
    return docs


def _day_label(day: str | None) -> str:
    if not day:
        return "chưa xác định"
    try:
        weekday = WEEKDAYS[datetime.strptime(day[:10], "%Y-%m-%d").weekday()]
    except ValueError:
        return day
    return f"{weekday}, {format_date_only(day)}"
