"""Ca bay, chuyến bay và kết quả phân bổ chuyến bay."""

from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import AssignmentMode, FlightDirection, sql_in

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.registration import Registration
    from app.models.user import User


class Shift(Base):
    """Ca bay (Ca 1 / Ca 2).

    Là dữ liệu, không phải enum cứng: mỗi kỳ BTC có thể khai báo số ca khác nhau.
    """

    __tablename__ = "shifts"
    __table_args__ = (UniqueConstraint("event_id", "code", name="uq_shifts_event_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(16), nullable=False)  # CA1, CA2
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512))
    earliest_departure: Mapped[str | None] = mapped_column(String(5))  # HH:MM
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    event: Mapped["Event"] = relationship(back_populates="shifts")
    flights: Mapped[list["Flight"]] = relationship(back_populates="shift")

    def __repr__(self) -> str:
        return f"<Shift {self.code}>"


class Flight(Base, TimestampMixin):
    """Một chuyến bay BTC đã mua slot."""

    __tablename__ = "flights"
    __table_args__ = (
        UniqueConstraint(
            "event_id",
            "flight_code",
            "direction",
            "departure_time",
            name="uq_flights_event_code_direction_time",
        ),
        CheckConstraint(f"direction IN {sql_in(FlightDirection)}", name="direction_valid"),
        CheckConstraint("capacity >= 0", name="capacity_non_negative"),
        CheckConstraint("reserved_slots >= 0", name="reserved_non_negative"),
        CheckConstraint("reserved_slots <= capacity", name="reserved_within_capacity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    flight_code: Mapped[str] = mapped_column(String(16), nullable=False)
    airline: Mapped[str | None] = mapped_column(String(128))
    direction: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    shift_id: Mapped[int | None] = mapped_column(ForeignKey("shifts.id"), index=True)

    departure_airport: Mapped[str] = mapped_column(String(8), nullable=False)
    arrival_airport: Mapped[str] = mapped_column(String(8), nullable=False)
    departure_time: Mapped[str] = mapped_column(String(32), nullable=False)
    arrival_time: Mapped[str] = mapped_column(String(32), nullable=False)

    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    # Slot giữ lại cho khách VIP/dự phòng, thuật toán không được đụng vào.
    reserved_slots: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    note: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)

    event: Mapped["Event"] = relationship(back_populates="flights")
    shift: Mapped["Shift | None"] = relationship(back_populates="flights")
    assignments: Mapped[list["FlightAssignment"]] = relationship(
        back_populates="flight", cascade="all, delete-orphan"
    )

    @property
    def usable_capacity(self) -> int:
        return self.capacity - self.reserved_slots

    def __repr__(self) -> str:
        return f"<Flight {self.flight_code} {self.direction}>"


class FlightAssignment(Base):
    """Gán một đăng ký vào một chuyến bay.

    UNIQUE(registration_id, direction): mỗi người đúng một chuyến cho mỗi chiều.
    Bảng riêng thay vì cột trên registrations để lưu được ai gán, khi nào, vì sao
    (xem docs/adr/002-separate-assignment-tables.md).
    """

    __tablename__ = "flight_assignments"
    __table_args__ = (
        UniqueConstraint(
            "registration_id", "direction", name="uq_flight_assignments_registration_direction"
        ),
        CheckConstraint(f"direction IN {sql_in(FlightDirection)}", name="direction_valid"),
        CheckConstraint(f"assignment_mode IN {sql_in(AssignmentMode)}", name="mode_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    registration_id: Mapped[int] = mapped_column(
        ForeignKey("registrations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    flight_id: Mapped[int] = mapped_column(
        ForeignKey("flights.id"), nullable=False, index=True
    )
    direction: Mapped[str] = mapped_column(String(16), nullable=False)

    seat_number: Mapped[str | None] = mapped_column(String(8))
    ticket_code: Mapped[str | None] = mapped_column(String(32))

    assignment_mode: Mapped[str] = mapped_column(
        String(16), nullable=False, default=AssignmentMode.AUTO
    )
    assigned_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    assigned_at: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)

    registration: Mapped["Registration"] = relationship(back_populates="flight_assignments")
    flight: Mapped["Flight"] = relationship(back_populates="assignments")
    assigner: Mapped["User | None"] = relationship()

    @property
    def is_manual(self) -> bool:
        """Bản ghi thủ công không bị auto allocation ghi đè."""
        return self.assignment_mode == AssignmentMode.MANUAL

    def __repr__(self) -> str:
        return f"<FlightAssignment reg={self.registration_id} flight={self.flight_id}>"
