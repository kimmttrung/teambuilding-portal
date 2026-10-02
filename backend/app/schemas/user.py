"""Schema hiển thị người dùng.

Ba mức, tương ứng ma trận quyền ở docs/09-security.md §4:

    UserPublic  — ai cũng xem được (danh sách team, trưởng xe)
    UserSelf    — chính chủ xem hồ sơ của mình
    UserAdmin   — BTC xem, có thêm trường quản trị

Không bao giờ trả thẳng ORM object ra API: `id_card_number` hay `health_note`
lọt ra ngoài là sự cố dữ liệu cá nhân, không phải lỗi hiển thị.
"""

import re
from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models.enums import Gender, UserRole


class TeamBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    color: str | None = None


class UserPublic(BaseModel):
    """Thông tin ai cũng thấy được. Không có số điện thoại, không có giấy tờ."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    display_name: str | None = None
    avatar_url: str | None = None
    job_title: str | None = None
    team: TeamBrief | None = None


class UserSelf(UserPublic):
    """Hồ sơ đầy đủ của chính người đang đăng nhập."""

    email: EmailStr
    employee_code: str | None = None
    role: UserRole
    phone: str | None = None
    personal_email: EmailStr | None = None
    gender: Gender | None = None
    date_of_birth: str | None = None
    address: str | None = None

    department_id: int | None = None
    work_location_id: int | None = None
    join_date: str | None = None

    id_card_number: str | None = None
    id_card_type: str | None = None
    id_card_issue_date: str | None = None
    id_card_issue_place: str | None = None

    shirt_size: str | None = None
    dietary_restriction: str | None = None
    health_note: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None

    must_change_password: bool = False
    # Đủ giấy tờ để BTC xuất vé máy bay chưa — frontend dựa vào đây để nhắc bổ sung.
    can_fly: bool = False


class UserAdmin(UserSelf):
    """Bản BTC nhìn thấy, thêm trạng thái tài khoản."""

    is_active: bool
    last_login_at: str | None = None
    # Có giá trị ở tương lai = đang bị khoá tạm vì nhập sai mật khẩu nhiều lần.
    locked_until: str | None = None
    created_at: str
    team_id: int | None = None


class UserProfileUpdate(BaseModel):
    """Các trường CBNV được tự sửa.

    Cố ý KHÔNG có: email, role, team_id, is_active — đổi những thứ đó là việc của BTC.
    """

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=32)
    personal_email: EmailStr | None = None
    gender: Gender | None = None
    date_of_birth: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    address: str | None = Field(default=None, max_length=512)
    avatar_url: str | None = Field(default=None, max_length=512)

    id_card_number: str | None = Field(default=None, max_length=32)
    id_card_type: str | None = Field(default=None, pattern=r"^(cccd|passport)$")
    id_card_issue_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    id_card_issue_place: str | None = Field(default=None, max_length=255)

    shirt_size: str | None = Field(default=None, pattern=r"^(XS|S|M|L|XL|XXL|XXXL)$")
    dietary_restriction: str | None = Field(default=None, max_length=255)
    health_note: str | None = Field(default=None, max_length=2000)
    emergency_contact_name: str | None = Field(default=None, max_length=255)
    emergency_contact_phone: str | None = Field(default=None, max_length=32)

    @field_validator("phone", "emergency_contact_phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = re.sub(r"[\s.-]", "", value)
        if not re.fullmatch(r"0\d{9,10}", normalized):
            raise ValueError("Số điện thoại phải là 10-11 số và bắt đầu bằng 0")
        return value

    @field_validator("date_of_birth", "id_card_issue_date")
    @classmethod
    def validate_past_date(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("Ngày không hợp lệ") from exc
        if parsed > date.today():
            raise ValueError("Ngày không thể ở tương lai")
        return value

    @model_validator(mode="after")
    def validate_document_number_when_type_is_known(self) -> "UserProfileUpdate":
        if not self.id_card_number or not self.id_card_type:
            return self
        number = re.sub(r"\s", "", self.id_card_number)
        valid = (
            bool(re.fullmatch(r"[A-Za-z0-9]{6,12}", number))
            if self.id_card_type == "passport"
            else bool(re.fullmatch(r"(?:\d{9}|\d{12})", number))
        )
        if not valid:
            raise ValueError(
                "Số hộ chiếu gồm 6-12 chữ và số"
                if self.id_card_type == "passport"
                else "Số CCCD gồm 12 số (CMND cũ 9 số)"
            )
        return self
