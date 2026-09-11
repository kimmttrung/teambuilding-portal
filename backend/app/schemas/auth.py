"""Schema cho đăng nhập, làm mới token và đổi mật khẩu."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.security import MAX_PASSWORD_BYTES
from app.schemas.user import UserSelf

MIN_PASSWORD_LENGTH = 8


def _check_password_bytes(value: str) -> str:
    if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(
            f"Mật khẩu quá dài (tối đa {MAX_PASSWORD_BYTES} byte). "
            "Tiếng Việt có dấu chiếm 2-3 byte mỗi ký tự."
        )
    return value


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # giây
    user: UserSelf


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class LogoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str | None = None
    # True = đăng xuất mọi thiết bị đang đăng nhập
    all_devices: bool = False


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH)

    @field_validator("new_password")
    @classmethod
    def _validate_new_password(cls, value: str) -> str:
        _check_password_bytes(value)
        if not any(character.isalpha() for character in value):
            raise ValueError("Mật khẩu phải có ít nhất một chữ cái.")
        if not any(character.isdigit() for character in value):
            raise ValueError("Mật khẩu phải có ít nhất một chữ số.")
        return value


class MessageResponse(BaseModel):
    message: str
