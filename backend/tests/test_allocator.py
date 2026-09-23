"""Kiểm thử thuật toán Auto Flight Allocation.

Bám theo bảng test bắt buộc ở docs/05-allocation-algorithm.md §8. Thuật toán là hàm
thuần nên không cần database ở đây — chỉ cần dựng Participant/FlightSlot.
"""

import random

from app.services.allocator import (
    FLAG_MISSING_ID_CARD,
    FLAG_SHIFT_LOCKED_VIOLATION,
    FLAG_SHIFT_NOT_SATISFIED,
    FLAG_TEAM_SPLIT,
    FLAG_TEAM_SPLIT_EXCEEDED,
    FLAG_TINY_CHUNK,
    FLAG_UNASSIGNED,
    SEVERITY_ERROR,
    AllocationParams,
    FlightSlot,
    Participant,
    allocate_flights,
)

CA1, CA2 = 1, 2


# --- Dựng dữ liệu ---


def make_team(
    team_id: int,
    size: int,
    *,
    shift: int | None = CA1,
    start: int = 1,
    locked: bool = False,
    has_documents: bool = True,
    department_id: int | None = None,
) -> list[Participant]:
    return [
        Participant(
            registration_id=start + index,
            user_id=start + index,
            full_name=f"Team{team_id} Người{index + 1}",
            team_id=team_id,
            team_name=f"Team {team_id}",
            department_id=department_id,
            requested_shift_id=shift,
            shift_locked=locked,
            has_documents=has_documents,
        )
        for index in range(size)
    ]


def flight(flight_id: int, capacity: int, *, shift: int | None = CA1, reserved: int = 0) -> FlightSlot:
    return FlightSlot(
        flight_id=flight_id,
        flight_code=f"VN{1000 + flight_id}",
        shift_id=shift,
        capacity=capacity,
        reserved=reserved,
    )


def run(participants, flights, **kwargs):
    return allocate_flights(
        participants=participants, flights=flights, direction="outbound", **kwargs
    )


def placement(result) -> dict[int, int]:
    return {a.registration_id: a.flight_id for a in result.assignments}


def per_flight(result) -> dict[int, int]:
    counts: dict[int, int] = {}
    for assignment in result.assignments:
        counts[assignment.flight_id] = counts.get(assignment.flight_id, 0) + 1
    return counts


# --- 1. Đủ slot, team nhỏ ---


def test_small_teams_with_spare_slots_keep_together_and_get_their_shift():
    participants = [
        *make_team(1, 8, shift=CA1, start=100),
        *make_team(2, 6, shift=CA2, start=200),
        *make_team(3, 5, shift=CA1, start=300),
    ]
    result = run(participants, [flight(1, 40, shift=CA1), flight(2, 40, shift=CA2)])

    assert result.summary.unassigned == 0
    assert result.summary.teams_split == 0
    assert result.summary.shift_satisfaction_rate == 1.0
    assert result.flags_of(FLAG_TEAM_SPLIT) == []
    assert result.flags_of(FLAG_SHIFT_NOT_SATISFIED) == []

    spots = placement(result)
    for team_start, size in ((100, 8), (200, 6), (300, 5)):
        ids = range(team_start, team_start + size)
        assert len({spots[registration_id] for registration_id in ids}) == 1


# --- 2. Tổng slot = tổng người ---


def test_exact_fit_assigns_everyone_without_exceeding_capacity():
    participants = [
        *make_team(1, 20, shift=CA1, start=100),
        *make_team(2, 20, shift=CA2, start=200),
    ]
    flights = [flight(1, 20, shift=CA1), flight(2, 20, shift=CA2)]

    result = run(participants, flights)

    assert result.summary.assigned == 40
    assert result.summary.unassigned == 0
    assert per_flight(result) == {1: 20, 2: 20}
    for load in result.flights:
        assert load.assigned <= load.usable_capacity
        assert load.remaining == 0


def test_reserved_slots_are_never_used():
    """Ghế giữ lại cho VIP: thuật toán không được đụng vào (docs/03 §5)."""
    participants = make_team(1, 12, shift=CA1, start=100)
    result = run(participants, [flight(1, 12, shift=CA1, reserved=4)])

    assert result.summary.assigned == 8
    assert result.summary.unassigned == 4
    assert per_flight(result) == {1: 8}


# --- 3. Thiếu slot ---


def test_shortage_flags_unassigned_and_respects_capacity():
    participants = [
        *make_team(1, 30, shift=CA1, start=100),
        *make_team(2, 30, shift=CA1, start=200),
    ]
    result = run(participants, [flight(1, 25, shift=CA1), flight(2, 25, shift=CA1)])

    assert result.summary.assigned == 50
    assert result.summary.unassigned == 10
    assert len(result.flags_of(FLAG_UNASSIGNED)) == 10
    assert result.has_errors
    assert per_flight(result) == {1: 25, 2: 25}


def test_no_flights_at_all_leaves_everyone_unassigned():
    result = run(make_team(1, 5, start=100), [])

    assert result.summary.assigned == 0
    assert result.summary.unassigned == 5
    assert len(result.flags_of(FLAG_UNASSIGNED)) == 5


# --- 4. Một team lớn hơn mọi chuyến ---


def test_oversized_team_splits_within_limits():
    participants = make_team(1, 40, shift=CA1, start=100)
    flights = [flight(1, 22, shift=CA1), flight(2, 22, shift=CA1)]

    result = run(participants, flights, params=AllocationParams(max_split_per_team=2, min_chunk_size=3))

    assert result.summary.unassigned == 0
    split = result.flags_of(FLAG_TEAM_SPLIT)
    assert len(split) == 1
    chunks = split[0].details["chunks"]
    assert len(chunks) <= 2
    assert min(chunks) >= 3
    assert sum(chunks) == 40
    assert result.flags_of(FLAG_TEAM_SPLIT_EXCEEDED) == []


def test_split_beyond_limit_is_an_error_flag():
    participants = make_team(1, 30, shift=CA1, start=100)
    flights = [flight(i, 10, shift=CA1) for i in range(1, 4)]

    result = run(participants, flights, params=AllocationParams(max_split_per_team=2))

    exceeded = result.flags_of(FLAG_TEAM_SPLIT_EXCEEDED)
    assert len(exceeded) == 1
    assert exceeded[0].severity == SEVERITY_ERROR
    assert exceeded[0].details["chunks"] == [10, 10, 10]


def test_tiny_chunk_is_reported_as_info():
    """Hai người lẻ phải đi riêng: không chặn được, nhưng BTC cần biết."""
    participants = make_team(1, 12, shift=CA1, start=100)
    flights = [flight(1, 10, shift=CA1), flight(2, 10, shift=CA1)]

    result = run(participants, flights, params=AllocationParams(min_chunk_size=3))

    tiny = result.flags_of(FLAG_TINY_CHUNK)
    assert len(tiny) == 1
    assert tiny[0].details["chunk_size"] == 2
    assert tiny[0].severity == "info"


# --- 5. Cả đoàn xin Ca 2 nhưng chỉ có chuyến Ca 1 ---


def test_everyone_wants_ca2_but_only_ca1_exists():
    participants = make_team(1, 15, shift=CA2, start=100)
    result = run(participants, [flight(1, 20, shift=CA1)])

    assert result.summary.assigned == 15
    assert result.summary.unassigned == 0
    assert result.summary.shift_satisfaction_rate == 0.0
    assert len(result.flags_of(FLAG_SHIFT_NOT_SATISFIED)) == 15
    # Lệch ca là cảnh báo, không phải lỗi: người vẫn bay được.
    assert not result.has_errors


def test_shift_preference_wins_when_both_shifts_available():
    participants = [
        *make_team(1, 10, shift=CA1, start=100),
        *make_team(2, 10, shift=CA2, start=200),
    ]
    result = run(participants, [flight(1, 15, shift=CA1), flight(2, 15, shift=CA2)])

    spots = placement(result)
    assert spots[100] == 1
    assert spots[200] == 2
    assert result.summary.shift_satisfaction_rate == 1.0


def test_participants_without_preference_do_not_skew_the_rate():
    """Không có nguyện vọng thì không thể "không được đáp ứng" — không tính vào tỉ lệ."""
    participants = [
        *make_team(1, 5, shift=None, start=100),
        *make_team(2, 5, shift=CA2, start=200),
    ]
    result = run(participants, [flight(1, 20, shift=CA1)])

    # 5 người xin CA2 bị xếp CA1 -> 0/5, 5 người không nguyện vọng không được tính.
    assert result.summary.shift_satisfaction_rate == 0.0
    assert len(result.flags_of(FLAG_SHIFT_NOT_SATISFIED)) == 5


# --- 6. Người bị khoá ca ---


def test_locked_shift_is_a_hard_constraint():
    participants = [
        *make_team(1, 4, shift=CA2, start=100, locked=True),
        *make_team(2, 20, shift=CA1, start=200),
    ]
    flights = [flight(1, 20, shift=CA1), flight(2, 10, shift=CA2)]

    result = run(participants, flights)
    spots = placement(result)

    for registration_id in range(100, 104):
        assert spots[registration_id] == 2  # chuyến Ca 2, 4 người bị khoá ca
    assert result.flags_of(FLAG_SHIFT_LOCKED_VIOLATION) == []


def test_locked_shift_without_capacity_raises_error_flag():
    participants = [
        *make_team(1, 3, shift=CA2, start=100, locked=True),
        *make_team(2, 10, shift=CA1, start=200),
    ]
    # Không có chuyến nào của Ca 2.
    result = run(participants, [flight(1, 20, shift=CA1)])

    violations = result.flags_of(FLAG_SHIFT_LOCKED_VIOLATION)
    assert len(violations) == 3
    assert all(flag.severity == SEVERITY_ERROR for flag in violations)
    # Thà để trống còn hơn xếp sai ca đã khoá.
    assert set(placement(result)) == set(range(200, 210))  # chỉ team 2 được xếp


def test_locked_members_force_split_when_team_cannot_fit_whole():
    """Team 10 người (8 xin Ca 1 + 2 bị khoá Ca 2), chuyến Ca 2 chỉ còn 2 chỗ.

    Không chuyến nào chứa nổi cả team nên vòng 2 phải tách, và tách theo đúng ca.
    """
    participants = [
        *make_team(1, 8, shift=CA1, start=100),
        *make_team(1, 2, shift=CA2, start=200, locked=True),
    ]
    flights = [flight(1, 20, shift=CA1), flight(2, 2, shift=CA2)]

    result = run(participants, flights)
    spots = placement(result)

    assert {spots[i] for i in range(100, 108)} == {1}
    assert {spots[i] for i in range(200, 202)} == {2}
    assert len(result.flags_of(FLAG_TEAM_SPLIT)) == 1
    assert result.flags_of(FLAG_SHIFT_LOCKED_VIOLATION) == []


def test_locked_members_can_pull_whole_team_to_their_shift():
    """Cùng dữ liệu nhưng chuyến Ca 2 rộng: cả team đi theo 2 người bị khoá.

    Nghe phản trực giác nhưng đúng hàm mục tiêu: giữ 10 người cùng chuyến được 45 cặp
    (450 điểm), tách 8+2 chỉ còn 29 cặp và bị trừ phạt tách — nên thuật toán chọn để cả
    team lệch ca. Đây chính là C2 > C3 mà BTC đã chọn làm mặc định.
    """
    participants = [
        *make_team(1, 8, shift=CA1, start=100),
        *make_team(1, 2, shift=CA2, start=200, locked=True),
    ]
    flights = [flight(1, 20, shift=CA1), flight(2, 20, shift=CA2)]

    result = run(participants, flights)

    assert result.summary.teams_split == 0
    assert set(per_flight(result)) == {2}  # tất cả trên chuyến Ca 2
    assert len(result.flags_of(FLAG_SHIFT_NOT_SATISFIED)) == 8
    assert result.flags_of(FLAG_SHIFT_LOCKED_VIOLATION) == []


# --- 7. Người đã gán thủ công ---


def test_manual_assignment_is_never_overwritten():
    pinned = Participant(
        registration_id=100,
        user_id=100,
        full_name="Người BTC xếp tay",
        team_id=1,
        team_name="Team 1",
        requested_shift_id=CA1,
        pinned_flight_id=2,  # BTC cố tình xếp sang chuyến Ca 2
    )
    participants = [pinned, *make_team(1, 9, shift=CA1, start=200)]
    flights = [flight(1, 20, shift=CA1), flight(2, 20, shift=CA2)]

    result = run(participants, flights)
    spots = placement(result)

    assert spots[100] == 2
    assert next(a for a in result.assignments if a.registration_id == 100).pinned is True
    # Cả team còn lại vẫn được giữ cùng nhau ở chuyến đúng ca.
    assert {spots[i] for i in range(200, 209)} == {1}


def test_pinned_people_consume_capacity():
    pinned = [
        Participant(
            registration_id=index,
            user_id=index,
            full_name=f"Pinned {index}",
            team_id=9,
            team_name="Team 9",
            requested_shift_id=CA1,
            pinned_flight_id=1,
        )
        for index in range(1, 9)
    ]
    participants = [*pinned, *make_team(1, 5, shift=CA1, start=100)]

    result = run(participants, [flight(1, 10, shift=CA1)])

    assert result.summary.assigned == 10  # 8 pinned + 2 người còn chỗ
    assert result.summary.unassigned == 3
    assert per_flight(result) == {1: 10}


def test_local_search_never_moves_pinned_people():
    pinned = Participant(
        registration_id=1,
        user_id=1,
        full_name="Pinned",
        team_id=1,
        team_name="Team 1",
        requested_shift_id=CA2,
        pinned_flight_id=1,
    )
    participants = [pinned, *make_team(2, 6, shift=CA1, start=100), *make_team(3, 6, shift=CA2, start=200)]
    flights = [flight(1, 8, shift=CA1), flight(2, 8, shift=CA2)]

    result = run(participants, flights, params=AllocationParams(local_search_iterations=500))

    assert placement(result)[1] == 1


# --- 8. Tính tái lập ---


def test_same_seed_gives_identical_result():
    participants = [
        *make_team(1, 17, shift=CA1, start=100),
        *make_team(2, 13, shift=CA2, start=200),
        *make_team(3, 9, shift=CA1, start=300),
        *make_team(4, 6, shift=CA2, start=400),
    ]
    flights = [flight(1, 22, shift=CA1), flight(2, 18, shift=CA2), flight(3, 12, shift=CA1)]

    first = run(participants, flights, seed=777)
    second = run(participants, flights, seed=777)

    assert placement(first) == placement(second)
    assert first.summary == second.summary
    assert [(f.type, f.registration_id, f.team_id) for f in first.flags] == [
        (f.type, f.registration_id, f.team_id) for f in second.flags
    ]


def test_input_order_does_not_change_result():
    """Đổi thứ tự đầu vào không được đổi kết quả: BTC chạy lại phải ra đúng bản cũ."""
    participants = [
        *make_team(1, 12, shift=CA1, start=100),
        *make_team(2, 9, shift=CA2, start=200),
        *make_team(3, 7, shift=CA1, start=300),
    ]
    flights = [flight(1, 16, shift=CA1), flight(2, 16, shift=CA2)]

    straight = run(participants, flights)
    shuffled_participants = list(reversed(participants))
    shuffled_flights = list(reversed(flights))
    shuffled = run(shuffled_participants, shuffled_flights)

    assert placement(straight) == placement(shuffled)


# --- 9. Property test: không bao giờ vượt capacity ---


def test_property_never_exceeds_capacity_on_random_inputs():
    """200 input ngẫu nhiên: ràng buộc cứng C1 và C4 không được vi phạm lần nào."""
    rng = random.Random(12345)

    for case in range(200):
        flights = [
            flight(
                index + 1,
                rng.randint(1, 30),
                shift=rng.choice([CA1, CA2, None]),
                reserved=rng.randint(0, 3),
            )
            for index in range(rng.randint(0, 4))
        ]

        participants = []
        next_id = 1
        for team_id in range(1, rng.randint(2, 6)):
            size = rng.randint(1, 25)
            locked = rng.random() < 0.2
            participants.extend(
                make_team(
                    team_id,
                    size,
                    shift=rng.choice([CA1, CA2, None]),
                    start=next_id,
                    locked=locked,
                )
            )
            next_id += size + 1

        result = run(participants, flights, seed=case)

        # C1: không chuyến nào vượt ghế dùng được.
        counts = per_flight(result)
        for slot in flights:
            assert counts.get(slot.flight_id, 0) <= slot.usable, (
                f"case {case}: chuyến {slot.flight_id} vượt {slot.usable} ghế"
            )

        # C4: người bị khoá ca chỉ nằm trên chuyến đúng ca.
        shift_of = {slot.flight_id: slot.shift_id for slot in flights}
        spots = placement(result)
        for participant in participants:
            if participant.shift_locked and participant.requested_shift_id is not None:
                assigned_flight = spots.get(participant.registration_id)
                if assigned_flight is not None:
                    assert shift_of[assigned_flight] == participant.requested_shift_id

        # Mỗi người đúng một chỗ, và tổng khớp summary.
        assert len(spots) == len(result.assignments)
        assert result.summary.assigned + result.summary.unassigned == len(participants)


# --- Tiền kiểm giấy tờ ---


def test_missing_documents_flagged_without_blocking_allocation():
    participants = [
        *make_team(1, 4, shift=CA1, start=100),
        *make_team(2, 2, shift=CA1, start=200, has_documents=False),
    ]
    result = run(participants, [flight(1, 20, shift=CA1)])

    missing = result.flags_of(FLAG_MISSING_ID_CARD)
    assert len(missing) == 2
    assert all(flag.severity == SEVERITY_ERROR for flag in missing)
    # Vẫn xếp chỗ: thiếu giấy tờ là việc bổ sung được trước ngày bay.
    assert result.summary.assigned == 6


# --- Trọng số điều khiển hành vi ---


def test_team_weight_beats_shift_weight_by_default():
    """Mặc định W_TEAM(10) > W_SHIFT(6): thà lệch ca còn hơn tách team.

    Team 12 người xin Ca 1; chuyến Ca 1 chỉ còn 8 chỗ, chuyến Ca 2 còn 12.
    Giữ nguyên team nghĩa là cả 12 người phải bay Ca 2.
    """
    participants = make_team(1, 12, shift=CA1, start=100)
    flights = [flight(1, 8, shift=CA1), flight(2, 12, shift=CA2)]

    result = run(participants, flights)

    assert result.summary.teams_split == 0
    assert set(per_flight(result)) == {2}
    assert len(result.flags_of(FLAG_SHIFT_NOT_SATISFIED)) == 12


def test_raising_shift_weight_flips_the_trade_off():
    """BTC đổi ưu tiên bằng cấu hình, không phải bằng sửa code (docs/05 §2)."""
    participants = make_team(1, 12, shift=CA1, start=100)
    flights = [flight(1, 8, shift=CA1), flight(2, 12, shift=CA2)]

    shift_first = run(
        participants,
        flights,
        params=AllocationParams(team_weight=1, shift_weight=50, split_penalty=0),
    )

    # Ưu tiên ca cao hơn hẳn -> chấp nhận tách team để 8 người được đúng ca.
    assert shift_first.summary.teams_split == 1
    assert len(shift_first.flags_of(FLAG_SHIFT_NOT_SATISFIED)) == 4


def test_score_is_reported_and_higher_is_better():
    participants = [*make_team(1, 10, shift=CA1, start=100), *make_team(2, 10, shift=CA2, start=200)]
    flights = [flight(1, 12, shift=CA1), flight(2, 12, shift=CA2)]

    good = run(participants, flights)
    # Chỉ có một chuyến Ca 1: hai team phải chen nhau, điểm phải thấp hơn.
    worse = run(participants, [flight(1, 20, shift=CA1)])

    assert good.summary.score > worse.summary.score


# --- Độ vừa khít tính theo tỉ lệ, không theo số ghế ---


def test_big_empty_flight_is_not_punished_for_being_big():
    """Chuyến đúng ca nhưng còn rỗng vẫn phải thắng chuyến lệch ca chỉ vì nhỏ hơn.

    Bản cũ phạt bằng SỐ ghế trống nên chuyến 100 ghế bị trừ 90 điểm, đè cả 10 nguyện vọng
    (60 điểm) — cả đoàn dồn vào chuyến nhỏ lệch ca. Đây chính là lỗi gặp trên dữ liệu thật.
    """
    participants = make_team(1, 10, shift=CA1, start=100)

    result = run(participants, [flight(1, 100, shift=CA1), flight(2, 12, shift=CA2)])

    assert per_flight(result) == {1: 10}
    assert result.flags_of(FLAG_SHIFT_NOT_SATISFIED) == []


def test_tight_flight_still_wins_when_shift_is_a_tie():
    """Vẫn chống phân mảnh: cùng ca thì chọn chuyến vừa khít, chừa chuyến rộng cho nhóm sau."""
    participants = make_team(1, 10, shift=CA1, start=100)

    result = run(participants, [flight(1, 100, shift=CA1), flight(2, 12, shift=CA1)])

    assert per_flight(result) == {2: 10}


# --- Tách team theo ca khi nguyện vọng chia đôi ---


def mixed_team(team_id: int, first: int, second: int, *, start: int) -> list[Participant]:
    return [
        *make_team(team_id, first, shift=CA1, start=start),
        *make_team(team_id, second, shift=CA2, start=start + first),
    ]


def test_evenly_divided_team_is_split_by_shift():
    participants = mixed_team(1, 10, 10, start=100)

    result = run(participants, [flight(1, 40, shift=CA1), flight(2, 40, shift=CA2)])

    assert per_flight(result) == {1: 10, 2: 10}
    assert result.summary.shift_satisfaction_rate == 1.0
    assert result.summary.teams_split == 1  # tách là có chủ ý, vẫn báo cho BTC biết


def test_small_minority_stays_with_its_team():
    """2 người xin ca khác không đáng để tách team — họ đi cùng đồng đội và nhận flag lệch ca."""
    participants = mixed_team(1, 2, 18, start=100)

    result = run(participants, [flight(1, 40, shift=CA1), flight(2, 40, shift=CA2)])

    assert per_flight(result) == {2: 20}
    assert len(result.flags_of(FLAG_SHIFT_NOT_SATISFIED)) == 2


def test_split_never_creates_a_chunk_below_min_chunk_size():
    """Ngưỡng phần trăm đạt nhưng mảnh nhỏ hơn min_chunk_size thì vẫn giữ nguyên team."""
    participants = mixed_team(1, 2, 4, start=100)

    result = run(
        participants,
        [flight(1, 40, shift=CA1), flight(2, 40, shift=CA2)],
        params=AllocationParams(min_chunk_size=3),
    )

    assert len(per_flight(result)) == 1


def test_shift_split_can_be_turned_off_by_settings():
    participants = mixed_team(1, 10, 10, start=100)

    result = run(
        participants,
        [flight(1, 40, shift=CA1), flight(2, 40, shift=CA2)],
        params=AllocationParams(shift_split_percent=0),
    )

    assert result.summary.teams_split == 0
