"""Kiểu dữ liệu vào/ra của thuật toán xếp phòng (`rooms.py`).

Cùng khuôn flight/bus: dataclass thuần, không ORM, để test chạy không cần database.
"""

from dataclasses import dataclass, field

from app.services.allocator.types import Flag

# --- Loại flag (docs/05-allocation-algorithm.md §7) ---

FLAG_NO_ROOM_CAPACITY = "NO_ROOM_CAPACITY"
FLAG_MISSING_GENDER = "MISSING_GENDER"
FLAG_PINNED_ROOM_CONFLICT = "PINNED_ROOM_CONFLICT"
FLAG_ALONE_FROM_TEAM = "ALONE_FROM_TEAM"
FLAG_HEALTH_NOTE = "HEALTH_NOTE"
FLAG_EMPTY_ROOM = "EMPTY_ROOM"

POLICY_ANY = "any"
GENDER_UNKNOWN = "unknown"


@dataclass(frozen=True)
class RoomGuest:
    """Một người tham gia cần phòng."""

    registration_id: int
    full_name: str
    # 'male' | 'female' | giá trị khác/None = chưa khai nam/nữ.
    gender: str | None
    team_id: int | None
    team_name: str
    department_id: int | None = None
    # Chuyến bay chiều đi: người đến cùng chuyến nhận phòng cùng lúc.
    flight_id: int | None = None
    flight_code: str | None = None
    is_team_leader: bool = False
    # Chỉ CÓ/KHÔNG — nội dung ghi chú sức khoẻ không bao giờ vào thuật toán.
    has_health_note: bool = False
    # BTC đã xếp tay: giữ nguyên (docs/05 §5).
    pinned_room_id: int | None = None
    pinned_captain: bool = False

    @property
    def gender_class(self) -> str:
        return self.gender if self.gender in ("male", "female") else GENDER_UNKNOWN


@dataclass(frozen=True)
class RoomSlot:
    room_id: int
    room_number: str
    hotel_id: int
    hotel_name: str
    capacity: int
    # 'male' | 'female' | 'any'
    gender_policy: str
    floor: str | None = None


@dataclass(frozen=True)
class RoomBed:
    registration_id: int
    room_id: int
    is_room_captain: bool = False
    pinned: bool = False


@dataclass(frozen=True)
class RoomGuestLoad:
    registration_id: int
    full_name: str
    team_id: int | None
    team_name: str
    gender: str | None
    flight_code: str | None = None
    pinned: bool = False
    is_room_captain: bool = False


@dataclass(frozen=True)
class RoomLoad:
    room_id: int
    room_number: str
    hotel_id: int
    hotel_name: str
    floor: str | None
    capacity: int
    gender_policy: str
    assigned: int
    remaining: int
    guests: list[RoomGuestLoad] = field(default_factory=list)


@dataclass(frozen=True)
class RoomAllocationSummary:
    total_guests: int
    assigned: int
    unassigned: int
    rooms_total: int
    rooms_used: int
    # Giường còn trống trong các phòng ĐÃ dùng (phòng trống hẳn không tính).
    empty_beds: int
    # Trong số người mà team có từ 2 người cùng giới được xếp: tỉ lệ ở chung với ít nhất một
    # đồng đội. Không có ai để so thì 1.0 (không có gì bị vi phạm).
    same_team_rate: float
    same_flight_rate: float
    mixed_team_rooms: int
    # Điểm hàm mục tiêu, chỉ để so sánh giữa các lần chạy.
    score: int


@dataclass(frozen=True)
class RoomAllocationResult:
    assignments: list[RoomBed]
    flags: list[Flag]
    summary: RoomAllocationSummary
    rooms: list[RoomLoad]
    unassigned: list[RoomGuestLoad]
    params: dict
