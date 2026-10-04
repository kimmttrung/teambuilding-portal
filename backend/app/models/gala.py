"""Gala Dinner: sơ đồ bàn ghế, bốc thăm thứ tự, giữ ghế và xác nhận ghế."""

from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import DrawStatus, GalaSelectionStatus, sql_in

if TYPE_CHECKING:
    from app.models.org import Team
    from app.models.registration import Registration
    from app.models.user import User


class GalaLayout(Base, TimestampMixin):
    """Sơ đồ khu vực Gala Dinner của một kỳ."""

    __tablename__ = "gala_layouts"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_gala_layouts_event"),
        CheckConstraint(
            f"selection_status IN {sql_in(GalaSelectionStatus)}", name="selection_status_valid"
        ),
        CheckConstraint("hold_seconds > 0", name="hold_seconds_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    venue: Mapped[str | None] = mapped_column(String(255))
    starts_at: Mapped[str | None] = mapped_column(String(32))

    stage_position: Mapped[str] = mapped_column(String(16), nullable=False, default="top")
    grid_width: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    grid_height: Mapped[int] = mapped_column(Integer, nullable=False, default=10)

    selection_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=GalaSelectionStatus.CLOSED
    )
    turn_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    hold_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    # UTC: đóng băng lượt và hold cho tới khi BTC tiếp tục.
    turn_paused_at: Mapped[str | None] = mapped_column(String(32))
    # Seed của lần bốc thăm gần nhất, lưu để tái lập kết quả khi cần đối chiếu.
    draw_seed: Mapped[int | None] = mapped_column(Integer)

    tables: Mapped[list["GalaTable"]] = relationship(
        back_populates="layout", cascade="all, delete-orphan"
    )
    draw_orders: Mapped[list["GalaDrawOrder"]] = relationship(
        back_populates="layout", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<GalaLayout {self.name}>"


class GalaTable(Base):
    """Một bàn tiệc, đặt tại toạ độ (pos_x, pos_y) trên lưới sơ đồ."""

    __tablename__ = "gala_tables"
    __table_args__ = (
        UniqueConstraint("layout_id", "table_code", name="uq_gala_tables_layout_code"),
        CheckConstraint("seat_count > 0", name="seat_count_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    layout_id: Mapped[int] = mapped_column(
        ForeignKey("gala_layouts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    table_code: Mapped[str] = mapped_column(String(16), nullable=False)  # B01
    table_name: Mapped[str | None] = mapped_column(String(128))
    seat_count: Mapped[int] = mapped_column(Integer, nullable=False)
    pos_x: Mapped[int] = mapped_column(Integer, nullable=False)
    pos_y: Mapped[int] = mapped_column(Integer, nullable=False)
    is_vip: Mapped[bool] = mapped_column(nullable=False, default=False)
    is_available: Mapped[bool] = mapped_column(nullable=False, default=True)

    layout: Mapped["GalaLayout"] = relationship(back_populates="tables")
    seats: Mapped[list["GalaSeat"]] = relationship(
        back_populates="table", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<GalaTable {self.table_code}>"


class GalaSeat(Base):
    """Một ghế quanh bàn và trạng thái giữ/xác nhận, không có bảng phân ghế riêng."""

    __tablename__ = "gala_seats"
    __table_args__ = (
        UniqueConstraint("table_id", "seat_number", name="uq_gala_seats_table_number"),
        UniqueConstraint("registration_id", name="uq_gala_seats_registration"),
        CheckConstraint("status IN ('free', 'held', 'taken')", name="status_valid"),
        CheckConstraint(
            "(status = 'free' AND team_id IS NULL AND registration_id IS NULL "
            "AND held_by IS NULL AND hold_expires_at IS NULL "
            "AND confirmed_by IS NULL AND confirmed_at IS NULL) "
            "OR (status = 'held' AND team_id IS NOT NULL AND held_by IS NOT NULL "
            "AND hold_expires_at IS NOT NULL AND registration_id IS NULL "
            "AND confirmed_by IS NULL AND confirmed_at IS NULL) "
            "OR (status = 'taken' AND held_by IS NULL AND hold_expires_at IS NULL "
            "AND confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL)",
            name="state_consistent",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    table_id: Mapped[int] = mapped_column(
        ForeignKey("gala_tables.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seat_number: Mapped[int] = mapped_column(Integer, nullable=False)
    is_available: Mapped[bool] = mapped_column(nullable=False, default=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="free", server_default="free", index=True
    )
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), index=True)
    registration_id: Mapped[int | None] = mapped_column(ForeignKey("registrations.id"))
    held_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    held_at: Mapped[str | None] = mapped_column(String(32))
    hold_expires_at: Mapped[str | None] = mapped_column(String(32), index=True)
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    confirmed_at: Mapped[str | None] = mapped_column(String(32))
    registration: Mapped["Registration | None"] = relationship(back_populates="gala_seat")
    team: Mapped["Team | None"] = relationship()
    holder: Mapped["User | None"] = relationship(foreign_keys=[held_by])
    confirmer: Mapped["User | None"] = relationship(foreign_keys=[confirmed_by])

    table: Mapped["GalaTable"] = relationship(back_populates="seats")

    def __repr__(self) -> str:
        return f"<GalaSeat table={self.table_id} #{self.seat_number}>"


class GalaDrawOrder(Base):
    """Thứ tự bốc thăm và hạn mức ghế của từng team."""

    __tablename__ = "gala_draw_orders"
    __table_args__ = (
        UniqueConstraint("layout_id", "team_id", name="uq_gala_draw_layout_team"),
        UniqueConstraint("layout_id", "draw_position", name="uq_gala_draw_layout_position"),
        CheckConstraint(f"status IN {sql_in(DrawStatus)}", name="status_valid"),
        CheckConstraint("quota >= 0", name="quota_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    layout_id: Mapped[int] = mapped_column(
        ForeignKey("gala_layouts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    draw_position: Mapped[int] = mapped_column(Integer, nullable=False)
    # Snapshot lúc bốc thăm, KHÔNG dùng làm quota hiện tại; service phải đếm người tham gia.
    quota: Mapped[int] = mapped_column(Integer, nullable=False)

    turn_started_at: Mapped[str | None] = mapped_column(String(32))
    turn_ends_at: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=DrawStatus.WAITING)

    layout: Mapped["GalaLayout"] = relationship(back_populates="draw_orders")
    team: Mapped["Team"] = relationship()

    def __repr__(self) -> str:
        return f"<GalaDrawOrder team={self.team_id} #{self.draw_position}>"
