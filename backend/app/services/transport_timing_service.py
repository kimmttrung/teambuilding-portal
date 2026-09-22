"""Giờ xe phải khớp giờ chuyến bay ở các chặng gắn sân bay.

Hai luật, áp cho mọi xe ở chặng `is_airport_linked` cùng chiều với chuyến bay:

- Xe **ra** sân bay (trước chuyến bay): giờ xe chạy phải SỚM hơn giờ cất cánh.
- Xe **đón** ở sân bay (sau chuyến bay): giờ xe chạy không được sớm hơn giờ hạ cánh.

Một xe "liên quan" tới chuyến bay khi nó được gắn chuyến đó (`linked_flight_id`) **hoặc**
đang chở người bay chuyến đó — BTC không gắn chuyến cho xe thì hành khách vẫn lỡ máy bay y hệt.

Kiểm ở mọi đường ghi có thể tạo ra lệch giờ (sửa chuyến bay, thêm/sửa xe, xếp/chuyển người
sang xe, phân xe tự động). Sửa chuyến bay mà làm lệch xe → chặn, BTC chỉnh xe trước rồi mới
lưu được; không tự dời giờ xe vì giờ xe là thứ đã báo cho tài xế.
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError
from app.core.timeutils import format_vn, from_iso
from app.models.flight import Flight, FlightAssignment
from app.models.transportation import Bus, BusAssignment, TripLeg

BEFORE_FLIGHT = "to_airport"
AFTER_FLIGHT = "from_airport"


@dataclass(frozen=True)
class FlightTimes:
    flight_id: int
    flight_code: str
    departure_time: str
    arrival_time: str


# --- Hàm thuần ---


def airport_side(leg: TripLeg, legs: list[TripLeg]) -> str | None:
    """Chặng này chạy trước hay sau chuyến bay.

    Mã chặng theo quy ước `*_TO_AIRPORT` / `AIRPORT_TO_*` là rõ nhất. Mã tự đặt khác thì dựa
    vào thứ tự: trong các chặng gắn sân bay cùng chiều, chặng đầu là ra sân bay, chặng cuối là
    đón ở sân bay. Không xác định được thì trả None và không kiểm — chặn nhầm tệ hơn bỏ sót.

    Mã chặng được xét cả khi BTC quên bật `is_airport_linked`: xe `CITY_TO_AIRPORT` vẫn phải tới
    sân bay trước giờ cất cánh, cờ đó chỉ quyết thuật toán có gom theo chuyến bay hay không.
    """
    code = (leg.code or "").upper()
    if "TO_AIRPORT" in code:
        return BEFORE_FLIGHT
    if code.startswith("AIRPORT_TO") or "FROM_AIRPORT" in code:
        return AFTER_FLIGHT
    if not leg.is_airport_linked:
        return None

    same = sorted(
        (item for item in legs if item.is_airport_linked and item.direction == leg.direction),
        key=lambda item: (item.display_order, item.id),
    )
    if len(same) >= 2:
        if same[0].id == leg.id:
            return BEFORE_FLIGHT
        if same[-1].id == leg.id:
            return AFTER_FLIGHT
    return None


def bus_time(*, departure_time: str | None, gather_time: str | None) -> str | None:
    """Giờ dùng để so: giờ xe chạy, thiếu thì lấy giờ tập trung."""
    return departure_time or gather_time


def conflict_reason(*, side: str | None, bus_at: str | None, flight: FlightTimes) -> str | None:
    """Lý do lệch giờ (tiếng Việt), hoặc None khi khớp / không đủ dữ liệu để so."""
    if side is None or not bus_at:
        return None
    moment = from_iso(bus_at)
    if side == BEFORE_FLIGHT and moment >= from_iso(flight.departure_time):
        return (
            f"xe chạy lúc {format_vn(bus_at)}, không kịp chuyến {flight.flight_code} "
            f"cất cánh lúc {format_vn(flight.departure_time)}"
        )
    if side == AFTER_FLIGHT and moment < from_iso(flight.arrival_time):
        return (
            f"xe chạy lúc {format_vn(bus_at)}, trước khi chuyến {flight.flight_code} "
            f"hạ cánh lúc {format_vn(flight.arrival_time)}"
        )
    return None


# --- Kiểm trên DB ---


def check_flight_change(
    db: Session, *, flight: Flight, departure_time: str, arrival_time: str
) -> None:
    """Chặn sửa giờ bay khi có xe liên quan không còn khớp. Gọi TRƯỚC khi gán giá trị mới.

    Chỉ chặn chỗ lệch DO lần sửa này gây ra. Xe đã lệch từ trước (ví dụ người bị chuyển chuyến
    trên bảng bay mà chưa đổi xe) không được khoá luôn việc sửa giờ bay — BTC có thể đang sửa
    giờ bay chính là để gỡ chỗ lệch đó.
    """
    times = FlightTimes(flight.id, flight.flight_code, departure_time, arrival_time)
    current = FlightTimes(flight.id, flight.flight_code, flight.departure_time, flight.arrival_time)
    legs = _legs(db, flight.event_id)
    conflicts = []
    for bus in _buses_for_flight(db, flight):
        leg = legs.get(bus.trip_leg_id)
        if leg is None or leg.direction != flight.direction:
            continue
        side = airport_side(leg, list(legs.values()))
        bus_at = bus_time(departure_time=bus.departure_time, gather_time=bus.gather_time)
        reason = conflict_reason(side=side, bus_at=bus_at, flight=times)
        if reason and not conflict_reason(side=side, bus_at=bus_at, flight=current):
            conflicts.append(_bus_item(bus, leg, reason))

    if conflicts:
        raise ConflictError(
            f"Giờ bay mới làm {len(conflicts)} xe không còn khớp: "
            + "; ".join(f"{item['bus_code']} ({item['reason']})" for item in conflicts)
            + ". Sửa giờ xe hoặc chuyển hành khách sang xe khác trước, rồi lưu lại chuyến bay.",
            code="FLIGHT_BUS_TIME_CONFLICT",
            details={"flight_id": flight.id, "buses": conflicts},
        )


def check_bus_change(
    db: Session,
    *,
    event_id: int,
    leg: TripLeg,
    bus_id: int | None,
    bus_code: str,
    linked_flight_id: int | None,
    departure_time: str | None,
    gather_time: str | None,
) -> None:
    """Chặn thêm/sửa xe khi giờ xe không khớp chuyến được gắn hoặc chuyến của hành khách."""
    legs = _legs(db, event_id)
    side = airport_side(leg, list(legs.values()))
    bus_at = bus_time(departure_time=departure_time, gather_time=gather_time)
    if side is None or not bus_at:
        return

    flight_ids = set() if bus_id is None else _rider_flight_ids(db, bus_id, leg.direction)
    if linked_flight_id is not None:
        flight_ids.add(linked_flight_id)

    conflicts = []
    for flight in _flights(db, flight_ids):
        reason = conflict_reason(side=side, bus_at=bus_at, flight=flight)
        if reason:
            conflicts.append({"flight_id": flight.flight_id, "flight_code": flight.flight_code, "reason": reason})

    if conflicts:
        raise ConflictError(
            f"Giờ xe {bus_code} không khớp chuyến bay: "
            + "; ".join(item["reason"] for item in conflicts)
            + ".",
            code="BUS_FLIGHT_TIME_CONFLICT",
            details={"bus_id": bus_id, "flights": conflicts},
        )


def check_rider(db: Session, *, bus: Bus, registration_id: int, full_name: str | None = None) -> None:
    """Chặn xếp một người lên xe chạy lệch giờ chuyến bay của chính họ."""
    leg = bus.trip_leg
    side = airport_side(leg, list(_legs(db, bus.event_id).values()))
    bus_at = bus_time(departure_time=bus.departure_time, gather_time=bus.gather_time)
    if side is None or not bus_at:
        return

    flight_id = db.scalar(
        select(FlightAssignment.flight_id).where(
            FlightAssignment.registration_id == registration_id,
            FlightAssignment.direction == leg.direction,
        )
    )
    for flight in _flights(db, {flight_id} if flight_id else set()):
        reason = conflict_reason(side=side, bus_at=bus_at, flight=flight)
        if reason:
            who = full_name or "Người này"
            raise ConflictError(
                f"{who} bay chuyến {flight.flight_code}; xe {bus.bus_code} {reason}. "
                "Chọn xe khác phù hợp giờ bay.",
                code="BUS_FLIGHT_TIME_CONFLICT",
                details={"bus_id": bus.id, "flight_id": flight.flight_id, "registration_id": registration_id},
            )


def rider_bus_conflicts(
    db: Session, *, registration_ids: list[int], flight: Flight
) -> list[dict[str, Any]]:
    """Xe hiện tại của những người sắp chuyển sang `flight` mà không khớp giờ chuyến đó.

    Dùng để CẢNH BÁO khi chuyển chuyến bay (không chặn): chuyến bay luôn xếp trước xe, BTC
    chuyển chuyến xong rồi mới chuyển xe — chặn ở đây là bắt làm ngược thứ tự.
    """
    if not registration_ids:
        return []
    legs = _legs(db, flight.event_id)
    times = FlightTimes(flight.id, flight.flight_code, flight.departure_time, flight.arrival_time)
    rows = db.execute(
        select(BusAssignment.registration_id, Bus)
        .join(Bus, Bus.id == BusAssignment.bus_id)
        .where(BusAssignment.registration_id.in_(registration_ids))
        .order_by(BusAssignment.registration_id, Bus.bus_code)
    ).all()
    result = []
    for registration_id, bus in rows:
        leg = legs.get(bus.trip_leg_id)
        if leg is None or leg.direction != flight.direction:
            continue
        reason = conflict_reason(
            side=airport_side(leg, list(legs.values())),
            bus_at=bus_time(departure_time=bus.departure_time, gather_time=bus.gather_time),
            flight=times,
        )
        if reason:
            result.append({"registration_id": registration_id, **_bus_item(bus, leg, reason)})
    return result


def incompatible_flight_ids(db: Session, *, event_id: int, leg: TripLeg, buses: list[Bus]) -> dict[int, frozenset[int]]:
    """{bus_id: các chuyến bay mà xe này chạy lệch giờ} — cho thuật toán phân xe loại trừ."""
    legs = _legs(db, event_id)
    side = airport_side(leg, list(legs.values()))
    if side is None:
        return {}
    flights = [
        FlightTimes(row.id, row.flight_code, row.departure_time, row.arrival_time)
        for row in db.scalars(
            select(Flight).where(Flight.event_id == event_id, Flight.direction == leg.direction)
        )
    ]
    result = {}
    for bus in buses:
        bus_at = bus_time(departure_time=bus.departure_time, gather_time=bus.gather_time)
        bad = frozenset(
            flight.flight_id
            for flight in flights
            if conflict_reason(side=side, bus_at=bus_at, flight=flight)
        )
        if bad:
            result[bus.id] = bad
    return result


# --- Nội bộ ---


def _legs(db: Session, event_id: int) -> dict[int, TripLeg]:
    return {leg.id: leg for leg in db.scalars(select(TripLeg).where(TripLeg.event_id == event_id))}


def _buses_for_flight(db: Session, flight: Flight) -> list[Bus]:
    riders = (
        select(BusAssignment.bus_id)
        .join(
            FlightAssignment,
            FlightAssignment.registration_id == BusAssignment.registration_id,
        )
        .where(FlightAssignment.flight_id == flight.id)
    )
    return list(
        db.scalars(
            select(Bus)
            .where(
                Bus.event_id == flight.event_id,
                or_(Bus.linked_flight_id == flight.id, Bus.id.in_(riders)),
            )
            .order_by(Bus.bus_code)
        )
    )


def _rider_flight_ids(db: Session, bus_id: int, direction: str) -> set[int]:
    return set(
        db.scalars(
            select(FlightAssignment.flight_id)
            .join(BusAssignment, BusAssignment.registration_id == FlightAssignment.registration_id)
            .where(BusAssignment.bus_id == bus_id, FlightAssignment.direction == direction)
            .distinct()
        )
    )


def _flights(db: Session, flight_ids: set[int]) -> list[FlightTimes]:
    if not flight_ids:
        return []
    return [
        FlightTimes(row.id, row.flight_code, row.departure_time, row.arrival_time)
        for row in db.scalars(select(Flight).where(Flight.id.in_(flight_ids)).order_by(Flight.id))
    ]


def _bus_item(bus: Bus, leg: TripLeg, reason: str) -> dict[str, Any]:
    return {
        "bus_id": bus.id,
        "bus_code": bus.bus_code,
        "trip_leg_id": leg.id,
        "trip_leg_name": leg.name,
        "departure_time": bus.departure_time,
        "gather_time": bus.gather_time,
        "reason": reason,
    }
