"""Auto Bus Allocation — xếp người lên xe cho MỘT chặng (docs/05 §6).

Chạy SAU phân bổ chuyến bay: ở chặng gắn sân bay, xe phải chờ đúng chuyến người đó bay,
nên không có chuyến bay thì không xếp được xe.

Thứ tự ưu tiên theo BRD 7.3:
1. Cùng chuyến bay — CỨNG ở chặng sân bay, mềm ở chặng nội thành.
2. Cùng team.
3. Tối ưu công suất — dồn người vào ít xe nhất có thể, báo xe thừa.
4. Không vượt sức chứa — CỨNG ở mọi chặng.

Thêm một ràng buộc cứng từ dữ liệu: xe đã gán điểm đón thì không nhận người chọn điểm đón
khác (xe không thể có mặt ở hai toà nhà cùng lúc).

Không có bước ngẫu nhiên nên không cần seed: cùng đầu vào luôn cho cùng kết quả.
"""

from collections import defaultdict

from app.services.allocator.bus_types import (
    FLAG_BUS_UNDERUTILIZED,
    FLAG_MISSING_FLIGHT_ASSIGNMENT,
    FLAG_MIXED_FLIGHT_ON_BUS,
    FLAG_NO_BUS_CAPACITY,
    FLAG_SURPLUS_BUS,
    BusAllocationResult,
    BusAllocationSummary,
    BusLoad,
    BusRider,
    BusSeat,
    BusSlot,
)
from app.services.allocator.types import (
    SEVERITY_ERROR,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    Flag,
    TeamLoad,
)

_SEVERITY_ORDER = {SEVERITY_ERROR: 0, SEVERITY_WARNING: 1, SEVERITY_INFO: 2}

# Điểm chọn xe. Các bậc cách nhau đủ xa để thứ tự ưu tiên của BRD không bao giờ bị
# một thành phần thấp hơn lật ngược (ví dụ độ vừa khít tối đa chỉ ~50 điểm).
_SCORE_SAME_FLIGHT = 2000
_SCORE_FITS_WHOLE_TEAM = 1000
_SCORE_HAS_TEAMMATE = 500
_SCORE_BUS_ALREADY_USED = 100


class _BusBin:
    __slots__ = ("slot", "members", "pinned_ids")

    def __init__(self, slot: BusSlot):
        self.slot = slot
        self.members: list[BusRider] = []
        self.pinned_ids: set[int] = set()

    @property
    def remaining(self) -> int:
        return self.slot.capacity - len(self.members)

    def add(self, rider: BusRider, *, pinned: bool = False) -> None:
        self.members.append(rider)
        if pinned:
            self.pinned_ids.add(rider.registration_id)

    def accepts(self, rider: BusRider, airport_linked: bool) -> bool:
        """Ràng buộc cứng, không tính sức chứa."""
        if airport_linked:
            if rider.flight_id is None:
                return False
            if self.slot.linked_flight_id is not None and self.slot.linked_flight_id != rider.flight_id:
                return False
            if rider.flight_id in self.slot.incompatible_flight_ids:
                return False
        if (
            self.slot.pickup_point_id is not None
            and rider.pickup_point_id is not None
            and self.slot.pickup_point_id != rider.pickup_point_id
        ):
            return False
        return True


def allocate_buses(
    *,
    riders: list[BusRider],
    buses: list[BusSlot],
    trip_leg_id: int,
    airport_linked: bool,
    underutilized_ratio: float = 0.5,
) -> BusAllocationResult:
    """Xếp người cần xe vào các xe của một chặng. Không ghi gì."""
    bins = [_BusBin(slot) for slot in sorted(buses, key=lambda slot: slot.bus_id)]
    ordered = sorted(riders, key=lambda rider: rider.registration_id)

    pending = _place_pinned(ordered, bins)

    missing_flight: list[BusRider] = []
    if airport_linked:
        missing_flight = [rider for rider in pending if rider.flight_id is None]
        pending = [rider for rider in pending if rider.flight_id is not None]

    no_seat: list[BusRider] = []
    for group in _groups(pending, airport_linked):
        teams: dict[tuple, list[BusRider]] = defaultdict(list)
        for rider in group:
            teams[rider.team_key].append(rider)
        for _key, members in sorted(teams.items(), key=lambda item: (-len(item[1]), str(item[0]))):
            no_seat.extend(_place_team(members, bins, airport_linked))

    return _build_result(
        trip_leg_id=trip_leg_id,
        airport_linked=airport_linked,
        riders=ordered,
        bins=bins,
        missing_flight=missing_flight,
        no_seat=no_seat,
        underutilized_ratio=underutilized_ratio,
    )


# --- Xếp chỗ ---


def _place_pinned(riders: list[BusRider], bins: list[_BusBin]) -> list[BusRider]:
    by_id = {bin_.slot.bus_id: bin_ for bin_ in bins}
    pending = []
    for rider in riders:
        target = by_id.get(rider.pinned_bus_id) if rider.pinned_bus_id else None
        if target is None:
            pending.append(rider)
        else:
            target.add(rider, pinned=True)
    return pending


def _groups(riders: list[BusRider], airport_linked: bool) -> list[list[BusRider]]:
    """Chặng sân bay nhóm theo chuyến bay; chặng nội thành theo điểm đón rồi chuyến bay.

    Nhóm lớn xếp trước (Best-Fit Decreasing): để sau thì chỉ còn chỗ vụn và nhóm lớn
    chắc chắn bị chia ra nhiều xe.
    """
    groups: dict[tuple, list[BusRider]] = defaultdict(list)
    for rider in riders:
        key = (rider.flight_id,) if airport_linked else (rider.pickup_point_id, rider.flight_id)
        groups[key].append(rider)
    return [
        members
        for _key, members in sorted(groups.items(), key=lambda item: (-len(item[1]), str(item[0])))
    ]


def _place_team(members: list[BusRider], bins: list[_BusBin], airport_linked: bool) -> list[BusRider]:
    """Xếp một team: nguyên khối nếu có xe vừa, không thì chia qua nhiều xe.

    Mỗi vòng chỉ lấy những người mà xe được chọn thực sự nhận — nhờ vậy dù trong team có
    người khác điểm đón, không ai bị nhét lên xe không đón được họ.
    """
    rest = sorted(members, key=lambda rider: rider.registration_id)
    unplaced: list[BusRider] = []

    while rest:
        first = rest[0]
        eligible = [
            bin_ for bin_ in bins if bin_.remaining > 0 and bin_.accepts(first, airport_linked)
        ]
        if not eligible:
            unplaced.append(first)
            rest = rest[1:]
            continue

        best = max(
            eligible,
            key=lambda bin_: (
                _bus_score(bin_, rest, first, airport_linked),
                -bin_.slot.bus_id,
            ),
        )

        accepted = [rider for rider in rest if best.accepts(rider, airport_linked)]
        taken = accepted[: best.remaining]
        taken_ids = {rider.registration_id for rider in taken}
        for rider in taken:
            best.add(rider)
        rest = [rider for rider in rest if rider.registration_id not in taken_ids]

    return unplaced


def _bus_score(bin_: _BusBin, rest: list[BusRider], first: BusRider, airport_linked: bool) -> int:
    chunk = sum(1 for rider in rest if bin_.accepts(rider, airport_linked))
    same_flight = first.flight_id is not None and bin_.slot.linked_flight_id == first.flight_id
    fits_whole = bin_.remaining >= chunk
    has_teammate = first.team_id is not None and any(
        member.team_id == first.team_id for member in bin_.members
    )
    leftover = bin_.remaining - min(chunk, bin_.remaining)

    return (
        (_SCORE_SAME_FLIGHT if same_flight else 0)
        + (_SCORE_FITS_WHOLE_TEAM if fits_whole else 0)
        + (_SCORE_HAS_TEAMMATE if has_teammate else 0)
        # Ưu tiên xe đã có người: dồn khách, để xe khác trống hẳn mà huỷ được.
        + (_SCORE_BUS_ALREADY_USED if bin_.members else 0)
        - leftover
    )


# --- Kết quả ---


def _build_result(
    *,
    trip_leg_id: int,
    airport_linked: bool,
    riders: list[BusRider],
    bins: list[_BusBin],
    missing_flight: list[BusRider],
    no_seat: list[BusRider],
    underutilized_ratio: float,
) -> BusAllocationResult:
    assignments = [
        BusSeat(
            registration_id=member.registration_id,
            bus_id=bin_.slot.bus_id,
            pinned=member.registration_id in bin_.pinned_ids,
        )
        for bin_ in bins
        for member in sorted(bin_.members, key=lambda rider: rider.registration_id)
    ]

    flags = [
        *_missing_flight_flags(missing_flight),
        *_no_seat_flags(no_seat, bins, airport_linked),
        *_bus_flags(bins, underutilized_ratio),
    ]
    flags.sort(
        key=lambda flag: (
            _SEVERITY_ORDER.get(flag.severity, 9),
            flag.type,
            flag.registration_id or 0,
            flag.details.get("bus_id") or 0,
        )
    )

    used = [bin_ for bin_ in bins if bin_.members]
    assigned = sum(len(bin_.members) for bin_ in bins)
    used_capacity = sum(bin_.slot.capacity for bin_ in used)

    summary = BusAllocationSummary(
        total_riders=len(riders),
        assigned=assigned,
        unassigned=len(missing_flight) + len(no_seat),
        buses_total=len(bins),
        buses_used=len(used),
        surplus_buses=len(bins) - len(used),
        mixed_flight_buses=sum(1 for bin_ in bins if len(_flight_ids(bin_)) > 1),
        utilization=round(assigned / used_capacity, 4) if used_capacity else 0.0,
    )

    return BusAllocationResult(
        trip_leg_id=trip_leg_id,
        airport_linked=airport_linked,
        assignments=assignments,
        flags=flags,
        summary=summary,
        buses=[_bus_load(bin_) for bin_ in bins],
    )


def _missing_flight_flags(riders: list[BusRider]) -> list[Flag]:
    return [
        Flag(
            type=FLAG_MISSING_FLIGHT_ASSIGNMENT,
            severity=SEVERITY_ERROR,
            message=(
                f"{rider.full_name} chưa có chuyến bay nên chưa xếp được xe ở chặng sân bay. "
                "Phân bổ chuyến bay trước."
            ),
            registration_id=rider.registration_id,
            team_id=rider.team_id,
        )
        for rider in sorted(riders, key=lambda item: item.registration_id)
    ]


def _no_seat_flags(riders: list[BusRider], bins: list[_BusBin], airport_linked: bool) -> list[Flag]:
    flags = []
    for rider in sorted(riders, key=lambda item: item.registration_id):
        # Phân biệt "hết chỗ" với "không có xe nào đi đúng điểm đón/chuyến": cách xử lý khác
        # nhau hoàn toàn (thuê thêm xe vs. gán xe hiện có sang điểm đón đó).
        served = any(bin_.accepts(rider, airport_linked) for bin_ in bins)
        message = (
            f"{rider.full_name}: các xe phù hợp đã hết chỗ."
            if served
            else f"{rider.full_name}: không có xe nào đi đúng điểm đón"
            + (" và chuyến bay" if airport_linked else "")
            + " của người này."
        )
        flags.append(
            Flag(
                type=FLAG_NO_BUS_CAPACITY,
                severity=SEVERITY_ERROR,
                message=message,
                registration_id=rider.registration_id,
                team_id=rider.team_id,
                flight_id=rider.flight_id,
                details={
                    "pickup_point_id": rider.pickup_point_id,
                    "reason": "full" if served else "no_matching_bus",
                },
            )
        )
    return flags


def _bus_flags(bins: list[_BusBin], underutilized_ratio: float) -> list[Flag]:
    flags = []
    used = [bin_ for bin_ in bins if bin_.members]

    for bin_ in bins:
        load = len(bin_.members)
        code = bin_.slot.bus_code
        details = {"bus_id": bin_.slot.bus_id, "assigned": load, "capacity": bin_.slot.capacity}

        if load == 0:
            flags.append(
                Flag(
                    type=FLAG_SURPLUS_BUS,
                    severity=SEVERITY_INFO,
                    message=f"Xe {code} không có ai — có thể huỷ để tiết kiệm chi phí.",
                    details=details,
                )
            )
            continue

        if load < bin_.slot.capacity * underutilized_ratio:
            flags.append(
                Flag(
                    type=FLAG_BUS_UNDERUTILIZED,
                    severity=SEVERITY_WARNING,
                    message=(
                        f"Xe {code} chỉ có {load}/{bin_.slot.capacity} người "
                        f"(dưới {round(underutilized_ratio * 100)}%)."
                    ),
                    details=details,
                )
            )

        flights = _flight_ids(bin_)
        if len(flights) > 1:
            flags.append(
                Flag(
                    type=FLAG_MIXED_FLIGHT_ON_BUS,
                    severity=SEVERITY_WARNING,
                    message=(
                        f"Xe {code} chở người của {len(flights)} chuyến bay khác nhau — "
                        "kiểm tra giờ tập trung có hợp với cả hai chuyến."
                    ),
                    details={**details, "flight_ids": flights},
                )
            )

    # Gợi ý dồn xe (docs/05 §6 bước 4): tính theo sức chứa thuần. Điểm đón và chuyến bay
    # có thể khiến việc dồn không làm được — nên chỉ là thông tin, không phải cảnh báo.
    if len(used) >= 2:
        assigned = sum(len(bin_.members) for bin_ in used)
        total = sum(bin_.slot.capacity for bin_ in used)
        smallest = min(bin_.slot.capacity for bin_ in used)
        if assigned <= total - smallest:
            flags.append(
                Flag(
                    type=FLAG_SURPLUS_BUS,
                    severity=SEVERITY_INFO,
                    message=(
                        f"{assigned} người trên {len(used)} xe: về sức chứa có thể bớt 1 xe. "
                        "Kiểm tra điểm đón và giờ bay trước khi huỷ xe."
                    ),
                    details={"used_buses": len(used), "assigned": assigned, "capacity": total},
                )
            )

    return flags


def _flight_ids(bin_: _BusBin) -> list[int]:
    return sorted({member.flight_id for member in bin_.members if member.flight_id is not None})


def _bus_load(bin_: _BusBin) -> BusLoad:
    per_team: dict[tuple[int | None, str], int] = defaultdict(int)
    for member in bin_.members:
        per_team[(member.team_id, member.team_name)] += 1

    return BusLoad(
        bus_id=bin_.slot.bus_id,
        bus_code=bin_.slot.bus_code,
        capacity=bin_.slot.capacity,
        assigned=len(bin_.members),
        remaining=bin_.remaining,
        pickup_point_id=bin_.slot.pickup_point_id,
        linked_flight_id=bin_.slot.linked_flight_id,
        flight_ids=_flight_ids(bin_),
        teams=[
            TeamLoad(team_id=team_id, team_name=team_name, count=count)
            for (team_id, team_name), count in sorted(
                per_team.items(), key=lambda item: (-item[1], item[0][1])
            )
        ],
    )
