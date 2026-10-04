"""Schema quản lý tài khoản CBNV cho BTC (docs/04-api-spec.md §10, docs/09-security.md §3)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models.enums import Gender, UserRole
from app.schemas.user import UserAdmin
from app.schemas.validators import (
    BirthDate,
    MobilePhone,
    PastDate,
    check_id_card,
    check_issue_after_birth,
)

EMPLOYEE_CODE_PATTERN = r"^[A-Za-z0-9._-]{2,32}$"

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

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    employee_code: str = Field(pattern=EMPLOYEE_CODE_PATTERN)
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    role: UserRole = UserRole.EMPLOYEE
    gender: Gender | None = None
    phone: MobilePhone | None = None
    team_id: int | None = None
    department_id: int | None = None
    work_location_id: int | None = None
    job_title: str | None = Field(default=None, max_length=128)
    join_date: PastDate | None = None

    @field_validator("full_name")
    @classmethod
    def _required_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Họ tên không được để trống.")
        return value


class UserAdminUpdate(BaseModel):
    """BTC sửa hồ sơ CBNV. Không có `role`, `is_active`, mật khẩu — mỗi việc một endpoint riêng
    để phân quyền và ghi nhật ký rõ ràng."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    employee_code: str | None = Field(default=None, pattern=EMPLOYEE_CODE_PATTERN)
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    display_name: str | None = Field(default=None, max_length=255)
    phone: MobilePhone | None = None
    personal_email: EmailStr | None = None
    gender: Gender | None = None
    date_of_birth: BirthDate | None = None
    address: str | None = Field(default=None, max_length=512)

    team_id: int | None = None
    department_id: int | None = None
    work_location_id: int | None = None
    job_title: str | None = Field(default=None, max_length=128)
    join_date: PastDate | None = None

    id_card_number: str | None = Field(default=None, max_length=32)
    id_card_type: str | None = Field(default=None, pattern=r"^(cccd|passport)$")
    id_card_issue_date: PastDate | None = None
    id_card_issue_place: str | None = Field(default=None, max_length=255)

    shirt_size: str | None = Field(default=None, pattern=r"^(XS|S|M|L|XL|XXL|XXXL)$")
    dietary_restriction: str | None = Field(default=None, max_length=255)
    health_note: str | None = Field(default=None, max_length=2000)
    emergency_contact_name: str | None = Field(default=None, max_length=255)
    emergency_contact_phone: MobilePhone | None = None

    @model_validator(mode="after")
    def _check_documents(self) -> "UserAdminUpdate":
        # Cùng luật với hồ sơ CBNV tự sửa; phần so với dữ liệu đang lưu kiểm ở service.
        if self.id_card_number:
            check_id_card(self.id_card_number, self.id_card_type)
        check_issue_after_birth(self.id_card_issue_date, self.date_of_birth)
        return self


class UserRoleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    role: UserRole
    reason: str | None = Field(default=None, max_length=500)


class UserStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    is_active: bool
    reason: str = Field(min_length=3, max_length=500)


class UserCredentialsOut(BaseModel):
    """Trả mật khẩu tạm MỘT lần duy nhất. Hệ thống không lưu bản rõ, không ghi vào nhật ký."""

    user: UserAdmin
    temporary_password: str


class PasswordResetOut(BaseModel):
    temporary_password: str
    sessions_revoked: int
