"""Thuật toán phân bổ (docs/05-allocation-algorithm.md).

`flights.py` là thuật toán thuần (không DB), `loader.py` đọc DB thành đầu vào cho nó.
Phân xe (`buses.py`, bước 15) và xếp phòng (`rooms.py`, bước 18d) cùng khuôn, mỗi thuật toán
có loader riêng (`bus_loader.py`, `room_loader.py`).
"""

from app.services.allocator.flights import allocate_flights
from app.services.allocator.loader import load_flight_slots, load_params, load_participants
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

__all__ = [
    "AllocationParams",
    "AllocationResult",
    "AllocationSummary",
    "Assignment",
    "DEFAULT_SEED",
    "FLAG_MISSING_ID_CARD",
    "FLAG_SHIFT_LOCKED_VIOLATION",
    "FLAG_SHIFT_NOT_SATISFIED",
    "FLAG_TEAM_SPLIT",
    "FLAG_TEAM_SPLIT_EXCEEDED",
    "FLAG_TINY_CHUNK",
    "FLAG_UNASSIGNED",
    "Flag",
    "FlightLoad",
    "FlightSlot",
    "Participant",
    "SEVERITY_ERROR",
    "SEVERITY_INFO",
    "SEVERITY_WARNING",
    "TeamLoad",
    "allocate_flights",
    "load_flight_slots",
    "load_params",
    "load_participants",
]
