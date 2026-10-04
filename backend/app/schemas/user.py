"""Schema hiển thị người dùng.

Ba mức, tương ứng ma trận quyền ở docs/09-security.md §4:

    UserPublic  — ai cũng xem được (danh sách team, trưởng xe)
    UserSelf    — chính chủ xem hồ sơ của mình
    UserAdmin   — BTC xem, có thêm trường quản trị

Không bao giờ trả thẳng ORM object ra API: `id_card_number` hay `health_note`
lọt ra ngoài là sự cố dữ liệu cá nhân, không phải lỗi hiển thị.
"""


from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    model_validator,
)

from app.models.enums import Gender, UserRole
from app.schemas.validators import (  # noqa: F401 — `CalendarDate` được module khác import từ đây
    BirthDate,
    CalendarDate,
    MobilePhone,
    PastDate,
    check_id_card,
    check_issue_after_birth,
)


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
    Cũng KHÔNG có `avatar_url`: ảnh chỉ đổi qua `POST /auth/me/avatar`. Nhận chuỗi tự do ở đây là
    cho phép trỏ ảnh sang site ngoài (theo dõi người xem) hoặc sang file ảnh của người khác.

    Luật ở đây chỉ thấy dữ liệu trong request. Phần phải so với hồ sơ ĐANG LƯU (số giấy tờ với
    loại giấy tờ đã có, ngày cấp với ngày sinh đã có) kiểm ở `auth_service.update_profile`.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    display_name: str | None = Field(default=None, max_length=255)
    phone: MobilePhone | None = None
    personal_email: EmailStr | None = None
    gender: Gender | None = None
    date_of_birth: BirthDate | None = None
    address: str | None = Field(default=None, max_length=512)

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
    def _check_documents(self) -> "UserProfileUpdate":
        if self.id_card_number:
            check_id_card(self.id_card_number, self.id_card_type)
        check_issue_after_birth(self.id_card_issue_date, self.date_of_birth)
        return self
