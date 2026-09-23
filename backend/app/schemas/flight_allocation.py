"""Schema cho phân bổ chuyến bay và điều chỉnh thủ công (docs/04-api-spec.md §5)."""

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AssignmentMode, FlightDirection


class ResetRequest(BaseModel):
    """Bỏ toàn bộ phân bổ của một chiều để chỉnh lại số ghế rồi chạy lại."""

    model_config = ConfigDict(extra="forbid")

    direction: FlightDirection
    # Lý do bắt buộc: thao tác này xoá chỗ của cả đoàn, audit log phải trả lời được "vì sao".
    reason: str = Field(min_length=3, max_length=500)
    # Xoá luôn người BTC đã gán tay. Mặc định giữ, như `force_reallocate` của phân bổ.
    include_manual: bool = False


class ResetResult(BaseModel):
    removed: int
    kept_manual: int


class AllocateRequest(BaseModel):
    """Yêu cầu chạy phân bổ.

    `dry_run=true` (mặc định) chỉ tính và trả preview, không ghi gì — BTC phải xem được
    kết quả trước khi nó thành sự thật với 99 người.
    """

    model_config = ConfigDict(extra="forbid")

    direction: FlightDirection
    dry_run: bool = True
    # Cho phép xếp lại cả những người BTC đã gán tay. Mặc định KHÔNG (docs/05 §5).
    force_reallocate: bool = False
    # Cùng seed thì cùng kết quả; để trống dùng seed mặc định.
    seed: int | None = None


class FlagOut(BaseModel):
    type: str
    severity: str
    message: str
    registration_id: int | None = None
    team_id: int | None = None
    flight_id: int | None = None
    details: dict = Field(default_factory=dict)


class TeamLoadOut(BaseModel):
    team_id: int | None = None
    team_name: str
    count: int


class AllocationFlightOut(BaseModel):
    flight_id: int
    flight_code: str
    shift_id: int | None = None
    capacity: int
    reserved: int
    usable_capacity: int
    assigned: int
    remaining: int
    teams: list[TeamLoadOut] = Field(default_factory=list)


class AllocationSummaryOut(BaseModel):
    total_participants: int
    assigned: int
    unassigned: int
    teams_split: int
    shift_satisfaction_rate: float
    score: int


class AllocationResponse(BaseModel):
    direction: FlightDirection
    dry_run: bool
    # true = đã ghi vào flight_assignments trong một transaction.
    committed: bool = False
    seed: int
    params: dict
    summary: AllocationSummaryOut
    flights: list[AllocationFlightOut]
    flags: list[FlagOut]
    # Số bản ghi rác đã dọn khi ghi: người đã huỷ đăng ký nhưng còn chiếm ghế.
    removed_stale: int = 0


class FlightAssignmentOut(BaseModel):
    """Một dòng phân bổ cho bảng điều chỉnh của BTC.

    Không có CCCD: bảng này hiển thị rộng. `has_flight_documents` đủ để BTC biết ai chưa
    xuất được vé.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    registration_id: int
    user_id: int
    full_name: str
    employee_code: str | None = None
    team_id: int | None = None
    team_name: str | None = None

    flight_id: int
    flight_code: str
    direction: FlightDirection
    flight_shift_id: int | None = None
    requested_shift_id: int | None = None
    requested_shift_code: str | None = None
    # true = đang bay lệch ca nguyện vọng. Frontend lọc theo cờ này.
    shift_mismatch: bool = False
    shift_locked: bool = False

    seat_number: str | None = None
    ticket_code: str | None = None
    assignment_mode: AssignmentMode
    assigned_at: str
    assigned_by: int | None = None
    note: str | None = None
    has_flight_documents: bool = False


class MoveRequest(BaseModel):
    """Chuyển một người sang chuyến khác.

    `reason` bắt buộc: audit log không có lý do thì sau này không ai giải thích được
    vì sao một người bị đổi chuyến (docs/09-security.md §6).
    """

    model_config = ConfigDict(extra="forbid")

    flight_id: int
    reason: str = Field(min_length=3, max_length=500)


class BulkMoveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    registration_ids: list[int] = Field(min_length=1, max_length=500)
    flight_id: int
    reason: str = Field(min_length=3, max_length=500)


class MoveResponse(BaseModel):
    """Kết quả điều chỉnh: đã chuyển ai, và những cảnh báo không chặn."""

    moved: int
    created: int = 0
    assignments: list[FlightAssignmentOut]
    warnings: list[FlagOut] = Field(default_factory=list)
