"""Schema cho kỳ Team Building."""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import EventStatus
from app.schemas.validators import CalendarDate, IsoDateTimeTz

DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"


def check_registration_window(
    opens_at: str | None, closes_at: str | None, start_date: str | None
) -> None:
    """Mở đăng ký phải trước khi đóng, và đóng không muộn hơn hết ngày bắt đầu kỳ (giờ Việt Nam).

    Hàm thường để `event_service.update_event` gọi lại với giá trị đã gộp cùng dữ liệu đang lưu —
    request sửa kỳ thường chỉ mang một trong ba mốc.
    """
    from app.core.timeutils import from_iso, to_vn

    if opens_at and closes_at and from_iso(closes_at) <= from_iso(opens_at):
        raise ValueError("Thời điểm đóng đăng ký phải sau thời điểm mở đăng ký.")
    if closes_at and start_date and to_vn(closes_at).strftime("%Y-%m-%d") > start_date:
        raise ValueError("Đăng ký phải đóng trước khi chương trình bắt đầu.")


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
    updated_at: str
    status_label: str = ""
    registration_opens_at: str | None = None
    registration_closes_at: str | None = None
    terms_version: str

    # Suy ra từ status — frontend dựa vào đây thay vì tự so chuỗi trạng thái.
    can_register: bool = False
    is_published: bool = False
    # Chương trình đang diễn ra / đã kết thúc: cấu hình kỳ chỉ còn để xem.
    config_locked: bool = False


class EventAdmin(EventPublic):
    is_active: bool
    created_at: str
    updated_at: str


class EventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str = Field(min_length=2, max_length=32, pattern=r"^[A-Z0-9_-]+$")
    name: str = Field(min_length=3, max_length=255)
    destination: str | None = Field(default=None, max_length=255)
    start_date: CalendarDate
    end_date: CalendarDate
    registration_opens_at: IsoDateTimeTz | None = None
    registration_closes_at: IsoDateTimeTz | None = None
    terms_version: str = Field(default="v1", min_length=1, max_length=16)
    terms_content: str | None = None

    @model_validator(mode="after")
    def _check_registration_window(self) -> "EventCreate":
        check_registration_window(
            self.registration_opens_at, self.registration_closes_at, self.start_date
        )
        return self


class EventUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=3, max_length=255)
    destination: str | None = Field(default=None, max_length=255)
    start_date: CalendarDate | None = None
    end_date: CalendarDate | None = None
    registration_opens_at: IsoDateTimeTz | None = None
    registration_closes_at: IsoDateTimeTz | None = None
    terms_version: str | None = Field(default=None, min_length=1, max_length=16)
    terms_content: str | None = None


class EventStatusChange(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: EventStatus
    reason: str | None = Field(default=None, max_length=1000)
    # Gửi email báo CBNV (người tham gia; mở đăng ký thì mọi người). Mặc định KHÔNG gửi:
    # BTC phải chủ động tích ô "Gửi email" — tránh spam khi thử nghiệm hoặc bấm nhầm rồi lùi lại.
    notify: bool = False


class TermsResponse(BaseModel):
    event_code: str
    version: str
    content: str


class TermsVersion(BaseModel):
    """Một bản quy định: bản đang dùng hoặc bản đã bị thay — để đối chiếu với `consent_version`."""

    version: str
    content: str
    # None với bản đang dùng.
    replaced_at: str | None = None
    consent_count: int
    is_current: bool = False


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

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    values: dict[str, object] = Field(
        description="Ví dụ: {\"allocation.team_weight\": 15, \"gala.hold_seconds\": 90}"
    )


class ConfigImpactItem(BaseModel):
    kind: str
    title: str
    count: int
    details: list[str] = []
    # Đường dẫn frontend tới màn hình xử lý.
    link: str


class ConfigImpact(BaseModel):
    """Những thứ đã xếp không còn khớp cấu hình kỳ — BTC cần rà lại phân bổ."""

    needs_review: bool
    items: list[ConfigImpactItem]
