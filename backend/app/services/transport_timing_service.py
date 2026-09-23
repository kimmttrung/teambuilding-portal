"""Giờ xe phải khớp giờ chuyến bay ở các chặng gắn sân bay.

Hai luật, áp cho mọi xe ở chặng `is_airport_linked` cùng chiều với chuyến bay:

- Xe **ra** sân bay: giờ xe chạy phải sớm hơn giờ cất cánh ít nhất
  `transport.to_airport_buffer_minutes` (mặc định 30 phút) — đi đường rồi còn làm thủ tục.
  Xe chạy 07:00 mà máy bay cất cánh 07:01 thì "đúng thứ tự" theo phép so giờ trần nhưng
  không ai lên kịp máy bay.
- Xe **đón** ở sân bay, ba mốc:
  - *Có mặt* (`gather_time`): muộn nhất là hạ cánh + `transport.from_airport_late_minutes`
    (mặc định 5 phút). Tới sớm bao nhiêu cũng được — xe chờ khách là bình thường, khách chờ
    xe mới là vấn đề.
  - *Rời sân bay* (`departure_time`): sớm nhất là hạ cánh +
    `transport.from_airport_min_wait_minutes` (mặc định 30 phút) — khách còn xuống máy bay và
    lấy hành lý; đi sớm hơn là bỏ lại người.
  - Và muộn nhất là hạ cánh + `transport.from_airport_max_wait_minutes` (mặc định 45 phút, 0 =
    bỏ giới hạn): xe chạy theo lịch, ai ra muộn hơn thì tự lo.

Các số nằm trong `event_settings` để BTC chỉnh theo từng kỳ (bay quốc tế còn nhập cảnh thì
nới mốc chờ tối thiểu).

Một xe "liên quan" tới chuyến bay khi nó được gắn chuyến đó (`linked_flight_id`) **hoặc**
đang chở người bay chuyến đó — BTC không gắn chuyến cho xe thì hành khách vẫn lỡ máy bay y hệt.

Kiểm ở mọi đường ghi có thể tạo ra lệch giờ (sửa chuyến bay, thêm/sửa xe, xếp/chuyển người
sang xe, phân xe tự động). Sửa chuyến bay mà làm lệch xe → chặn, BTC chỉnh xe trước rồi mới
lưu được; không tự dời giờ xe vì giờ xe là thứ đã báo cho tài xế.
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError
from app.core.timeutils import format_vn, from_iso
from app.models.event import DEFAULT_EVENT_SETTINGS, EventSetting
from app.models.flight import Flight, FlightAssignment
from app.models.registration import Registration
from app.models.transportation import Bus, BusAssignment, TripLeg
from app.models.user import User

BEFORE_FLIGHT = "to_airport"
AFTER_FLIGHT = "from_airport"

# Khoá cấu hình -> khoá trong dict luật. Hai chiều KHÁC nghĩa nhau: ra sân bay là "phải chạy
# sớm trước bao nhiêu", đón ở sân bay là "được có mặt muộn nhất bao nhiêu" + cửa sổ chờ khách.
MIN_WAIT = "pickup_min_wait"
MAX_WAIT = "pickup_max_wait"
RULE_SETTING_KEYS = {
    BEFORE_FLIGHT: "transport.to_airport_buffer_minutes",
    AFTER_FLIGHT: "transport.from_airport_late_minutes",
    MIN_WAIT: "transport.from_airport_min_wait_minutes",
    MAX_WAIT: "transport.from_airport_max_wait_minutes",
}


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


def bus_time(
    *, departure_time: str | None, gather_time: str | None, side: str | None = None
) -> str | None:
    """Giờ của xe dùng để so với giờ bay — mỗi chiều nhìn vào một cột khác nhau.

    - Ra sân bay: **giờ xuất phát** (lúc xe rời điểm đón); thiếu thì lấy giờ tập trung.
    - Đón ở sân bay: **giờ tập trung** (lúc xe có mặt ở sân bay chờ khách); thiếu thì lấy giờ
      xuất phát. Lấy giờ xuất phát ở chiều này là hiểu sai dữ liệu: xe rời sân bay 30 phút sau
      khi hạ cánh là bình thường (khách xuống máy bay, lấy hành lý rồi mới lên xe), cái phải
      kiểm là xe CÓ MẶT kịp hay không.
    """
    if side == AFTER_FLIGHT:
        return gather_time or departure_time
    return departure_time or gather_time


def conflict_reason(
    *,
    side: str | None,
    bus_at: str | None,
    flight: FlightTimes,
    buffers: dict[str, int] | None = None,
) -> str | None:
    """Lý do lệch giờ (tiếng Việt), hoặc None khi khớp / không đủ dữ liệu để so.

    `buffers` = số phút đệm tối thiểu theo từng chiều; thiếu thì coi như 0 (chỉ so giờ trần).
    """
    if side is None or not bus_at:
        return None
    minutes = (buffers or {}).get(side, 0)
    moment = from_iso(bus_at)
    required = timedelta(minutes=minutes)

    if side == BEFORE_FLIGHT:
        # Khoảng cách còn lại từ lúc xe chạy tới lúc cất cánh. Đúng bằng mức tối thiểu là đạt.
        margin = from_iso(flight.departure_time) - moment
        if margin <= timedelta(0) or margin < required:
            return (
                f"xe chạy lúc {format_vn(bus_at)}, chuyến {flight.flight_code} cất cánh lúc "
                f"{format_vn(flight.departure_time)} — {_gap_note(margin, minutes)}"
            )
    if side == AFTER_FLIGHT:
        # Tới sớm không giới hạn: xe chờ khách thì không ai lỡ gì cả.
        late = moment - from_iso(flight.arrival_time)
        if late > required:
            return (
                f"xe đón có mặt lúc {format_vn(bus_at)}, chuyến {flight.flight_code} hạ cánh lúc "
                f"{format_vn(flight.arrival_time)} — {_late_note(late, minutes)}"
            )
    return None


def pickup_departure_reason(
    *, departure_at: str | None, flight: FlightTimes, rules: dict[str, int] | None = None
) -> str | None:
    """Lý do giờ RỜI sân bay của xe đón không hợp lệ, hoặc None.

    Hai mốc ngược chiều nhau và đều có lý do thật: đi quá sớm là bỏ lại người còn đang lấy
    hành lý; chờ quá lâu thì cả xe phải đợi một vài người, trong khi lịch xe đã báo trước.
    """
    if not departure_at:
        return None
    rules = rules or {}
    waited = from_iso(departure_at) - from_iso(flight.arrival_time)
    minutes = int(waited.total_seconds() // 60)

    min_wait = rules.get(MIN_WAIT, 0)
    if min_wait and waited < timedelta(minutes=min_wait):
        when = (
            f"chỉ {minutes} phút sau khi"
            if minutes >= 0
            else f"tận {-minutes} phút TRƯỚC khi"
        )
        return (
            f"xe rời sân bay lúc {format_vn(departure_at)}, {when} chuyến "
            f"{flight.flight_code} hạ cánh ({format_vn(flight.arrival_time)}) — cần chờ ít nhất "
            f"{min_wait} phút để khách xuống máy bay và lấy hành lý"
        )

    max_wait = rules.get(MAX_WAIT, 0)
    if max_wait and waited > timedelta(minutes=max_wait):
        return (
            f"xe rời sân bay lúc {format_vn(departure_at)}, {minutes} phút sau khi chuyến "
            f"{flight.flight_code} hạ cánh ({format_vn(flight.arrival_time)}) — không chờ quá "
            f"{max_wait} phút; xe đón nhiều chuyến hạ cánh cách xa nhau thì phải tách xe"
        )
    return None


def bus_conflict_reason(
    *,
    side: str | None,
    gather_time: str | None,
    departure_time: str | None,
    flight: FlightTimes,
    rules: dict[str, int] | None = None,
) -> str | None:
    """Toàn bộ luật giờ của MỘT xe với MỘT chuyến bay. Dùng ở mọi chỗ kiểm trên DB.

    Chiều đón chỉ kiểm giờ CÓ MẶT khi có `gather_time` thật. Lấy `departure_time` thay thế là
    hai luật tự đánh nhau: giờ rời bến phải muộn hơn giờ hạ cánh ít nhất 30 phút, mà giờ có mặt
    thì không được muộn quá 5 phút — không giá trị nào thoả cả hai.
    """
    if side == AFTER_FLIGHT:
        presence = (
            conflict_reason(side=side, bus_at=gather_time, flight=flight, buffers=rules)
            if gather_time
            else None
        )
        return presence or pickup_departure_reason(
            departure_at=departure_time, flight=flight, rules=rules
        )

    return conflict_reason(
        side=side,
        bus_at=bus_time(departure_time=departure_time, gather_time=gather_time, side=side),
        flight=flight,
        buffers=rules,
    )


def _late_note(late: timedelta, minutes: int) -> str:
    """Xe đón: muộn hơn giờ hạ cánh bao nhiêu phút, so với mức cho phép."""
    gap = int(late.total_seconds() // 60)
    allowed = f"chỉ cho phép muộn {minutes} phút" if minutes else "phải có mặt trước khi hạ cánh"
    return f"xe tới muộn {gap} phút, {allowed}"


def _gap_note(margin: timedelta, minutes: int) -> str:
    """Xe ra sân bay: còn bao nhiêu phút trước giờ cất cánh, so với mức tối thiểu."""
    gap = int(margin.total_seconds() // 60)
    if gap < 0:
        return f"sai thứ tự, cần cách nhau tối thiểu {minutes} phút" if minutes else "sai thứ tự"
    if not minutes:
        return "không kịp"
    return f"chỉ cách nhau {gap} phút, cần tối thiểu {minutes} phút"


# --- Kiểm trên DB ---


def self_transport_lead(db: Session, event_id: int) -> int:
    """Người tự đi cần có mặt ở sân bay trước giờ bay bao nhiêu phút.

    Không phải luật chặn gì cả — chỉ là con số để viết câu nhắc trong lịch trình của người
    không đăng ký xe BTC. Vẫn để trong cấu hình kỳ vì bay nội địa và quốc tế khác nhau xa.
    """
    key = "transport.self_transport_lead_minutes"
    raw = db.scalar(
        select(EventSetting.value).where(
            EventSetting.event_id == event_id, EventSetting.key == key
        )
    )
    try:
        return max(int(str(raw if raw is not None else DEFAULT_EVENT_SETTINGS[key][0]).strip().strip('"')), 0)
    except (TypeError, ValueError):
        return int(DEFAULT_EVENT_SETTINGS[key][0])


def timing_rules(db: Session, event_id: int) -> dict[str, int]:
    """Các mốc phút của kỳ: đệm ra sân bay, mức tới muộn và cửa sổ chờ của xe đón.

    Đọc thẳng `event_settings` thay vì qua `event_service` để không tạo vòng import (chính
    `event_service` gọi ngược vào đây khi chặn công bố). Giá trị lạ thì dùng mặc định: một ô
    cấu hình gõ sai không được làm cả việc kiểm giờ im lặng bỏ qua.
    """
    stored = {
        row.key: row.value
        for row in db.scalars(
            select(EventSetting).where(
                EventSetting.event_id == event_id,
                EventSetting.key.in_(RULE_SETTING_KEYS.values()),
            )
        )
    }
    result = {}
    for side, key in RULE_SETTING_KEYS.items():
        raw = stored.get(key, DEFAULT_EVENT_SETTINGS[key][0])
        try:
            result[side] = max(int(str(raw).strip().strip('"')), 0)
        except (TypeError, ValueError):
            result[side] = int(DEFAULT_EVENT_SETTINGS[key][0])
    return result


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
    rules = timing_rules(db, flight.event_id)
    conflicts = []
    for bus in _buses_for_flight(db, flight):
        leg = legs.get(bus.trip_leg_id)
        if leg is None or leg.direction != flight.direction:
            continue
        side = airport_side(leg, list(legs.values()))
        check = {
            "side": side,
            "gather_time": bus.gather_time,
            "departure_time": bus.departure_time,
            "rules": rules,
        }
        reason = bus_conflict_reason(flight=times, **check)
        if reason and not bus_conflict_reason(flight=current, **check):
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
    if side is None or not (departure_time or gather_time):
        return

    flight_ids = set() if bus_id is None else _rider_flight_ids(db, bus_id, leg.direction)
    if linked_flight_id is not None:
        flight_ids.add(linked_flight_id)

    rules = timing_rules(db, event_id)
    conflicts = []
    for flight in _flights(db, flight_ids):
        reason = bus_conflict_reason(
            side=side,
            gather_time=gather_time,
            departure_time=departure_time,
            flight=flight,
            rules=rules,
        )
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
    if side is None or not (bus.departure_time or bus.gather_time):
        return

    flight_id = db.scalar(
        select(FlightAssignment.flight_id).where(
            FlightAssignment.registration_id == registration_id,
            FlightAssignment.direction == leg.direction,
        )
    )
    rules = timing_rules(db, bus.event_id)
    for flight in _flights(db, {flight_id} if flight_id else set()):
        reason = bus_conflict_reason(
            side=side,
            gather_time=bus.gather_time,
            departure_time=bus.departure_time,
            flight=flight,
            rules=rules,
        )
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
    rules = timing_rules(db, flight.event_id)
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
        reason = bus_conflict_reason(
            side=airport_side(leg, list(legs.values())),
            gather_time=bus.gather_time,
            departure_time=bus.departure_time,
            flight=times,
            rules=rules,
        )
        if reason:
            result.append({"registration_id": registration_id, **_bus_item(bus, leg, reason)})
    return result


def bus_timing_issues(db: Session, *, event_id: int) -> dict[int, list[str]]:
    """{bus_id: các câu mô tả xe đó đang lệch giờ như thế nào}.

    Dành cho màn hình Xe đưa đón: chặn khi lưu thì BTC biết ngay, nhưng lệch còn đến từ phía
    khác (đổi giờ bay, chuyển người sang chuyến khác) nên mở danh sách lên phải thấy ngay xe
    nào hỏng, thay vì mở từng xe ra dò.

    Xét cả chuyến được gắn (`linked_flight_id`) lẫn chuyến của hành khách đang ngồi trên xe —
    cùng tập "chuyến liên quan" với các hàm chặn, để cảnh báo và chỗ chặn không nói khác nhau.
    """
    legs = _legs(db, event_id)
    all_legs = list(legs.values())
    rules = timing_rules(db, event_id)

    buses = list(db.scalars(select(Bus).where(Bus.event_id == event_id)))
    if not buses:
        return {}

    rider_flights: dict[int, set[int]] = {}
    for bus_id, flight_id in db.execute(
        select(BusAssignment.bus_id, FlightAssignment.flight_id)
        .join(Bus, Bus.id == BusAssignment.bus_id)
        .join(TripLeg, TripLeg.id == Bus.trip_leg_id)
        .join(
            FlightAssignment,
            (FlightAssignment.registration_id == BusAssignment.registration_id)
            & (FlightAssignment.direction == TripLeg.direction),
        )
        .where(Bus.event_id == event_id)
        .distinct()
    ):
        rider_flights.setdefault(bus_id, set()).add(flight_id)

    wanted = {fid for ids in rider_flights.values() for fid in ids}
    wanted |= {bus.linked_flight_id for bus in buses if bus.linked_flight_id}
    flights = {item.flight_id: item for item in _flights(db, wanted)}

    issues: dict[int, list[str]] = {}
    for bus in buses:
        leg = legs.get(bus.trip_leg_id)
        if leg is None:
            continue
        side = airport_side(leg, all_legs)
        related = set(rider_flights.get(bus.id, set()))
        if bus.linked_flight_id:
            related.add(bus.linked_flight_id)

        reasons = []
        for flight_id in sorted(related):
            flight = flights.get(flight_id)
            if flight is None:
                continue
            reason = bus_conflict_reason(
                side=side,
                gather_time=bus.gather_time,
                departure_time=bus.departure_time,
                flight=flight,
                rules=rules,
            )
            if reason and reason not in reasons:
                reasons.append(reason)
        if reasons:
            issues[bus.id] = reasons
    return issues


def event_mismatches(db: Session, *, event_id: int) -> list[dict[str, Any]]:
    """Mọi chỗ xe hiện đang lệch giờ bay của chính hành khách, trên cả kỳ.

    Các hàm `check_*` chỉ chặn lệch do MỘT thao tác gây ra, nên lệch vẫn tích tụ được: chuyển
    người sang chuyến khác chỉ cảnh báo, và BTC có thể sửa giờ xe khi chưa ai ngồi lên. Đây là
    lần rà cuối trước khi công bố — công bố kèm lệch giờ thì CBNV mở My Journey thấy xe chạy
    sau giờ cất cánh và không hiểu phải tin cái nào.
    """
    legs = _legs(db, event_id)
    all_legs = list(legs.values())
    sides = {leg_id: airport_side(leg, all_legs) for leg_id, leg in legs.items()}
    rules = timing_rules(db, event_id)

    rows = db.execute(
        select(BusAssignment.registration_id, Bus, TripLeg, Flight, User.full_name)
        .join(Bus, Bus.id == BusAssignment.bus_id)
        .join(TripLeg, TripLeg.id == Bus.trip_leg_id)
        .join(Registration, Registration.id == BusAssignment.registration_id)
        .join(User, User.id == Registration.user_id)
        .join(
            FlightAssignment,
            (FlightAssignment.registration_id == BusAssignment.registration_id)
            & (FlightAssignment.direction == TripLeg.direction),
        )
        .join(Flight, Flight.id == FlightAssignment.flight_id)
        .where(Bus.event_id == event_id)
        .order_by(User.full_name, TripLeg.display_order)
    ).all()

    mismatches = []
    for registration_id, bus, leg, flight, full_name in rows:
        reason = bus_conflict_reason(
            side=sides.get(leg.id),
            gather_time=bus.gather_time,
            departure_time=bus.departure_time,
            flight=FlightTimes(flight.id, flight.flight_code, flight.departure_time, flight.arrival_time),
            rules=rules,
        )
        if reason:
            mismatches.append(
                {
                    "registration_id": registration_id,
                    "full_name": full_name,
                    "flight_id": flight.id,
                    "flight_code": flight.flight_code,
                    **_bus_item(bus, leg, reason),
                }
            )
    return mismatches


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
    rules = timing_rules(db, event_id)
    result = {}
    for bus in buses:
        bad = frozenset(
            flight.flight_id
            for flight in flights
            if bus_conflict_reason(
                side=side,
                gather_time=bus.gather_time,
                departure_time=bus.departure_time,
                flight=flight,
                rules=rules,
            )
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
