"""Nghiệp vụ chuyến bay: CRUD và tình trạng slot.

Hai luật không được phá, vì phá là BTC xếp người vượt số ghế đã mua:

1. Chỗ trống luôn được TÍNH (`capacity - reserved_slots - số đã gán`), không lưu sẵn.
2. Không hạ `capacity` / tăng `reserved_slots` xuống dưới số người đã xếp, và không
   xoá hay tắt chuyến còn hành khách — phải chuyển người đi trước.

Bước 12 (thuật toán phân bổ) sẽ đọc `capacity_summary` và `list_flights` ở đây, nên
mọi phép đếm slot chỉ tồn tại một bản duy nhất trong file này.
"""

import logging
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.core.timeutils import from_iso
from app.models.enums import FlightDirection, RegistrationStatus
from app.models.event import Event
from app.models.flight import Flight, FlightAssignment, Shift
from app.models.registration import Registration
from app.models.user import User
from app.services import audit_service, transport_timing_service

logger = logging.getLogger(__name__)

AUDITED_FIELDS = [
    "flight_code",
    "airline",
    "direction",
    "shift_id",
    "departure_airport",
    "arrival_airport",
    "departure_time",
    "arrival_time",
    "capacity",
    "reserved_slots",
    "is_active",
]


# --- Truy vấn ---


def list_flights(
    db: Session,
    *,
    event_id: int,
    direction: str | None = None,
    shift_id: int | None = None,
    is_active: bool | None = None,
    search: str | None = None,
) -> list[tuple[Flight, int]]:
    """Chuyến bay kèm số người đã xếp.

    Đếm bằng subquery gộp sẵn thay vì đọc `flight.assignments` cho từng dòng: danh sách
    này là màn hình BTC mở nhiều nhất, N+1 query ở đây thấy rõ ngay khi có 20 chuyến.
    """
    assigned = (
        select(FlightAssignment.flight_id, func.count(FlightAssignment.id).label("assigned"))
        .group_by(FlightAssignment.flight_id)
        .subquery()
    )

    query = (
        select(Flight, func.coalesce(assigned.c.assigned, 0))
        .outerjoin(assigned, assigned.c.flight_id == Flight.id)
        .where(Flight.event_id == event_id)
        .options(selectinload(Flight.shift))
    )

    if direction:
        query = query.where(Flight.direction == direction)
    if shift_id is not None:
        query = query.where(Flight.shift_id == shift_id)
    if is_active is not None:
        query = query.where(Flight.is_active.is_(is_active))
    if search:
        pattern = f"%{search.strip().upper()}%"
        query = query.where(
            or_(
                Flight.flight_code.like(pattern),
                Flight.departure_airport.like(pattern),
                Flight.arrival_airport.like(pattern),
            )
        )

    rows = db.execute(query.order_by(Flight.direction, Flight.departure_time)).all()
    return [(flight, count) for flight, count in rows]


def get_flight(db: Session, *, event_id: int, flight_id: int) -> Flight:
    flight = db.scalar(
        select(Flight)
        .where(Flight.id == flight_id, Flight.event_id == event_id)
        .options(selectinload(Flight.shift))
    )
    if flight is None:
        raise NotFoundError(
            f"Không tìm thấy chuyến bay #{flight_id} trong kỳ này.", code="FLIGHT_NOT_FOUND"
        )
    return flight


def count_assigned(db: Session, flight_id: int) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(FlightAssignment)
            .where(FlightAssignment.flight_id == flight_id)
        )
        or 0
    )


def list_passengers(db: Session, *, flight: Flight) -> list[dict[str, Any]]:
    """Hành khách của một chuyến, kèm team và nguyện vọng ca ban đầu."""
    rows = db.scalars(
        select(FlightAssignment)
        .where(FlightAssignment.flight_id == flight.id)
        .options(
            selectinload(FlightAssignment.registration)
            .selectinload(Registration.user)
            .selectinload(User.team),
            selectinload(FlightAssignment.registration).selectinload(Registration.shift),
        )
    ).all()

    passengers = []
    for assignment in rows:
        registration = assignment.registration
        user = registration.user
        passengers.append(
            {
                "assignment_id": assignment.id,
                "registration_id": registration.id,
                "user_id": user.id,
                "full_name": user.full_name,
                "employee_code": user.employee_code,
                "team_id": user.team_id,
                "team_name": user.team.name if user.team else None,
                "requested_shift_code": registration.shift.code if registration.shift else None,
                "seat_number": assignment.seat_number,
                "ticket_code": assignment.ticket_code,
                "assignment_mode": assignment.assignment_mode,
                "assigned_at": assignment.assigned_at,
                "note": assignment.note,
                "has_flight_documents": user.can_fly,
            }
        )

    # Sắp theo team rồi tên: BTC đọc danh sách này khi điểm danh ở sân bay, đi theo team.
    passengers.sort(key=lambda item: (item["team_name"] or "", item["full_name"]))
    return passengers


def capacity_summary(db: Session, *, event_id: int) -> dict[str, Any]:
    """Tổng quan slot theo chiều và theo ca, so với số người tham gia."""
    participants = _count_participants(db, event_id)
    shifts = list(
        db.scalars(select(Shift).where(Shift.event_id == event_id).order_by(Shift.display_order))
    )
    requested_by_shift = _count_requested_by_shift(db, event_id)
    flights = list_flights(db, event_id=event_id, is_active=True)

    directions = []
    for direction in FlightDirection:
        in_direction = [(f, count) for f, count in flights if f.direction == direction]
        capacity = sum(f.capacity for f, _ in in_direction)
        reserved = sum(f.reserved_slots for f, _ in in_direction)
        assigned = sum(count for _, count in in_direction)
        usable = capacity - reserved

        by_shift = []
        for shift in [*shifts, None]:
            shift_id = shift.id if shift else None
            of_shift = [(f, c) for f, c in in_direction if f.shift_id == shift_id]
            # Ca chưa có chuyến nào và cũng không ai đăng ký thì bỏ, đừng làm rối bảng.
            if not of_shift and not (shift and requested_by_shift.get(shift_id)):
                continue
            shift_capacity = sum(f.capacity for f, _ in of_shift)
            shift_reserved = sum(f.reserved_slots for f, _ in of_shift)
            shift_assigned = sum(c for _, c in of_shift)
            shift_usable = shift_capacity - shift_reserved
            # Nguyện vọng ca chỉ áp cho chiều đi; chiều về BTC tự cân.
            requested = (
                requested_by_shift.get(shift_id, 0)
                if direction == FlightDirection.OUTBOUND
                else 0
            )
            by_shift.append(
                {
                    "shift_id": shift_id,
                    "shift_code": shift.code if shift else "—",
                    "shift_name": shift.name if shift else "Chưa gán ca",
                    "flights": len(of_shift),
                    "capacity": shift_capacity,
                    "usable_capacity": shift_usable,
                    "assigned": shift_assigned,
                    "remaining": shift_usable - shift_assigned,
                    "requested": requested,
                    "shortfall": max(requested - shift_usable, 0),
                }
            )

        directions.append(
            {
                "direction": direction,
                "flights": len(in_direction),
                "capacity": capacity,
                "reserved": reserved,
                "usable_capacity": usable,
                "assigned": assigned,
                "remaining": usable - assigned,
                "shortfall": max(participants - usable, 0),
                "by_shift": by_shift,
            }
        )

    return {"participants": participants, "directions": directions}


# --- Ghi ---


def create_flight(
    db: Session,
    *,
    event: Event,
    data: dict[str, Any],
    actor: User,
    ip_address: str | None = None,
) -> Flight:
    _validate_shift(db, event, data.get("shift_id"))

    flight = Flight(event_id=event.id, **data)
    db.add(flight)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise _duplicate_error(data) from exc

    audit_service.log(
        db,
        action="flight.created",
        entity_type="flight",
        entity_id=flight.id,
        actor_id=actor.id,
        event_id=event.id,
        after=audit_service.snapshot(flight, AUDITED_FIELDS),
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(flight)
    logger.info("Thêm chuyến bay %s (%s)", flight.flight_code, flight.direction)
    return flight


def update_flight(
    db: Session,
    *,
    event: Event,
    flight: Flight,
    data: dict[str, Any],
    actor: User,
    ip_address: str | None = None,
) -> Flight:
    if not data:
        return flight

    assigned = count_assigned(db, flight.id)
    before = audit_service.snapshot(flight, AUDITED_FIELDS)

    if "shift_id" in data:
        _validate_shift(db, event, data["shift_id"])

    _check_times(
        departure=data.get("departure_time", flight.departure_time),
        arrival=data.get("arrival_time", flight.arrival_time),
    )
    _check_airports(
        departure=data.get("departure_airport", flight.departure_airport),
        arrival=data.get("arrival_airport", flight.arrival_airport),
    )
    _check_capacity_floor(
        capacity=data.get("capacity", flight.capacity),
        reserved=data.get("reserved_slots", flight.reserved_slots),
        assigned=assigned,
        flight=flight,
    )

    # Giờ bay đổi mà xe ra/đón sân bay giữ nguyên là CBNV lỡ chuyến: chặn, bắt chỉnh xe trước.
    if "departure_time" in data or "arrival_time" in data:
        transport_timing_service.check_flight_change(
            db,
            flight=flight,
            departure_time=data.get("departure_time", flight.departure_time),
            arrival_time=data.get("arrival_time", flight.arrival_time),
        )

    if data.get("is_active") is False and assigned:
        raise ConflictError(
            f"Chuyến {flight.flight_code} còn {assigned} hành khách nên không tắt được. "
            "Chuyển họ sang chuyến khác trước.",
            code="FLIGHT_HAS_PASSENGERS",
            details={"assigned_count": assigned},
        )

    for field, value in data.items():
        setattr(flight, field, value)

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise _duplicate_error({**before, **data}) from exc

    after = audit_service.snapshot(flight, AUDITED_FIELDS)
    audit_service.log(
        db,
        action="flight.updated",
        entity_type="flight",
        entity_id=flight.id,
        actor_id=actor.id,
        event_id=event.id,
        before=before,
        after=audit_service.diff(before, after),
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(flight)
    return flight


def delete_flight(
    db: Session,
    *,
    event: Event,
    flight: Flight,
    actor: User,
    ip_address: str | None = None,
) -> None:
    """Xoá chuyến bay. Chặn khi còn hành khách.

    `flight_assignments` có cascade delete ở quan hệ ORM, nên xoá thẳng là mất luôn
    phân bổ của từng người mà không ai biết — chặn ở đây là chặn đúng chỗ.
    """
    assigned = count_assigned(db, flight.id)
    if assigned:
        raise ConflictError(
            f"Chuyến {flight.flight_code} còn {assigned} hành khách. Chuyển họ sang chuyến "
            "khác hoặc bỏ phân bổ trước khi xoá.",
            code="FLIGHT_HAS_PASSENGERS",
            details={"assigned_count": assigned},
        )

    snapshot = audit_service.snapshot(flight, AUDITED_FIELDS)
    flight_id = flight.id
    db.delete(flight)
    db.flush()

    audit_service.log(
        db,
        action="flight.deleted",
        entity_type="flight",
        entity_id=flight_id,
        actor_id=actor.id,
        event_id=event.id,
        before=snapshot,
        ip_address=ip_address,
    )
    db.commit()
    logger.info("Xoá chuyến bay #%s (%s)", flight_id, snapshot.get("flight_code"))


# --- Kiểm tra ---


def _validate_shift(db: Session, event: Event, shift_id: int | None) -> None:
    if shift_id is None:
        return
    shift = db.get(Shift, shift_id)
    if shift is None or shift.event_id != event.id:
        raise NotFoundError(
            f"Ca #{shift_id} không thuộc kỳ Team Building này.", code="SHIFT_NOT_FOUND"
        )


def _check_times(*, departure: str, arrival: str) -> None:
    if from_iso(arrival) <= from_iso(departure):
        raise AppError(
            "Giờ đến phải sau giờ khởi hành.",
            code="INVALID_FLIGHT_TIME",
            details={"departure_time": departure, "arrival_time": arrival},
        )


def _check_airports(*, departure: str, arrival: str) -> None:
    if departure == arrival:
        raise AppError(
            "Sân bay đi và sân bay đến không thể trùng nhau.",
            code="INVALID_FLIGHT_ROUTE",
            details={"airport": departure},
        )


def _check_capacity_floor(
    *, capacity: int, reserved: int, assigned: int, flight: Flight
) -> None:
    """Ghế dùng được không được tụt xuống dưới số người đã xếp."""
    if reserved > capacity:
        raise AppError(
            "Số ghế giữ lại không thể lớn hơn tổng số ghế.",
            code="INVALID_CAPACITY",
            details={"capacity": capacity, "reserved_slots": reserved},
        )
    if capacity - reserved < assigned:
        raise ConflictError(
            f"Chuyến {flight.flight_code} đã xếp {assigned} người, không thể hạ ghế dùng được "
            f"xuống {capacity - reserved}. Chuyển người sang chuyến khác trước.",
            code="CAPACITY_BELOW_ASSIGNED",
            details={
                "assigned_count": assigned,
                "capacity": capacity,
                "reserved_slots": reserved,
                "usable_capacity": capacity - reserved,
            },
        )


def _duplicate_error(data: dict[str, Any]) -> ConflictError:
    return ConflictError(
        f"Chuyến {data.get('flight_code')} chiều {data.get('direction')} khởi hành "
        f"{data.get('departure_time')} đã có trong kỳ này.",
        code="FLIGHT_DUPLICATED",
        details={
            "flight_code": data.get("flight_code"),
            "direction": data.get("direction"),
            "departure_time": data.get("departure_time"),
        },
    )


# --- Nội bộ ---


def _count_participants(db: Session, event_id: int) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(Registration)
            .where(
                Registration.event_id == event_id,
                Registration.status == RegistrationStatus.SUBMITTED,
                Registration.is_participating.is_(True),
            )
        )
        or 0
    )


def _count_requested_by_shift(db: Session, event_id: int) -> dict[int | None, int]:
    return {
        shift_id: count
        for shift_id, count in db.execute(
            select(Registration.shift_id, func.count(Registration.id))
            .where(
                Registration.event_id == event_id,
                Registration.status == RegistrationStatus.SUBMITTED,
                Registration.is_participating.is_(True),
            )
            .group_by(Registration.shift_id)
        ).all()
    }
