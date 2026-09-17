"""Tra cứu "người này đang ở đâu" cho BTC: chuyến bay, xe từng chặng, phòng, ghế Gala.

Vì sao cần endpoint riêng thay vì lọc ở frontend: danh sách `/flights` chỉ trả chuyến, `/rooms` chỉ trả
phòng — tên người nằm ở endpoint con của **từng** chuyến, **từng** xe. Lọc phía client sẽ phải tải hành
khách của mọi chuyến và mọi xe rồi mới biết ai ở đâu.

Khác `GET /journey/{user_id}` ở một điểm quan trọng: **không chặn theo `information_published`**.
Luật "chỉ xem sau công bố" sinh ra để chặn CBNV nhìn bản nháp phân bổ (docs/09 §4); BTC chính là người
đang xếp, chặn họ lúc `allocation_processing` thì tính năng vô dụng đúng lúc cần nhất. `/journey/me` và
`/journey/{user_id}` giữ nguyên hành vi cũ.

Không trả CCCD, ngày sinh, ghi chú sức khoẻ: màn hình này để biết chỗ ngồi, không phải để xem hồ sơ.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import NotFoundError
from app.models.accommodation import Hotel, Room, RoomAssignment
from app.models.enums import FlightDirection, RegistrationStatus
from app.models.event import Event
from app.models.flight import Flight, FlightAssignment, Shift
from app.models.gala import GalaSeat, GalaSeatAssignment, GalaTable
from app.models.org import Team
from app.models.registration import Registration
from app.models.transportation import Bus, BusAssignment, TripLeg
from app.models.user import User
from app.services.excel import normalize

SEARCH_LIMIT = 20


def search(db: Session, *, event: Event, query: str, limit: int = SEARCH_LIMIT) -> list[dict[str, Any]]:
    """Gợi ý người theo tên / email / mã nhân viên. Nhẹ — chỉ đủ để chọn đúng người.

    **Bỏ dấu khi so**: gõ "nguyen van a" phải ra "Nguyễn Văn A". SQLite không có hàm bỏ dấu nên `LIKE`
    trong SQL không làm được — thử trên dữ liệu thật, gõ "nguyen" ra 0 kết quả trong khi có 7 người tên
    Nguyễn. Vì vậy lọc bằng Python trên toàn bảng: vài trăm CBNV mỗi kỳ, một lượt quét là đủ nhanh, và
    đây là thứ BTC gõ liên tục nên sai còn tốn thời gian hơn nhiều.

    Không lọc theo "đã đăng ký": BTC hay tra cứu đúng những người **chưa** có gì để biết còn sót ai.
    """
    needle = normalize(query)
    if not needle:
        return []

    rows = db.execute(
        select(User, Team.name, Registration.status, Registration.is_participating)
        .outerjoin(Team, Team.id == User.team_id)
        .outerjoin(
            Registration,
            (Registration.user_id == User.id) & (Registration.event_id == event.id),
        )
        .order_by(User.full_name, User.id)
    ).all()

    found = []
    for user, team_name, status, participating in rows:
        haystack = normalize(f"{user.full_name} {user.email} {user.employee_code or ''}")
        if needle not in haystack:
            continue
        found.append(
            {
                "user_id": user.id,
                "full_name": user.full_name,
                "email": user.email,
                "employee_code": user.employee_code,
                "team_name": team_name,
                "registration_status": status,
                "is_participating": bool(participating) if status is not None else False,
            }
        )
        if len(found) >= limit:
            break
    return found


def locate(db: Session, *, event: Event, user_id: int) -> dict[str, Any]:
    """Vị trí chính xác của một người trong kỳ: ca, bay đi/về, xe từng chặng, phòng, ghế Gala.

    Mỗi mục kèm `*_id` để màn hình biết tô đỏ dòng/thẻ/ghế nào. Mục chưa xếp trả `None` chứ không bỏ
    khỏi response — "chưa có xe chặng 2" là thông tin BTC cần thấy, không phải chỗ trống im lặng.
    """
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError(f"Không tìm thấy CBNV #{user_id}.", code="USER_NOT_FOUND")

    team = db.get(Team, user.team_id) if user.team_id else None
    registration = db.scalar(
        select(Registration)
        .where(Registration.event_id == event.id, Registration.user_id == user_id)
        .options(selectinload(Registration.shift))
    )

    located: dict[str, Any] = {
        "user_id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "employee_code": user.employee_code,
        "phone": user.phone,
        "team_id": user.team_id,
        "team_name": team.name if team else None,
        "team_color": team.color if team else None,
        "registration_id": registration.id if registration else None,
        "registration_status": registration.status if registration else None,
        "is_participating": bool(registration.is_participating) if registration else False,
        "shift": _shift(registration),
        "flights": {"outbound": None, "return": None},
        "buses": _empty_legs(db, event.id),
        "room": None,
        "gala": None,
    }

    # Chưa đăng ký, hoặc đã huỷ / không tham gia: không có bản ghi phân bổ nào để tìm.
    # Vẫn trả khung đầy đủ để màn hình nói được "người này không tham gia" thay vì hiện lỗi.
    if registration is None or registration.status != RegistrationStatus.SUBMITTED:
        return located

    located["flights"] = _flights(db, registration.id)
    located["buses"] = _buses(db, event.id, registration.id)
    located["room"] = _room(db, registration.id)
    located["gala"] = _gala(db, event.id, registration.id)
    return located


def _shift(registration: Registration | None) -> dict[str, Any] | None:
    if registration is None or registration.shift is None:
        return None
    shift: Shift = registration.shift
    return {"id": shift.id, "code": shift.code, "name": shift.name}


def _flights(db: Session, registration_id: int) -> dict[str, Any]:
    result: dict[str, Any] = {"outbound": None, "return": None}
    rows = db.execute(
        select(FlightAssignment, Flight)
        .join(Flight, Flight.id == FlightAssignment.flight_id)
        .where(FlightAssignment.registration_id == registration_id)
    ).all()
    for assignment, flight in rows:
        key = "outbound" if assignment.direction == FlightDirection.OUTBOUND else "return"
        result[key] = {
            "flight_id": flight.id,
            "flight_code": flight.flight_code,
            "airline": flight.airline,
            "departure_airport": flight.departure_airport,
            "arrival_airport": flight.arrival_airport,
            "departure_time": flight.departure_time,
            "arrival_time": flight.arrival_time,
            "seat_number": assignment.seat_number,
            "assignment_mode": assignment.assignment_mode,
        }
    return result


def _empty_legs(db: Session, event_id: int) -> list[dict[str, Any]]:
    """Khung đủ mọi chặng của kỳ, chưa xếp thì `bus_id` để trống.

    Trả đúng những chặng đã xếp thì màn hình không phân biệt nổi "kỳ này chỉ có 2 chặng" với "còn 2
    chặng chưa xếp" — hai chuyện rất khác nhau với người đang rà soát.
    """
    legs = db.scalars(
        select(TripLeg).where(TripLeg.event_id == event_id).order_by(TripLeg.display_order, TripLeg.id)
    ).all()
    return [
        {
            "trip_leg_id": leg.id,
            "leg_code": leg.code,
            "leg_name": leg.name,
            "direction": leg.direction,
            "bus_id": None,
            "bus_code": None,
            "pickup_point_id": None,
            "pickup_name": None,
            "departure_time": None,
            "assignment_mode": None,
        }
        for leg in legs
    ]


def _buses(db: Session, event_id: int, registration_id: int) -> list[dict[str, Any]]:
    legs = _empty_legs(db, event_id)
    by_leg = {leg["trip_leg_id"]: leg for leg in legs}

    rows = db.execute(
        select(BusAssignment, Bus)
        .join(Bus, Bus.id == BusAssignment.bus_id)
        .where(BusAssignment.registration_id == registration_id)
        .options(selectinload(BusAssignment.bus).selectinload(Bus.pickup_point))
    ).all()
    for assignment, bus in rows:
        leg = by_leg.get(assignment.trip_leg_id)
        if leg is None:
            continue  # chặng đã bị xoá nhưng bản ghi xếp còn sót — bỏ qua, không làm hỏng response
        leg.update(
            bus_id=bus.id,
            bus_code=bus.bus_code,
            pickup_point_id=bus.pickup_point_id,
            pickup_name=bus.pickup_point.name if bus.pickup_point else None,
            departure_time=bus.departure_time,
            assignment_mode=assignment.assignment_mode,
        )
    return legs


def _room(db: Session, registration_id: int) -> dict[str, Any] | None:
    row = db.execute(
        select(RoomAssignment, Room, Hotel)
        .join(Room, Room.id == RoomAssignment.room_id)
        .join(Hotel, Hotel.id == Room.hotel_id)
        .where(RoomAssignment.registration_id == registration_id)
    ).first()
    if row is None:
        return None
    assignment, room, hotel = row
    return {
        "room_id": room.id,
        "room_number": room.room_number,
        "floor": room.floor,
        "room_type": room.room_type,
        "hotel_id": hotel.id,
        "hotel_name": hotel.name,
        "is_room_captain": bool(assignment.is_room_captain),
        "assignment_mode": assignment.assignment_mode,
    }


def _gala(db: Session, event_id: int, registration_id: int) -> dict[str, Any] | None:
    row = db.execute(
        select(GalaSeatAssignment, GalaSeat, GalaTable)
        .join(GalaSeat, GalaSeat.id == GalaSeatAssignment.seat_id)
        .join(GalaTable, GalaTable.id == GalaSeat.table_id)
        .where(GalaSeatAssignment.registration_id == registration_id)
    ).first()
    if row is None:
        return None
    _assignment, seat, table = row
    return {
        "seat_id": seat.id,
        "seat_number": seat.seat_number,
        "table_id": table.id,
        "table_code": table.table_code,
        "table_name": table.table_name,
    }
