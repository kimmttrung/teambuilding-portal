"""Nhật ký email đã gửi."""

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import EmailStatus, sql_in


class EmailLog(Base):
    """Mỗi email hệ thống gửi đi là một dòng ở đây.

    Cần thiết vì BTC phải trả lời được câu "tôi không nhận được mail" - phải biết
    mail đã gửi chưa, thất bại vì lý do gì.
    """

    __tablename__ = "email_logs"
    __table_args__ = (CheckConstraint(f"status IN {sql_in(EmailStatus)}", name="status_valid"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # Thư thuộc kỳ nào — nhật ký và thống kê email lọc theo kỳ đang chọn (`X-Event-Id`).
    # Nullable: dòng cũ trước khi có cột này, và thư nào đó sau này không gắn kỳ.
    # Không `ondelete=CASCADE`: xoá kỳ mà mất luôn bằng chứng "đã gửi thư cho ai" là mất
    # đúng thứ BTC cần khi CBNV nói "tôi không nhận được mail".
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    to_email: Mapped[str] = mapped_column(String(255), nullable=False)
    template: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body_preview: Mapped[str | None] = mapped_column(Text)

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=EmailStatus.QUEUED, index=True
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Trỏ mềm tới bản ghi liên quan (registration, flight_assignment...) mà không
    # cần FK cứng - vì một template dùng cho nhiều loại đối tượng.
    related_type: Mapped[str | None] = mapped_column(String(64))
    related_id: Mapped[int | None] = mapped_column(Integer)

    sent_at: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)

    def __repr__(self) -> str:
        return f"<EmailLog {self.template} -> {self.to_email} ({self.status})>"
