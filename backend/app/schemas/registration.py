"""Schema cho đăng ký tham gia Team Building."""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import RegistrationStatus
from app.schemas.cancellation import CancellationBrief
from app.schemas.user import UserProfileUpdate


class BusNeedIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trip_leg_id: int
    needs_bus: bool = False
    pickup_point_id: int | None = None
    note: str | None = Field(default=None, max_length=512)


class BusNeedOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    trip_leg_id: int
    trip_leg_code: str = ""
    trip_leg_name: str = ""
    needs_bus: bool
    pickup_point_id: int | None = None
    pickup_point_name: str | None = None
    note: str | None = None


class RegistrationCreate(BaseModel):
    """Nội dung CBNV gửi khi đăng ký.

    `profile_patch` cho phép sửa hồ sơ ngay trong form đăng ký — CBNV không phải
    nhảy qua trang hồ sơ rồi quay lại, và cả hai được ghi trong cùng transaction.
    """

    model_config = ConfigDict(extra="forbid")

    is_participating: bool
    not_participating_reason: str | None = Field(default=None, max_length=512)
    shift_id: int | None = None
    departure_location_id: int | None = None
    bus_needs: list[BusNeedIn] = Field(default_factory=list)
    wish_note: str | None = Field(default=None, max_length=2000)
    companion_count: int = Field(default=0, ge=0, le=5)
    agreed_terms_version: str | None = None
    profile_patch: UserProfileUpdate | None = None

    @model_validator(mode="after")
    def _check_participation_fields(self) -> "RegistrationCreate":
        if self.is_participating and not self.agreed_terms_version:
            raise ValueError("Phải xác nhận đã đọc và đồng ý quy định chương trình.")
        if not self.is_participating and self.bus_needs:
            raise ValueError("Không tham gia thì không đăng ký nhu cầu xe.")
        return self


class RegistrationUpdate(BaseModel):
    """Sửa đăng ký. Mọi trường đều tuỳ chọn, chỉ gửi thứ cần đổi."""

    model_config = ConfigDict(extra="forbid")

    is_participating: bool | None = None
    not_participating_reason: str | None = Field(default=None, max_length=512)
    shift_id: int | None = None
    departure_location_id: int | None = None
    bus_needs: list[BusNeedIn] | None = None
    wish_note: str | None = Field(default=None, max_length=2000)
    companion_count: int | None = Field(default=None, ge=0, le=5)
    agreed_terms_version: str | None = None
    profile_patch: UserProfileUpdate | None = None


class RegistrationCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=512)


class ShiftBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str


class RegistrationOut(BaseModel):
    """Đăng ký của chính mình."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    user_id: int
    is_participating: bool
    not_participating_reason: str | None = None
    shift: ShiftBrief | None = None
    departure_location_id: int | None = None
    wish_note: str | None = None
    companion_count: int
    status: RegistrationStatus
    submitted_at: str | None = None
    cancelled_at: str | None = None
    cancel_reason: str | None = None
    penalty_applied: bool
    bus_needs: list[BusNeedOut] = Field(default_factory=list)

    # Suy ra — frontend dựa vào đây thay vì tự tính lại luật nghiệp vụ.
    can_edit: bool = False
    agreed_terms_version: str | None = None
    # Huỷ theo giai đoạn kỳ: "self" tự huỷ ngay · "request" gửi yêu cầu BTC duyệt ·
    # "contact_btc" chương trình đã bắt đầu · None khi đã huỷ (docs/04 §4.3).
    cancel_policy: str | None = None
    latest_cancellation: CancellationBrief | None = None
    # Người đã huỷ còn đăng ký lại được không (tới trước khi công bố). Frontend dựa vào đây
    # để hiện nút "Đăng ký lại" thay vì tự suy luật theo trạng thái kỳ.
    reregister_allowed: bool = False


class RegistrationPersonBrief(BaseModel):
    """Thông tin người đăng ký cho danh sách của BTC.

    Không có CCCD, địa chỉ, ghi chú sức khoẻ — danh sách này hiển thị rộng,
    dữ liệu nhạy cảm chỉ xem ở màn hình chi tiết.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_code: str | None = None
    full_name: str
    email: str
    phone: str | None = None
    gender: str | None = None
    team_id: int | None = None
    team_name: str | None = None
    work_location_id: int | None = None
    can_fly: bool = False


class RegistrationAdminOut(RegistrationOut):
    user: RegistrationPersonBrief
    has_consent: bool = False


class RegistrationStats(BaseModel):
    """Số liệu cho dashboard BTC."""

    total_users: int
    submitted: int
    not_submitted: int
    participating: int
    not_participating: int
    cancelled: int
    by_shift: dict[str, int]
    bus_demand_by_leg: dict[str, int]
    missing_flight_documents: int
