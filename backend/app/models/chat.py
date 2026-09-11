"""Lịch sử hội thoại với chatbot RAG."""

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import ChatRole, sql_in

if TYPE_CHECKING:
    from app.models.user import User


class ChatSession(Base):
    """Một phiên hội thoại của một người dùng."""

    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    title: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)

    user: Mapped["User"] = relationship()
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.id"
    )

    def __repr__(self) -> str:
        return f"<ChatSession user={self.user_id}>"


class ChatMessage(Base):
    """Một lượt hỏi hoặc đáp.

    Lưu cả `sources` để hiển thị trích dẫn và để kiểm tra chatbot lấy thông tin từ đâu
    khi cần rà soát chất lượng trả lời.
    """

    __tablename__ = "chat_messages"
    __table_args__ = (CheckConstraint(f"role IN {sql_in(ChatRole)}", name="role_valid"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[str | None] = mapped_column(Text)  # JSON: tài liệu đã trích dẫn
    tokens_used: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)

    session: Mapped["ChatSession"] = relationship(back_populates="messages")

    def __repr__(self) -> str:
        return f"<ChatMessage {self.role} session={self.session_id}>"
