"""Khách sạn và phòng; thông tin phân phòng nằm trên registrations."""

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
from app.models.enums import RoomGenderPolicy, sql_in

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
    rooms: Mapped[list["Room"]] = relationship(back_populates="hotel", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Hotel {self.name}>"


class Room(Base):
    """Một phòng cụ thể trong khách sạn."""

    __tablename__ = "rooms"
    __table_args__ = (
        UniqueConstraint("hotel_id", "room_number", name="uq_rooms_hotel_number"),
        CheckConstraint("capacity > 0", name="capacity_positive"),
        CheckConstraint(f"gender_policy IN {sql_in(RoomGenderPolicy)}", name="gender_policy_valid"),
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
    registrations: Mapped[list["Registration"]] = relationship(back_populates="room")

    def __repr__(self) -> str:
        return f"<Room {self.room_number}>"
