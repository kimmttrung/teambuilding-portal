"""Nghiệp vụ xe: CRUD, Trưởng xe, phân xe tự động và điều chỉnh thủ công.

Cùng các luật với chuyến bay (bước 11-13):
- Ghế trống luôn được TÍNH từ `bus_assignments`, không lưu cột.
- Không hạ sức chứa dưới số người đã xếp, không xoá xe còn khách.
- Ghi phân bổ và chuyển người trong `BEGIN IMMEDIATE`, đếm lại chỗ ngay trong transaction.
- Bản ghi `manual` không bị auto ghi đè; mọi thay đổi có audit log.
"""

import logging
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.database import immediate_transaction
from app.core.exceptions import AppError, ConflictError, NotFoundError, PermissionDeniedError
from app.core.timeutils import from_iso, utcnow_iso
from app.models.enums import AssignmentMode, RegistrationStatus, UserRole
from app.models.event import Event
from app.models.flight import Flight, FlightAssignment
from app.models.registration import Registration, RegistrationBusNeed
from app.models.transportation import Bus, BusAssignment, PickupPoint, TripLeg
from app.models.user import User
from app.services import audit_service, event_service
from app.services.allocator.bus_loader import load_bus_riders, load_bus_slots
from app.services.allocator.bus_types import FLAG_MIXED_FLIGHT_ON_BUS, BusAllocationResult
from app.services.allocator.buses import allocate_buses
from app.services.allocator.types import SEVERITY_WARNING, Flag

logger = logging.getLogger(__name__)

WARN_PICKUP_MISMATCH = "PICKUP_MISMATCH"

AUDITED_FIELDS = [
    "bus_code",
    "plate_number",
    "capacity",
    "pickup_point_id",
    "dropoff_point",
    "gather_time",
    "departure_time",
    "leader_user_id",
    "leader_name",
    "leader_phone",
    "driver_name",
    "driver_phone",
    "linked_flight_id",
]

_LEADER_FIELDS = ["leader_user_id", "leader_name", "leader_phone"]
_ADMIN_ROLES = (UserRole.ADMIN, UserRole.SUPER_ADMIN)


# --- Truy vấn xe ---


def list_buses(
    db: Session,
    *,
    event_id: int,
    trip_leg_id: int | None = None,
    search: str | None = None,
) -> list[tuple[Bus, int]]:
    """Xe kèm số người đã xếp, đếm bằng subquery gộp để không N+1."""
    assigned = (
        select(BusAssignment.bus_id, func.count(BusAssignment.id).label("assigned"))
        .group_by(BusAssignment.bus_id)
        .subquery()
    )
    query = (
        select(Bus, func.coalesce(assigned.c.assigned, 0))
        .outerjoin(assigned, assigned.c.bus_id == Bus.id)
        .join(TripLeg, TripLeg.id == Bus.trip_leg_id)
        .where(Bus.event_id == event_id)
        .options(
            selectinload(Bus.trip_leg),
            selectinload(Bus.pickup_point),
            selectinload(Bus.linked_flight),
        )
    )
    if trip_leg_id is not None:
        query = query.where(Bus.trip_leg_id == trip_leg_id)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(
            or_(
                Bus.bus_code.like(pattern),
                Bus.plate_number.like(pattern),
                Bus.leader_name.like(pattern),
            )
        )

    rows = db.execute(query.order_by(TripLeg.display_order, Bus.bus_code)).all()
    return [(bus, count) for bus, count in rows]


def get_bus(db: Session, *, event_id: int, bus_id: int) -> Bus:
    bus = db.scalar(
        select(Bus)
        .where(Bus.id == bus_id, Bus.event_id == event_id)
        .options(
            selectinload(Bus.trip_leg),
            selectinload(Bus.pickup_point),
            selectinload(Bus.linked_flight),
        )
    )
    if bus is None:
        raise NotFoundError(f"Không tìm thấy xe #{bus_id} trong kỳ này.", code="BUS_NOT_FOUND")
    return bus


def count_assigned(db: Session, bus_id: int) -> int:
    return (
        db.scalar(
            select(func.count()).select_from(BusAssignment).where(BusAssignment.bus_id == bus_id)
        )
        or 0
    )


# --- Ghi xe ---


def create_bus(
    db: Session,
    *,
    event: Event,
    data: dict[str, Any],
    actor: User,
    ip_address: str | None = None,
) -> Bus:
    _validate_refs(
        db,
        event=event,
        trip_leg_id=data["trip_leg_id"],
        pickup_point_id=data.get("pickup_point_id"),
        linked_flight_id=data.get("linked_flight_id"),
        leader_user_id=data.get("leader_user_id"),
    )

    bus = Bus(event_id=event.id, **data)
    _sync_leader_from_user(db, bus)
    db.add(bus)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise _duplicate_code(data.get("bus_code")) from exc

    audit_service.log(
        db,
        action="bus.created",
        entity_type="bus",
        entity_id=bus.id,
        actor_id=actor.id,
        event_id=event.id,
        after=audit_service.snapshot(bus, AUDITED_FIELDS),
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(bus)
    return bus


def update_bus(
    db: Session,
    *,
    event: Event,
    bus: Bus,
    data: dict[str, Any],
    actor: User,
    ip_address: str | None = None,
) -> Bus:
    if not data:
        return bus

    before = audit_service.snapshot(bus, AUDITED_FIELDS)
    assigned = count_assigned(db, bus.id)

    _validate_refs(
        db,
        event=event,
        trip_leg_id=bus.trip_leg_id,
        pickup_point_id=data.get("pickup_point_id"),
        linked_flight_id=data.get("linked_flight_id"),
    )

    if "capacity" in data and data["capacity"] < assigned:
        raise ConflictError(
            f"Xe {bus.bus_code} đã xếp {assigned} người, không thể hạ sức chứa xuống "
            f"{data['capacity']}. Chuyển người sang xe khác trước.",
            code="CAPACITY_BELOW_ASSIGNED",
            details={"assigned_count": assigned, "capacity": data["capacity"]},
        )

    _check_times(
        gather=data.get("gather_time", bus.gather_time),
        departure=data.get("departure_time", bus.departure_time),
    )

    for field, value in data.items():
        setattr(bus, field, value)

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise _duplicate_code(data.get("bus_code")) from exc

    after = audit_service.snapshot(bus, AUDITED_FIELDS)
    audit_service.log(
        db,
        action="bus.updated",
        entity_type="bus",
        entity_id=bus.id,
        actor_id=actor.id,
        event_id=event.id,
        before=before,
        after=audit_service.diff(before, after),
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(bus)
    return bus


def delete_bus(
    db: Session, *, event: Event, bus: Bus, actor: User, ip_address: str | None = None
) -> None:
    """Xoá xe. Chặn khi còn khách: cascade ORM sẽ xoá luôn phân xe mà không ai biết."""
    assigned = count_assigned(db, bus.id)
    if assigned:
        raise ConflictError(
            f"Xe {bus.bus_code} còn {assigned} người. Chuyển họ sang xe khác trước khi xoá.",
            code="BUS_HAS_PASSENGERS",
            details={"assigned_count": assigned},
        )

    snapshot = audit_service.snapshot(bus, AUDITED_FIELDS)
    bus_id = bus.id
    db.delete(bus)
    db.flush()
    audit_service.log(
        db,
        action="bus.deleted",
        entity_type="bus",
        entity_id=bus_id,
        actor_id=actor.id,
        event_id=event.id,
        before=snapshot,
        ip_address=ip_address,
    )
    db.commit()


def set_leader(
    db: Session,
    *,
    event: Event,
    bus: Bus,
    data: dict[str, Any],
    actor: User,
    ip_address: str | None = None,
) -> Bus:
    """Gán Trưởng xe là CBNV (lấy luôn tên, số điện thoại từ hồ sơ) hoặc người ngoài."""
    before = audit_service.snapshot(bus, _LEADER_FIELDS)

    if data.get("leader_user_id") is not None:
        bus.leader_user_id = data["leader_user_id"]
        _sync_leader_from_user(db, bus)
    else:
        bus.leader_user_id = None
        bus.leader_name = data.get("leader_name")
        bus.leader_phone = data.get("leader_phone")

    db.flush()
    audit_service.log(
        db,
        action="bus.leader_changed",
        entity_type="bus",
        entity_id=bus.id,
        actor_id=actor.id,
        event_id=event.id,
        before=before,
        after=audit_service.snapshot(bus, _LEADER_FIELDS),
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(bus)
    return bus


# --- Hành khách ---


def ensure_can_view_passengers(user: User, bus: Bus) -> None:
    """BTC xem mọi xe; Trưởng xe chỉ xem xe MÌNH phụ trách (docs/04 §7, vai trò 🔵).

    Danh sách có số điện thoại — lộ cho Trưởng xe khác là lộ dữ liệu cá nhân không cần thiết.
    """
    if user.role in _ADMIN_ROLES:
        return
    if bus.leader_user_id is not None and bus.leader_user_id == user.id:
        return
    raise PermissionDeniedError(
        "Chỉ Ban tổ chức và Trưởng xe của xe này xem được danh sách hành khách."
    )


def list_passengers(db: Session, *, bus: Bus) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(BusAssignment)
        .where(BusAssignment.bus_id == bus.id)
        .options(
            selectinload(BusAssignment.registration)
            .selectinload(Registration.user)
            .selectinload(User.team)
        )
    ).all()

    registration_ids = [row.registration_id for row in rows]
    pickups = _pickup_map(db, registration_ids)
    flights = _flight_map(db, registration_ids)
    point_names = _pickup_names(db, bus.event_id)
    direction = bus.trip_leg.direction

    passengers = []
    for row in rows:
        user = row.registration.user
        pickup_id = pickups.get((row.registration_id, bus.trip_leg_id))
        flight = flights.get((row.registration_id, direction))
        passengers.append(
            {
                "assignment_id": row.id,
                "registration_id": row.registration_id,
                "user_id": user.id,
                "full_name": user.full_name,
                "employee_code": user.employee_code,
                "phone": user.phone,
                "team_id": user.team_id,
                "team_name": user.team.name if user.team else None,
                "pickup_point_id": pickup_id,
                "pickup_point_name": point_names.get(pickup_id),
                "flight_code": flight[1] if flight else None,
                "assignment_mode": row.assignment_mode,
            }
        )

    # Theo team rồi tên: Trưởng xe điểm danh theo nhóm.
    passengers.sort(key=lambda item: (item["team_name"] or "", item["full_name"]))
    return passengers


# --- Phân xe tự động ---


def preview(
    db: Session, *, event: Event, trip_leg_id: int, force_reallocate: bool = False
) -> tuple[BusAllocationResult, TripLeg]:
    """Tính phân xe cho một chặng, KHÔNG ghi gì.

    Chặng có "gắn sân bay" hay không lấy từ `trip_legs.is_airport_linked` chứ không đoán
    theo mã chặng — số chặng và tính chất từng chặng là dữ liệu BTC khai (CLAUDE.md #3).
    """
    leg = _require_leg(db, event_id=event.id, trip_leg_id=trip_leg_id)
    riders = load_bus_riders(db, event_id=event.id, trip_leg=leg, keep_manual=not force_reallocate)
    buses = load_bus_slots(db, event_id=event.id, trip_leg_id=leg.id)

    result = allocate_buses(
        riders=riders,
        buses=buses,
        trip_leg_id=leg.id,
        airport_linked=leg.is_airport_linked,
    )
    return result, leg


def commit(
    db: Session,
    *,
    event: Event,
    trip_leg_id: int,
    actor: User,
    force_reallocate: bool = False,
    ip_address: str | None = None,
) -> tuple[BusAllocationResult, str, int]:
    """Chạy lại phân xe và ghi trong một transaction. Trả về (kết quả, mã chặng, số rác đã dọn)."""
    event_service.require_registration_closed(event)
    event_id, actor_id = event.id, actor.id

    with immediate_transaction(db):
        result, leg = preview(
            db, event=event, trip_leg_id=trip_leg_id, force_reallocate=force_reallocate
        )
        leg_id, leg_code = leg.id, leg.code
        removed_stale = _write_assignments(
            db,
            event_id=event_id,
            trip_leg_id=leg_id,
            result=result,
            actor_id=actor_id,
            force_reallocate=force_reallocate,
        )
        audit_service.log(
            db,
            action="bus.allocated",
            entity_type="bus_allocation",
            entity_id=leg_id,
            actor_id=actor_id,
            event_id=event_id,
            after={
                "trip_leg_id": leg_id,
                "trip_leg_code": leg_code,
                "force_reallocate": force_reallocate,
                "assigned": result.summary.assigned,
                "unassigned": result.summary.unassigned,
                "buses_used": result.summary.buses_used,
                "surplus_buses": result.summary.surplus_buses,
                "removed_stale": removed_stale,
            },
            ip_address=ip_address,
        )

    logger.info(
        "Đã ghi phân xe chặng %s: %s người, dọn %s bản ghi rác",
        leg_code,
        result.summary.assigned,
        removed_stale,
    )
    return result, leg_code, removed_stale


def _write_assignments(
    db: Session,
    *,
    event_id: int,
    trip_leg_id: int,
    result: BusAllocationResult,
    actor_id: int,
    force_reallocate: bool,
) -> int:
    """Thay các bản ghi phân xe của một chặng.

    Người không còn cần xe ở chặng này (bỏ tick, không tham gia, huỷ đăng ký) bị xoá bản
    ghi bất kể mode — để lại là họ chiếm một ghế không ai ngồi.
    """
    existing = {
        row.registration_id: row
        for row in db.scalars(select(BusAssignment).where(BusAssignment.trip_leg_id == trip_leg_id))
    }
    still_riding = set(
        db.scalars(
            select(Registration.id)
            .join(RegistrationBusNeed, RegistrationBusNeed.registration_id == Registration.id)
            .where(
                Registration.event_id == event_id,
                Registration.status == RegistrationStatus.SUBMITTED,
                Registration.is_participating.is_(True),
                RegistrationBusNeed.trip_leg_id == trip_leg_id,
                RegistrationBusNeed.needs_bus.is_(True),
            )
        ).all()
    )

    removed_stale = 0
    for registration_id, row in existing.items():
        if registration_id not in still_riding:
            db.delete(row)
            removed_stale += 1
        elif force_reallocate or not row.is_manual:
            db.delete(row)
    db.flush()

    now = utcnow_iso()
    for seat in result.assignments:
        if seat.pinned and not force_reallocate:
            continue  # bản ghi thủ công giữ nguyên, không chèn lại (UNIQUE registration+leg)
        db.add(
            BusAssignment(
                registration_id=seat.registration_id,
                bus_id=seat.bus_id,
                trip_leg_id=trip_leg_id,
                assignment_mode=AssignmentMode.AUTO,
                assigned_by=actor_id,
                assigned_at=now,
            )
        )
    db.flush()
    return removed_stale


# --- Danh sách phân xe & điều chỉnh ---


def list_assignments(
    db: Session,
    *,
    event_id: int,
    trip_leg_id: int | None = None,
    bus_id: int | None = None,
    team_id: int | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    query = (
        select(BusAssignment)
        .join(Bus, Bus.id == BusAssignment.bus_id)
        .join(Registration, Registration.id == BusAssignment.registration_id)
        .join(User, User.id == Registration.user_id)
        .where(Bus.event_id == event_id)
        .options(
            selectinload(BusAssignment.bus),
            selectinload(BusAssignment.registration)
            .selectinload(Registration.user)
            .selectinload(User.team),
        )
    )
    if trip_leg_id is not None:
        query = query.where(BusAssignment.trip_leg_id == trip_leg_id)
    if bus_id is not None:
        query = query.where(BusAssignment.bus_id == bus_id)
    if team_id is not None:
        query = query.where(User.team_id == team_id)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(
            or_(
                User.full_name.like(pattern),
                User.employee_code.like(pattern),
                Bus.bus_code.like(pattern),
            )
        )

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(Bus.bus_code, User.full_name).limit(limit).offset(offset)).all()
    return _assignment_rows(db, event_id, list(rows)), total


def move_assignment(
    db: Session,
    *,
    event: Event,
    assignment_id: int,
    bus_id: int,
    reason: str,
    actor: User,
    ip_address: str | None = None,
) -> tuple[dict[str, Any], list[Flag]]:
    """Chuyển một người sang xe khác cùng chặng. Sức chứa chặn cứng; lệch điểm đón hoặc
    chuyến bay chỉ cảnh báo — BTC được quyền quyết ngoại lệ, miễn là thấy và để lại lý do."""
    event_id, actor_id = event.id, actor.id

    with immediate_transaction(db):
        assignment = _require_assignment(db, event_id=event_id, assignment_id=assignment_id)
        target = get_bus(db, event_id=event_id, bus_id=bus_id)

        if target.trip_leg_id != assignment.trip_leg_id:
            raise AppError(
                f"Xe {target.bus_code} thuộc chặng khác. Mỗi chặng một người chỉ ngồi một xe "
                "của chính chặng đó.",
                code="TRIP_LEG_MISMATCH",
                details={"bus_trip_leg_id": target.trip_leg_id, "expected": assignment.trip_leg_id},
            )
        if target.id == assignment.bus_id:
            raise ConflictError(
                f"Người này đã ở xe {target.bus_code}.",
                code="ALREADY_ON_BUS",
                details={"bus_id": target.id},
            )

        occupied = (
            db.scalar(
                select(func.count())
                .select_from(BusAssignment)
                .where(
                    BusAssignment.bus_id == target.id,
                    BusAssignment.registration_id != assignment.registration_id,
                )
            )
            or 0
        )
        remaining = target.capacity - occupied
        if remaining < 1:
            raise ConflictError(
                f"Xe {target.bus_code} đã đủ {target.capacity} chỗ.",
                code="BUS_CAPACITY_EXCEEDED",
                details={"bus_id": target.id, "remaining": max(remaining, 0), "requested": 1},
            )

        previous_bus_id = assignment.bus_id
        assignment.bus_id = target.id
        # Đánh dấu manual: lần chạy auto sau phải tôn trọng quyết định này.
        assignment.assignment_mode = AssignmentMode.MANUAL
        assignment.assigned_by = actor_id
        assignment.assigned_at = utcnow_iso()
        db.flush()
        db.expire(assignment, ["bus"])

        row = _assignment_rows(db, event_id, [assignment])[0]
        warnings = _move_warnings(row, target)

        audit_service.log(
            db,
            action="bus_assignment.moved",
            entity_type="bus_assignment",
            entity_id=assignment.id,
            actor_id=actor_id,
            event_id=event_id,
            before={"bus_id": previous_bus_id},
            after={"bus_id": target.id, "assignment_mode": AssignmentMode.MANUAL},
            reason=reason,
            ip_address=ip_address,
        )

    return row, warnings


# --- Kiểm tra ---


def _validate_refs(
    db: Session,
    *,
    event: Event,
    trip_leg_id: int,
    pickup_point_id: int | None = None,
    linked_flight_id: int | None = None,
    leader_user_id: int | None = None,
) -> TripLeg:
    leg = _require_leg(db, event_id=event.id, trip_leg_id=trip_leg_id)

    if pickup_point_id is not None:
        point = db.get(PickupPoint, pickup_point_id)
        if point is None or point.event_id != event.id:
            raise NotFoundError(
                f"Không tìm thấy điểm đón #{pickup_point_id} trong kỳ này.",
                code="PICKUP_POINT_NOT_FOUND",
            )
        if point.trip_leg_id is not None and point.trip_leg_id != leg.id:
            raise AppError(
                f"Điểm đón '{point.name}' thuộc chặng khác, không gán cho xe chặng {leg.code} được.",
                code="PICKUP_POINT_LEG_MISMATCH",
                details={"pickup_trip_leg_id": point.trip_leg_id, "bus_trip_leg_id": leg.id},
            )

    if linked_flight_id is not None:
        flight = db.get(Flight, linked_flight_id)
        if flight is None or flight.event_id != event.id:
            raise NotFoundError(
                f"Không tìm thấy chuyến bay #{linked_flight_id} trong kỳ này.",
                code="FLIGHT_NOT_FOUND",
            )
        if flight.direction != leg.direction:
            raise AppError(
                f"Chuyến {flight.flight_code} bay chiều {flight.direction}, còn chặng "
                f"{leg.code} là chiều {leg.direction}.",
                code="FLIGHT_DIRECTION_MISMATCH",
                details={"flight_direction": flight.direction, "leg_direction": leg.direction},
            )

    if leader_user_id is not None:
        _require_active_user(db, leader_user_id)

    return leg


def _require_leg(db: Session, *, event_id: int, trip_leg_id: int) -> TripLeg:
    leg = db.get(TripLeg, trip_leg_id)
    if leg is None or leg.event_id != event_id:
        raise NotFoundError(
            f"Không tìm thấy chặng #{trip_leg_id} trong kỳ này.", code="TRIP_LEG_NOT_FOUND"
        )
    return leg


def _require_active_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise NotFoundError(f"Không tìm thấy CBNV #{user_id}.", code="USER_NOT_FOUND")
    return user


def _require_assignment(db: Session, *, event_id: int, assignment_id: int) -> BusAssignment:
    assignment = db.scalar(
        select(BusAssignment)
        .join(Bus, Bus.id == BusAssignment.bus_id)
        .where(BusAssignment.id == assignment_id, Bus.event_id == event_id)
        .options(
            selectinload(BusAssignment.registration)
            .selectinload(Registration.user)
            .selectinload(User.team)
        )
    )
    if assignment is None:
        raise NotFoundError(
            f"Không tìm thấy phân xe #{assignment_id} trong kỳ này.", code="ASSIGNMENT_NOT_FOUND"
        )
    return assignment


def _check_times(*, gather: str | None, departure: str | None) -> None:
    if gather and departure and from_iso(departure) < from_iso(gather):
        raise AppError(
            "Giờ xe chạy không thể trước giờ tập trung.",
            code="INVALID_BUS_TIME",
            details={"gather_time": gather, "departure_time": departure},
        )


def _duplicate_code(bus_code: str | None) -> ConflictError:
    return ConflictError(
        f"Mã xe '{bus_code}' đã có ở chặng này.",
        code="BUS_CODE_DUPLICATED",
        details={"bus_code": bus_code},
    )


def _sync_leader_from_user(db: Session, bus: Bus) -> None:
    """Trưởng xe là CBNV thì lấy tên và số điện thoại từ hồ sơ — một nguồn duy nhất."""
    if bus.leader_user_id is None:
        return
    user = _require_active_user(db, bus.leader_user_id)
    bus.leader_name = user.full_name
    bus.leader_phone = user.phone


# --- Dựng dòng hiển thị ---


def _assignment_rows(db: Session, event_id: int, rows: list[BusAssignment]) -> list[dict[str, Any]]:
    """Dựng dòng phân xe kèm điểm đón và chuyến bay của từng người, truy vấn gộp một lần."""
    registration_ids = [row.registration_id for row in rows]
    pickups = _pickup_map(db, registration_ids)
    flights = _flight_map(db, registration_ids)
    point_names = _pickup_names(db, event_id)
    leg_directions = {
        leg.id: leg.direction
        for leg in db.scalars(select(TripLeg).where(TripLeg.event_id == event_id))
    }

    result = []
    for row in rows:
        user = row.registration.user
        bus = row.bus
        pickup_id = pickups.get((row.registration_id, row.trip_leg_id))
        flight = flights.get((row.registration_id, leg_directions.get(row.trip_leg_id)))
        result.append(
            {
                "id": row.id,
                "registration_id": row.registration_id,
                "user_id": user.id,
                "full_name": user.full_name,
                "team_id": user.team_id,
                "team_name": user.team.name if user.team else None,
                "bus_id": bus.id,
                "bus_code": bus.bus_code,
                "trip_leg_id": row.trip_leg_id,
                "pickup_point_id": pickup_id,
                "pickup_point_name": point_names.get(pickup_id),
                "flight_code": flight[1] if flight else None,
                "pickup_mismatch": bus.pickup_point_id is not None
                and pickup_id is not None
                and bus.pickup_point_id != pickup_id,
                "flight_mismatch": bus.linked_flight_id is not None
                and flight is not None
                and bus.linked_flight_id != flight[0],
                "assignment_mode": row.assignment_mode,
                "assigned_at": row.assigned_at,
            }
        )
    return result


def _move_warnings(row: dict[str, Any], target: Bus) -> list[Flag]:
    warnings = []
    if row["pickup_mismatch"]:
        warnings.append(
            Flag(
                type=WARN_PICKUP_MISMATCH,
                severity=SEVERITY_WARNING,
                message=(
                    f"{row['full_name']} chọn điểm đón {row['pickup_point_name'] or 'khác'} "
                    f"nhưng xe {target.bus_code} đón ở điểm khác. Báo lại cho người này."
                ),
                registration_id=row["registration_id"],
                team_id=row["team_id"],
                details={"bus_id": target.id},
            )
        )
    if row["flight_mismatch"]:
        warnings.append(
            Flag(
                type=FLAG_MIXED_FLIGHT_ON_BUS,
                severity=SEVERITY_WARNING,
                message=(
                    f"{row['full_name']} bay chuyến {row['flight_code']} nhưng xe "
                    f"{target.bus_code} phục vụ chuyến khác — kiểm tra giờ tập trung."
                ),
                registration_id=row["registration_id"],
                team_id=row["team_id"],
                details={"bus_id": target.id},
            )
        )
    return warnings


def _pickup_map(db: Session, registration_ids: list[int]) -> dict[tuple[int, int], int | None]:
    if not registration_ids:
        return {}
    rows = db.execute(
        select(
            RegistrationBusNeed.registration_id,
            RegistrationBusNeed.trip_leg_id,
            RegistrationBusNeed.pickup_point_id,
        ).where(RegistrationBusNeed.registration_id.in_(registration_ids))
    ).all()
    return {(registration_id, leg_id): pickup for registration_id, leg_id, pickup in rows}


def _flight_map(db: Session, registration_ids: list[int]) -> dict[tuple[int, str], tuple[int, str]]:
    if not registration_ids:
        return {}
    rows = db.execute(
        select(
            FlightAssignment.registration_id,
            FlightAssignment.direction,
            Flight.id,
            Flight.flight_code,
        )
        .join(Flight, Flight.id == FlightAssignment.flight_id)
        .where(FlightAssignment.registration_id.in_(registration_ids))
    ).all()
    return {
        (registration_id, direction): (flight_id, code)
        for registration_id, direction, flight_id, code in rows
    }


def _pickup_names(db: Session, event_id: int) -> dict[int, str]:
    return {
        point.id: point.name
        for point in db.scalars(select(PickupPoint).where(PickupPoint.event_id == event_id))
    }
