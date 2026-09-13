"""Auto Room Allocation — xếp người tham gia vào phòng khách sạn (docs/05 §7).

Ràng buộc CỨNG:
1. Đúng `gender_policy`: nam vào phòng nam hoặc phòng không giới hạn, nữ tương tự. Người chưa
   khai giới tính nam/nữ chỉ vào phòng không giới hạn — không đoán thay họ.
2. Không vượt sức chứa.
3. Không trộn giới trong một phòng, kể cả phòng không giới hạn: chính sách phòng cho phép, nhưng
   không ai muốn ở chung phòng với người khác giới chỉ vì thuật toán thấy còn giường.
4. Giữ nguyên người BTC đã xếp tay (trừ khi `force_reallocate`).

Ưu tiên MỀM (trọng số trong event_settings): cùng team > cùng chuyến bay chiều đi > cùng phòng
ban; và dồn gọn — lấp đầy phòng trước khi mở phòng mới để BTC trả bớt phòng thừa.

Cách làm: xếp tham lam theo từng team, team đông trước (Best-Fit Decreasing); phòng không giới
hạn để dành cho người chưa khai giới tính rồi mới nhận phần tràn của nam/nữ. Sau đó cải thiện
cục bộ bằng đổi chỗ / chuyển người giữa hai phòng cùng giới. Không có bước ngẫu nhiên: cùng đầu
vào luôn cho cùng kết quả, bất kể thứ tự đầu vào.
"""

from collections import Counter, defaultdict

from app.services.allocator.params import RoomAllocationParams
from app.services.allocator.room_types import (
    FLAG_ALONE_FROM_TEAM,
    FLAG_EMPTY_ROOM,
    FLAG_HEALTH_NOTE,
    FLAG_MISSING_GENDER,
    FLAG_NO_ROOM_CAPACITY,
    FLAG_PINNED_ROOM_CONFLICT,
    GENDER_UNKNOWN,
    POLICY_ANY,
    RoomAllocationResult,
    RoomAllocationSummary,
    RoomBed,
    RoomGuest,
    RoomGuestLoad,
    RoomLoad,
    RoomSlot,
)
from app.services.allocator.types import SEVERITY_ERROR, SEVERITY_INFO, SEVERITY_WARNING, Flag

KNOWN_GENDERS = ("male", "female")
_GENDER_LABELS = {"male": "nam", "female": "nữ"}
_SEVERITY_ORDER = {SEVERITY_ERROR: 0, SEVERITY_WARNING: 1, SEVERITY_INFO: 2}
_MIXED = "mixed"

# Điểm chọn phòng khi xếp tham lam. Các bậc cách xa nhau để thứ tự ưu tiên không bị một thành
# phần thấp hơn lật ngược.
_FIT_JOIN_TEAMMATES = 4000
_FIT_EXACT = 2000
_FIT_FILLS_ROOM = 1000
_FIT_PER_BED_FILLED = 10
_FIT_ROOM_IN_USE = 300
_FIT_SAME_FLIGHT = 150
_FIT_PER_EMPTY_BED = 100


class _RoomBin:
    __slots__ = ("slot", "order", "members", "pinned_ids", "captain_id", "_keys")

    def __init__(self, slot: RoomSlot, order: int):
        self.slot = slot
        self.order = order
        self.members: list[RoomGuest] = []
        self.pinned_ids: set[int] = set()
        self.captain_id: int | None = None
        self._keys: set | None = None

    @property
    def remaining(self) -> int:
        return self.slot.capacity - len(self.members)

    @property
    def gender_class(self) -> str | None:
        classes = {member.gender_class for member in self.members}
        if not classes:
            return None
        return classes.pop() if len(classes) == 1 else _MIXED

    @property
    def keys(self) -> set:
        """Team / chuyến bay / phòng ban có mặt trong phòng — để bỏ qua cặp phòng không liên quan."""
        if self._keys is None:
            self._keys = {
                (kind, value)
                for member in self.members
                for kind, value in (
                    ("team", member.team_id),
                    ("flight", member.flight_id),
                    ("department", member.department_id),
                )
                if value is not None
            }
        return self._keys

    def allows(self, gender_class: str) -> bool:
        """Chính sách giới tính của phòng, chưa tính chỗ trống và người đang ở."""
        policy = self.slot.gender_policy
        return policy == POLICY_ANY or policy == gender_class

    def accepts(self, gender_class: str) -> bool:
        return (
            self.remaining > 0
            and self.allows(gender_class)
            and self.gender_class in (None, gender_class)
        )

    def add(self, guest: RoomGuest, *, pinned: bool = False) -> None:
        self.members.append(guest)
        if pinned:
            self.pinned_ids.add(guest.registration_id)
        self._keys = None

    def remove(self, guest: RoomGuest) -> None:
        self.members.remove(guest)
        self._keys = None

    def replace(self, old: RoomGuest, new: RoomGuest) -> None:
        self.members[self.members.index(old)] = new
        self._keys = None

    def movable(self) -> list[RoomGuest]:
        return [member for member in self.members if member.registration_id not in self.pinned_ids]


def allocate_rooms(
    *,
    guests: list[RoomGuest],
    rooms: list[RoomSlot],
    params: RoomAllocationParams | None = None,
) -> RoomAllocationResult:
    """Xếp người tham gia vào phòng. Không ghi gì."""
    params = params or RoomAllocationParams()
    bins = [_RoomBin(slot, index) for index, slot in enumerate(sorted(rooms, key=_room_sort_key))]
    ordered = sorted(guests, key=lambda guest: guest.registration_id)

    pending, conflicts = _place_pinned(ordered, bins)
    by_class: dict[str, list[RoomGuest]] = defaultdict(list)
    for guest in pending:
        by_class[guest.gender_class].append(guest)

    shared = [bin_ for bin_ in bins if bin_.slot.gender_policy == POLICY_ANY]

    # 1. Người chưa khai giới tính chỉ ở được phòng không giới hạn: xếp trước, để phần tràn của
    #    nam/nữ không chiếm mất giường duy nhất họ dùng được.
    unplaced = _place_class(by_class[GENDER_UNKNOWN], shared, GENDER_UNKNOWN)

    # 2. Nam, nữ vào đúng phòng của mình trước.
    overflow = {
        gender: _place_class(
            by_class[gender],
            [bin_ for bin_ in bins if bin_.slot.gender_policy == gender],
            gender,
        )
        for gender in KNOWN_GENDERS
    }

    # 3. Phần tràn sang phòng không giới hạn; giới tràn nhiều hơn chọn trước.
    for gender in sorted(KNOWN_GENDERS, key=lambda item: (-len(overflow[item]), item)):
        unplaced.extend(_place_class(overflow[gender], shared, gender))

    _improve(bins, params)
    # Đổi chỗ cục bộ có thể làm trống hẳn một phòng (người trong đó sang ở với đồng đội). Phòng
    # đó giờ nhận được người trước đây bị kẹt vì phòng đang có người khác giới — xếp lại một lượt.
    if unplaced:
        unplaced = _place_leftovers(unplaced, bins)
    _choose_captains(bins)
    return _build_result(ordered, bins, unplaced, conflicts, params)


def _place_leftovers(unplaced: list[RoomGuest], bins: list[_RoomBin]) -> list[RoomGuest]:
    by_class: dict[str, list[RoomGuest]] = defaultdict(list)
    for guest in unplaced:
        by_class[guest.gender_class].append(guest)

    shared = [bin_ for bin_ in bins if bin_.slot.gender_policy == POLICY_ANY]
    remaining = _place_class(by_class[GENDER_UNKNOWN], shared, GENDER_UNKNOWN)
    for gender in KNOWN_GENDERS:
        own = [bin_ for bin_ in bins if bin_.slot.gender_policy == gender]
        rest = _place_class(by_class[gender], own, gender)
        remaining.extend(_place_class(rest, shared, gender))
    return remaining


# --- Xếp tham lam ---


def _natural(value: object) -> tuple:
    text = str(value or "")
    return (0, int(text), "") if text.isdigit() else (1, 0, text)


def _room_sort_key(slot: RoomSlot) -> tuple:
    return (
        slot.hotel_name,
        slot.hotel_id,
        slot.floor is None,
        _natural(slot.floor),
        _natural(slot.room_number),
        slot.room_id,
    )


def _place_pinned(guests: list[RoomGuest], bins: list[_RoomBin]) -> tuple[list[RoomGuest], list[Flag]]:
    by_id = {bin_.slot.room_id: bin_ for bin_ in bins}
    pending: list[RoomGuest] = []
    conflicts: list[Flag] = []

    for guest in guests:
        target = by_id.get(guest.pinned_room_id) if guest.pinned_room_id else None
        if target is None:
            pending.append(guest)
            continue
        if not target.allows(guest.gender_class):
            conflicts.append(
                Flag(
                    type=FLAG_PINNED_ROOM_CONFLICT,
                    severity=SEVERITY_WARNING,
                    message=(
                        f"{guest.full_name} được BTC xếp tay vào phòng {target.slot.room_number} "
                        "nhưng không hợp giới tính của phòng. Giữ nguyên theo quyết định tay — "
                        "kiểm tra lại."
                    ),
                    registration_id=guest.registration_id,
                    team_id=guest.team_id,
                    details={"room_id": target.slot.room_id},
                )
            )
        target.add(guest, pinned=True)

    for bin_ in bins:
        if bin_.remaining < 0:
            conflicts.append(
                Flag(
                    type=FLAG_PINNED_ROOM_CONFLICT,
                    severity=SEVERITY_WARNING,
                    message=(
                        f"Phòng {bin_.slot.room_number} có {len(bin_.members)} người xếp tay, vượt "
                        f"sức chứa {bin_.slot.capacity}."
                    ),
                    details={"room_id": bin_.slot.room_id},
                )
            )
        if bin_.gender_class == _MIXED:
            conflicts.append(
                Flag(
                    type=FLAG_PINNED_ROOM_CONFLICT,
                    severity=SEVERITY_WARNING,
                    message=f"Phòng {bin_.slot.room_number} đang có người xếp tay thuộc cả hai giới.",
                    details={"room_id": bin_.slot.room_id},
                )
            )
    return pending, conflicts


def _place_class(members: list[RoomGuest], bins: list[_RoomBin], gender_class: str) -> list[RoomGuest]:
    """Xếp một giới vào các phòng cho trước. Trả về người không còn chỗ."""
    unplaced: list[RoomGuest] = []
    for group in _groups(members):
        rest = group
        while rest:
            candidates = [bin_ for bin_ in bins if bin_.accepts(gender_class)]
            if not candidates:
                unplaced.extend(rest)
                break
            best = max(candidates, key=lambda bin_: (_fit_score(bin_, rest), -bin_.order))
            taken = rest[: best.remaining]
            for guest in taken:
                best.add(guest)
            rest = rest[len(taken):]
    return unplaced


def _groups(members: list[RoomGuest]) -> list[list[RoomGuest]]:
    """Mỗi team một nhóm, team đông trước; người không có team gom chung một nhóm cuối.

    Trong nhóm sắp theo chuyến bay rồi phòng ban: khi một team phải chia nhiều phòng, những người
    đứng cạnh nhau (cùng chuyến) rơi vào cùng phòng.
    """
    teams: dict[int, list[RoomGuest]] = defaultdict(list)
    solos: list[RoomGuest] = []
    for guest in members:
        if guest.team_id is None:
            solos.append(guest)
        else:
            teams[guest.team_id].append(guest)

    groups = [
        sorted(group, key=_member_key)
        for _team_id, group in sorted(teams.items(), key=lambda item: (-len(item[1]), item[0]))
    ]
    if solos:
        groups.append(sorted(solos, key=_member_key))
    return groups


def _member_key(guest: RoomGuest) -> tuple:
    return (
        guest.flight_id is None,
        guest.flight_id or 0,
        guest.department_id is None,
        guest.department_id or 0,
        guest.full_name,
        guest.registration_id,
    )


def _fit_score(bin_: _RoomBin, rest: list[RoomGuest]) -> int:
    lead = rest[0]
    group_size = len(rest)
    space = bin_.remaining

    score = 0
    if lead.team_id is not None and any(member.team_id == lead.team_id for member in bin_.members):
        score += _FIT_JOIN_TEAMMATES
    if space == group_size:
        score += _FIT_EXACT
    elif space < group_size:
        # Lấp kín phòng; phòng to trước để dùng ít phòng nhất.
        score += _FIT_FILLS_ROOM + space * _FIT_PER_BED_FILLED
    else:
        score -= (space - group_size) * _FIT_PER_EMPTY_BED
    if bin_.members:
        # Lấp phòng đang dở trước khi mở phòng mới.
        score += _FIT_ROOM_IN_USE
    if lead.flight_id is not None and any(member.flight_id == lead.flight_id for member in bin_.members):
        score += _FIT_SAME_FLIGHT
    return score


# --- Cải thiện cục bộ ---


def _pair_score(members: list[RoomGuest], params: RoomAllocationParams) -> int:
    total = 0
    for index, first in enumerate(members):
        for second in members[index + 1 :]:
            if first.team_id is not None and first.team_id == second.team_id:
                total += params.team_weight
            if first.flight_id is not None and first.flight_id == second.flight_id:
                total += params.flight_weight
            if first.department_id is not None and first.department_id == second.department_id:
                total += params.department_weight
    return total


def _improve(bins: list[_RoomBin], params: RoomAllocationParams) -> None:
    """Đổi chỗ hai người, hoặc chuyển một người sang phòng còn chỗ, khi làm tăng điểm.

    Chỉ giữa hai phòng CÙNG giới đang có người: không mở phòng mới, không trộn giới. Cặp phòng
    không có team/chuyến/phòng ban chung thì đổi thế nào điểm cũng không tăng — bỏ qua cho nhanh.
    """
    for _sweep in range(params.local_search_sweeps):
        changed = False
        active = [bin_ for bin_ in bins if bin_.members and bin_.gender_class not in (None, _MIXED)]
        for index, first in enumerate(active):
            for second in active[index + 1 :]:
                if not first.members or not second.members:
                    continue
                if first.gender_class != second.gender_class or not (first.keys & second.keys):
                    continue
                if (
                    _try_swap(first, second, params)
                    or _try_move(first, second, params)
                    or _try_move(second, first, params)
                ):
                    changed = True
        if not changed:
            return


def _try_swap(first: _RoomBin, second: _RoomBin, params: RoomAllocationParams) -> bool:
    base = _pair_score(first.members, params) + _pair_score(second.members, params)
    for left in first.movable():
        for right in second.movable():
            if left.team_id == right.team_id and left.flight_id == right.flight_id:
                continue
            if not (first.allows(right.gender_class) and second.allows(left.gender_class)):
                continue
            new_first = [right if member is left else member for member in first.members]
            new_second = [left if member is right else member for member in second.members]
            if _pair_score(new_first, params) + _pair_score(new_second, params) > base:
                first.replace(left, right)
                second.replace(right, left)
                return True
    return False


def _try_move(source: _RoomBin, target: _RoomBin, params: RoomAllocationParams) -> bool:
    if target.remaining <= 0:
        return False
    base = _pair_score(source.members, params) + _pair_score(target.members, params)
    for guest in source.movable():
        if not target.allows(guest.gender_class):
            continue
        new_source = [member for member in source.members if member is not guest]
        if _pair_score(new_source, params) + _pair_score([*target.members, guest], params) > base:
            source.remove(guest)
            target.add(guest)
            return True
    return False


def _choose_captains(bins: list[_RoomBin]) -> None:
    """Trưởng phòng: giữ người BTC đã chọn; không có thì ưu tiên trưởng nhóm, rồi người thuộc team
    đông nhất trong phòng. Chỉ chọn trong người xếp tự động — không sửa bản ghi xếp tay."""
    for bin_ in bins:
        pinned_captains = sorted(
            member.registration_id
            for member in bin_.members
            if member.registration_id in bin_.pinned_ids and member.pinned_captain
        )
        if pinned_captains:
            bin_.captain_id = pinned_captains[0]
            continue
        candidates = bin_.movable()
        if not candidates:
            bin_.captain_id = None
            continue
        team_sizes = Counter(member.team_id for member in bin_.members if member.team_id is not None)
        bin_.captain_id = min(
            candidates,
            key=lambda member: (
                not member.is_team_leader,
                -team_sizes.get(member.team_id, 0),
                member.full_name,
                member.registration_id,
            ),
        ).registration_id


# --- Kết quả ---


def _build_result(
    guests: list[RoomGuest],
    bins: list[_RoomBin],
    unplaced: list[RoomGuest],
    conflicts: list[Flag],
    params: RoomAllocationParams,
) -> RoomAllocationResult:
    assignments: list[RoomBed] = []
    loads: list[RoomLoad] = []
    for bin_ in bins:
        guest_loads = []
        for member in sorted(bin_.members, key=lambda item: item.registration_id):
            pinned = member.registration_id in bin_.pinned_ids
            captain = member.pinned_captain if pinned else member.registration_id == bin_.captain_id
            assignments.append(
                RoomBed(
                    registration_id=member.registration_id,
                    room_id=bin_.slot.room_id,
                    is_room_captain=captain,
                    pinned=pinned,
                )
            )
            guest_loads.append(_guest_load(member, pinned=pinned, captain=captain))
        guest_loads.sort(key=lambda item: (not item.is_room_captain, item.full_name))
        loads.append(
            RoomLoad(
                room_id=bin_.slot.room_id,
                room_number=bin_.slot.room_number,
                hotel_id=bin_.slot.hotel_id,
                hotel_name=bin_.slot.hotel_name,
                floor=bin_.slot.floor,
                capacity=bin_.slot.capacity,
                gender_policy=bin_.slot.gender_policy,
                assigned=len(bin_.members),
                remaining=bin_.remaining,
                guests=guest_loads,
            )
        )

    flags = [
        *conflicts,
        *_unplaced_flags(unplaced, bins),
        *_placement_flags(bins),
    ]
    flags.sort(
        key=lambda flag: (
            _SEVERITY_ORDER.get(flag.severity, 9),
            flag.type,
            flag.registration_id or 0,
            flag.details.get("room_id") or 0,
        )
    )

    return RoomAllocationResult(
        assignments=assignments,
        flags=flags,
        summary=_summary(guests, bins, unplaced, params),
        rooms=loads,
        unassigned=[
            _guest_load(guest, pinned=False, captain=False)
            for guest in sorted(unplaced, key=lambda item: item.registration_id)
        ],
        params=params.as_dict(),
    )


def _guest_load(guest: RoomGuest, *, pinned: bool, captain: bool) -> RoomGuestLoad:
    return RoomGuestLoad(
        registration_id=guest.registration_id,
        full_name=guest.full_name,
        team_id=guest.team_id,
        team_name=guest.team_name,
        gender=guest.gender,
        flight_code=guest.flight_code,
        pinned=pinned,
        is_room_captain=captain,
    )


def _unplaced_flags(unplaced: list[RoomGuest], bins: list[_RoomBin]) -> list[Flag]:
    has_shared = any(bin_.slot.gender_policy == POLICY_ANY for bin_ in bins)
    flags = []
    for guest in sorted(unplaced, key=lambda item: item.registration_id):
        if guest.gender_class == GENDER_UNKNOWN:
            flags.append(
                Flag(
                    type=FLAG_MISSING_GENDER,
                    severity=SEVERITY_ERROR,
                    message=(
                        f"{guest.full_name} chưa khai giới tính nam/nữ nên chỉ xếp được vào phòng không "
                        "giới hạn — "
                        + ("các phòng đó đã đủ người." if has_shared else "kỳ này chưa có phòng như vậy.")
                        + " Bổ sung hồ sơ hoặc thêm phòng không giới hạn."
                    ),
                    registration_id=guest.registration_id,
                    team_id=guest.team_id,
                    details={"gender": guest.gender},
                )
            )
            continue
        label = _GENDER_LABELS[guest.gender_class]
        flags.append(
            Flag(
                type=FLAG_NO_ROOM_CAPACITY,
                severity=SEVERITY_ERROR,
                message=(
                    f"{guest.full_name} ({label}): hết giường ở phòng {label}"
                    + (" và phòng không giới hạn." if has_shared else ".")
                    + f" Thêm phòng hoặc đổi một phòng trống sang phòng {label}."
                ),
                registration_id=guest.registration_id,
                team_id=guest.team_id,
                details={"gender": guest.gender},
            )
        )
    return flags


def _placement_flags(bins: list[_RoomBin]) -> list[Flag]:
    flags: list[Flag] = []
    team_class = Counter(
        (member.team_id, member.gender_class)
        for bin_ in bins
        for member in bin_.members
        if member.team_id is not None
    )

    for bin_ in bins:
        number = bin_.slot.room_number
        for member in bin_.members:
            if member.has_health_note:
                flags.append(
                    Flag(
                        type=FLAG_HEALTH_NOTE,
                        severity=SEVERITY_INFO,
                        message=(
                            f"{member.full_name} (phòng {number}) có ghi chú sức khoẻ — xem hồ sơ để cân "
                            "nhắc phòng tầng thấp hoặc gần thang máy."
                        ),
                        registration_id=member.registration_id,
                        team_id=member.team_id,
                        details={"room_id": bin_.slot.room_id},
                    )
                )
            if (
                member.team_id is None
                or member.registration_id in bin_.pinned_ids
                or team_class[(member.team_id, member.gender_class)] < 2
                or any(other is not member and other.team_id == member.team_id for other in bin_.members)
            ):
                continue
            flags.append(
                Flag(
                    type=FLAG_ALONE_FROM_TEAM,
                    severity=SEVERITY_INFO,
                    message=(
                        f"{member.full_name} ({member.team_name}) ở phòng {number} không có ai cùng team "
                        "— số giường không chia vừa theo team."
                    ),
                    registration_id=member.registration_id,
                    team_id=member.team_id,
                    details={"room_id": bin_.slot.room_id},
                )
            )

    empty = [bin_ for bin_ in bins if not bin_.members]
    if empty:
        numbers = ", ".join(bin_.slot.room_number for bin_ in empty[:10])
        if len(empty) > 10:
            numbers += f" và {len(empty) - 10} phòng khác"
        flags.append(
            Flag(
                type=FLAG_EMPTY_ROOM,
                severity=SEVERITY_INFO,
                message=f"{len(empty)} phòng không có ai ({numbers}) — có thể báo khách sạn trả bớt.",
                details={"room_ids": [bin_.slot.room_id for bin_ in empty]},
            )
        )
    return flags


def _summary(
    guests: list[RoomGuest],
    bins: list[_RoomBin],
    unplaced: list[RoomGuest],
    params: RoomAllocationParams,
) -> RoomAllocationSummary:
    placed = [(bin_, member) for bin_ in bins for member in bin_.members]
    team_class = Counter((m.team_id, m.gender_class) for _b, m in placed if m.team_id is not None)
    flight_class = Counter((m.flight_id, m.gender_class) for _b, m in placed if m.flight_id is not None)

    team_total = team_ok = flight_total = flight_ok = 0
    for bin_, member in placed:
        others = [other for other in bin_.members if other is not member]
        if member.team_id is not None and team_class[(member.team_id, member.gender_class)] >= 2:
            team_total += 1
            team_ok += any(other.team_id == member.team_id for other in others)
        if member.flight_id is not None and flight_class[(member.flight_id, member.gender_class)] >= 2:
            flight_total += 1
            flight_ok += any(other.flight_id == member.flight_id for other in others)

    used = [bin_ for bin_ in bins if bin_.members]
    return RoomAllocationSummary(
        total_guests=len(guests),
        assigned=len(placed),
        unassigned=len(unplaced),
        rooms_total=len(bins),
        rooms_used=len(used),
        empty_beds=sum(max(bin_.remaining, 0) for bin_ in used),
        same_team_rate=round(team_ok / team_total, 4) if team_total else 1.0,
        same_flight_rate=round(flight_ok / flight_total, 4) if flight_total else 1.0,
        mixed_team_rooms=sum(
            1 for bin_ in used if len(bin_.members) >= 2 and len({m.team_id for m in bin_.members}) > 1
        ),
        score=sum(_pair_score(bin_.members, params) for bin_ in bins),
    )
