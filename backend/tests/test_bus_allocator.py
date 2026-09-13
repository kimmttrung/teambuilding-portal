"""Kiểm thử thuật toán phân xe (docs/05-allocation-algorithm.md §6).

Hàm thuần — không cần database. Ràng buộc cứng được canh bằng property test.
"""

import random

from app.services.allocator.bus_types import (
    FLAG_BUS_UNDERUTILIZED,
    FLAG_MISSING_FLIGHT_ASSIGNMENT,
    FLAG_MIXED_FLIGHT_ON_BUS,
    FLAG_NO_BUS_CAPACITY,
    FLAG_SURPLUS_BUS,
    BusRider,
    BusSlot,
)
from app.services.allocator.buses import allocate_buses

PICKUP_A, PICKUP_B = 1, 2
FLIGHT_1, FLIGHT_2 = 11, 22


def riders(
    team_id: int | None,
    size: int,
    *,
    start: int,
    pickup: int | None = PICKUP_A,
    flight: int | None = FLIGHT_1,
) -> list[BusRider]:
    return [
        BusRider(
            registration_id=start + index,
            full_name=f"Người {start + index}",
            team_id=team_id,
            team_name=f"Team {team_id}" if team_id else "Chưa có team",
            pickup_point_id=pickup,
            flight_id=flight,
        )
        for index in range(size)
    ]


def bus(bus_id: int, capacity: int = 45, *, pickup: int | None = None, flight: int | None = None) -> BusSlot:
    return BusSlot(
        bus_id=bus_id,
        bus_code=f"XE-{bus_id:02d}",
        capacity=capacity,
        pickup_point_id=pickup,
        linked_flight_id=flight,
    )


def run(people, buses, *, airport_linked: bool = False):
    return allocate_buses(
        riders=people, buses=buses, trip_leg_id=1, airport_linked=airport_linked
    )


def placement(result) -> dict[int, int]:
    return {seat.registration_id: seat.bus_id for seat in result.assignments}


def per_bus(result) -> dict[int, int]:
    counts: dict[int, int] = {}
    for seat in result.assignments:
        counts[seat.bus_id] = counts.get(seat.bus_id, 0) + 1
    return counts


# --- Chặng sân bay: cùng chuyến bay là ràng buộc cứng ---


def test_airport_leg_keeps_each_flight_on_its_own_bus():
    people = [
        *riders(1, 10, start=100, pickup=None, flight=FLIGHT_1),
        *riders(2, 10, start=200, pickup=None, flight=FLIGHT_2),
    ]
    result = run(people, [bus(1, flight=FLIGHT_1), bus(2, flight=FLIGHT_2)], airport_linked=True)

    spots = placement(result)
    assert {spots[i] for i in range(100, 110)} == {1}
    assert {spots[i] for i in range(200, 210)} == {2}
    assert result.flags_of(FLAG_MIXED_FLIGHT_ON_BUS) == []
    assert result.summary.unassigned == 0


def test_airport_leg_never_puts_rider_on_bus_of_another_flight():
    """Xe của chuyến 1 còn trống vẫn không được nhận người bay chuyến 2."""
    people = riders(1, 5, start=100, pickup=None, flight=FLIGHT_2)
    result = run(people, [bus(1, flight=FLIGHT_1)], airport_linked=True)

    assert result.summary.assigned == 0
    flags = result.flags_of(FLAG_NO_BUS_CAPACITY)
    assert len(flags) == 5
    assert flags[0].details["reason"] == "no_matching_bus"


def test_airport_leg_rider_without_flight_is_flagged_not_placed():
    people = [
        *riders(1, 3, start=100, pickup=None, flight=None),
        *riders(1, 3, start=200, pickup=None, flight=FLIGHT_1),
    ]
    # Có cả xe không gắn chuyến còn trống — vẫn không được xếp người chưa có chuyến bay.
    result = run(people, [bus(1, flight=FLIGHT_1), bus(2)], airport_linked=True)

    missing = result.flags_of(FLAG_MISSING_FLIGHT_ASSIGNMENT)
    assert {flag.registration_id for flag in missing} == {100, 101, 102}
    assert set(placement(result)) == {200, 201, 202}
    assert result.has_errors


def test_unlinked_bus_mixing_flights_is_warned():
    people = [
        *riders(1, 4, start=100, pickup=None, flight=FLIGHT_1),
        *riders(2, 4, start=200, pickup=None, flight=FLIGHT_2),
    ]
    result = run(people, [bus(1)], airport_linked=True)

    assert result.summary.assigned == 8
    mixed = result.flags_of(FLAG_MIXED_FLIGHT_ON_BUS)
    assert len(mixed) == 1
    assert mixed[0].details["flight_ids"] == [FLIGHT_1, FLIGHT_2]
    assert result.summary.mixed_flight_buses == 1


# --- Chặng nội thành: điểm đón ---


def test_bus_with_fixed_pickup_rejects_other_pickup_points():
    people = [
        *riders(1, 5, start=100, pickup=PICKUP_B),
        *riders(2, 5, start=200, pickup=None),
    ]
    result = run(people, [bus(1, pickup=PICKUP_A)])

    spots = placement(result)
    # Người không chọn điểm đón lên xe nào cũng được.
    assert set(spots) == set(range(200, 205))
    no_bus = result.flags_of(FLAG_NO_BUS_CAPACITY)
    assert {flag.registration_id for flag in no_bus} == set(range(100, 105))
    assert "không có xe nào đi đúng điểm đón" in no_bus[0].message


def test_city_leg_prefers_bus_linked_to_rider_flight():
    """Ưu tiên (1) cùng chuyến bay đứng trên (2) cùng team."""
    people = [
        *riders(1, 5, start=100, flight=FLIGHT_1),
        *riders(1, 5, start=200, flight=FLIGHT_2),
    ]
    result = run(people, [bus(1, pickup=PICKUP_A, flight=FLIGHT_1), bus(2, pickup=PICKUP_A, flight=FLIGHT_2)])

    spots = placement(result)
    assert {spots[i] for i in range(100, 105)} == {1}
    assert {spots[i] for i in range(200, 205)} == {2}
    assert result.flags_of(FLAG_MIXED_FLIGHT_ON_BUS) == []


# --- Sức chứa ---


def test_shortage_flags_exact_overflow_and_respects_capacity():
    people = riders(1, 50, start=100)
    result = run(people, [bus(1, 45, pickup=PICKUP_A)])

    assert per_bus(result) == {1: 45}
    full = result.flags_of(FLAG_NO_BUS_CAPACITY)
    assert len(full) == 5
    assert full[0].details["reason"] == "full"
    assert result.summary.assigned + result.summary.unassigned == 50


def test_teams_are_kept_whole_when_buses_fit():
    people = [*riders(1, 20, start=100), *riders(2, 20, start=200)]
    result = run(people, [bus(1, 25, pickup=PICKUP_A), bus(2, 25, pickup=PICKUP_A)])

    spots = placement(result)
    assert len({spots[i] for i in range(100, 120)}) == 1
    assert len({spots[i] for i in range(200, 220)}) == 1
    assert spots[100] != spots[200]


def test_team_larger_than_any_bus_is_split_without_overflow():
    people = riders(1, 60, start=100)
    result = run(people, [bus(1, 45, pickup=PICKUP_A), bus(2, 45, pickup=PICKUP_A)])

    assert result.summary.unassigned == 0
    counts = per_bus(result)
    assert sum(counts.values()) == 60
    assert all(count <= 45 for count in counts.values())


# --- Tối ưu công suất ---


def test_consolidates_into_fewest_buses_and_reports_surplus():
    people = [*riders(1, 10, start=100), *riders(2, 10, start=200), *riders(3, 10, start=300)]
    buses = [bus(1, pickup=PICKUP_A), bus(2, pickup=PICKUP_A), bus(3, pickup=PICKUP_A)]

    result = run(people, buses)

    assert per_bus(result) == {1: 30}
    assert result.summary.buses_used == 1
    assert result.summary.surplus_buses == 2
    surplus = [flag for flag in result.flags_of(FLAG_SURPLUS_BUS) if "bus_id" in flag.details]
    assert {flag.details["bus_id"] for flag in surplus} == {2, 3}


def test_underutilized_bus_is_warned():
    result = run(riders(1, 10, start=100), [bus(1, 45, pickup=PICKUP_A)])

    under = result.flags_of(FLAG_BUS_UNDERUTILIZED)
    assert len(under) == 1
    assert under[0].severity == "warning"


def test_surplus_hint_when_people_fit_in_one_less_bus():
    """Hai xe bắt buộc dùng vì khác điểm đón -> không có gợi ý bớt xe mức chặng."""
    people = [*riders(1, 10, start=100, pickup=PICKUP_A), *riders(2, 10, start=200, pickup=PICKUP_B)]
    result = run(people, [bus(1, pickup=PICKUP_A), bus(2, pickup=PICKUP_B)])

    hints = [flag for flag in result.flags_of(FLAG_SURPLUS_BUS) if "used_buses" in flag.details]
    # 20 người trên 2 xe 45 chỗ -> về sức chứa bớt được 1 xe (kèm lời nhắc kiểm điểm đón).
    assert len(hints) == 1
    assert "Kiểm tra điểm đón" in hints[0].message


# --- Xếp tay ---


def test_pinned_rider_stays_on_manual_bus():
    pinned = BusRider(
        registration_id=1,
        full_name="Người BTC xếp tay",
        team_id=1,
        team_name="Team 1",
        pickup_point_id=PICKUP_A,
        flight_id=FLIGHT_1,
        pinned_bus_id=2,
    )
    people = [pinned, *riders(1, 5, start=100)]
    result = run(people, [bus(1, pickup=PICKUP_A), bus(2, pickup=PICKUP_A)])

    assert placement(result)[1] == 2
    assert next(seat for seat in result.assignments if seat.registration_id == 1).pinned is True


# --- Tính tái lập ---


def test_input_order_does_not_change_result():
    people = [
        *riders(1, 17, start=100),
        *riders(2, 9, start=200, pickup=PICKUP_B),
        *riders(3, 12, start=300, flight=FLIGHT_2),
    ]
    buses = [bus(1, 30, pickup=PICKUP_A), bus(2, 30, pickup=PICKUP_B), bus(3, 30)]

    straight = run(people, buses)
    shuffled = run(list(reversed(people)), list(reversed(buses)))

    assert placement(straight) == placement(shuffled)
    assert straight.summary == shuffled.summary


# --- Property test: ràng buộc cứng không bao giờ bị vi phạm ---


def test_property_hard_constraints_hold_on_random_inputs():
    rng = random.Random(2026)

    for case in range(300):
        airport_linked = rng.random() < 0.5
        buses = [
            bus(
                index + 1,
                rng.randint(1, 50),
                pickup=rng.choice([None, PICKUP_A, PICKUP_B]),
                flight=rng.choice([None, FLIGHT_1, FLIGHT_2]),
            )
            for index in range(rng.randint(0, 5))
        ]

        people = []
        next_id = 1
        for team_id in range(1, rng.randint(2, 7)):
            size = rng.randint(1, 30)
            people.extend(
                riders(
                    rng.choice([team_id, None]),
                    size,
                    start=next_id,
                    pickup=rng.choice([None, PICKUP_A, PICKUP_B]),
                    flight=rng.choice([None, FLIGHT_1, FLIGHT_2]),
                )
            )
            next_id += size

        result = run(people, buses, airport_linked=airport_linked)
        slots = {slot.bus_id: slot for slot in buses}
        by_id = {rider.registration_id: rider for rider in people}

        # Sức chứa.
        for bus_id, count in per_bus(result).items():
            assert count <= slots[bus_id].capacity, f"case {case}: {bus_id} vượt sức chứa"

        # Mỗi người tối đa một ghế, và tổng khớp summary.
        seats = [seat.registration_id for seat in result.assignments]
        assert len(seats) == len(set(seats)), f"case {case}: có người ngồi hai xe"
        assert result.summary.assigned + result.summary.unassigned == len(people)

        # Điểm đón và chuyến bay.
        for seat in result.assignments:
            rider = by_id[seat.registration_id]
            slot = slots[seat.bus_id]
            if slot.pickup_point_id is not None and rider.pickup_point_id is not None:
                assert slot.pickup_point_id == rider.pickup_point_id, f"case {case}: sai điểm đón"
            if airport_linked:
                assert rider.flight_id is not None, f"case {case}: xếp người chưa có chuyến bay"
                if slot.linked_flight_id is not None:
                    assert slot.linked_flight_id == rider.flight_id, f"case {case}: sai chuyến bay"
