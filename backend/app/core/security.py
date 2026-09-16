"""Băm mật khẩu, phát hành và kiểm tra JWT.

Cố ý dùng `bcrypt` trực tiếp thay vì passlib: passlib 1.7.4 không tương thích
bcrypt >= 4.1 (lỗi ở `bcrypt.__about__`) và dự án này đang chạy bcrypt 5.
"""

import hashlib
import secrets
from dataclasses import dataclass
from typing import Any, Protocol

import bcrypt
import jwt

from app.core.config import settings
from app.core.exceptions import UnauthorizedError
from app.core.timeutils import from_iso, iso_in, utcnow

# bcrypt chỉ xét 72 byte đầu; mật khẩu dài hơn bị cắt âm thầm nên chặn thẳng.
MAX_PASSWORD_BYTES = 72
BCRYPT_ROUNDS = 12

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"

# Chống dò mật khẩu (docs/09-security.md §5) — hai lớp, cố ý khác ngưỡng nhau.
#
# Lớp 1 (theo tài khoản): khoá `users.locked_until`, BTC gỡ được bằng nút "Gỡ khoá".
# Ngưỡng 10 chứ không phải 5: khoá theo tài khoản là con dao hai lưỡi — ai biết email
# người khác là khoá được tài khoản người đó (DoS). Đẩy ngưỡng lên và để lớp 2 chặn
# sớm hơn thì kẻ phá đám phải tự vượt rate limit IP trước khi khoá nổi ai.
MAX_FAILED_LOGINS = 10
LOCKOUT_MINUTES = 15

# Lớp 2 (theo IP, bảng `login_attempts` — xem app/services/login_guard.py): chặn TRƯỚC
# khi so mật khẩu nên kẻ dò không tốn được CPU bcrypt của server.
ATTEMPT_WINDOW_MINUTES = 15
# Cùng một email từ cùng một IP: chặn sớm, người dùng thật ở IP khác không bị ảnh hưởng.
MAX_FAILED_PER_EMAIL_IP = 5
# Một IP rải nhiều email khác nhau (4 lần/email cho hàng trăm email vẫn qua lớp 1).
MAX_FAILED_PER_IP = 20
# Dọn dòng cũ ngay lúc ghi, không cần job nền.
ATTEMPT_RETENTION_HOURS = 24


# --- Mật khẩu ---


def hash_password(plain: str) -> str:
    _ensure_password_length(plain)
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode()


def verify_password(plain: str, hashed: str | None) -> bool:
    """So khớp mật khẩu. Trả False thay vì ném lỗi để chỗ gọi xử lý thống nhất."""
    if not hashed or not plain:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:MAX_PASSWORD_BYTES], hashed.encode("utf-8"))
    except ValueError:
        # Hash hỏng hoặc sai định dạng — coi như sai mật khẩu, không làm sập request.
        return False


def _ensure_password_length(plain: str) -> None:
    if len(plain.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(
            f"Mật khẩu vượt quá {MAX_PASSWORD_BYTES} byte (bcrypt chỉ xử lý được ngần đó)."
        )


def generate_password(length: int = 12) -> str:
    """Sinh mật khẩu ban đầu khi BTC import danh sách CBNV."""
    alphabet = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # bỏ ký tự dễ nhìn nhầm
    return "".join(secrets.choice(alphabet) for _ in range(length))


# --- JWT ---


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    refresh_jti: str
    refresh_expires_at: str
    expires_in: int  # giây, cho access token


def _encode(payload: dict[str, Any]) -> str:
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_token_pair(user_id: int, role: str) -> TokenPair:
    """Phát hành cặp access + refresh.

    Payload cố ý chỉ chứa id và role — không nhét email, tên hay dữ liệu cá nhân,
    vì JWT ai cũng giải mã đọc được (chỉ có chữ ký là không giả được).
    """
    now = utcnow()
    access_ttl = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    refresh_expires_at = iso_in(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_jti = secrets.token_urlsafe(24)

    access_token = _encode(
        {
            "sub": str(user_id),
            "role": role,
            "type": TOKEN_TYPE_ACCESS,
            "iat": int(now.timestamp()),
            "exp": int(now.timestamp()) + access_ttl,
            "jti": secrets.token_urlsafe(16),
        }
    )
    refresh_token = _encode(
        {
            "sub": str(user_id),
            "role": role,
            "type": TOKEN_TYPE_REFRESH,
            "iat": int(now.timestamp()),
            "exp": int(from_iso(refresh_expires_at).timestamp()),
            "jti": refresh_jti,
        }
    )
    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        refresh_jti=refresh_jti,
        refresh_expires_at=refresh_expires_at,
        expires_in=access_ttl,
    )


def decode_token(token: str, *, expected_type: str) -> dict[str, Any]:
    """Giải mã và kiểm tra token, ném UnauthorizedError với thông điệp tiếng Việt."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError(
            "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.", code="TOKEN_EXPIRED"
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError("Token không hợp lệ.", code="TOKEN_INVALID") from exc

    if payload.get("type") != expected_type:
        # Chặn dùng refresh token như access token và ngược lại.
        raise UnauthorizedError("Sai loại token.", code="TOKEN_WRONG_TYPE")
    return payload


def hash_token(token: str) -> str:
    """SHA-256 của refresh token — chỉ hash này được lưu vào database."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# --- Cắm SSO sau này ---


class AuthProvider(Protocol):
    """Giao diện xác thực.

    MVP dùng LocalAuthProvider (email + mật khẩu). Khi hạ tầng có SSO, viết thêm
    AzureADProvider rồi đăng ký ở đây — tầng API và service không phải sửa.
    """

    name: str

    def authenticate(self, credentials: dict[str, Any]) -> int | None:
        """Trả user_id nếu hợp lệ, None nếu không."""
        ...
