"""Schema cho chuyến bay và tình trạng slot.

Slot trống KHÔNG lưu thành cột: luôn tính `capacity - reserved_slots - số đã gán`
(docs/03-data-model.md §5). Lưu sẵn một con số là mở đường cho dữ liệu lệch giữa
bảng phân bổ và bộ đếm — đúng loại lỗi làm BTC xếp quá số ghế đã mua.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.timeutils import from_iso
from app.models.enums import AssignmentMode, FlightDirection

AIRPORT_PATTERN = r"^[A-Z]{3}$"
FLIGHT_CODE_PATTERN = r"^[A-Z0-9]{2,16}$"


def _check_iso(value: str | None, label: str) -> str | None:
    if value is None:
        return None
    try:
        from_iso(value)
    except ValueError as exc:
        raise ValueError(
            f"{label} phải là thời điểm ISO-8601, ví dụ 2026-10-15T06:30:00+00:00 (giờ UTC)."
        ) from exc
    return value


class FlightIn(BaseModel):
    """Tạo chuyến bay mới."""

    model_config = ConfigDict(extra="forbid")

    flight_code: str = Field(pattern=FLIGHT_CODE_PATTERN)
    airline: str | None = Field(default=None, max_length=128)
    direction: FlightDirection
    shift_id: int | None = None

    departure_airport: str = Field(pattern=AIRPORT_PATTERN)
    arrival_airport: str = Field(pattern=AIRPORT_PATTERN)
    departure_time: str
    arrival_time: str

    capacity: int = Field(ge=1, le=1000)
    # Ghế giữ cho khách VIP / dự phòng. Thuật toán phân bổ không được đụng vào.
    reserved_slots: int = Field(default=0, ge=0)

    note: str | None = Field(default=None, max_length=2000)
    is_active: bool = True

    @field_validator("departure_time", "arrival_time")
    @classmethod
    def _validate_times(cls, value: str) -> str:
        return _check_iso(value, "Thời gian")

    @model_validator(mode="after")
    def _check_consistency(self) -> "FlightIn":
        if self.departure_airport == self.arrival_airport:
            raise ValueError("Sân bay đi và sân bay đến không thể trùng nhau.")
        if from_iso(self.arrival_time) <= from_iso(self.departure_time):
            raise ValueError("Giờ đến phải sau giờ khởi hành.")
        if self.reserved_slots > self.capacity:
            raise ValueError("Số ghế giữ lại không thể lớn hơn tổng số ghế.")
        return self


class FlightUpdate(BaseModel):
    """Sửa chuyến bay. Chỉ gửi trường cần đổi.

    Kiểm tra chéo (giờ đến sau giờ đi, ghế không tụt dưới số đã xếp) làm ở service,
    vì phải ghép với giá trị đang có trong DB mới biết kết quả cuối cùng có hợp lệ.
    """

    model_config = ConfigDict(extra="forbid")

    flight_code: str | None = Field(default=None, pattern=FLIGHT_CODE_PATTERN)
    airline: str | None = Field(default=None, max_length=128)
    direction: FlightDirection | None = None
    shift_id: int | None = None

    departure_airport: str | None = Field(default=None, pattern=AIRPORT_PATTERN)
    arrival_airport: str | None = Field(default=None, pattern=AIRPORT_PATTERN)
    departure_time: str | None = None
    arrival_time: str | None = None

    capacity: int | None = Field(default=None, ge=1, le=1000)
    reserved_slots: int | None = Field(default=None, ge=0)

    note: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None

    @field_validator("departure_time", "arrival_time")
    @classmethod
    def _validate_times(cls, value: str | None) -> str | None:
        return _check_iso(value, "Thời gian")


class FlightOut(BaseModel):
    """Chuyến bay kèm tình trạng slot — thứ BTC nhìn vào để quyết định."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    flight_code: str
    airline: str | None = None
    direction: FlightDirection
    shift_id: int | None = None
    shift_code: str | None = None
    shift_name: str | None = None

    departure_airport: str
    arrival_airport: str
    departure_time: str
    arrival_time: str

    capacity: int
    reserved_slots: int
    usable_capacity: int = 0
    assigned_count: int = 0
    remaining_slots: int = 0
    # >= 1.0 nghĩa là hết chỗ dùng được; frontend đổi màu cột theo tỉ lệ này.
    load_ratio: float = 0.0

    note: str | None = None
    is_active: bool
    created_at: str
    updated_at: str


class PassengerOut(BaseModel):
    """Hành khách trên một chuyến.

    Cố ý KHÔNG có số CCCD hay ngày sinh: danh sách này hiển thị rộng và in ra giấy.
    `has_flight_documents` đủ để BTC biết ai chưa xuất được vé mà không phơi giấy tờ.
    """

    model_config = ConfigDict(from_attributes=True)

    assignment_id: int
    registration_id: int
    user_id: int
    full_name: str
    employee_code: str | None = None
    team_id: int | None = None
    team_name: str | None = None
    requested_shift_code: str | None = None
    seat_number: str | None = None
    ticket_code: str | None = None
    assignment_mode: AssignmentMode
    assigned_at: str
    note: str | None = None
    has_flight_documents: bool = False


class ShiftLoad(BaseModel):
    """Cung và cầu của một ca: BTC mở thêm chuyến khi `requested` vượt `usable_capacity`."""

    shift_id: int | None = None
    shift_code: str = "—"
    shift_name: str = "Chưa gán ca"
    flights: int = 0
    capacity: int = 0
    usable_capacity: int = 0
    assigned: int = 0
    remaining: int = 0
    # Số người có nguyện vọng ca này (chỉ tính chiều đi — nguyện vọng ca là cho chuyến đi).
    requested: int = 0
    # Nguyện vọng vượt ghế dùng được bao nhiêu. > 0 nghĩa là chắc chắn có người phải
    # đổi ca, dù tổng ghế cả chiều vẫn đủ — BTC cần biết TRƯỚC khi chạy phân bổ.
    shortfall: int = 0


class DirectionLoad(BaseModel):
    direction: FlightDirection
    flights: int = 0
    capacity: int = 0
    reserved: int = 0
    usable_capacity: int = 0
    assigned: int = 0
    remaining: int = 0
    # Thiếu bao nhiêu ghế so với số người tham gia. 0 = đủ chỗ.
    shortfall: int = 0
    by_shift: list[ShiftLoad] = Field(default_factory=list)


class FlightCapacitySummary(BaseModel):
    """Tổng quan slot trước khi chạy phân bổ (bước 12).

    BTC phải thấy "còn thiếu 6 ghế chiều đi" TRƯỚC khi bấm phân bổ tự động, chứ không
    phải sau khi thuật toán chạy xong và bỏ lại 6 người không có chỗ.
    """

    participants: int
    directions: list[DirectionLoad]
