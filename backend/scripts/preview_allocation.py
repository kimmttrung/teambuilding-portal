"""Chạy thử phân bổ chuyến bay trên dữ liệu thật và in kết quả. KHÔNG ghi gì vào DB.

Dùng để BTC (và người làm) xem thuật toán quyết định thế nào trước khi có API ở bước 13:

    py -3.13 scripts/preview_allocation.py
    py -3.13 scripts/preview_allocation.py --direction return
    py -3.13 scripts/preview_allocation.py --shift-weight 30 --team-weight 1
    py -3.13 scripts/preview_allocation.py --seed 42 --flags 20
"""

import argparse
import sys
from collections import Counter
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.database import session_scope  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.flight import Shift  # noqa: E402
from app.services.allocator import (  # noqa: E402
    DEFAULT_SEED,
    AllocationParams,
    allocate_flights,
    load_flight_slots,
    load_params,
    load_participants,
)

SEVERITY_MARK = {"error": "[LỖI]  ", "warning": "[CẢNH] ", "info": "[TIN]  "}


def main() -> int:
    parser = argparse.ArgumentParser(description="Xem trước kết quả phân bổ chuyến bay")
    parser.add_argument("--direction", default="outbound", choices=["outbound", "return"])
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--flags", type=int, default=10, help="Số flag in ra mỗi loại")
    parser.add_argument("--team-weight", type=int, help="Ghi đè allocation.team_weight")
    parser.add_argument("--shift-weight", type=int, help="Ghi đè allocation.shift_weight")
    parser.add_argument("--split-penalty", type=int, help="Ghi đè allocation.split_penalty")
    args = parser.parse_args()

    with session_scope() as db:
        event = db.scalar(select(Event).where(Event.is_active.is_(True)))
        if event is None:
            print("Chưa có kỳ Team Building nào đang mở.")
            return 1

        # Lấy ra chuỗi thường NGAY trong session: ra khỏi `with` là session đóng và mọi
        # thuộc tính ORM chưa nạp sẽ ném DetachedInstanceError.
        event_label = f"{event.code} — {event.name}"

        params = _override(load_params(db, event_id=event.id), args)
        participants = load_participants(db, event_id=event.id, direction=args.direction)
        flights = load_flight_slots(db, event_id=event.id, direction=args.direction)
        shift_names = {
            shift.id: shift.code
            for shift in db.scalars(select(Shift).where(Shift.event_id == event.id))
        }

        started = perf_counter()
        result = allocate_flights(
            participants=participants,
            flights=flights,
            direction=args.direction,
            params=params,
            seed=args.seed,
        )
        elapsed_ms = (perf_counter() - started) * 1000

    _print_report(event_label, args, result, params, shift_names, elapsed_ms, len(participants))
    return 0


def _override(params: AllocationParams, args) -> AllocationParams:
    overrides = {
        name: value
        for name, value in (
            ("team_weight", args.team_weight),
            ("shift_weight", args.shift_weight),
            ("split_penalty", args.split_penalty),
        )
        if value is not None
    }
    return AllocationParams(**{**params.as_dict(), **overrides}) if overrides else params


def _print_report(event_label, args, result, params, shift_names, elapsed_ms, total) -> None:
    summary = result.summary

    print(f"\n{event_label}")
    print(f"Chiều: {args.direction} · seed: {result.seed} · chạy trong {elapsed_ms:.1f} ms")
    print(
        "Trọng số: team={team_weight} shift={shift_weight} split={split_penalty} "
        "max_split={max_split_per_team} min_chunk={min_chunk_size}".format(**params.as_dict())
    )

    print("\n" + "=" * 78)
    print(
        f"Tham gia {total} · xếp được {summary.assigned} · không có chỗ {summary.unassigned} "
        f"· team bị tách {summary.teams_split} "
        f"· đúng ca {summary.shift_satisfaction_rate * 100:.1f}% · điểm {summary.score}"
    )
    print("=" * 78)

    print(f"\n{'Chuyến':9} {'Ca':5} {'Ghế':>4} {'Dùng':>5} {'Xếp':>4} {'Còn':>4}  Team trên chuyến")
    for load in result.flights:
        teams = ", ".join(f"{t.team_name} ({t.count})" for t in load.teams) or "—"
        print(
            f"{load.flight_code:9} {shift_names.get(load.shift_id, '—'):5} {load.capacity:>4} "
            f"{load.usable_capacity:>5} {load.assigned:>4} {load.remaining:>4}  {teams}"
        )

    counts = Counter(flag.type for flag in result.flags)
    if not counts:
        print("\nKhông có cảnh báo nào.")
        return

    print("\nFlag:")
    for flag_type, count in counts.most_common():
        print(f"  {flag_type:24} {count}")

    print()
    for flag_type in counts:
        flags = result.flags_of(flag_type)
        for flag in flags[: args.flags]:
            print(f"{SEVERITY_MARK.get(flag.severity, '')}{flag.message}")
        if len(flags) > args.flags:
            print(f"       … và {len(flags) - args.flags} dòng {flag_type} nữa")


if __name__ == "__main__":
    raise SystemExit(main())
