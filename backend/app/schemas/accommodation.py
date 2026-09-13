"""Schema cho khách sạn, phòng, phân phòng và import Excel (docs/04-api-spec.md §6)."""

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.timeutils import from_iso
from app.models.enums import AssignmentMode, RoomGenderPolicy

ROOM_TYPE_PATTERN = r"^(single|twin|double|triple|quad)$"
ROOM_NUMBER_PATTERN = r"^[A-Za-z0-9._-]{1,32}$"


def _check_iso(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        from_iso(value)
    except ValueError as exc:
        raise ValueError(
            "Thời gian phải là ISO-8601, ví dụ 2026-10-15T07:00:00+00:00 (giờ UTC)."
        ) from exc
    return value


# --- Khách sạn ---


class HotelIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    address: str | None = Field(default=None, max_length=512)
    phone: str | None = Field(default=None, max_length=32)
    check_in_at: str | None = None
    check_out_at: str | None = None
    map_url: str | None = Field(default=None, max_length=512)
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("check_in_at", "check_out_at")
    @classmethod
    def _validate_times(cls, value: str | None) -> str | None:
        return _check_iso(value)

    @model_validator(mode="after")
    def _check_out_after_check_in(self) -> "HotelIn":
        if self.check_in_at and self.check_out_at:
            if from_iso(self.check_out_at) <= from_iso(self.check_in_at):
                raise ValueError("Giờ trả phòng phải sau giờ nhận phòng.")
        return self


class HotelUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    address: str | None = Field(default=None, max_length=512)
    phone: str | None = Field(default=None, max_length=32)
    check_in_at: str | None = None
    check_out_at: str | None = None
    map_url: str | None = Field(default=None, max_length=512)
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("check_in_at", "check_out_at")
    @classmethod
    def _validate_times(cls, value: str | None) -> str | None:
        return _check_iso(value)


class HotelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    name: str
    address: str | None = None
    phone: str | None = None
    check_in_at: str | None = None
    check_out_at: str | None = None
    map_url: str | None = None
    note: str | None = None
    room_count: int = 0
    bed_count: int = 0
    assigned_count: int = 0
    created_at: str
    updated_at: str


# --- Phòng ---


class RoomIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hotel_id: int
    room_number: str = Field(pattern=ROOM_NUMBER_PATTERN)
    room_type: str | None = Field(default=None, pattern=ROOM_TYPE_PATTERN)
    capacity: int = Field(ge=1, le=10)
    floor: str | None = Field(default=None, max_length=16)
    # Ràng buộc cứng khi xếp phòng: 'any' = không giới hạn giới tính.
    gender_policy: RoomGenderPolicy = RoomGenderPolicy.ANY
    note: str | None = Field(default=None, max_length=512)


class RoomUpdate(BaseModel):
    """Sửa phòng. Không cho đổi `hotel_id`: chuyển một phòng đang có người sang khách sạn
    khác không có nghĩa thực tế — tạo phòng mới thay vì sửa."""

    model_config = ConfigDict(extra="forbid")

    room_number: str | None = Field(default=None, pattern=ROOM_NUMBER_PATTERN)
    room_type: str | None = Field(default=None, pattern=ROOM_TYPE_PATTERN)
    capacity: int | None = Field(default=None, ge=1, le=10)
    floor: str | None = Field(default=None, max_length=16)
    gender_policy: RoomGenderPolicy | None = None
    note: str | None = Field(default=None, max_length=512)


class RoomOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hotel_id: int
    hotel_name: str = ""
    room_number: str
    room_type: str | None = None
    capacity: int
    floor: str | None = None
    gender_policy: RoomGenderPolicy
    note: str | None = None
    occupied: int = 0
    remaining: int = 0
    has_captain: bool = False


class OccupantOut(BaseModel):
    assignment_id: int
    registration_id: int
    user_id: int
    full_name: str
    employee_code: str | None = None
    gender: str | None = None
    team_id: int | None = None
    team_name: str | None = None
    is_room_captain: bool
    assignment_mode: AssignmentMode
    assigned_at: str
    dietary_restriction: str | None = None
    # Chỉ báo CÓ ghi chú sức khoẻ, không đưa nội dung: danh sách phòng hiển thị rộng và hay
    # được in ra (docs/05 §7 bước 3 cần biết để xếp gần thang máy, không cần đọc bệnh án).
    has_health_note: bool = False


# --- Phân phòng ---


class RoomAssignIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    registration_id: int
    room_id: int
    is_room_captain: bool = False
    # Người đã có phòng khác: phải bật cờ này mới chuyển, tránh ghi đè nhầm bằng một cú bấm.
    replace_existing: bool = False
    reason: str | None = Field(default=None, max_length=500)


class RoomAssignmentOut(BaseModel):
    id: int
    registration_id: int
    user_id: int
    full_name: str
    employee_code: str | None = None
    gender: str | None = None
    team_id: int | None = None
    team_name: str | None = None
    room_id: int
    room_number: str
    hotel_id: int
    hotel_name: str
    is_room_captain: bool
    assignment_mode: AssignmentMode
    assigned_at: str


class RoomAssignResponse(BaseModel):
    assignment: RoomAssignmentOut
    moved_from_room_id: int | None = None


# --- Tổng quan giường ---


class PolicyLoad(BaseModel):
    gender_policy: RoomGenderPolicy
    rooms: int = 0
    beds: int = 0
    occupied: int = 0
    remaining: int = 0
    # Số người tham gia chỉ ở được loại phòng này (phòng 'any': người khai giới tính khác/trống).
    participants: int = 0
    shortfall: int = 0


class RoomSummary(BaseModel):
    participants: int
    assigned: int
    unassigned: int
    total_beds: int
    # Số người CHẮC CHẮN không có giường hợp giới tính, sau khi đã dùng hết phòng 'any'.
    uncovered: int
    by_policy: list[PolicyLoad]


# --- Import Excel ---


class ImportRowError(BaseModel):
    row: int
    code: str
    message: str


class RoomImportResult(BaseModel):
    dry_run: bool
    committed: bool = False
    total_rows: int
    valid_rows: int
    error_count: int
    errors: list[ImportRowError] = Field(default_factory=list)
    to_create: int = 0
    to_move: int = 0
    unchanged: int = 0
