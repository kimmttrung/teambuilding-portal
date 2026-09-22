"""Đọc DB thành đầu vào thuần cho thuật toán phân xe (`buses.py`).

Tách khỏi thuật toán để `buses.py` không biết gì về SQLAlchemy — test thuật toán chạy
không cần database, còn mọi truy vấn nằm gọn ở đây.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import AssignmentMode, RegistrationStatus
from app.models.flight import FlightAssignment
from app.models.registration import Registration, RegistrationBusNeed
from app.models.transportation import Bus, BusAssignment, TripLeg
from app.models.user import User
from app.services import transport_timing_service
from app.services.allocator.bus_types import BusRider, BusSlot


def load_bus_riders(
    db: Session, *, event_id: int, trip_leg: TripLeg, keep_manual: bool = True
) -> list[BusRider]:
    """Người tham gia cần xe ở chặng này, kèm điểm đón và chuyến bay cùng chiều.

    `keep_manual=False` (ứng với `force_reallocate`) thì bỏ pin các bản ghi BTC xếp tay.
    """
    rows = db.execute(
        select(Registration, RegistrationBusNeed.pickup_point_id)
        .join(RegistrationBusNeed, RegistrationBusNeed.registration_id == Registration.id)
        .where(
            Registration.event_id == event_id,
            Registration.status == RegistrationStatus.SUBMITTED,
            Registration.is_participating.is_(True),
            RegistrationBusNeed.trip_leg_id == trip_leg.id,
            RegistrationBusNeed.needs_bus.is_(True),
        )
        .options(selectinload(Registration.user).selectinload(User.team))
        .order_by(Registration.id)
    ).all()

    registration_ids = [registration.id for registration, _pickup in rows]
    flights = _flight_ids(db, registration_ids, trip_leg.direction)
    pinned = _pinned_bus_ids(db, trip_leg.id) if keep_manual else {}

    riders = []
    for registration, pickup_point_id in rows:
        user = registration.user
        riders.append(
            BusRider(
                registration_id=registration.id,
                full_name=user.full_name,
                team_id=user.team_id,
                team_name=user.team.name if user.team else "Chưa có team",
                pickup_point_id=pickup_point_id,
                flight_id=flights.get(registration.id),
                pinned_bus_id=pinned.get(registration.id),
            )
        )
    return riders


def load_bus_slots(db: Session, *, event_id: int, trip_leg_id: int) -> list[BusSlot]:
    buses = db.scalars(
        select(Bus)
        .where(Bus.event_id == event_id, Bus.trip_leg_id == trip_leg_id)
        .order_by(Bus.id)
    ).all()
    leg = db.get(TripLeg, trip_leg_id)
    incompatible = (
        transport_timing_service.incompatible_flight_ids(db, event_id=event_id, leg=leg, buses=list(buses))
        if leg is not None
        else {}
    )
    return [
        BusSlot(
            bus_id=bus.id,
            bus_code=bus.bus_code,
            capacity=bus.capacity,
            pickup_point_id=bus.pickup_point_id,
            linked_flight_id=bus.linked_flight_id,
            incompatible_flight_ids=incompatible.get(bus.id, frozenset()),
        )
        for bus in buses
    ]


# --- Nội bộ ---


def _flight_ids(db: Session, registration_ids: list[int], direction: str) -> dict[int, int]:
    """Chuyến bay của từng người ở chiều của chặng (chặng chiều đi -> chuyến chiều đi)."""
    if not registration_ids:
        return {}
    rows = db.execute(
        select(FlightAssignment.registration_id, FlightAssignment.flight_id).where(
            FlightAssignment.registration_id.in_(registration_ids),
            FlightAssignment.direction == direction,
        )
    ).all()
    return {registration_id: flight_id for registration_id, flight_id in rows}


def _pinned_bus_ids(db: Session, trip_leg_id: int) -> dict[int, int]:
    rows = db.execute(
        select(BusAssignment.registration_id, BusAssignment.bus_id).where(
            BusAssignment.trip_leg_id == trip_leg_id,
            BusAssignment.assignment_mode == AssignmentMode.MANUAL,
        )
    ).all()
    return {registration_id: bus_id for registration_id, bus_id in rows}
