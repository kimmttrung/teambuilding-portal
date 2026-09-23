"""Dựng My Journey: mọi thứ một CBNV cần mang theo chuyến đi, trong một response.

Luật cứng (CLAUDE.md cạm bẫy #6): dữ liệu phân bổ — chuyến bay, xe, phòng, ghế Gala — chỉ
trả khi `event.status >= information_published`. Trước đó BTC còn đang xếp và sửa; lộ ra
sớm là CBNV chụp màn hình "tôi bay VN1234" rồi hôm sau bị đổi chuyến.

Lịch trình chung và thông báo thì luôn hiện: đó không phải kết quả phân bổ.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import NotFoundError
from app.core.timeutils import VN_TZ, from_iso, is_expired, to_iso
from app.models.accommodation import Room, RoomAssignment
from app.models.content import Announcement, ItineraryItem
from app.models.enums import (
    AnnouncementTarget,
    EventStatus,
    FlightDirection,
    RegistrationStatus,
)
from app.models.event import Event
from app.models.flight import Flight, FlightAssignment
from app.models.gala import GalaSeat, GalaSeatAssignment, GalaTable
from app.models.registration import Registration, RegistrationBusNeed
from app.models.transportation import Bus, BusAssignment, TripLeg
from app.models.user import User
from app.services import transport_timing_service

logger = logging.getLogger(__name__)

PARTS = ("flights", "buses", "accommodation", "gala")
REASON_NOT_PARTICIPATING = "not_participating"
REASON_NOT_PUBLISHED = "not_published"
REASON_NOT_ASSIGNED = "not_assigned"
ANNOUNCEMENT_LIMIT = 10


def require_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise NotFoundError(f"Không tìm thấy CBNV #{user_id}.", code="USER_NOT_FOUND")
    return user


def build_journey(db: Session, *, event: Event, user: User) -> dict[str, Any]:
    registration = _registration(db, event_id=event.id, user_id=user.id)
    participating = (
        registration is not None
        and registration.status == RegistrationStatus.SUBMITTED
        and registration.is_participating
    )
    published = EventStatus(event.status).at_least(EventStatus.INFORMATION_PUBLISHED)

    journey: dict[str, Any] = {
        "event": {
            "id": event.id,
            "code": event.code,
            "name": event.name,
            "status": event.status,
            "destination": event.destination,
            "start_date": event.start_date,
            "end_date": event.end_date,
            "is_published": published,
        },
        "profile": _profile(user),
        "registration": _registration_brief(registration),
        "flights": {"outbound": None, "return": None},
        "buses": [],
        # Không nằm trong khối `participating` bên dưới: Trưởng xe có thể là người không
        # đi chuyến này, chỉ ra điều phối ở điểm đón.
        "led_buses": _led_buses(db, event_id=event.id, user=user) if published else [],
        "accommodation": None,
        "gala": None,
        "pending": [],
        "pending_reasons": {},
    }

    def mark(part: str, reason: str) -> None:
        journey["pending"].append(part)
        journey["pending_reasons"][part] = reason

    flight_ids: set[int] = set()
    bus_ids: set[int] = set()
    assigned_shift_code: str | None = None
    arrival_at: str | None = None

    if not participating:
        for part in PARTS:
            mark(part, REASON_NOT_PARTICIPATING)
    elif not published:
        for part in PARTS:
            mark(part, REASON_NOT_PUBLISHED)
    else:
        flights, flight_ids, assigned_shift_code = _flights(db, registration)
        journey["flights"] = flights
        if flights["outbound"] is None or flights["return"] is None:
            mark("flights", REASON_NOT_ASSIGNED)
        if flights["outbound"] is not None:
            arrival_at = flights["outbound"].get("arrival_time")

        buses, needed, bus_ids = _buses(db, registration)
        journey["buses"] = buses
        # Chỉ "đang chờ" khi người này CÓ cần xe mà chưa đủ xe. Tự đi thì không chờ gì cả.
        if needed > len(buses):
            mark("buses", REASON_NOT_ASSIGNED)

        journey["accommodation"] = _accommodation(db, registration)
        if journey["accommodation"] is None:
            mark("accommodation", REASON_NOT_ASSIGNED)

        journey["gala"] = _gala(db, registration)
        if journey["gala"] is None:
            mark("gala", REASON_NOT_ASSIGNED)

    journey["itinerary"] = _itinerary(
        db,
        event_id=event.id,
        team_code=user.team.code if user.team else None,
        shift_code=assigned_shift_code,
        # Giờ hạ cánh thật (đã công bố mới có): mốc chung của ngày đến mà kết thúc
        # trước lúc mình hạ cánh thì mình không dự được — ẩn cho khỏi lẫn.
        arrival_at=arrival_at,
        # Mốc gắn chặng xe chỉ dành cho người đi xe chặng đó, và lấy giờ từ xe của chính họ.
        buses=journey["buses"],
        bus_needs=_bus_need_legs(db, registration) if participating else set(),
        flights=journey["flights"] if published else {},
    )
    journey["announcements"] = _announcements(
        db, event_id=event.id, user=user, flight_ids=flight_ids, bus_ids=bus_ids
    )
    return journey


# --- Thông tin cá nhân ---


def _registration(db: Session, *, event_id: int, user_id: int) -> Registration | None:
    return db.scalar(
        select(Registration)
        .where(Registration.event_id == event_id, Registration.user_id == user_id)
        .options(selectinload(Registration.shift))
    )


def _profile(user: User) -> dict[str, Any]:
    team = user.team
    return {
        "user_id": user.id,
        "full_name": user.full_name,
        "display_name": user.display_name,
        "employee_code": user.employee_code,
        "avatar_url": user.avatar_url,
        "phone": user.phone,
        "team": {"id": team.id, "name": team.name, "color": team.color} if team else None,
    }


def _registration_brief(registration: Registration | None) -> dict[str, Any] | None:
    if registration is None:
        return None
    shift = registration.shift
    return {
        "status": registration.status,
        "is_participating": registration.is_participating,
        "requested_shift_code": shift.code if shift else None,
        "requested_shift_name": shift.name if shift else None,
    }


# --- Phân bổ (chỉ gọi khi đã công bố) ---


def _flights(db: Session, registration: Registration) -> tuple[dict, set[int], str | None]:
    rows = db.scalars(
        select(FlightAssignment)
        .where(FlightAssignment.registration_id == registration.id)
        .options(selectinload(FlightAssignment.flight).selectinload(Flight.shift))
    ).all()

    flights: dict[str, Any] = {"outbound": None, "return": None}
    ids: set[int] = set()
    outbound_shift: str | None = None

    for row in rows:
        flight = row.flight
        ids.add(flight.id)
        flights[row.direction] = {
            "flight_code": flight.flight_code,
            "airline": flight.airline,
            "direction": flight.direction,
            "shift_code": flight.shift.code if flight.shift else None,
            "departure_airport": flight.departure_airport,
            "arrival_airport": flight.arrival_airport,
            "departure_time": flight.departure_time,
            "arrival_time": flight.arrival_time,
            "seat_number": row.seat_number,
            "ticket_code": row.ticket_code,
        }
        if row.direction == FlightDirection.OUTBOUND and flight.shift:
            outbound_shift = flight.shift.code

    return flights, ids, outbound_shift


def _buses(db: Session, registration: Registration) -> tuple[list[dict], int, set[int]]:
    rows = db.scalars(
        select(BusAssignment)
        .where(BusAssignment.registration_id == registration.id)
        .options(
            selectinload(BusAssignment.bus).selectinload(Bus.trip_leg),
            selectinload(BusAssignment.bus).selectinload(Bus.pickup_point),
            selectinload(BusAssignment.bus).selectinload(Bus.linked_flight),
            selectinload(BusAssignment.bus).selectinload(Bus.leader),
        )
    ).all()
    needed = (
        db.scalar(
            select(func.count())
            .select_from(RegistrationBusNeed)
            .where(
                RegistrationBusNeed.registration_id == registration.id,
                RegistrationBusNeed.needs_bus.is_(True),
            )
        )
        or 0
    )

    buses = []
    ids: set[int] = set()
    for row in sorted(rows, key=lambda item: item.bus.trip_leg.display_order):
        bus = row.bus
        leg = bus.trip_leg
        ids.add(bus.id)

        leader_name = bus.leader_name or (bus.leader.full_name if bus.leader else None)
        leader_phone = bus.leader_phone or (bus.leader.phone if bus.leader else None)
        point = bus.pickup_point

        buses.append(
            {
                "trip_leg": _leg(leg),
                "bus_id": bus.id,
                "bus_code": bus.bus_code,
                "plate_number": bus.plate_number,
                "gather_time": bus.gather_time,
                "departure_time": bus.departure_time,
                "pickup_point": _place(point),
                "dropoff_point": bus.dropoff_point,
                "leader": {"name": leader_name, "phone": leader_phone} if leader_name else None,
                "driver": (
                    {"name": bus.driver_name, "phone": bus.driver_phone} if bus.driver_name else None
                ),
                "linked_flight_code": bus.linked_flight.flight_code if bus.linked_flight else None,
            }
        )
    return buses, needed, ids


def _led_buses(db: Session, *, event_id: int, user: User) -> list[dict[str, Any]]:
    """Xe người này phụ trách, kể cả xe họ không tự đi (docs/13 task 2).

    Chỉ dữ liệu của chính chiếc xe — tên và số điện thoại hành khách nằm ở
    `GET /buses/{id}/passengers`, nơi `bus_service.ensure_can_view_passengers` chặn
    Trưởng xe khác. Không nhét danh sách vào đây: My Journey là response ai cũng gọi.
    """
    buses = db.scalars(
        select(Bus)
        .where(Bus.event_id == event_id, Bus.leader_user_id == user.id)
        .options(
            selectinload(Bus.trip_leg),
            selectinload(Bus.pickup_point),
            selectinload(Bus.linked_flight),
        )
    ).all()
    if not buses:
        return []

    counts = dict(
        db.execute(
            select(BusAssignment.bus_id, func.count(BusAssignment.id))
            .where(BusAssignment.bus_id.in_([bus.id for bus in buses]))
            .group_by(BusAssignment.bus_id)
        ).all()
    )

    return [
        {
            "bus_id": bus.id,
            "bus_code": bus.bus_code,
            "plate_number": bus.plate_number,
            "trip_leg": _leg(bus.trip_leg),
            "gather_time": bus.gather_time,
            "departure_time": bus.departure_time,
            "pickup_point": _place(bus.pickup_point),
            "linked_flight_code": bus.linked_flight.flight_code if bus.linked_flight else None,
            "capacity": bus.capacity,
            "passenger_count": counts.get(bus.id, 0),
        }
        for bus in sorted(buses, key=lambda item: (item.trip_leg.display_order, item.bus_code))
    ]


def _leg(leg) -> dict[str, Any]:
    return {
        "id": leg.id,
        "code": leg.code,
        "name": leg.name,
        "direction": leg.direction,
        "leg_date": leg.leg_date,
        "display_order": leg.display_order,
    }


def _place(point) -> dict[str, Any] | None:
    if point is None:
        return None
    return {"name": point.name, "address": point.address, "map_url": point.map_url}


def _accommodation(db: Session, registration: Registration) -> dict[str, Any] | None:
    assignment = db.scalar(
        select(RoomAssignment)
        .where(RoomAssignment.registration_id == registration.id)
        .options(selectinload(RoomAssignment.room).selectinload(Room.hotel))
    )
    if assignment is None:
        return None

    room = assignment.room
    hotel = room.hotel
    mates = db.scalars(
        select(RoomAssignment)
        .where(
            RoomAssignment.room_id == room.id,
            RoomAssignment.registration_id != registration.id,
        )
        .options(
            selectinload(RoomAssignment.registration)
            .selectinload(Registration.user)
            .selectinload(User.team)
        )
    ).all()

    roommates = [
        {
            "full_name": mate.registration.user.full_name,
            "phone": mate.registration.user.phone,
            "team_name": mate.registration.user.team.name if mate.registration.user.team else None,
            "is_room_captain": mate.is_room_captain,
        }
        for mate in mates
    ]
    roommates.sort(key=lambda item: (not item["is_room_captain"], item["full_name"]))

    return {
        "hotel_name": hotel.name,
        "address": hotel.address,
        "phone": hotel.phone,
        "map_url": hotel.map_url,
        "check_in_at": hotel.check_in_at,
        "check_out_at": hotel.check_out_at,
        "room_number": room.room_number,
        "room_type": room.room_type,
        "floor": room.floor,
        "is_room_captain": assignment.is_room_captain,
        "roommates": roommates,
    }


def _gala(db: Session, registration: Registration) -> dict[str, Any] | None:
    row = db.scalar(
        select(GalaSeatAssignment)
        .where(GalaSeatAssignment.registration_id == registration.id)
        .options(
            selectinload(GalaSeatAssignment.seat)
            .selectinload(GalaSeat.table)
            .selectinload(GalaTable.layout)
        )
    )
    if row is None:
        return None

    seat = row.seat
    table = seat.table
    layout = table.layout
    return {
        "name": layout.name,
        "venue": layout.venue,
        "starts_at": layout.starts_at,
        "table_code": table.table_code,
        "table_name": table.table_name,
        "seat_number": seat.seat_number,
    }


# --- Thông tin chung ---


def _bus_need_legs(db: Session, registration: Registration | None) -> set[int]:
    """Chặng mà người này ĐĂNG KÝ đi xe của BTC (dù đã được xếp xe hay chưa)."""
    if registration is None:
        return set()
    return set(
        db.scalars(
            select(RegistrationBusNeed.trip_leg_id).where(
                RegistrationBusNeed.registration_id == registration.id,
                RegistrationBusNeed.needs_bus.is_(True),
            )
        )
    )


def _itinerary(
    db: Session,
    *,
    event_id: int,
    team_code: str | None,
    shift_code: str | None,
    arrival_at: str | None = None,
    buses: list[dict[str, Any]] | None = None,
    bus_needs: set[int] | None = None,
    flights: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Lịch trình của riêng người này: mục chung + mục của team + mục của ca ĐƯỢC XẾP.

    Dùng ca của chuyến bay đã công bố, không dùng ca nguyện vọng: người xin Ca 2 nhưng bị xếp
    Ca 1 mà thấy "tập trung lúc 17:15" là ra sân bay trễ chuyến. Chưa công bố thì chưa hiện mục
    theo ca nào.

    Riêng ngày hạ cánh: mục chung (`all`) nào đã kết thúc trước giờ mình hạ cánh thì ẩn —
    người bay tối không dự được tiệc trưa, hiện ra chỉ thêm lẫn. Mục riêng của ca/team
    luôn giữ (đó là việc của chính họ), mục không có giờ kết thúc cũng giữ.

    Mốc gắn `trip_leg_id` (tập trung tại điểm đón, ra sân bay) là việc của riêng người ĐI XE
    chặng đó: ai không đăng ký xe thì tự thuê xe đi, mốc tập trung không liên quan tới họ.
    Đã xếp xe rồi thì giờ và địa điểm lấy từ CHÍNH xe đó, không dùng giờ BTC gõ trong lịch
    trình — hai nguồn giờ cho cùng một việc là lệch sớm muộn gì cũng xảy ra.
    """
    audiences = {"all"}
    if team_code:
        audiences.add(team_code)
    if shift_code:
        audiences.add(shift_code)
    arrival = _vn_moment(arrival_at)
    bus_by_leg = {
        item["trip_leg"]["id"]: item
        for item in (buses or [])
        if item.get("trip_leg")
    }
    needed_legs = (bus_needs or set()) | set(bus_by_leg)

    items = db.scalars(
        select(ItineraryItem)
        .where(ItineraryItem.event_id == event_id)
        .order_by(ItineraryItem.day_date, ItineraryItem.display_order, ItineraryItem.start_time)
    ).all()

    visible = []
    for item in items:
        if item.audience not in audiences:
            continue
        if item.trip_leg_id is not None and item.trip_leg_id not in needed_legs:
            continue
        if (
            arrival is not None
            # Mốc gắn chặng xe là việc đi lại của chính họ: nó LUÔN nằm trước giờ hạ cánh
            # (tập trung rồi mới bay), nên luật "ẩn mục đã xong trước khi mình tới" không
            # được đụng vào, nếu không người đi xe mất luôn mốc tập trung của mình.
            and item.trip_leg_id is None
            and item.audience == "all"
            and item.day_date == arrival[0]
            and item.end_time
            and item.end_time <= arrival[1]
        ):
            continue
        visible.append(
            _with_bus_times(
                {
                    "id": item.id,
                    "day_date": item.day_date,
                    "start_time": item.start_time,
                    "end_time": item.end_time,
                    "title": item.title,
                    "description": item.description,
                    "location": item.location,
                    "audience": item.audience,
                    "trip_leg_id": item.trip_leg_id,
                    "is_personal": item.trip_leg_id is not None,
                },
                bus_by_leg.get(item.trip_leg_id),
            )
        )

    visible.extend(_self_transport_items(db, event_id=event_id, flights=flights or {}, needed_legs=needed_legs))
    # Sắp lại theo dòng thời gian: giờ của mốc gắn xe vừa bị thay bằng giờ xe thật, và mốc
    # "tự di chuyển" là mốc sinh thêm — cả hai không theo `display_order` của lịch trình gốc.
    visible.sort(key=lambda row: (row["day_date"], row["start_time"] or "", row.get("display_order", 0)))
    return visible


def _with_bus_times(row: dict[str, Any], bus: dict[str, Any] | None) -> dict[str, Any]:
    """Thay giờ/địa điểm của mốc gắn chặng bằng giờ xe thật của người này (nếu đã xếp xe)."""
    if bus is None:
        return row
    gather = _vn_moment(bus.get("gather_time"))
    depart = _vn_moment(bus.get("departure_time"))
    if gather:
        row["day_date"], row["start_time"] = gather
    if depart and (not gather or depart[0] == row["day_date"]):
        row["end_time"] = depart[1]

    point = bus.get("pickup_point") or {}
    if point.get("name"):
        row["location"] = point["name"]
    label = " · ".join(filter(None, [bus.get("bus_code"), bus.get("plate_number")]))
    if label:
        row["description"] = " ".join(filter(None, [row.get("description"), f"Xe của bạn: {label}."]))
    return row


def _self_transport_items(
    db: Session, *, event_id: int, flights: dict[str, Any], needed_legs: set[int]
) -> list[dict[str, Any]]:
    """Mốc nhắc người KHÔNG đăng ký xe của BTC tự căn giờ ra sân bay.

    Ẩn mốc tập trung mà không nói gì thì họ chỉ còn mốc "chuyến bay 07:00" và dễ ra sân bay
    muộn. Chỉ sinh khi đã công bố (lúc đó mới biết chuyến thật của họ) và chỉ cho chặng gắn
    sân bay mà họ không đi xe.
    """
    outbound = flights.get("outbound") if flights else None
    if not outbound or not outbound.get("departure_time"):
        return []

    legs = list(
        db.scalars(
            select(TripLeg)
            .where(TripLeg.event_id == event_id, TripLeg.direction == FlightDirection.OUTBOUND)
            .order_by(TripLeg.display_order)
        )
    )
    to_airport = next(
        (
            leg
            for leg in legs
            if transport_timing_service.airport_side(leg, legs)
            == transport_timing_service.BEFORE_FLIGHT
        ),
        None,
    )
    if to_airport is None or to_airport.id in needed_legs:
        return []

    lead = transport_timing_service.self_transport_lead(db, event_id)
    be_there = _vn_moment(
        to_iso(from_iso(outbound["departure_time"]) - timedelta(minutes=lead))
    )
    if be_there is None:
        return []
    return [
        {
            "id": None,
            "day_date": be_there[0],
            "start_time": be_there[1],
            "end_time": None,
            "title": "Tự di chuyển ra sân bay",
            "description": (
                f"Bạn không đăng ký xe của Ban tổ chức ở chặng {to_airport.name}, nên tự sắp xếp "
                f"phương tiện. Có mặt tại sân bay trước {be_there[1]} để kịp làm thủ tục chuyến "
                f"{outbound.get('flight_code') or ''}".strip()
                + "."
            ),
            "location": outbound.get("departure_airport"),
            "audience": "all",
            "trip_leg_id": to_airport.id,
            "is_personal": True,
        }
    ]


def _vn_moment(iso_value: str | None) -> tuple[str, str] | None:
    """ISO UTC -> (ngày, giờ HH:MM) theo giờ Việt Nam. Sai định dạng thì bỏ qua lọc."""
    if not iso_value:
        return None
    try:
        moment = datetime.fromisoformat(iso_value)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=VN_TZ)
    local = moment.astimezone(VN_TZ)
    return (local.strftime("%Y-%m-%d"), local.strftime("%H:%M"))


def _announcements(
    db: Session, *, event_id: int, user: User, flight_ids: set[int], bus_ids: set[int]
) -> list[dict[str, Any]]:
    """Thông báo đã đến giờ đăng và nhắm đúng người này, mới nhất trước.

    Thông báo theo chuyến bay/xe chỉ tới được người khi phân bổ đã công bố — `flight_ids`
    và `bus_ids` rỗng trước thời điểm đó, nên không lộ phân bổ qua đường thông báo.
    """
    rows = db.scalars(
        select(Announcement)
        .where(Announcement.event_id == event_id, Announcement.published_at.is_not(None))
        .order_by(Announcement.published_at.desc())
    ).all()

    visible = []
    for row in rows:
        # published_at ở tương lai = BTC hẹn giờ đăng, chưa được hiện.
        if not is_expired(row.published_at):
            continue
        if not _targets(row, user=user, flight_ids=flight_ids, bus_ids=bus_ids):
            continue
        visible.append(
            {
                "id": row.id,
                "title": row.title,
                "content": row.content,
                "severity": row.severity,
                "published_at": row.published_at,
            }
        )
        if len(visible) >= ANNOUNCEMENT_LIMIT:
            break
    return visible


def _targets(row: Announcement, *, user: User, flight_ids: set[int], bus_ids: set[int]) -> bool:
    target = row.target_type
    if target == AnnouncementTarget.ALL:
        return True
    if target == AnnouncementTarget.TEAM:
        return user.team_id is not None and row.target_id == user.team_id
    if target == AnnouncementTarget.USER:
        return row.target_id == user.id
    if target == AnnouncementTarget.FLIGHT:
        return row.target_id in flight_ids
    if target == AnnouncementTarget.BUS:
        return row.target_id in bus_ids
    return False
