"""Khách sạn, phòng và phân phòng."""

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
from app.models.enums import AssignmentMode, RoomGenderPolicy, sql_in

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.registration import Registration


class Hotel(Base, TimestampMixin):
    """Khách sạn của kỳ Team Building."""

    __tablename__ = "hotels"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(String(512))
    phone: Mapped[str | None] = mapped_column(String(32))
    check_in_at: Mapped[str | None] = mapped_column(String(32))
    check_out_at: Mapped[str | None] = mapped_column(String(32))
    map_url: Mapped[str | None] = mapped_column(String(512))
    note: Mapped[str | None] = mapped_column(Text)

    event: Mapped["Event"] = relationship()
    rooms: Mapped[list["Room"]] = relationship(
        back_populates="hotel", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Hotel {self.name}>"


class Room(Base):
    """Một phòng cụ thể trong khách sạn."""

    __tablename__ = "rooms"
    __table_args__ = (
        UniqueConstraint("hotel_id", "room_number", name="uq_rooms_hotel_number"),
        CheckConstraint("capacity > 0", name="capacity_positive"),
        CheckConstraint(
            f"gender_policy IN {sql_in(RoomGenderPolicy)}", name="gender_policy_valid"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_id: Mapped[int] = mapped_column(
        ForeignKey("hotels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    room_number: Mapped[str] = mapped_column(String(32), nullable=False)
    room_type: Mapped[str | None] = mapped_column(String(32))  # twin | double | triple
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    floor: Mapped[str | None] = mapped_column(String(16))
    # Ràng buộc cứng khi phân phòng: 'any' = không giới hạn giới tính.
    gender_policy: Mapped[str] = mapped_column(
        String(16), nullable=False, default=RoomGenderPolicy.ANY
    )
    note: Mapped[str | None] = mapped_column(String(512))

    hotel: Mapped["Hotel"] = relationship(back_populates="rooms")
    assignments: Mapped[list["RoomAssignment"]] = relationship(
        back_populates="room", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Room {self.room_number}>"


class RoomAssignment(Base):
    """Xếp một người vào một phòng.

    MVP: BTC import từ Excel (assignment_mode='manual'). Auto allocation ở Phase 2
    dùng chung khuôn này nên không phải đổi schema.
    """

    __tablename__ = "room_assignments"
    __table_args__ = (
        UniqueConstraint("registration_id", name="uq_room_assignments_registration"),
        CheckConstraint(f"assignment_mode IN {sql_in(AssignmentMode)}", name="mode_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    registration_id: Mapped[int] = mapped_column(
        ForeignKey("registrations.id", ondelete="CASCADE"), nullable=False
    )
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), nullable=False, index=True)
    is_room_captain: Mapped[bool] = mapped_column(nullable=False, default=False)

    assignment_mode: Mapped[str] = mapped_column(
        String(16), nullable=False, default=AssignmentMode.MANUAL
    )
    assigned_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    assigned_at: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[str | None] = mapped_column(String(512))

    registration: Mapped["Registration"] = relationship(back_populates="room_assignment")
    room: Mapped["Room"] = relationship(back_populates="assignments")

    def __repr__(self) -> str:
        return f"<RoomAssignment reg={self.registration_id} room={self.room_id}>"
