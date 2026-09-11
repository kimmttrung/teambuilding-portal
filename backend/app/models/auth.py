"""Refresh token đã phát hành.

Lưu để thu hồi được: đăng xuất, đổi mật khẩu hoặc admin khoá tài khoản thì mọi
phiên đang mở phải chết ngay. Access token sống ngắn (60 phút) nên không cần lưu.
"""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
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
