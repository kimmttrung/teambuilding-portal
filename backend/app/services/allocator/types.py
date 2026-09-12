"""Kiểu dữ liệu vào/ra của thuật toán phân bổ.

Thuật toán cố tình KHÔNG nhận ORM object: đầu vào là dataclass thuần (docs/05 §3).
Nhờ vậy nó chạy được trong unit test không cần database, và property test bơm được
hàng nghìn input ngẫu nhiên trong vài giây. Việc đọc/ghi DB nằm ở `loader.py` và
service của bước 13.
"""

from dataclasses import dataclass, field

# --- Loại flag (docs/05-allocation-algorithm.md §4) ---

FLAG_UNASSIGNED = "UNASSIGNED"
FLAG_TEAM_SPLIT = "TEAM_SPLIT"
FLAG_TEAM_SPLIT_EXCEEDED = "TEAM_SPLIT_EXCEEDED"
FLAG_SHIFT_NOT_SATISFIED = "SHIFT_NOT_SATISFIED"
FLAG_SHIFT_LOCKED_VIOLATION = "SHIFT_LOCKED_VIOLATION"
FLAG_TINY_CHUNK = "TINY_CHUNK"
FLAG_MISSING_ID_CARD = "MISSING_ID_CARD"

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"


@dataclass(frozen=True)
class Participant:
    """Một người cần xếp chỗ trên một chiều bay."""

    registration_id: int
    user_id: int
    full_name: str
    team_id: int | None
    team_name: str
    department_id: int | None = None
    # Nguyện vọng ca. None = không có nguyện vọng, xếp đâu cũng được.
    requested_shift_id: int | None = None
    # BTC ép cứng ca cho trường hợp đặc biệt -> ràng buộc CỨNG, không phải nguyện vọng.
    shift_locked: bool = False
    # Đã được BTC gán tay: auto allocation phải giữ nguyên (docs/05 §5).
    pinned_flight_id: int | None = None
    # Đủ CCCD + ngày sinh để xuất vé chưa. Không ảnh hưởng việc xếp chỗ, chỉ sinh flag.
    has_documents: bool = True
    # Dùng để giữ người cùng điểm đón cạnh nhau khi phải tách team.
    pickup_point_id: int | None = None

    @property
    def group_key(self) -> tuple:
        """Khoá nhóm khi xếp "nguyên team".

        Người không có team đứng riêng từng người: gộp họ thành một nhóm giả sẽ khiến
        thuật toán cố giữ những người chẳng liên quan gì nhau đi cùng chuyến.
        """
        return ("team", self.team_id) if self.team_id else ("solo", self.registration_id)


@dataclass(frozen=True)
class FlightSlot:
    """Một chuyến bay với số ghế dùng được."""

    flight_id: int
    flight_code: str
    shift_id: int | None
    capacity: int
    reserved: int = 0

    @property
    def usable(self) -> int:
        return max(self.capacity - self.reserved, 0)


@dataclass(frozen=True)
class Assignment:
    registration_id: int
    flight_id: int
    # True = giữ nguyên bản ghi thủ công của BTC, thuật toán không xếp lại.
    pinned: bool = False


@dataclass(frozen=True)
class Flag:
    type: str
    severity: str
    message: str
    registration_id: int | None = None
    team_id: int | None = None
    flight_id: int | None = None
    details: dict = field(default_factory=dict)


@dataclass(frozen=True)
class TeamLoad:
    team_id: int | None
    team_name: str
    count: int


@dataclass(frozen=True)
class FlightLoad:
    """Tình trạng một chuyến sau khi phân bổ — dùng cho preview của BTC."""

    flight_id: int
    flight_code: str
    shift_id: int | None
    capacity: int
    reserved: int
    usable_capacity: int
    assigned: int
    remaining: int
    teams: list[TeamLoad] = field(default_factory=list)


@dataclass(frozen=True)
class AllocationSummary:
    total_participants: int
    assigned: int
    unassigned: int
    teams_split: int
    shift_satisfaction_rate: float
    # Điểm hàm mục tiêu (docs/05 §2). Chỉ để so sánh giữa các lần chạy, không có đơn vị.
    score: int


@dataclass(frozen=True)
class AllocationResult:
    direction: str
    seed: int
    assignments: list[Assignment]
    flags: list[Flag]
    summary: AllocationSummary
    flights: list[FlightLoad]
    params: dict

    @property
    def has_errors(self) -> bool:
        return any(flag.severity == SEVERITY_ERROR for flag in self.flags)

    def flags_of(self, flag_type: str) -> list[Flag]:
        return [flag for flag in self.flags if flag.type == flag_type]
