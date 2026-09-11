"""Schema cho master data: phòng ban, địa điểm, team, ca, chặng, điểm đón.

Đây là nguồn của mọi dropdown trong form đăng ký. BRD §4.2 yêu cầu CBNV chọn từ
danh sách chứ không nhập tự do, để tên Team thống nhất giữa các bộ phận.
"""

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import FlightDirection

CODE_PATTERN = r"^[A-Z0-9_-]+$"


# --- Phòng ban ---


class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    display_order: int
    is_active: bool


class DepartmentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=32, pattern=CODE_PATTERN)
    name: str = Field(min_length=1, max_length=255)
    display_order: int = 0
    is_active: bool = True


class DepartmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    display_order: int | None = None
    is_active: bool | None = None


# --- Địa điểm làm việc ---


class WorkLocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    city: str | None = None
    airport_code: str | None = None
    display_order: int
    is_active: bool


class WorkLocationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=16, pattern=CODE_PATTERN)
    name: str = Field(min_length=1, max_length=255)
    city: str | None = Field(default=None, max_length=128)
    airport_code: str | None = Field(default=None, max_length=8, pattern=r"^[A-Z]{3}$")
    display_order: int = 0
    is_active: bool = True


class WorkLocationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    city: str | None = Field(default=None, max_length=128)
    airport_code: str | None = Field(default=None, max_length=8, pattern=r"^[A-Z]{3}$")
    display_order: int | None = None
    is_active: bool | None = None


# --- Team ---


class TeamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    department_id: int | None = None
    leader_user_id: int | None = None
    color: str | None = None
    is_active: bool
    member_count: int = 0


class TeamIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=32, pattern=CODE_PATTERN)
    name: str = Field(min_length=1, max_length=255)
    department_id: int | None = None
    leader_user_id: int | None = None
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    is_active: bool = True


class TeamUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    department_id: int | None = None
    leader_user_id: int | None = None
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    is_active: bool | None = None


# --- Ca bay ---


class ShiftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    code: str
    name: str
    description: str | None = None
    earliest_departure: str | None = None
    display_order: int


class ShiftIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=16, pattern=CODE_PATTERN)
    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=512)
    earliest_departure: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    display_order: int = 0


class ShiftUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=512)
    earliest_departure: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    display_order: int | None = None


# --- Chặng xe ---


class TripLegOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    code: str
    name: str
    direction: FlightDirection
    leg_date: str | None = None
    is_airport_linked: bool
    display_order: int


class TripLegIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=32, pattern=CODE_PATTERN)
    name: str = Field(min_length=1, max_length=255)
    direction: FlightDirection
    leg_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    is_airport_linked: bool = False
    display_order: int = 0


class TripLegUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    direction: FlightDirection | None = None
    leg_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    is_airport_linked: bool | None = None
    display_order: int | None = None


# --- Điểm đón ---


class PickupPointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    trip_leg_id: int | None = None
    work_location_id: int | None = None
    name: str
    address: str | None = None
    map_url: str | None = None
    display_order: int


class PickupPointIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trip_leg_id: int | None = None
    work_location_id: int | None = None
    name: str = Field(min_length=1, max_length=255)
    address: str | None = Field(default=None, max_length=512)
    map_url: str | None = Field(default=None, max_length=512)
    display_order: int = 0


class PickupPointUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trip_leg_id: int | None = None
    work_location_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    address: str | None = Field(default=None, max_length=512)
    map_url: str | None = Field(default=None, max_length=512)
    display_order: int | None = None


# --- Gói chung cho form đăng ký ---


class RegistrationFormOptions(BaseModel):
    """Mọi lựa chọn form đăng ký cần, trong MỘT request.

    Frontend gọi 1 lần thay vì 5 lần — form đăng ký là màn hình CBNV vào nhiều nhất.
    """

    teams: list[TeamOut]
    departments: list[DepartmentOut]
    work_locations: list[WorkLocationOut]
    shifts: list[ShiftOut]
    trip_legs: list[TripLegOut]
    pickup_points: list[PickupPointOut]
