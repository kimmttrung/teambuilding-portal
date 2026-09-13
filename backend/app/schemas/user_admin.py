"""Schema quản lý tài khoản CBNV cho BTC (docs/04-api-spec.md §10, docs/09-security.md §3)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import Gender, UserRole
from app.schemas.user import UserAdmin

EMPLOYEE_CODE_PATTERN = r"^[A-Za-z0-9._-]{2,32}$"
DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"

# Lọc theo đăng ký của kỳ đang chạy. "none" = chưa gửi đăng ký (kể cả bản nháp).
RegistrationFilter = Literal["none", "submitted", "participating", "not_participating", "cancelled"]


class UserListItem(BaseModel):
    """Một dòng danh sách CBNV. Cố ý KHÔNG có CCCD, ngày sinh, ghi chú sức khoẻ: danh sách hiện
    rộng và hay bị chụp màn hình — xem chi tiết từng người mới thấy đủ hồ sơ."""

    id: int
    employee_code: str | None = None
    full_name: str
    email: str
    phone: str | None = None
    gender: str | None = None
    role: UserRole
    job_title: str | None = None
    team_id: int | None = None
    team_name: str | None = None
    department_id: int | None = None
    department_name: str | None = None
    work_location_id: int | None = None
    work_location_name: str | None = None
    is_active: bool
    must_change_password: bool
    # Đang bị khoá tạm vì nhập sai mật khẩu nhiều lần.
    is_locked: bool
    last_login_at: str | None = None
    can_fly: bool
    registration_status: str | None = None
    is_participating: bool | None = None


class UserCreate(BaseModel):
    """BTC tạo tài khoản. Mật khẩu do hệ thống sinh, không nhận từ client."""

    model_config = ConfigDict(extra="forbid")

    employee_code: str = Field(pattern=EMPLOYEE_CODE_PATTERN)
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    role: UserRole = UserRole.EMPLOYEE
    gender: Gender | None = None
    phone: str | None = Field(default=None, max_length=32)
    team_id: int | None = None
    department_id: int | None = None
    work_location_id: int | None = None
    job_title: str | None = Field(default=None, max_length=128)
    join_date: str | None = Field(default=None, pattern=DATE_PATTERN)


class UserAdminUpdate(BaseModel):
    """BTC sửa hồ sơ CBNV. Không có `role`, `is_active`, mật khẩu — mỗi việc một endpoint riêng
    để phân quyền và ghi nhật ký rõ ràng."""

    model_config = ConfigDict(extra="forbid")

    employee_code: str | None = Field(default=None, pattern=EMPLOYEE_CODE_PATTERN)
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    display_name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=32)
    personal_email: EmailStr | None = None
    gender: Gender | None = None
    date_of_birth: str | None = Field(default=None, pattern=DATE_PATTERN)
    address: str | None = Field(default=None, max_length=512)

    team_id: int | None = None
    department_id: int | None = None
    work_location_id: int | None = None
    job_title: str | None = Field(default=None, max_length=128)
    join_date: str | None = Field(default=None, pattern=DATE_PATTERN)

    id_card_number: str | None = Field(default=None, max_length=32)
    id_card_type: str | None = Field(default=None, pattern=r"^(cccd|passport)$")
    id_card_issue_date: str | None = Field(default=None, pattern=DATE_PATTERN)
    id_card_issue_place: str | None = Field(default=None, max_length=255)

    shirt_size: str | None = Field(default=None, pattern=r"^(XS|S|M|L|XL|XXL|XXXL)$")
    dietary_restriction: str | None = Field(default=None, max_length=255)
    health_note: str | None = Field(default=None, max_length=2000)
    emergency_contact_name: str | None = Field(default=None, max_length=255)
    emergency_contact_phone: str | None = Field(default=None, max_length=32)


class UserRoleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: UserRole
    reason: str | None = Field(default=None, max_length=500)


class UserStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_active: bool
    reason: str = Field(min_length=3, max_length=500)


class UserCredentialsOut(BaseModel):
    """Trả mật khẩu tạm MỘT lần duy nhất. Hệ thống không lưu bản rõ, không ghi vào nhật ký."""

    user: UserAdmin
    temporary_password: str


class PasswordResetOut(BaseModel):
    temporary_password: str
    sessions_revoked: int
