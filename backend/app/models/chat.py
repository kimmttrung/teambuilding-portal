"""Lịch sử hội thoại với chatbot RAG."""

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import ChatRole, sql_in

if TYPE_CHECKING:
    from app.models.user import User


class ChatMessage(Base):
    """Một lượt hỏi hoặc đáp.

    Lưu cả `sources` để hiển thị trích dẫn và để kiểm tra chatbot lấy thông tin từ đâu
    khi cần rà soát chất lượng trả lời.
    """

    __tablename__ = "chat_messages"
    __table_args__ = (
        CheckConstraint(f"role IN {sql_in(ChatRole)}", name="role_valid"),
        Index("ix_chat_messages_owner_conversation", "user_id", "event_id", "conversation_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    event_id: Mapped[int | None] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), index=True
    )
    conversation_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    conversation_title: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[str | None] = mapped_column(Text)  # JSON: tài liệu đã trích dẫn
    tokens_used: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)

    user: Mapped["User"] = relationship()

    def __repr__(self) -> str:
        return f"<ChatMessage {self.role} conversation={self.conversation_id}>"
