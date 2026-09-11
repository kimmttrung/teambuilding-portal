"""Lịch trình, thông báo và tài liệu quy định (nguồn cho RAG)."""

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import (
    AnnouncementSeverity,
    AnnouncementTarget,
    PolicyDocType,
    sql_in,
)

if TYPE_CHECKING:
    from app.models.user import User


class ItineraryItem(Base):
    """Một mục trong lịch trình chương trình."""

    __tablename__ = "itinerary_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    day_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    start_time: Mapped[str | None] = mapped_column(String(5))  # HH:MM
    end_time: Mapped[str | None] = mapped_column(String(5))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(255))
    # 'all' hoặc mã ca/mã team - để hiển thị lịch riêng cho từng nhóm.
    audience: Mapped[str] = mapped_column(String(32), nullable=False, default="all")
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Đã đưa vào vector store của chatbot chưa.
    is_indexed: Mapped[bool] = mapped_column(nullable=False, default=False)

    def __repr__(self) -> str:
        return f"<ItineraryItem {self.day_date} {self.title}>"


class Announcement(Base):
    """Thông báo từ BTC, có thể gửi cho tất cả hoặc một nhóm cụ thể."""

    __tablename__ = "announcements"
    __table_args__ = (
        CheckConstraint(f"severity IN {sql_in(AnnouncementSeverity)}", name="severity_valid"),
        CheckConstraint(f"target_type IN {sql_in(AnnouncementTarget)}", name="target_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)  # markdown
    severity: Mapped[str] = mapped_column(
        String(16), nullable=False, default=AnnouncementSeverity.INFO
    )
    target_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default=AnnouncementTarget.ALL
    )
    target_id: Mapped[int | None] = mapped_column(Integer)

    published_at: Mapped[str | None] = mapped_column(String(32), index=True)
    send_email: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)

    author: Mapped["User | None"] = relationship()

    def __repr__(self) -> str:
        return f"<Announcement {self.title}>"


class PolicyDocument(Base):
    """Tài liệu văn bản: quy định, FAQ, hướng dẫn.

    Là nguồn chính cho vector store của chatbot. Chỉ chứa nội dung công khai với
    mọi CBNV - không bao giờ chứa dữ liệu cá nhân (docs/06-rag-chatbot.md §5).
    """

    __tablename__ = "policy_documents"
    __table_args__ = (
        CheckConstraint(f"doc_type IN {sql_in(PolicyDocType)}", name="doc_type_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int | None] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), index=True
    )
    doc_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)  # markdown
    version: Mapped[str] = mapped_column(String(16), nullable=False, default="v1")
    is_indexed: Mapped[bool] = mapped_column(nullable=False, default=False, index=True)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)

    def __repr__(self) -> str:
        return f"<PolicyDocument {self.doc_type}:{self.title}>"
