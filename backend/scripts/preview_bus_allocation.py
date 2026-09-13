"""Chạy thử phân xe trên dữ liệu thật và in kết quả. KHÔNG ghi gì vào DB.

    py -3.13 scripts/preview_bus_allocation.py                    # mọi chặng
    py -3.13 scripts/preview_bus_allocation.py --leg CITY_TO_AIRPORT
    py -3.13 scripts/preview_bus_allocation.py --simulate-flights never

Chặng gắn sân bay cần biết mỗi người bay chuyến nào. Nếu DB chưa có kết quả phân bổ chuyến
bay cho chiều đó, script chạy thuật toán phân bổ bay TRONG BỘ NHỚ để có số liệu xem trước
(mặc định `--simulate-flights auto`). Kết quả giả lập này cũng không ghi vào DB.
"""

import argparse
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select  # noqa: E402

from app.core.database import session_scope  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.flight import FlightAssignment  # noqa: E402
from app.models.registration import Registration  # noqa: E402
from app.models.transportation import TripLeg  # noqa: E402
from app.services.allocator import (  # noqa: E402
    allocate_flights,
    load_flight_slots,
    load_params,
    load_participants,
)
from app.services.allocator.bus_loader import load_bus_riders, load_bus_slots  # noqa: E402
from app.services.allocator.buses import allocate_buses  # noqa: E402

SEVERITY_MARK = {"error": "[LỖI]  ", "warning": "[CẢNH] ", "info": "[TIN]  "}


def main() -> int:
    parser = argparse.ArgumentParser(description="Xem trước kết quả phân xe")
    parser.add_argument("--leg", help="Mã chặng, ví dụ CITY_TO_AIRPORT. Bỏ trống = mọi chặng")
    parser.add_argument("--flags", type=int, default=4, help="Số flag in ra mỗi loại")
    parser.add_argument(
        "--simulate-flights",
        choices=["auto", "always", "never"],
        default="auto",
        help="auto = giả lập phân bổ bay khi DB chưa có kết quả cho chiều đó",
    )
    args = parser.parse_args()

    reports = []
    with session_scope() as db:
        event = db.scalar(select(Event).where(Event.is_active.is_(True)))
        if event is None:
            print("Chưa có kỳ Team Building nào đang mở.")
            return 1
        # Copy ra biến thường ngay trong session (CLAUDE.md cạm bẫy #10).
        event_id, event_label = event.id, f"{event.code} — {event.name}"

        query = select(TripLeg).where(TripLeg.event_id == event_id).order_by(TripLeg.display_order)
        if args.leg:
            query = query.where(TripLeg.code == args.leg)
        legs = db.scalars(query).all()
        if not legs:
            print(f"Không có chặng nào khớp '{args.leg}'.")
            return 1

        simulated_cache: dict[str, dict[int, int]] = {}
        for leg in legs:
            riders = load_bus_riders(db, event_id=event_id, trip_leg=leg)
            note = "chuyến bay lấy từ DB"

            if leg.is_airport_linked and _should_simulate(db, event_id, leg.direction, args.simulate_flights):
                if leg.direction not in simulated_cache:
                    simulated_cache[leg.direction] = _simulate_flights(db, event_id, leg.direction)
                simulated = simulated_cache[leg.direction]
                riders = [
                    replace(rider, flight_id=simulated.get(rider.registration_id))
                    for rider in riders
                ]
                note = "chuyến bay GIẢ LẬP trong bộ nhớ (DB chưa có phân bổ bay chiều này)"

            buses = load_bus_slots(db, event_id=event_id, trip_leg_id=leg.id)
            started = perf_counter()
            result = allocate_buses(
                riders=riders,
                buses=buses,
                trip_leg_id=leg.id,
                airport_linked=leg.is_airport_linked,
            )
            reports.append(
                {
                    "code": leg.code,
                    "name": leg.name,
                    "airport_linked": leg.is_airport_linked,
                    "note": note,
                    "elapsed_ms": (perf_counter() - started) * 1000,
                    "result": result,
                }
            )

    print(f"\n{event_label}")
    for report in reports:
        _print_report(report, args.flags)
    return 0


def _should_simulate(db, event_id: int, direction: str, mode: str) -> bool:
    if mode == "never":
        return False
    if mode == "always":
        return True
    existing = db.scalar(
        select(func.count())
        .select_from(FlightAssignment)
        .join(Registration, Registration.id == FlightAssignment.registration_id)
        .where(Registration.event_id == event_id, FlightAssignment.direction == direction)
    )
    return not existing


def _simulate_flights(db, event_id: int, direction: str) -> dict[int, int]:
    result = allocate_flights(
        participants=load_participants(db, event_id=event_id, direction=direction),
        flights=load_flight_slots(db, event_id=event_id, direction=direction),
        direction=direction,
        params=load_params(db, event_id=event_id),
    )
    return {seat.registration_id: seat.flight_id for seat in result.assignments}


def _print_report(report: dict, flag_limit: int) -> None:
    result = report["result"]
    summary = result.summary

    print("\n" + "=" * 78)
    kind = "gắn sân bay" if report["airport_linked"] else "nội thành"
    print(f"{report['code']} — {report['name']}  ({kind}, {report['elapsed_ms']:.1f} ms)")
    print(f"  {report['note']}")
    print(
        f"  Cần xe {summary.total_riders} · có ghế {summary.assigned} · chưa có {summary.unassigned}"
        f" · xe dùng {summary.buses_used}/{summary.buses_total} · lấp ghế {summary.utilization * 100:.0f}%"
    )
    print("=" * 78)

    for load in result.buses:
        teams = ", ".join(f"{team.team_name} ({team.count})" for team in load.teams[:4]) or "—"
        print(f"  {load.bus_code:6} {load.assigned:>3}/{load.capacity:<3} {teams}")

    counts = Counter(flag.type for flag in result.flags)
    if not counts:
        print("  Không có cảnh báo nào.")
        return

    print("  Flag: " + " · ".join(f"{name} {count}" for name, count in counts.most_common()))
    for flag_type in counts:
        flags = result.flags_of(flag_type)
        for flag in flags[:flag_limit]:
            print(f"  {SEVERITY_MARK.get(flag.severity, '')}{flag.message}")
        if len(flags) > flag_limit:
            print(f"         … và {len(flags) - flag_limit} dòng {flag_type} nữa")


if __name__ == "__main__":
    raise SystemExit(main())
