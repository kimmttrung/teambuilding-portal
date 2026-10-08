"""Đọc dữ liệu từ DB thành đầu vào thuần của thuật toán.

Tách khỏi `flights.py` để thuật toán không biết gì về SQLAlchemy: test thuật toán chạy
không cần database, còn mọi truy vấn nằm gọn ở đây.

Slot chuyến bay lấy qua `flight_service.list_flights` chứ không tự đếm lại — phép đếm
"còn bao nhiêu ghế" chỉ được tồn tại một bản trong cả hệ thống (xem bước 11).
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import FlightDirection, RegistrationStatus
from app.models.event import Event
from app.models.flight import FlightAssignment
from app.models.org import WorkLocation
from app.models.registration import Registration
from app.models.user import User
from app.services import flight_service
from app.services.allocator.params import AllocationParams
from app.services.allocator.types import FlightSlot, Participant

logger = logging.getLogger(__name__)


def load_participants(
    db: Session, *, event_id: int, direction: str, keep_manual: bool = True
) -> list[Participant]:
    """CBNV tham gia của kỳ, kèm thông tin cần cho thuật toán.

    `keep_manual=False` (ứng với `force_reallocate`) thì bỏ pin: thuật toán được xếp lại
    cả những người BTC từng gán tay.
    """
    registrations = db.scalars(
        select(Registration)
        .where(
            Registration.event_id == event_id,
            Registration.status == RegistrationStatus.SUBMITTED,
            Registration.is_participating.is_(True),
        )
        .options(
            selectinload(Registration.user).selectinload(User.team),
            selectinload(Registration.user).selectinload(User.work_location),
            selectinload(Registration.legs),
        )
        .order_by(Registration.id)
    ).all()

    pinned = _pinned_flight_ids(db, event_id=event_id, direction=direction)
    airports = dict(db.execute(select(WorkLocation.id, WorkLocation.airport_code)).all())

    participants = []
    for registration in registrations:
        user = registration.user
        origin = airports.get(registration.departure_location_id) or (
            user.work_location.airport_code if user.work_location else None
        )
        participants.append(
            Participant(
                registration_id=registration.id,
                user_id=user.id,
                full_name=user.full_name,
                team_id=user.team_id,
                team_name=user.team.name if user.team else "Chưa có team",
                department_id=user.department_id,
                requested_shift_id=registration.shift_id,
                shift_locked=registration.is_shift_locked,
                pinned_flight_id=pinned.get(registration.id) if keep_manual else None,
                has_documents=user.can_fly,
                pickup_point_id=_first_pickup_point(registration),
                origin_airport=origin,
            )
        )
    return participants


def load_flight_slots(db: Session, *, event_id: int, direction: str) -> list[FlightSlot]:
    """Chuyến bay đang dùng được của một chiều."""
    rows = flight_service.list_flights(
        db, event_id=event_id, direction=direction, is_active=True
    )
    return [
        FlightSlot(
            flight_id=flight.id,
            flight_code=flight.flight_code,
            shift_id=flight.shift_id,
            capacity=flight.capacity,
            reserved=flight.reserved_slots,
            city_airport=(
                flight.departure_airport
                if direction == FlightDirection.OUTBOUND
                else flight.arrival_airport
            ),
        )
        for flight, _assigned in rows
    ]


def load_params(db: Session, *, event_id: int) -> AllocationParams:
    # Schema v2 lưu cấu hình trong events.settings. Không phụ thuộc API cấu hình kỳ (F9).
    event = db.get(Event, event_id)
    return AllocationParams.from_settings(event.settings if event else None)


# --- Nội bộ ---


def _pinned_flight_ids(db: Session, *, event_id: int, direction: str) -> dict[int, int]:
    """registration_id -> flight_id của những bản ghi BTC đã gán tay."""
    rows = db.execute(
        select(FlightAssignment.registration_id, FlightAssignment.flight_id)
        .join(Registration, Registration.id == FlightAssignment.registration_id)
        .where(
            Registration.event_id == event_id,
            FlightAssignment.direction == direction,
            FlightAssignment.assignment_mode == "manual",
        )
    ).all()
    return {registration_id: flight_id for registration_id, flight_id in rows}


def _first_pickup_point(registration: Registration) -> int | None:
    """Điểm đón đầu tiên người này chọn — dùng để giữ họ cạnh nhau khi phải tách team."""
    for need in sorted(registration.legs, key=lambda item: item.trip_leg_id):
        if need.needs_bus and need.pickup_point_id:
            return need.pickup_point_id
    return None
