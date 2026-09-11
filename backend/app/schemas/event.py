"""Schema cho kỳ Team Building."""

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import EventStatus

DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"


class EventPublic(BaseModel):
    """Bản CBNV nhìn thấy. Không có terms_content (lấy riêng ở /terms cho nhẹ)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    destination: str | None = None
    start_date: str
    end_date: str
    status: EventStatus
    status_label: str = ""
    registration_opens_at: str | None = None
    registration_closes_at: str | None = None
    terms_version: str
    banner_url: str | None = None

    # Suy ra từ status — frontend dựa vào đây thay vì tự so chuỗi trạng thái.
    can_register: bool = False
    is_published: bool = False


class EventAdmin(EventPublic):
    is_active: bool
    created_at: str
    updated_at: str


class EventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=2, max_length=32, pattern=r"^[A-Z0-9_-]+$")
    name: str = Field(min_length=3, max_length=255)
    destination: str | None = Field(default=None, max_length=255)
    start_date: str = Field(pattern=DATE_PATTERN)
    end_date: str = Field(pattern=DATE_PATTERN)
    registration_opens_at: str | None = None
    registration_closes_at: str | None = None
    terms_version: str = Field(default="v1", max_length=16)
    terms_content: str | None = None
    banner_url: str | None = Field(default=None, max_length=512)


class EventUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=3, max_length=255)
    destination: str | None = Field(default=None, max_length=255)
    start_date: str | None = Field(default=None, pattern=DATE_PATTERN)
    end_date: str | None = Field(default=None, pattern=DATE_PATTERN)
    registration_opens_at: str | None = None
    registration_closes_at: str | None = None
    terms_version: str | None = Field(default=None, max_length=16)
    terms_content: str | None = None
    banner_url: str | None = Field(default=None, max_length=512)


class EventStatusChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: EventStatus
    reason: str | None = Field(default=None, max_length=1000)


class TermsResponse(BaseModel):
    event_code: str
    version: str
    content: str


class EventStatusOverview(BaseModel):
    """Dữ liệu cho thanh trạng thái ở màn hình quản trị."""

    status: EventStatus
    status_label: str
    can_register: bool
    is_published: bool
    allowed_next_statuses: list[str]
    total_users: int
    registered: int
    not_registered: int
    participants: int


class SettingValue(BaseModel):
    value: object
    description: str | None = None


class EventSettingsUpdate(BaseModel):
    """Cập nhật một phần cấu hình: chỉ gửi những khoá muốn đổi."""

    model_config = ConfigDict(extra="forbid")

    values: dict[str, object] = Field(
        description="Ví dụ: {\"allocation.team_weight\": 15, \"gala.hold_seconds\": 90}"
    )
