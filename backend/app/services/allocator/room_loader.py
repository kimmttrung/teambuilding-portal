"""Đọc DB thành đầu vào thuần cho thuật toán xếp phòng (`rooms.py`).

Tách khỏi thuật toán để `rooms.py` không biết gì về SQLAlchemy.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.accommodation import Hotel, Room, RoomAssignment
from app.models.enums import AssignmentMode, FlightDirection, RegistrationStatus, UserRole
from app.models.flight import Flight, FlightAssignment
from app.models.registration import Registration
from app.models.user import User
from app.services.allocator.params import RoomAllocationParams
from app.services.allocator.room_types import RoomGuest, RoomSlot


def load_room_guests(db: Session, *, event_id: int, keep_manual: bool = True) -> list[RoomGuest]:
    """Mọi người đã xác nhận tham gia, kèm chuyến bay chiều đi và phòng đang xếp tay.

    `keep_manual=False` (ứng với `force_reallocate`) thì bỏ pin các bản ghi BTC xếp tay.
    Ghi chú sức khoẻ chỉ lấy CÓ/KHÔNG — nội dung không bao giờ rời khỏi hồ sơ.
    """
    registrations = db.scalars(
        select(Registration)
        .where(
            Registration.event_id == event_id,
            Registration.status == RegistrationStatus.SUBMITTED,
            Registration.is_participating.is_(True),
        )
        .options(selectinload(Registration.user).selectinload(User.team))
        .order_by(Registration.id)
    ).all()

    registration_ids = [registration.id for registration in registrations]
    flights = _outbound_flights(db, registration_ids)
    existing = _existing_rooms(db, registration_ids)

    guests = []
    for registration in registrations:
        user = registration.user
        current = existing.get(registration.id)
        pinned = keep_manual and current is not None and current[1] == AssignmentMode.MANUAL
        flight = flights.get(registration.id)
        guests.append(
            RoomGuest(
                registration_id=registration.id,
                full_name=user.full_name,
                gender=user.gender,
                team_id=user.team_id,
                team_name=user.team.name if user.team else "Chưa có team",
                department_id=user.department_id,
                flight_id=flight[0] if flight else None,
                flight_code=flight[1] if flight else None,
                is_team_leader=user.role == UserRole.TEAM_LEADER,
                has_health_note=bool(user.health_note),
                pinned_room_id=current[0] if pinned else None,
                pinned_captain=bool(current[2]) if pinned else False,
            )
        )
    return guests


def load_room_slots(db: Session, *, event_id: int) -> list[RoomSlot]:
    rooms = db.scalars(
        select(Room)
        .join(Hotel, Hotel.id == Room.hotel_id)
        .where(Hotel.event_id == event_id)
        .options(selectinload(Room.hotel))
        .order_by(Room.id)
    ).all()
    return [
        RoomSlot(
            room_id=room.id,
            room_number=room.room_number,
            hotel_id=room.hotel_id,
            hotel_name=room.hotel.name,
            capacity=room.capacity,
            gender_policy=room.gender_policy,
            floor=room.floor,
        )
        for room in rooms
    ]


def load_room_params(db: Session, *, event_id: int) -> RoomAllocationParams:
    # Import tại đây để tránh vòng import: event_service không biết gì về allocator.
    from app.services import event_service

    return RoomAllocationParams.from_settings(event_service.get_settings(db, event_id))


# --- Nội bộ ---


def _outbound_flights(db: Session, registration_ids: list[int]) -> dict[int, tuple[int, str]]:
    if not registration_ids:
        return {}
    rows = db.execute(
        select(FlightAssignment.registration_id, Flight.id, Flight.flight_code)
        .join(Flight, Flight.id == FlightAssignment.flight_id)
        .where(
            FlightAssignment.registration_id.in_(registration_ids),
            FlightAssignment.direction == FlightDirection.OUTBOUND,
        )
    ).all()
    return {registration_id: (flight_id, code) for registration_id, flight_id, code in rows}


def _existing_rooms(db: Session, registration_ids: list[int]) -> dict[int, tuple[int, str, bool]]:
    if not registration_ids:
        return {}
    rows = db.execute(
        select(
            RoomAssignment.registration_id,
            RoomAssignment.room_id,
            RoomAssignment.assignment_mode,
            RoomAssignment.is_room_captain,
        ).where(RoomAssignment.registration_id.in_(registration_ids))
    ).all()
    return {registration_id: (room_id, mode, captain) for registration_id, room_id, mode, captain in rows}
