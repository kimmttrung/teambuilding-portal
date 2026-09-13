"""Chạy thử xếp phòng tự động trên dữ liệu thật và in kết quả. KHÔNG ghi gì vào DB.

    py -3.13 scripts/preview_room_allocation.py
    py -3.13 scripts/preview_room_allocation.py --force      # bỏ qua người BTC đã xếp tay
    py -3.13 scripts/preview_room_allocation.py --rooms      # in từng phòng
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
from app.services.allocator.room_loader import (  # noqa: E402
    load_room_guests,
    load_room_params,
    load_room_slots,
)
from app.services.allocator.rooms import allocate_rooms  # noqa: E402

SEVERITY_MARK = {"error": "[LỖI]  ", "warning": "[CẢNH] ", "info": "[TIN]  "}
POLICY = {"male": "Nam", "female": "Nữ", "any": "Tự do"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Xem trước kết quả xếp phòng tự động")
    parser.add_argument("--force", action="store_true", help="Xếp lại cả người BTC đã xếp tay")
    parser.add_argument("--rooms", action="store_true", help="In danh sách từng phòng")
    parser.add_argument("--flags", type=int, default=4, help="Số flag in ra mỗi loại")
    args = parser.parse_args()

    with session_scope() as db:
        event = db.scalar(select(Event).where(Event.is_active.is_(True)))
        if event is None:
            print("Chưa có kỳ Team Building nào đang mở.")
            return 1
        # Copy ra biến thường ngay trong session (CLAUDE.md cạm bẫy #10).
        label = f"{event.code} — {event.name}"
        guests = load_room_guests(db, event_id=event.id, keep_manual=not args.force)
        rooms = load_room_slots(db, event_id=event.id)
        params = load_room_params(db, event_id=event.id)

    started = perf_counter()
    result = allocate_rooms(guests=guests, rooms=rooms, params=params)
    elapsed_ms = (perf_counter() - started) * 1000

    summary = result.summary
    genders = Counter(guest.gender_class for guest in guests)
    print(f"Kỳ: {label}")
    print(f"Người cần phòng: {summary.total_guests} (nam {genders['male']}, nữ {genders['female']}, chưa khai {genders['unknown']})")
    print(f"Có phòng: {summary.assigned} · Chưa có phòng: {summary.unassigned}")
    print(f"Phòng dùng: {summary.rooms_used}/{summary.rooms_total} · giường trống trong phòng đã dùng: {summary.empty_beds}")
    print(f"Ở cùng đồng đội: {summary.same_team_rate:.1%} · cùng chuyến bay: {summary.same_flight_rate:.1%}")
    print(f"Phòng lẫn team: {summary.mixed_team_rooms} · điểm: {summary.score} · thời gian: {elapsed_ms:.1f} ms")

    by_type: dict[str, list] = {}
    for flag in result.flags:
        by_type.setdefault(flag.type, []).append(flag)
    for flag_type, flags in by_type.items():
        print(f"\n{flag_type} ({len(flags)})")
        for flag in flags[: args.flags]:
            print(f"  {SEVERITY_MARK.get(flag.severity, '')}{flag.message}")

    if args.rooms:
        print()
        for load in result.rooms:
            names = ", ".join(
                f"{guest.full_name}{'*' if guest.is_room_captain else ''} ({guest.team_name})"
                for guest in load.guests
            )
            print(f"  {load.hotel_name} · {load.room_number:>6} · {POLICY.get(load.gender_policy, load.gender_policy):>5} · {load.assigned}/{load.capacity} · {names or '—'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
