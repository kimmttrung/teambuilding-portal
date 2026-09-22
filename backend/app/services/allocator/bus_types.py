"""Kiểu dữ liệu vào/ra của thuật toán phân xe (docs/05-allocation-algorithm.md §6).

Cùng khuôn với phân bổ chuyến bay: dataclass thuần, không ORM, để test chạy không cần DB.
Dùng lại `Flag`, `TeamLoad` và mức độ nghiêm trọng của `types.py` để frontend hiển thị
cảnh báo xe và cảnh báo chuyến bay bằng cùng một component.
"""

from dataclasses import dataclass, field

from app.services.allocator.types import SEVERITY_ERROR, Flag, TeamLoad

# --- Loại flag (docs/05 §6 bước 5) ---

FLAG_NO_BUS_CAPACITY = "NO_BUS_CAPACITY"
# Chặng gắn sân bay mà người này chưa có chuyến bay: không biết họ đi xe nào.
# Không có trong danh sách gốc ở docs/05 §6 — thêm vì gộp nó vào NO_BUS_CAPACITY sẽ
# khiến BTC đi mua thêm xe trong khi việc cần làm là phân bổ chuyến bay trước.
FLAG_MISSING_FLIGHT_ASSIGNMENT = "MISSING_FLIGHT_ASSIGNMENT"
FLAG_BUS_UNDERUTILIZED = "BUS_UNDERUTILIZED"
FLAG_MIXED_FLIGHT_ON_BUS = "MIXED_FLIGHT_ON_BUS"
FLAG_SURPLUS_BUS = "SURPLUS_BUS"


@dataclass(frozen=True)
class BusRider:
    """Một người cần xe ở một chặng."""

    registration_id: int
    full_name: str
    team_id: int | None
    team_name: str
    # Điểm đón người này chọn ở chặng này (chặng sân bay thường để trống).
    pickup_point_id: int | None = None
    # Chuyến bay của người này ở chiều tương ứng với chặng. None = chưa phân bổ bay.
    flight_id: int | None = None
    # BTC đã xếp tay: giữ nguyên, thuật toán không đụng vào.
    pinned_bus_id: int | None = None

    @property
    def team_key(self) -> tuple:
        """Người không có team đứng riêng — gộp họ thành một nhóm giả là vô nghĩa."""
        return ("team", self.team_id) if self.team_id else ("solo", self.registration_id)


@dataclass(frozen=True)
class BusSlot:
    bus_id: int
    bus_code: str
    capacity: int
    # Xe đón ở điểm cố định thì chỉ nhận người chọn điểm đó (hoặc người không chọn điểm).
    pickup_point_id: int | None = None
    # Xe phục vụ chuyến bay nào. Ở chặng sân bay đây là ràng buộc CỨNG.
    linked_flight_id: int | None = None
    # Chuyến bay mà giờ xe này không khớp (ra sân bay sau giờ cất cánh / đón trước giờ hạ cánh).
    incompatible_flight_ids: frozenset[int] = frozenset()


@dataclass(frozen=True)
class BusSeat:
    registration_id: int
    bus_id: int
    pinned: bool = False


@dataclass(frozen=True)
class BusLoad:
    bus_id: int
    bus_code: str
    capacity: int
    assigned: int
    remaining: int
    pickup_point_id: int | None = None
    linked_flight_id: int | None = None
    # Các chuyến bay có người trên xe — nhiều hơn một là dấu hiệu xe phải chờ nhiều giờ.
    flight_ids: list[int] = field(default_factory=list)
    teams: list[TeamLoad] = field(default_factory=list)


@dataclass(frozen=True)
class BusAllocationSummary:
    total_riders: int
    assigned: int
    unassigned: int
    buses_total: int
    buses_used: int
    surplus_buses: int
    mixed_flight_buses: int
    # Tỉ lệ lấp ghế của các xe CÓ dùng. Xe trống không kéo tỉ lệ xuống.
    utilization: float


@dataclass(frozen=True)
class BusAllocationResult:
    trip_leg_id: int
    airport_linked: bool
    assignments: list[BusSeat]
    flags: list[Flag]
    summary: BusAllocationSummary
    buses: list[BusLoad]

    @property
    def has_errors(self) -> bool:
        return any(flag.severity == SEVERITY_ERROR for flag in self.flags)

    def flags_of(self, flag_type: str) -> list[Flag]:
        return [flag for flag in self.flags if flag.type == flag_type]
