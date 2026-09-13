"""Schema cho xe, Trưởng xe, phân xe và điều chỉnh (docs/04-api-spec.md §7)."""

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.timeutils import from_iso
from app.models.enums import AssignmentMode, FlightDirection
from app.schemas.flight_allocation import FlagOut, TeamLoadOut

BUS_CODE_PATTERN = r"^[A-Z0-9_-]{1,32}$"
PHONE_MAX = 32


def _check_iso(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        from_iso(value)
    except ValueError as exc:
        raise ValueError(
            "Thời gian phải là ISO-8601, ví dụ 2026-10-15T04:30:00+00:00 (giờ UTC)."
        ) from exc
    return value


class BusIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trip_leg_id: int
    bus_code: str = Field(pattern=BUS_CODE_PATTERN)
    plate_number: str | None = Field(default=None, max_length=32)
    capacity: int = Field(ge=1, le=100)

    pickup_point_id: int | None = None
    dropoff_point: str | None = Field(default=None, max_length=255)
    gather_time: str | None = None
    departure_time: str | None = None

    leader_user_id: int | None = None
    leader_name: str | None = Field(default=None, max_length=255)
    leader_phone: str | None = Field(default=None, max_length=PHONE_MAX)
    driver_name: str | None = Field(default=None, max_length=255)
    driver_phone: str | None = Field(default=None, max_length=PHONE_MAX)

    linked_flight_id: int | None = None
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("gather_time", "departure_time")
    @classmethod
    def _validate_times(cls, value: str | None) -> str | None:
        return _check_iso(value)

    @model_validator(mode="after")
    def _gather_before_departure(self) -> "BusIn":
        if self.gather_time and self.departure_time:
            if from_iso(self.departure_time) < from_iso(self.gather_time):
                raise ValueError("Giờ xe chạy không thể trước giờ tập trung.")
        return self


class BusUpdate(BaseModel):
    """Sửa xe. Cố ý KHÔNG cho đổi `trip_leg_id`: chuyển một xe đang chở người sang chặng
    khác thì mọi phân xe của nó thành vô nghĩa — tạo xe mới cho chặng kia thay vì sửa."""

    model_config = ConfigDict(extra="forbid")

    bus_code: str | None = Field(default=None, pattern=BUS_CODE_PATTERN)
    plate_number: str | None = Field(default=None, max_length=32)
    capacity: int | None = Field(default=None, ge=1, le=100)

    pickup_point_id: int | None = None
    dropoff_point: str | None = Field(default=None, max_length=255)
    gather_time: str | None = None
    departure_time: str | None = None

    driver_name: str | None = Field(default=None, max_length=255)
    driver_phone: str | None = Field(default=None, max_length=PHONE_MAX)

    linked_flight_id: int | None = None
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("gather_time", "departure_time")
    @classmethod
    def _validate_times(cls, value: str | None) -> str | None:
        return _check_iso(value)


class LeaderUpdate(BaseModel):
    """Gán Trưởng xe: một CBNV (`leader_user_id`) hoặc người ngoài (tên + số điện thoại).

    Gửi tất cả rỗng để bỏ Trưởng xe.
    """

    model_config = ConfigDict(extra="forbid")

    leader_user_id: int | None = None
    leader_name: str | None = Field(default=None, max_length=255)
    leader_phone: str | None = Field(default=None, max_length=PHONE_MAX)

    @model_validator(mode="after")
    def _one_kind_of_leader(self) -> "LeaderUpdate":
        if self.leader_user_id is not None and (self.leader_name or self.leader_phone):
            raise ValueError(
                "Chọn một trong hai: Trưởng xe là CBNV (leader_user_id) hoặc người ngoài "
                "(leader_name + leader_phone)."
            )
        if self.leader_user_id is None and bool(self.leader_name) != bool(self.leader_phone):
            raise ValueError("Trưởng xe là người ngoài thì cần cả tên và số điện thoại.")
        return self


class BusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    trip_leg_id: int
    trip_leg_code: str = ""
    trip_leg_name: str = ""
    direction: FlightDirection | None = None
    airport_linked: bool = False

    bus_code: str
    plate_number: str | None = None
    capacity: int
    assigned_count: int = 0
    remaining_seats: int = 0
    load_ratio: float = 0.0

    pickup_point_id: int | None = None
    pickup_point_name: str | None = None
    dropoff_point: str | None = None
    gather_time: str | None = None
    departure_time: str | None = None

    leader_user_id: int | None = None
    leader_name: str | None = None
    leader_phone: str | None = None
    driver_name: str | None = None
    driver_phone: str | None = None

    linked_flight_id: int | None = None
    linked_flight_code: str | None = None
    note: str | None = None
    created_at: str
    updated_at: str


class BusPassengerOut(BaseModel):
    """Hành khách một xe — dành cho BTC và Trưởng xe của CHÍNH xe đó.

    Có số điện thoại: việc của Trưởng xe là điểm danh và gọi người đến muộn. Endpoint đã
    giới hạn đúng người được xem, nên không phơi số điện thoại ra rộng hơn cần thiết.
    Không có CCCD, ngày sinh.
    """

    assignment_id: int
    registration_id: int
    user_id: int
    full_name: str
    employee_code: str | None = None
    phone: str | None = None
    team_id: int | None = None
    team_name: str | None = None
    pickup_point_id: int | None = None
    pickup_point_name: str | None = None
    flight_code: str | None = None
    assignment_mode: AssignmentMode


class BusAllocateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trip_leg_id: int
    dry_run: bool = True
    force_reallocate: bool = False


class BusLoadOut(BaseModel):
    bus_id: int
    bus_code: str
    capacity: int
    assigned: int
    remaining: int
    pickup_point_id: int | None = None
    linked_flight_id: int | None = None
    flight_ids: list[int] = Field(default_factory=list)
    teams: list[TeamLoadOut] = Field(default_factory=list)


class BusAllocationSummaryOut(BaseModel):
    total_riders: int
    assigned: int
    unassigned: int
    buses_total: int
    buses_used: int
    surplus_buses: int
    mixed_flight_buses: int
    utilization: float


class BusAllocationResponse(BaseModel):
    trip_leg_id: int
    trip_leg_code: str
    airport_linked: bool
    dry_run: bool
    committed: bool = False
    summary: BusAllocationSummaryOut
    buses: list[BusLoadOut]
    flags: list[FlagOut]
    # Bản ghi rác đã dọn khi ghi: người không còn cần xe / đã huỷ tham gia.
    removed_stale: int = 0


class BusAssignRequest(BaseModel):
    """Xếp tay một người chưa có xe ở chặng của xe này. Lý do bắt buộc để ghi audit log."""

    model_config = ConfigDict(extra="forbid")

    registration_id: int
    bus_id: int
    reason: str = Field(min_length=3, max_length=500)


class BusAssignmentOut(BaseModel):
    id: int
    registration_id: int
    user_id: int
    full_name: str
    # Màn hình BTC gọi người đến muộn ngay từ danh sách xe. Endpoint chỉ dành cho BTC.
    employee_code: str | None = None
    phone: str | None = None
    team_id: int | None = None
    team_name: str | None = None
    bus_id: int
    bus_code: str
    trip_leg_id: int
    pickup_point_id: int | None = None
    pickup_point_name: str | None = None
    flight_code: str | None = None
    # true = xe đón điểm khác / chờ chuyến bay khác so với người này.
    pickup_mismatch: bool = False
    flight_mismatch: bool = False
    assignment_mode: AssignmentMode
    assigned_at: str


class BusMoveRequest(BaseModel):
    """Chuyển một người sang xe khác cùng chặng. Lý do bắt buộc để ghi audit log."""

    model_config = ConfigDict(extra="forbid")

    bus_id: int
    reason: str = Field(min_length=3, max_length=500)


class BusMoveResponse(BaseModel):
    assignment: BusAssignmentOut
    warnings: list[FlagOut] = Field(default_factory=list)
