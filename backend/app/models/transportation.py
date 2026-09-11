"""Chặng di chuyển, điểm đón, xe và phân xe."""

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
    from app.models.flight import Flight
    from app.models.org import WorkLocation
    from app.models.registration import Registration
    from app.models.user import User


class TripLeg(Base):
    """Một chặng di chuyển bằng xe.

    Mặc định 4 chặng (thành phố -> sân bay -> khách sạn -> sân bay -> thành phố)
    nhưng là dữ liệu nên BTC thêm chặng mới không cần sửa code.
    """

    __tablename__ = "trip_legs"
    __table_args__ = (
        UniqueConstraint("event_id", "code", name="uq_trip_legs_event_code"),
        CheckConstraint(f"direction IN {sql_in(FlightDirection)}", name="direction_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)  # CITY_TO_AIRPORT...
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    leg_date: Mapped[str | None] = mapped_column(String(10))
    # True với chặng gắn sân bay: xe phải khớp giờ chuyến bay, không gộp khác chuyến.
    is_airport_linked: Mapped[bool] = mapped_column(nullable=False, default=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    event: Mapped["Event"] = relationship(back_populates="trip_legs")
    buses: Mapped[list["Bus"]] = relationship(
        back_populates="trip_leg", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<TripLeg {self.code}>"


class PickupPoint(Base):
    """Điểm tập trung đón/trả CBNV."""

    __tablename__ = "pickup_points"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trip_leg_id: Mapped[int | None] = mapped_column(ForeignKey("trip_legs.id"), index=True)
    work_location_id: Mapped[int | None] = mapped_column(ForeignKey("work_locations.id"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(String(512))
    map_url: Mapped[str | None] = mapped_column(String(512))
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    work_location: Mapped["WorkLocation | None"] = relationship()

    def __repr__(self) -> str:
        return f"<PickupPoint {self.name}>"


class Bus(Base, TimestampMixin):
    """Một xe phục vụ một chặng cụ thể."""

    __tablename__ = "buses"
    __table_args__ = (
        UniqueConstraint("event_id", "trip_leg_id", "bus_code", name="uq_buses_event_leg_code"),
        CheckConstraint("capacity > 0", name="capacity_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trip_leg_id: Mapped[int] = mapped_column(
        ForeignKey("trip_legs.id"), nullable=False, index=True
    )
    bus_code: Mapped[str] = mapped_column(String(32), nullable=False)
    plate_number: Mapped[str | None] = mapped_column(String(32))
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)

    pickup_point_id: Mapped[int | None] = mapped_column(ForeignKey("pickup_points.id"))
    dropoff_point: Mapped[str | None] = mapped_column(String(255))
    gather_time: Mapped[str | None] = mapped_column(String(32))
    departure_time: Mapped[str | None] = mapped_column(String(32))

    # Trưởng xe thường là CBNV; leader_name/phone dùng khi là người ngoài danh sách.
    leader_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    leader_name: Mapped[str | None] = mapped_column(String(255))
    leader_phone: Mapped[str | None] = mapped_column(String(32))
    driver_name: Mapped[str | None] = mapped_column(String(255))
    driver_phone: Mapped[str | None] = mapped_column(String(32))

    # Xe này phục vụ chuyến bay nào - quyết định giờ đón ở chặng gắn sân bay.
    linked_flight_id: Mapped[int | None] = mapped_column(ForeignKey("flights.id"), index=True)
    note: Mapped[str | None] = mapped_column(Text)

    trip_leg: Mapped["TripLeg"] = relationship(back_populates="buses")
    pickup_point: Mapped["PickupPoint | None"] = relationship()
    leader: Mapped["User | None"] = relationship()
    linked_flight: Mapped["Flight | None"] = relationship()
    assignments: Mapped[list["BusAssignment"]] = relationship(
        back_populates="bus", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Bus {self.bus_code} leg={self.trip_leg_id}>"


class BusAssignment(Base):
    """Gán một người vào một xe ở một chặng.

    UNIQUE(registration_id, trip_leg_id): mỗi chặng một người chỉ ngồi một xe.
    """

    __tablename__ = "bus_assignments"
    __table_args__ = (
        UniqueConstraint(
            "registration_id", "trip_leg_id", name="uq_bus_assignments_registration_leg"
        ),
        CheckConstraint(f"assignment_mode IN {sql_in(AssignmentMode)}", name="mode_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    registration_id: Mapped[int] = mapped_column(
        ForeignKey("registrations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bus_id: Mapped[int] = mapped_column(ForeignKey("buses.id"), nullable=False, index=True)
    trip_leg_id: Mapped[int] = mapped_column(ForeignKey("trip_legs.id"), nullable=False)

    assignment_mode: Mapped[str] = mapped_column(
        String(16), nullable=False, default=AssignmentMode.AUTO
    )
    assigned_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    assigned_at: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)

    registration: Mapped["Registration"] = relationship(back_populates="bus_assignments")
    bus: Mapped["Bus"] = relationship(back_populates="assignments")

    @property
    def is_manual(self) -> bool:
        return self.assignment_mode == AssignmentMode.MANUAL

    def __repr__(self) -> str:
        return f"<BusAssignment reg={self.registration_id} bus={self.bus_id}>"
