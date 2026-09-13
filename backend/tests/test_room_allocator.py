"""Kiểm thử thuật toán xếp phòng (docs/05-allocation-algorithm.md §7).

Hàm thuần — không cần database. Ràng buộc cứng được canh bằng property test.
"""

import random
from time import perf_counter

from app.services.allocator.params import RoomAllocationParams
from app.services.allocator.room_types import (
    FLAG_EMPTY_ROOM,
    FLAG_HEALTH_NOTE,
    FLAG_MISSING_GENDER,
    FLAG_NO_ROOM_CAPACITY,
    FLAG_PINNED_ROOM_CONFLICT,
    RoomGuest,
    RoomSlot,
)
from app.services.allocator.rooms import allocate_rooms


def guest(
    registration_id: int,
    gender: str | None = "male",
    team: int | None = None,
    *,
    flight: int | None = None,
    department: int | None = None,
    leader: bool = False,
    health: bool = False,
    pinned: int | None = None,
    captain: bool = False,
) -> RoomGuest:
    return RoomGuest(
        registration_id=registration_id,
        full_name=f"Người {registration_id:03d}",
        gender=gender,
        team_id=team,
        team_name=f"Team {team}" if team else "Chưa có team",
        department_id=department,
        flight_id=flight,
        flight_code=f"VN{flight}" if flight else None,
        is_team_leader=leader,
        has_health_note=health,
        pinned_room_id=pinned,
        pinned_captain=captain,
    )


def room(room_id: int, capacity: int = 2, policy: str = "male", *, floor: str = "1") -> RoomSlot:
    return RoomSlot(
        room_id=room_id,
        room_number=str(room_id),
        hotel_id=1,
        hotel_name="Sunset",
        capacity=capacity,
        gender_policy=policy,
        floor=floor,
    )


def run(guests, rooms, **params):
    return allocate_rooms(
        guests=guests, rooms=rooms, params=RoomAllocationParams(**params) if params else None
    )


def placement(result) -> dict[int, int]:
    return {bed.registration_id: bed.room_id for bed in result.assignments}


def roommates(result) -> list[set[int]]:
    groups: dict[int, set[int]] = {}
    for bed in result.assignments:
        groups.setdefault(bed.room_id, set()).add(bed.registration_id)
    return sorted(groups.values(), key=min)


def gender_class(gender: str | None) -> str:
    return gender if gender in ("male", "female") else "unknown"


# --- Ràng buộc cứng ---


def test_men_and_women_go_to_their_own_rooms():
    result = run(
        [guest(1, "male"), guest(2, "female"), guest(3, "male"), guest(4, "female")],
        [room(10, policy="male"), room(20, policy="female")],
    )

    assert placement(result) == {1: 10, 3: 10, 2: 20, 4: 20}
    assert result.summary.unassigned == 0


def test_unknown_gender_only_goes_to_shared_rooms():
    without_shared = run([guest(1, "male"), guest(2, None)], [room(10)])
    with_shared = run([guest(1, "male"), guest(2, None)], [room(10), room(30, policy="any")])

    assert placement(without_shared) == {1: 10}
    flag = without_shared.flags[0]
    assert (flag.type, flag.severity, flag.registration_id) == (FLAG_MISSING_GENDER, "error", 2)
    assert placement(with_shared) == {1: 10, 2: 30}


def test_shared_rooms_take_overflow_but_never_mix_genders():
    people = [guest(1), guest(2), guest(3), guest(4, "female"), guest(5, "female")]
    result = run(people, [room(10), room(30, 3, "any"), room(31, 2, "any")])

    assert placement(result) == {1: 10, 2: 10, 3: 30, 4: 31, 5: 31}


def test_one_shared_room_left_is_not_split_between_genders():
    people = [guest(1), guest(2), guest(3), guest(4, "female")]
    result = run(people, [room(10), room(31, 2, "any")])

    assert placement(result) == {1: 10, 2: 10, 4: 31}
    assert [(flag.type, flag.registration_id) for flag in result.flags if flag.severity == "error"] == [
        (FLAG_NO_ROOM_CAPACITY, 3)
    ]


def test_no_room_capacity_is_reported():
    result = run([guest(1), guest(2), guest(3)], [room(10)])

    assert result.summary.unassigned == 1
    assert [guest_load.registration_id for guest_load in result.unassigned] == [3]
    assert result.flags[0].type == FLAG_NO_ROOM_CAPACITY


# --- Ưu tiên mềm ---


def test_teams_share_rooms_even_when_input_is_interleaved():
    people = [guest(index, team=1 if index % 2 else 2) for index in range(1, 9)]
    result = run(people, [room(10), room(11), room(12), room(13)])

    assert roommates(result) == [{1, 3}, {2, 4}, {5, 7}, {6, 8}]
    assert result.summary.same_team_rate == 1.0
    assert result.summary.mixed_team_rooms == 0


def test_team_of_five_fills_a_triple_then_a_twin_and_leaves_a_room_empty():
    result = run([guest(index, team=1) for index in range(1, 6)], [room(10), room(11, 3), room(12)])

    assert roommates(result) == [{1, 2, 3}, {4, 5}]
    assert result.summary.rooms_used == 2
    assert [flag.type for flag in result.flags] == [FLAG_EMPTY_ROOM]


def test_people_without_team_room_with_same_flight():
    people = [guest(1, flight=1), guest(2, flight=2), guest(3, flight=1), guest(4, flight=2)]
    result = run(people, [room(10), room(11)])

    assert roommates(result) == [{1, 3}, {2, 4}]
    assert result.summary.same_flight_rate == 1.0


def test_local_search_brings_teammates_together():
    """Tham lam theo team lớn trước để team 1 (3 người) chiếm phòng ba, team 2 và 3 phải chia
    phòng đôi với mảnh lẻ; đổi chỗ cục bộ phải gom được đồng đội lại."""
    people = [
        *[guest(index, team=1) for index in (1, 2, 3)],
        *[guest(index, team=2) for index in (4, 5)],
        *[guest(index, team=3) for index in (6, 7)],
        guest(8, team=4),
    ]
    result = run(people, [room(10, 3), room(11, 2), room(12, 2), room(13, 1)])

    assert result.summary.unassigned == 0
    assert result.summary.same_team_rate == 1.0


def test_team_weight_beats_flight_weight():
    people = [
        guest(1, team=1, flight=1),
        guest(2, team=1, flight=2),
        guest(3, team=2, flight=1),
        guest(4, team=2, flight=2),
    ]
    result = run(people, [room(10), room(11)])

    assert roommates(result) == [{1, 2}, {3, 4}]


# --- Xếp tay & trưởng phòng ---


def test_pinned_guest_stays_and_teammate_joins():
    people = [guest(1, team=5, pinned=10), guest(2, team=5), guest(3, team=6)]
    result = run(people, [room(10), room(11)])

    assert placement(result) == {1: 10, 2: 10, 3: 11}
    beds = {bed.registration_id: bed for bed in result.assignments}
    assert beds[1].pinned is True
    assert beds[2].pinned is False


def test_pinned_guest_in_wrong_room_is_kept_but_flagged():
    result = run([guest(1, "female", pinned=10)], [room(10, policy="male")])

    assert placement(result) == {1: 10}
    assert result.flags[0].type == FLAG_PINNED_ROOM_CONFLICT


def test_captain_prefers_team_leader_and_keeps_manual_captain():
    people = [
        guest(1, team=7),
        guest(2, team=7, leader=True),
        guest(3, team=7),
        guest(5, pinned=21, captain=True),
        guest(6),
    ]
    result = run(people, [room(20, 3), room(21, 2)])

    captains = {bed.registration_id for bed in result.assignments if bed.is_room_captain}
    assert placement(result) == {1: 20, 2: 20, 3: 20, 5: 21, 6: 21}
    assert captains == {2, 5}


def test_health_note_is_flagged_without_content():
    result = run([guest(1, health=True), guest(2)], [room(10), room(11, policy="female")])

    health = [flag for flag in result.flags if flag.type == FLAG_HEALTH_NOTE]
    assert [flag.registration_id for flag in health] == [1]
    assert any(flag.type == FLAG_EMPTY_ROOM for flag in result.flags)


# --- Tính chất chung ---


def _random_case(rng: random.Random):
    rooms = [
        room(100 + index, rng.choice([1, 2, 3, 4]), rng.choice(["male", "female", "any"]))
        for index in range(rng.randint(0, 8))
    ]
    people = [
        guest(
            index + 1,
            rng.choice(["male", "female", None]),
            rng.choice([None, 1, 2, 3]),
            flight=rng.choice([None, 1, 2]),
            department=rng.choice([None, 1, 2]),
        )
        for index in range(rng.randint(0, 20))
    ]
    return people, rooms


def test_hard_constraints_hold_on_random_inputs():
    rng = random.Random(20261015)
    for _trial in range(200):
        people, rooms = _random_case(rng)
        result = run(people, rooms)

        placed = [bed.registration_id for bed in result.assignments]
        assert len(placed) == len(set(placed))
        assert len(placed) + len(result.unassigned) == len(people)

        final_class: dict[int, set[str]] = {}
        for load in result.rooms:
            classes = {gender_class(item.gender) for item in load.guests}
            final_class[load.room_id] = classes
            assert load.assigned <= load.capacity
            assert len(classes) <= 1
            for item in load.guests:
                assert load.gender_policy == "any" or item.gender == load.gender_policy

        by_id = {load.room_id: load for load in result.rooms}
        for item in result.unassigned:
            wanted = gender_class(item.gender)
            for room_id, classes in final_class.items():
                load = by_id[room_id]
                policy_ok = load.gender_policy == "any" or load.gender_policy == wanted
                assert not (load.remaining > 0 and policy_ok and classes <= {wanted}), (
                    f"Người {item.registration_id} bị bỏ sót dù phòng {room_id} còn chỗ hợp lệ"
                )


def test_same_input_in_any_order_gives_same_result():
    rng = random.Random(7)
    people, rooms = _random_case(rng)
    people = [*people, *[guest(50 + index, team=9) for index in range(5)]]
    rooms = [*rooms, room(900, 3), room(901, 2)]

    expected = run(people, rooms)
    for seed in range(5):
        shuffled_people, shuffled_rooms = people[:], rooms[:]
        random.Random(seed).shuffle(shuffled_people)
        random.Random(seed).shuffle(shuffled_rooms)
        assert run(shuffled_people, shuffled_rooms).assignments == expected.assignments


def test_five_hundred_guests_finish_quickly():
    rng = random.Random(1)
    people = [
        guest(
            index + 1,
            rng.choice(["male", "female"]),
            rng.randint(1, 40),
            flight=rng.randint(1, 6),
            department=rng.randint(1, 10),
        )
        for index in range(500)
    ]
    rooms = [room(1000 + index, 2, "male" if index % 2 else "female", floor=str(index // 20)) for index in range(300)]

    started = perf_counter()
    result = run(people, rooms)
    elapsed = perf_counter() - started

    assert result.summary.assigned + result.summary.unassigned == 500
    assert elapsed < 5, f"Xếp 500 người mất {elapsed:.2f}s"
