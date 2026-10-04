"""Nghiệp vụ xe: CRUD, Trưởng xe, phân xe tự động và điều chỉnh thủ công.

Cùng các luật với chuyến bay (bước 11-13):
- Ghế trống luôn được TÍNH từ `registration_legs`, không lưu cột.
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
from app.models.enums import AssignmentMode, EventStatus, RegistrationStatus, UserRole
from app.models.event import Event
from app.models.flight import Flight, FlightAssignment
from app.models.registration import Registration, RegistrationLeg
from app.models.transportation import Bus, PickupPoint, TripLeg
from app.models.user import User
from app.services import audit_service, event_service, transport_timing_service
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
    "note",
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
        select(RegistrationLeg.bus_id, func.count(RegistrationLeg.id).label("assigned"))
        .group_by(RegistrationLeg.bus_id)
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
            select(func.count()).select_from(RegistrationLeg).where(RegistrationLeg.bus_id == bus_id)
        )
        or 0
    )


def list_led_buses(db: Session, *, event: Event, user: User) -> list[tuple[Bus, int]]:
    """Dữ liệu cho F6: xe phụ trách, kể cả người không đăng ký/không ngồi trên xe."""
    if not EventStatus(event.status).at_least(EventStatus.INFORMATION_PUBLISHED):
        return []
    # Lọc ngay trong SQL, không phụ thuộc vai trò Trưởng nhóm hay đăng ký của người xem.
    assigned = (
        select(RegistrationLeg.bus_id, func.count(RegistrationLeg.id).label("assigned"))
        .group_by(RegistrationLeg.bus_id).subquery()
    )
    rows = db.execute(
        select(Bus, func.coalesce(assigned.c.assigned, 0))
        .outerjoin(assigned, assigned.c.bus_id == Bus.id)
        .join(TripLeg, TripLeg.id == Bus.trip_leg_id)
        .where(Bus.event_id == event.id, Bus.leader_user_id == user.id)
        .options(selectinload(Bus.trip_leg), selectinload(Bus.pickup_point),
                 selectinload(Bus.linked_flight))
        .order_by(TripLeg.display_order, Bus.bus_code)
    ).all()
    return [(bus, count) for bus, count in rows]


def list_unassigned(
    db: Session, *, event_id: int, trip_leg_id: int,
    pickup_point_id: int | None = None, team_id: int | None = None,
    search: str | None = None, limit: int = 50, offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    leg = _require_leg(db, event_id=event_id, trip_leg_id=trip_leg_id)
    query = (
        select(RegistrationLeg)
        .join(Registration, Registration.id == RegistrationLeg.registration_id)
        .join(User, User.id == Registration.user_id)
        .where(Registration.event_id == event_id,
               Registration.status == RegistrationStatus.SUBMITTED,
               Registration.is_participating.is_(True),
               RegistrationLeg.trip_leg_id == leg.id,
               RegistrationLeg.needs_bus.is_(True), RegistrationLeg.bus_id.is_(None))
        .options(selectinload(RegistrationLeg.pickup_point),
                 selectinload(RegistrationLeg.registration)
                 .selectinload(Registration.user).selectinload(User.team))
    )
    if pickup_point_id is not None:
        query = query.where(RegistrationLeg.pickup_point_id == pickup_point_id)
    if team_id is not None:
        query = query.where(User.team_id == team_id)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(or_(User.full_name.like(pattern), User.employee_code.like(pattern)))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(RegistrationLeg.pickup_point_id, User.full_name,
                                   RegistrationLeg.id).limit(limit).offset(offset)).all()
    flights = _flight_map(db, [row.registration_id for row in rows])
    result = []
    for row in rows:
        user = row.registration.user
        flight = flights.get((row.registration_id, leg.direction))
        result.append({
            "id": row.id, "registration_id": row.registration_id, "user_id": user.id,
            "full_name": user.full_name, "employee_code": user.employee_code, "phone": user.phone,
            "team_id": user.team_id, "team_name": user.team.name if user.team else None,
            "trip_leg_id": row.trip_leg_id, "pickup_point_id": row.pickup_point_id,
            "pickup_point_name": row.pickup_point.name if row.pickup_point else None,
            "flight_id": flight[0] if flight else None, "flight_code": flight[1] if flight else None,
        })
    return result, total


# --- Ghi xe ---


def create_bus(
    db: Session,
    *,
    event: Event,
    data: dict[str, Any],
    actor: User,
    ip_address: str | None = None,
) -> Bus:
    leg = _validate_refs(
        db,
        event=event,
        trip_leg_id=data["trip_leg_id"],
        pickup_point_id=data.get("pickup_point_id"),
        linked_flight_id=data.get("linked_flight_id"),
        leader_user_id=data.get("leader_user_id"),
    )
    transport_timing_service.check_bus_change(
        db,
        event_id=event.id,
        leg=leg,
        bus_id=None,
        bus_code=data["bus_code"],
        linked_flight_id=data.get("linked_flight_id"),
        departure_time=data.get("departure_time"),
        gather_time=data.get("gather_time"),
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

    event_id, bus_id = event.id, bus.id
    with immediate_transaction(db):
        bus = get_bus(db, event_id=event_id, bus_id=bus_id)
        before = audit_service.snapshot(bus, AUDITED_FIELDS)
        assigned = count_assigned(db, bus.id)

        leg = _validate_refs(
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
        # Giờ xe phải khớp cả chuyến được gắn lẫn chuyến của người đang ngồi trên xe. Chỉ kiểm khi
        # đổi giờ / chuyến gắn: sửa biển số một xe đã lệch từ trước không nên bị chặn.
        if {"gather_time", "departure_time", "linked_flight_id"} & data.keys():
            transport_timing_service.check_bus_change(
                db,
                event_id=event.id,
                leg=leg,
                bus_id=bus.id,
                bus_code=data.get("bus_code", bus.bus_code),
                linked_flight_id=data.get("linked_flight_id", bus.linked_flight_id),
                departure_time=data.get("departure_time", bus.departure_time),
                gather_time=data.get("gather_time", bus.gather_time),
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

    db.refresh(bus)
    return bus


def delete_bus(
    db: Session, *, event: Event, bus: Bus, actor: User, ip_address: str | None = None
) -> None:
    """Xoá xe; kiểm tra còn khách trong cùng transaction ghi."""
    event_id, bus_id = event.id, bus.id
    with immediate_transaction(db):
        bus = get_bus(db, event_id=event_id, bus_id=bus_id)
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


def ensure_can_view_passengers(user: User, bus: Bus, *, event: Event) -> None:
    """BTC xem mọi xe; Trưởng xe chỉ xem xe MÌNH phụ trách (docs/04 §7, vai trò 🔵).

    Danh sách có số điện thoại — lộ cho Trưởng xe khác là lộ dữ liệu cá nhân không cần thiết.
    """
    if user.role in _ADMIN_ROLES:
        return
    if bus.leader_user_id is not None and bus.leader_user_id == user.id:
        if not EventStatus(event.status).at_least(EventStatus.INFORMATION_PUBLISHED):
            raise PermissionDeniedError("Thông tin xe chưa được công bố.", code="BUS_NOT_PUBLISHED")
        return
    raise PermissionDeniedError(
        "Chỉ Ban tổ chức và Trưởng xe của xe này xem được danh sách hành khách."
    )


def list_passengers(db: Session, *, bus: Bus) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(RegistrationLeg)
        .where(RegistrationLeg.bus_id == bus.id)
        .options(
            selectinload(RegistrationLeg.registration)
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
    expected_assignments: list[dict[str, Any]] | None = None,
    ip_address: str | None = None,
) -> tuple[BusAllocationResult, str, int]:
    """Chạy lại phân xe và ghi trong một transaction. Trả về (kết quả, mã chặng, số rác đã dọn)."""
    event_service.require_registration_closed(event)
    event_id, actor_id = event.id, actor.id

    with immediate_transaction(db):
        result, leg = preview(
            db, event=event, trip_leg_id=trip_leg_id, force_reallocate=force_reallocate
        )
        if expected_assignments is not None:
            expected = sorted((item["registration_id"], item["bus_id"], item["pinned"])
                              for item in expected_assignments)
            actual = sorted((seat.registration_id, seat.bus_id, seat.pinned)
                            for seat in result.assignments)
            if expected != actual:
                raise ConflictError("Phân xe đã thay đổi. Vui lòng xem trước lại.",
                                    code="BUS_ALLOCATION_PREVIEW_STALE")
        if any(load.assigned > load.capacity for load in result.buses):
            raise ConflictError("Bản phân xe có xe vượt sức chứa. Chuyển người trước khi ghi.",
                                code="BUS_CAPACITY_EXCEEDED")
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
    """Cập nhật phần phân bổ; giữ ID, nhu cầu, điểm đón và ghi chú đăng ký."""
    existing = {
        row.registration_id: row
        for row in db.scalars(
            select(RegistrationLeg)
            .join(Registration, Registration.id == RegistrationLeg.registration_id)
            .where(Registration.event_id == event_id, RegistrationLeg.trip_leg_id == trip_leg_id)
            .options(selectinload(RegistrationLeg.registration))
        )
    }
    removed_stale = 0
    for row in existing.values():
        registration = row.registration
        eligible = (
            registration.status == RegistrationStatus.SUBMITTED
            and registration.is_participating and row.needs_bus
        )
        if not eligible:
            if row.bus_id is not None:
                removed_stale += 1
            _clear_assignment(row)
        elif force_reallocate or not row.is_manual:
            _clear_assignment(row)

    now = utcnow_iso()
    for seat in result.assignments:
        if seat.pinned and not force_reallocate:
            continue
        row = existing[seat.registration_id]
        row.bus_id = seat.bus_id
        row.assignment_mode = AssignmentMode.AUTO
        row.assigned_by = actor_id
        row.assigned_at = now
    db.flush()
    return removed_stale


def _clear_assignment(row: RegistrationLeg) -> None:
    row.bus_id = None
    row.assignment_mode = None
    row.assigned_by = None
    row.assigned_at = None
    row.assignment_note = None


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
        select(RegistrationLeg)
        .join(Bus, Bus.id == RegistrationLeg.bus_id)
        .join(Registration, Registration.id == RegistrationLeg.registration_id)
        .join(User, User.id == Registration.user_id)
        .where(Bus.event_id == event_id)
        .options(
            selectinload(RegistrationLeg.bus),
            selectinload(RegistrationLeg.registration)
            .selectinload(Registration.user)
            .selectinload(User.team),
        )
    )
    if trip_leg_id is not None:
        query = query.where(RegistrationLeg.trip_leg_id == trip_leg_id)
    if bus_id is not None:
        query = query.where(RegistrationLeg.bus_id == bus_id)
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
    reason = _validate_reason(reason)
    event_id, actor_id = event.id, actor.id

    with immediate_transaction(db):
        assignment = _require_assignment(db, event_id=event_id, assignment_id=assignment_id)
        if not assignment.registration.is_active_participant or not assignment.needs_bus:
            raise AppError("Người này không còn đăng ký đi xe ở chặng này.",
                           code="BUS_NOT_REQUESTED")
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
                .select_from(RegistrationLeg)
                .where(
                    RegistrationLeg.bus_id == target.id,
                    RegistrationLeg.registration_id != assignment.registration_id,
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

        transport_timing_service.check_rider(
            db,
            bus=target,
            registration_id=assignment.registration_id,
            full_name=assignment.registration.user.full_name,
        )

        previous_bus_id = assignment.bus_id
        assignment.bus_id = target.id
        # Đánh dấu manual: lần chạy auto sau phải tôn trọng quyết định này.
        assignment.assignment_mode = AssignmentMode.MANUAL
        assignment.assigned_by = actor_id
        assignment.assigned_at = utcnow_iso()
        assignment.assignment_note = reason
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


def assign_rider(
    db: Session,
    *,
    event: Event,
    registration_id: int,
    bus_id: int,
    reason: str,
    actor: User,
    ip_address: str | None = None,
) -> tuple[dict[str, Any], list[Flag]]:
    """Xếp tay một người CHƯA có xe ở chặng của xe này (cột "Chưa có xe" trên màn hình).

    Chỉ nhận người thật sự đăng ký đi xe ở chặng đó: xếp người không cần xe là chiếm ghế của
    người khác, và lần chạy phân xe sau cũng dọn bản ghi đó đi. Người đã có xe thì phải
    chuyển (PATCH) — không tạo bản ghi thứ hai cho cùng một chặng.
    """
    reason = _validate_reason(reason)
    event_id, actor_id = event.id, actor.id

    with immediate_transaction(db):
        target = get_bus(db, event_id=event_id, bus_id=bus_id)
        leg_id, leg_name = target.trip_leg_id, target.trip_leg.name

        registration = db.scalar(
            select(Registration).where(
                Registration.id == registration_id,
                Registration.event_id == event_id,
                Registration.status == RegistrationStatus.SUBMITTED,
                Registration.is_participating.is_(True),
            )
        )
        if registration is None:
            raise NotFoundError(
                f"Không tìm thấy người tham gia #{registration_id} trong kỳ này.",
                code="REGISTRATION_NOT_FOUND",
            )

        existing = db.scalar(
            select(RegistrationLeg).where(
                RegistrationLeg.registration_id == registration_id,
                RegistrationLeg.trip_leg_id == leg_id,
                RegistrationLeg.needs_bus.is_(True),
            )
        )
        if existing is None:
            raise AppError(
                f"Người này không đăng ký đi xe ở chặng {leg_name}.",
                code="BUS_NOT_REQUESTED", details={"trip_leg_id": leg_id},
            )
        if existing.bus_id is not None:
            raise ConflictError(
                "Người này đã có xe ở chặng này. Dùng chức năng chuyển xe thay vì xếp mới.",
                code="ALREADY_ASSIGNED_ON_LEG",
                details={"assignment_id": existing.id, "bus_id": existing.bus_id},
            )

        if count_assigned(db, target.id) >= target.capacity:
            raise ConflictError(
                f"Xe {target.bus_code} đã đủ {target.capacity} chỗ.",
                code="BUS_CAPACITY_EXCEEDED",
                details={"bus_id": target.id, "remaining": 0, "requested": 1},
            )

        transport_timing_service.check_rider(
            db, bus=target, registration_id=registration_id, full_name=registration.user.full_name
        )

        existing.bus_id = target.id
        existing.assignment_mode = AssignmentMode.MANUAL
        existing.assigned_by = actor_id
        existing.assigned_at = utcnow_iso()
        existing.assignment_note = reason
        db.flush()
        db.expire(existing, ["bus"])

        assignment = _require_assignment(db, event_id=event_id, assignment_id=existing.id)
        row = _assignment_rows(db, event_id, [assignment])[0]
        warnings = _move_warnings(row, target)

        audit_service.log(
            db,
            action="bus_assignment.created",
            entity_type="bus_assignment",
            entity_id=assignment.id,
            actor_id=actor_id,
            event_id=event_id,
            after={
                "registration_id": registration_id,
                "bus_id": target.id,
                "assignment_mode": AssignmentMode.MANUAL,
            },
            reason=reason,
            ip_address=ip_address,
        )

    return row, warnings


def remove_assignment(
    db: Session,
    *,
    event: Event,
    assignment_id: int,
    reason: str,
    actor: User,
    ip_address: str | None = None,
) -> None:
    """Bỏ xếp xe của một người, bắt buộc có lý do.

    Người đó vẫn đăng ký cần xe, nên lần chạy phân xe tự động sau sẽ xếp lại họ. Muốn họ không
    đi xe hẳn thì CBNV phải bỏ nhu cầu xe trong đăng ký.
    """
    reason = _validate_reason(reason)
    event_id, actor_id = event.id, actor.id

    with immediate_transaction(db):
        assignment = _require_assignment(db, event_id=event_id, assignment_id=assignment_id)
        snapshot = {
            "registration_id": assignment.registration_id,
            "bus_id": assignment.bus_id,
            "trip_leg_id": assignment.trip_leg_id,
            "assignment_mode": assignment.assignment_mode,
        }
        _clear_assignment(assignment)
        db.flush()
        audit_service.log(
            db,
            action="bus_assignment.removed",
            entity_type="bus_assignment",
            entity_id=assignment_id,
            actor_id=actor_id,
            event_id=event_id,
            before=snapshot,
            reason=reason,
            ip_address=ip_address,
        )


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


def _require_assignment(db: Session, *, event_id: int, assignment_id: int) -> RegistrationLeg:
    assignment = db.scalar(
        select(RegistrationLeg)
        .join(Bus, Bus.id == RegistrationLeg.bus_id)
        .where(RegistrationLeg.id == assignment_id, Bus.event_id == event_id)
        .options(
            selectinload(RegistrationLeg.registration)
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


def _assignment_rows(db: Session, event_id: int, rows: list[RegistrationLeg]) -> list[dict[str, Any]]:
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
                "employee_code": user.employee_code,
                "phone": user.phone,
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
                "assignment_note": row.assignment_note,
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
            RegistrationLeg.registration_id,
            RegistrationLeg.trip_leg_id,
            RegistrationLeg.pickup_point_id,
        ).where(RegistrationLeg.registration_id.in_(registration_ids))
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


def _validate_reason(reason: str) -> str:
    reason = reason.strip()
    if len(reason) < 3 or len(reason) > 500:
        raise AppError("Lý do phải có từ 3 đến 500 ký tự.", code="BUS_REASON_INVALID", status_code=422)
    return reason
