"""Lớp Base và các mixin dùng chung cho toàn bộ ORM model."""

from sqlalchemy import MetaData, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.timeutils import utcnow_iso

# Đặt tên constraint theo quy ước để Alembic batch mode (bắt buộc trên SQLite)
# có thể drop/tạo lại constraint. Thiếu phần này, migration đổi cột sẽ gãy.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base khai báo chung. Alembic autogenerate đọc metadata từ đây."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    """Thêm created_at / updated_at cho mọi bảng nghiệp vụ."""

    created_at: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=utcnow_iso,
        server_default=func.current_timestamp(),
    )
    updated_at: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=utcnow_iso,
        onupdate=utcnow_iso,
        server_default=func.current_timestamp(),
    )
