"""Bảng phục vụ xác thực: refresh token đã phát hành và nhật ký lần đăng nhập.

Refresh token lưu để thu hồi được: đăng xuất, đổi mật khẩu hoặc admin khoá tài khoản
thì mọi phiên đang mở phải chết ngay. Access token sống ngắn (60 phút) nên không cần lưu.
"""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class RefreshToken(Base):
    """Một phiên đăng nhập.

    Chỉ lưu SHA-256 của token, không lưu token gốc: rò rỉ database cũng không
    mạo danh được ai.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # jti của JWT, dùng để tra cứu nhanh khi refresh
    jti: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    issued_at: Mapped[str] = mapped_column(String(32), nullable=False)
    expires_at: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    revoked_at: Mapped[str | None] = mapped_column(String(32))
    # Ghi lại vì sao bị thu hồi: logout | rotated | password_changed | admin_revoked
    revoked_reason: Mapped[str | None] = mapped_column(String(32))

    user_agent: Mapped[str | None] = mapped_column(String(255))
    ip_address: Mapped[str | None] = mapped_column(String(64))

    user: Mapped["User"] = relationship()

    def __repr__(self) -> str:
        return f"<RefreshToken user={self.user_id} jti={self.jti[:8]}...>"


class LoginAttempt(Base):
    """Một lần gọi POST /auth/login — nền cho rate limit theo IP (docs/09 §5).

    Phải là bảng DB chứ không phải bộ đếm trong bộ nhớ: uvicorn chạy nhiều worker
    (mỗi worker một tiến trình riêng) và container khởi động lại thường xuyên, bộ
    đếm in-memory sẽ reset đúng lúc kẻ tấn công cần.

    Dòng cũ hơn ATTEMPT_RETENTION_HOURS bị dọn ngay trong lúc ghi nên bảng không phình.
    """

    __tablename__ = "login_attempts"
    __table_args__ = (
        # Hai truy vấn đếm của login_guard: (email, ip, thời gian) và (ip, thời gian).
        Index("ix_login_attempts_email_ip_time", "email", "ip_address", "attempted_at"),
        Index("ix_login_attempts_ip_time", "ip_address", "attempted_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Email đã lower + strip, không ForeignKey: email không tồn tại cũng phải đếm,
    # nếu không thì dò danh sách email là miễn phí.
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    # "unknown" khi không xác định được IP — vẫn phải đếm chứ không được bỏ qua.
    ip_address: Mapped[str] = mapped_column(String(64), nullable=False)
    succeeded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attempted_at: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    def __repr__(self) -> str:
        return f"<LoginAttempt {self.email} from={self.ip_address} ok={self.succeeded}>"
