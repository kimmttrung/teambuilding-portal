"""Auto Flight Allocation — greedy có trọng số + cải thiện cục bộ (docs/05 §3).

Bài toán là bin-packing có ràng buộc nhóm (NP-hard). Với n ≤ 1000 và 4 ngày làm, đây là
greedy 3 vòng chứ không phải ILP — đổi lời giải tối ưu tuyệt đối lấy thời gian chạy đoán
được và code đọc được.

Ràng buộc **cứng** (không bao giờ được vi phạm):
- C1: không xếp quá `capacity - reserved_slots` của mỗi chuyến.
- C4: người có `shift_locked` chỉ được xếp vào chuyến đúng ca đó.

Ràng buộc **mềm** (tối đa hoá, có thể không đạt và sinh flag):
- C2: giữ người cùng team trên cùng chuyến (ưu tiên cao hơn C3).
- C3: đáp ứng nguyện vọng ca.

Hàm này thuần: không chạm database, không đọc thời gian hệ thống, và cùng `seed` thì
cùng kết quả — BTC phải đối chiếu được bản preview đã xem với bản đã ghi vào DB.
"""

import logging
import random
from collections import defaultdict

from app.services.allocator.params import DEFAULT_SEED, AllocationParams
from app.services.allocator.types import (
    FLAG_MISSING_ID_CARD,
    FLAG_SHIFT_LOCKED_VIOLATION,
    FLAG_SHIFT_NOT_SATISFIED,
    FLAG_TEAM_SPLIT,
    FLAG_TEAM_SPLIT_EXCEEDED,
    FLAG_TINY_CHUNK,
    FLAG_UNASSIGNED,
    SEVERITY_ERROR,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    AllocationResult,
    AllocationSummary,
    Assignment,
    Flag,
    FlightLoad,
    FlightSlot,
    Participant,
    TeamLoad,
)

logger = logging.getLogger(__name__)

_SEVERITY_ORDER = {SEVERITY_ERROR: 0, SEVERITY_WARNING: 1, SEVERITY_INFO: 2}


class _Bin:
    """Một chuyến bay trong lúc xếp: ghế còn lại và danh sách người đã vào."""

    __slots__ = ("slot", "members", "pinned_ids")

    def __init__(self, slot: FlightSlot):
        self.slot = slot
        self.members: list[Participant] = []
        self.pinned_ids: set[int] = set()

    @property
    def remaining(self) -> int:
        return self.slot.usable - len(self.members)

    def add(self, participant: Participant, *, pinned: bool = False) -> None:
        self.members.append(participant)
        if pinned:
            self.pinned_ids.add(participant.registration_id)

    def accepts(self, participant: Participant) -> bool:
        """C4: người bị khoá ca chỉ vào được chuyến đúng ca đó."""
        if not participant.shift_locked or participant.requested_shift_id is None:
            return True
        return self.slot.shift_id == participant.requested_shift_id


def allocate_flights(
    *,
    participants: list[Participant],
    flights: list[FlightSlot],
    direction: str,
    params: AllocationParams | None = None,
    seed: int = DEFAULT_SEED,
) -> AllocationResult:
    """Xếp người vào chuyến bay cho MỘT chiều.

    Không ghi gì cả: trả về kết quả để nơi gọi hoặc preview cho BTC xem, hoặc ghi vào DB
    trong một transaction (bước 13).
    """
    params = params or AllocationParams()
    rng = random.Random(seed)

    bins = [_Bin(slot) for slot in sorted(flights, key=lambda s: (s.flight_id,))]
    ordered = sorted(participants, key=lambda p: p.registration_id)

    pending = _place_pinned(ordered, bins)
    split_queue = _round_one_whole_groups(pending, bins, params)
    unplaced = _round_two_split_groups(split_queue, bins, params)
    _round_three_local_search(bins, params, rng)

    return _build_result(
        direction=direction,
        seed=seed,
        params=params,
        participants=ordered,
        bins=bins,
        unplaced=unplaced,
    )


# --- Vòng 0: giữ nguyên bản ghi thủ công ---


def _place_pinned(participants: list[Participant], bins: list[_Bin]) -> list[Participant]:
    """Đưa người đã được BTC gán tay vào đúng chuyến cũ, trả về những người còn lại.

    Ghi đè bản ghi thủ công là xoá quyết định của con người bằng quyết định của máy
    (docs/05 §5). Muốn xếp lại thì phía API phải truyền `force_reallocate` và bỏ pin
    trước khi gọi vào đây.
    """
    by_flight = {bin_.slot.flight_id: bin_ for bin_ in bins}
    pending: list[Participant] = []

    for participant in participants:
        target = by_flight.get(participant.pinned_flight_id) if participant.pinned_flight_id else None
        if target is None:
            pending.append(participant)
            continue
        target.add(participant, pinned=True)

    return pending


# --- Vòng 1: xếp nguyên team ---


def _round_one_whole_groups(
    pending: list[Participant], bins: list[_Bin], params: AllocationParams
) -> list[list[Participant]]:
    """Thử xếp mỗi team nguyên khối vào một chuyến.

    Best-Fit Decreasing: nhóm lớn xử lý trước vì chúng khó xếp nhất; để sau thì chỉ còn
    những khoảng trống vụn và team lớn chắc chắn bị tách.
    """
    groups: dict[tuple, list[Participant]] = defaultdict(list)
    for participant in pending:
        groups[participant.group_key].append(participant)

    # Sắp xếp tất định: size giảm dần, rồi theo khoá nhóm để hai lần chạy không đảo thứ tự.
    ordered_groups = sorted(groups.items(), key=lambda item: (-len(item[1]), str(item[0])))

    split_queue: list[list[Participant]] = []
    for _key, group in ordered_groups:
        candidates = [
            bin_
            for bin_ in bins
            if bin_.remaining >= len(group) and all(bin_.accepts(p) for p in group)
        ]
        if not candidates:
            split_queue.append(group)
            continue

        best = max(candidates, key=lambda bin_: (_group_fit_score(group, bin_, params), -bin_.slot.flight_id))
        for participant in group:
            best.add(participant)

    return split_queue


def _group_fit_score(group: list[Participant], bin_: _Bin, params: AllocationParams) -> int:
    """Điểm của việc đặt nguyên nhóm `group` lên chuyến `bin_`.

    Ba thành phần theo docs/05 §3 bước 2: khớp ca nguyện vọng, độ vừa khít (chừa lại càng
    ít ghế càng tốt, giảm phân mảnh cho nhóm sau), và đã có người cùng team trên chuyến.
    """
    shift_matches = sum(1 for p in group if p.requested_shift_id == bin_.slot.shift_id)
    leftover = bin_.remaining - len(group)

    team_id = group[0].team_id
    has_teammate = team_id is not None and any(
        member.team_id == team_id for member in bin_.members
    )

    return (
        shift_matches * params.shift_weight
        - leftover
        + (params.team_weight if has_teammate else 0)
    )


# --- Vòng 2: tách team ---


def _round_two_split_groups(
    split_queue: list[list[Participant]], bins: list[_Bin], params: AllocationParams
) -> list[Participant]:
    """Tách những nhóm không lọt nguyên khối vào bất kỳ chuyến nào.

    Chia theo nguyện vọng ca trước rồi mới chia theo chỗ trống: tách theo ca giữ được
    C3 cho phần lớn mọi người, thay vì cắt ngang team rồi ai cũng lệch ca.
    """
    unplaced: list[Participant] = []

    for group in split_queue:
        parts: dict[tuple, list[Participant]] = defaultdict(list)
        for participant in group:
            # Gộp theo (ca, có bị khoá ca hay không) để mọi người trong một phần có cùng
            # điều kiện chuyến hợp lệ — nhờ vậy cả mảnh cắt ra luôn xếp được vào chuyến đã chọn.
            parts[(participant.requested_shift_id, participant.shift_locked)].append(participant)

        for (shift_id, locked), members in sorted(
            parts.items(), key=lambda item: (-len(item[1]), str(item[0]))
        ):
            # Cùng phòng ban / cùng điểm đón nằm cạnh nhau -> khi cắt, họ vào cùng mảnh.
            rest = sorted(
                members,
                key=lambda p: (p.department_id or 0, p.pickup_point_id or 0, p.registration_id),
            )

            while rest:
                target = _pick_bin_for_chunk(bins, rest, shift_id, locked, params)
                if target is None:
                    unplaced.extend(rest)
                    break

                take = min(target.remaining, len(rest))
                for participant in rest[:take]:
                    target.add(participant)
                rest = rest[take:]

    return unplaced


def _pick_bin_for_chunk(
    bins: list[_Bin],
    rest: list[Participant],
    shift_id: int | None,
    locked: bool,
    params: AllocationParams,
) -> _Bin | None:
    """Chọn chuyến cho mảnh tiếp theo: đúng ca trước, còn nhiều chỗ trước."""
    eligible = [
        bin_
        for bin_ in bins
        if bin_.remaining > 0 and (not locked or bin_.slot.shift_id == shift_id)
    ]
    if not eligible:
        return None

    ranked = sorted(
        eligible,
        key=lambda bin_: (bin_.slot.shift_id != shift_id, -bin_.remaining, bin_.slot.flight_id),
    )

    # Tránh cắt ra mảnh vụn khi vẫn còn chuyến rộng hơn (docs/05 §3 bước 3).
    for bin_ in ranked:
        if min(bin_.remaining, len(rest)) >= params.min_chunk_size:
            return bin_
    return ranked[0]


# --- Vòng 3: cải thiện cục bộ ---


def _round_three_local_search(
    bins: list[_Bin], params: AllocationParams, rng: random.Random
) -> None:
    """Cải thiện cục bộ: thử đổi chỗ hai người, hoặc chuyển một người sang chuyến còn trống.

    Hai phép biến đổi, cả hai đều giữ C1 và C4:
    - swap 1-đổi-1: số người mỗi chuyến không đổi.
    - relocate: chỉ chuyển vào chuyến còn ghế trống.

    docs/05 §3 bước 4 chỉ nói tới swap, nhưng chỉ swap thì trọng số ở §2 không phát huy
    được trong một trường hợp có thật: team lọt nguyên khối vào một chuyến lệch ca sẽ mãi
    nằm đó, vì vòng 1 đã xếp xong và không có ai để đổi chỗ. Thiếu relocate thì việc BTC
    hạ `team_weight` / tăng `shift_weight` không đổi được kết quả — tức là cấu hình vô nghĩa.

    Số vòng bị chặn cứng để thời gian chạy luôn đoán được.
    """
    if len(bins) < 2:
        return

    current = _score(bins, params)

    for _ in range(params.local_search_iterations):
        if rng.random() < 0.5:
            current = _try_swap(bins, params, rng, current)
        else:
            current = _try_relocate(bins, params, rng, current)


def _try_swap(
    bins: list[_Bin], params: AllocationParams, rng: random.Random, current: int
) -> int:
    """Đổi chỗ hai người khác team giữa hai chuyến."""
    movable = [bin_ for bin_ in bins if len(bin_.members) > len(bin_.pinned_ids)]
    if len(movable) < 2:
        return current

    left, right = rng.sample(movable, 2)
    first = _random_movable(left, rng)
    second = _random_movable(right, rng)
    if first is None or second is None:
        return current
    if first.team_id is not None and first.team_id == second.team_id:
        return current  # đổi hai người cùng team không thay đổi độ gắn kết
    if not left.accepts(second) or not right.accepts(first):
        return current  # C4

    _swap(left, first, right, second)
    candidate = _score(bins, params)
    if candidate > current:
        return candidate

    _swap(left, second, right, first)  # hoàn tác
    return current


def _try_relocate(
    bins: list[_Bin], params: AllocationParams, rng: random.Random, current: int
) -> int:
    """Chuyển một người sang chuyến còn ghế trống."""
    sources = [bin_ for bin_ in bins if len(bin_.members) > len(bin_.pinned_ids)]
    targets = [bin_ for bin_ in bins if bin_.remaining > 0]
    if not sources or not targets:
        return current

    source = rng.choice(sources)
    target = rng.choice(targets)
    if source is target:
        return current

    mover = _random_movable(source, rng)
    if mover is None or not target.accepts(mover):
        return current

    source.members.remove(mover)
    target.members.append(mover)
    candidate = _score(bins, params)
    if candidate > current:
        return candidate

    target.members.remove(mover)  # hoàn tác
    source.members.append(mover)
    return current


def _random_movable(bin_: _Bin, rng: random.Random) -> Participant | None:
    choices = [m for m in bin_.members if m.registration_id not in bin_.pinned_ids]
    return rng.choice(choices) if choices else None


def _swap(left: _Bin, from_left: Participant, right: _Bin, from_right: Participant) -> None:
    left.members.remove(from_left)
    right.members.remove(from_right)
    left.members.append(from_right)
    right.members.append(from_left)


def _score(bins: list[_Bin], params: AllocationParams) -> int:
    """Hàm mục tiêu của docs/05 §2.

    `team_cohesion` đếm theo CẶP cùng team cùng chuyến, không đếm theo người: một team 20
    người đi cùng nhau được 190 cặp, tách 10+10 chỉ còn 90 — nhờ vậy thuật toán ghét việc
    tách team mạnh hơn nhiều so với việc lệch ca của vài người.
    """
    cohesion = 0
    satisfaction = 0
    team_bins: dict[int, set[int]] = defaultdict(set)

    for bin_ in bins:
        per_team: dict[int, int] = defaultdict(int)
        for member in bin_.members:
            if member.requested_shift_id is not None and member.requested_shift_id == bin_.slot.shift_id:
                satisfaction += 1
            if member.team_id is not None:
                per_team[member.team_id] += 1
                team_bins[member.team_id].add(bin_.slot.flight_id)
        cohesion += sum(count * (count - 1) // 2 for count in per_team.values())

    splits = sum(max(len(flight_ids) - 1, 0) for flight_ids in team_bins.values())

    return (
        params.team_weight * cohesion
        + params.shift_weight * satisfaction
        - params.split_penalty * splits
    )


# --- Kết quả, flag và số liệu ---


def _build_result(
    *,
    direction: str,
    seed: int,
    params: AllocationParams,
    participants: list[Participant],
    bins: list[_Bin],
    unplaced: list[Participant],
) -> AllocationResult:
    assignments = [
        Assignment(
            registration_id=member.registration_id,
            flight_id=bin_.slot.flight_id,
            pinned=member.registration_id in bin_.pinned_ids,
        )
        for bin_ in bins
        for member in sorted(bin_.members, key=lambda m: m.registration_id)
    ]

    flags = [
        *_document_flags(participants),
        *_unassigned_flags(unplaced),
        *_shift_flags(bins),
        *_split_flags(bins, params),
    ]
    flags.sort(
        key=lambda flag: (
            _SEVERITY_ORDER.get(flag.severity, 9),
            flag.type,
            flag.registration_id or 0,
            flag.team_id or 0,
        )
    )

    return AllocationResult(
        direction=direction,
        seed=seed,
        assignments=assignments,
        flags=flags,
        summary=_summary(participants, bins, unplaced, params),
        flights=_flight_loads(bins),
        params=params.as_dict(),
    )


def _document_flags(participants: list[Participant]) -> list[Flag]:
    """Thiếu CCCD/ngày sinh thì BTC không xuất được vé — bước tiền kiểm của docs/05 §4."""
    return [
        Flag(
            type=FLAG_MISSING_ID_CARD,
            severity=SEVERITY_ERROR,
            message=f"{p.full_name} thiếu CCCD hoặc ngày sinh nên không xuất được vé.",
            registration_id=p.registration_id,
            team_id=p.team_id,
        )
        for p in participants
        if not p.has_documents
    ]


def _unassigned_flags(unplaced: list[Participant]) -> list[Flag]:
    flags = []
    for participant in sorted(unplaced, key=lambda p: p.registration_id):
        if participant.shift_locked and participant.requested_shift_id is not None:
            flags.append(
                Flag(
                    type=FLAG_SHIFT_LOCKED_VIOLATION,
                    severity=SEVERITY_ERROR,
                    message=(
                        f"{participant.full_name} bị khoá ca nhưng không còn chỗ trên chuyến "
                        "đúng ca. Cần BTC can thiệp."
                    ),
                    registration_id=participant.registration_id,
                    team_id=participant.team_id,
                    details={"requested_shift_id": participant.requested_shift_id},
                )
            )
        else:
            flags.append(
                Flag(
                    type=FLAG_UNASSIGNED,
                    severity=SEVERITY_ERROR,
                    message=f"{participant.full_name} không còn chỗ trên chiều này.",
                    registration_id=participant.registration_id,
                    team_id=participant.team_id,
                )
            )
    return flags


def _shift_flags(bins: list[_Bin]) -> list[Flag]:
    flags = []
    for bin_ in bins:
        for member in bin_.members:
            if member.requested_shift_id is None:
                continue
            if member.requested_shift_id == bin_.slot.shift_id:
                continue
            flags.append(
                Flag(
                    type=FLAG_SHIFT_NOT_SATISFIED,
                    severity=SEVERITY_WARNING,
                    message=(
                        f"{member.full_name} xin ca khác nhưng được xếp chuyến "
                        f"{bin_.slot.flight_code}."
                    ),
                    registration_id=member.registration_id,
                    team_id=member.team_id,
                    flight_id=bin_.slot.flight_id,
                    details={
                        "requested_shift_id": member.requested_shift_id,
                        "assigned_shift_id": bin_.slot.shift_id,
                    },
                )
            )
    return flags


def _split_flags(bins: list[_Bin], params: AllocationParams) -> list[Flag]:
    """Flag về việc tách team — tính từ kết quả CUỐI, sau cả vòng cải thiện cục bộ.

    Tính trong lúc xếp sẽ ra số sai: vòng 3 còn hoán đổi người giữa các chuyến.
    """
    chunks: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    names: dict[int, str] = {}

    for bin_ in bins:
        for member in bin_.members:
            if member.team_id is None:
                continue
            chunks[member.team_id][bin_.slot.flight_id] += 1
            names[member.team_id] = member.team_name

    flags = []
    for team_id, per_flight in sorted(chunks.items()):
        if len(per_flight) < 2:
            continue
        sizes = [per_flight[flight_id] for flight_id in sorted(per_flight)]
        team_name = names.get(team_id, f"Team #{team_id}")

        flags.append(
            Flag(
                type=FLAG_TEAM_SPLIT,
                severity=SEVERITY_WARNING,
                message=(
                    f"Team {team_name} bị tách thành {len(sizes)} chuyến "
                    f"({' + '.join(str(size) for size in sizes)})."
                ),
                team_id=team_id,
                details={"chunks": sizes},
            )
        )

        if len(sizes) > params.max_split_per_team:
            flags.append(
                Flag(
                    type=FLAG_TEAM_SPLIT_EXCEEDED,
                    severity=SEVERITY_ERROR,
                    message=(
                        f"Team {team_name} bị tách {len(sizes)} mảnh, vượt giới hạn "
                        f"{params.max_split_per_team}."
                    ),
                    team_id=team_id,
                    details={"chunks": sizes, "max_split_per_team": params.max_split_per_team},
                )
            )

        for flight_id, size in sorted(per_flight.items()):
            if size < params.min_chunk_size:
                flags.append(
                    Flag(
                        type=FLAG_TINY_CHUNK,
                        severity=SEVERITY_INFO,
                        message=(
                            f"Chỉ {size} người của team {team_name} đi riêng một chuyến "
                            f"(tối thiểu nên là {params.min_chunk_size})."
                        ),
                        team_id=team_id,
                        flight_id=flight_id,
                        details={"chunk_size": size},
                    )
                )

    return flags


def _summary(
    participants: list[Participant],
    bins: list[_Bin],
    unplaced: list[Participant],
    params: AllocationParams,
) -> AllocationSummary:
    assigned = sum(len(bin_.members) for bin_ in bins)

    with_preference = 0
    satisfied = 0
    for bin_ in bins:
        for member in bin_.members:
            if member.requested_shift_id is None:
                continue
            with_preference += 1
            if member.requested_shift_id == bin_.slot.shift_id:
                satisfied += 1
    # Người không có nguyện vọng không tính vào tỉ lệ: đưa vào sẽ làm tỉ lệ đẹp lên
    # một cách vô nghĩa (không có nguyện vọng thì không thể "không được đáp ứng").
    for participant in unplaced:
        if participant.requested_shift_id is not None:
            with_preference += 1

    teams_split = sum(
        1
        for flight_ids in _team_flight_map(bins).values()
        if len(flight_ids) > 1
    )

    return AllocationSummary(
        total_participants=len(participants),
        assigned=assigned,
        unassigned=len(unplaced),
        teams_split=teams_split,
        shift_satisfaction_rate=round(satisfied / with_preference, 4) if with_preference else 0.0,
        score=_score(bins, params),
    )


def _team_flight_map(bins: list[_Bin]) -> dict[int, set[int]]:
    mapping: dict[int, set[int]] = defaultdict(set)
    for bin_ in bins:
        for member in bin_.members:
            if member.team_id is not None:
                mapping[member.team_id].add(bin_.slot.flight_id)
    return mapping


def _flight_loads(bins: list[_Bin]) -> list[FlightLoad]:
    loads = []
    for bin_ in bins:
        per_team: dict[tuple[int | None, str], int] = defaultdict(int)
        for member in bin_.members:
            per_team[(member.team_id, member.team_name)] += 1

        loads.append(
            FlightLoad(
                flight_id=bin_.slot.flight_id,
                flight_code=bin_.slot.flight_code,
                shift_id=bin_.slot.shift_id,
                capacity=bin_.slot.capacity,
                reserved=bin_.slot.reserved,
                usable_capacity=bin_.slot.usable,
                assigned=len(bin_.members),
                remaining=bin_.remaining,
                teams=[
                    TeamLoad(team_id=team_id, team_name=team_name, count=count)
                    for (team_id, team_name), count in sorted(
                        per_team.items(), key=lambda item: (-item[1], item[0][1])
                    )
                ],
            )
        )
    return loads
