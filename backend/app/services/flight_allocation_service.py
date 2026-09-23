"""Ghi kết quả phân bổ chuyến bay và điều chỉnh thủ công.

Thuật toán nằm ở `services/allocator/` và không biết gì về DB. File này là lớp giữa:
đọc dữ liệu, gọi thuật toán, rồi ghi trong MỘT transaction.

Hai điểm sinh tử:

1. **`BEGIN IMMEDIATE` cho mọi thao tác ghi.** Hai BTC bấm cùng lúc, hoặc một người bấm
   "phân bổ" trong khi người kia đang chuyển một CBNV: nếu chỉ dùng transaction đọc rồi
   nâng lên ghi, cả hai đọc "còn 1 chỗ" rồi cả hai ghi -> vượt số ghế đã mua. Giành
   write-lock ngay từ đầu là cách duy nhất SQLite chặn được việc đó.
2. **Đếm lại slot NGAY TRONG transaction** trước khi ghi. Số liệu preview BTC đang xem có
   thể đã cũ vài phút.
"""

import logging
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.database import immediate_transaction
from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.core.timeutils import utcnow_iso
from app.models.enums import AssignmentMode, RegistrationStatus
from app.models.event import Event
from app.models.flight import Flight, FlightAssignment, Shift
from app.models.registration import Registration
from app.models.user import User
from app.services import audit_service, event_service, flight_service, transport_timing_service
from app.services.allocator import (
    DEFAULT_SEED,
    SEVERITY_WARNING,
    AllocationResult,
    Flag,
    allocate_flights,
    load_flight_slots,
    load_params,
    load_participants,
)

logger = logging.getLogger(__name__)

# Cảnh báo của thao tác thủ công — không chặn, nhưng phải hiện cho BTC thấy (docs/05 §5).
WARN_SHIFT_MISMATCH = "SHIFT_NOT_SATISFIED"
WARN_TEAM_SPLIT = "TEAM_SPLIT"
WARN_MISSING_ID_CARD = "MISSING_ID_CARD"
WARN_BUS_TIME_MISMATCH = "BUS_TIME_MISMATCH"


# --- Chạy thuật toán ---


def preview(
    db: Session,
    *,
    event: Event,
    direction: str,
    force_reallocate: bool = False,
    seed: int | None = None,
) -> AllocationResult:
    """Tính kết quả phân bổ, KHÔNG ghi gì."""
    participants = load_participants(
        db, event_id=event.id, direction=direction, keep_manual=not force_reallocate
    )
    flights = load_flight_slots(db, event_id=event.id, direction=direction)
    params = load_params(db, event_id=event.id)

    result = allocate_flights(
        participants=participants,
        flights=flights,
        direction=direction,
        params=params,
        seed=seed if seed is not None else DEFAULT_SEED,
    )
    logger.info(
        "Preview phân bổ %s: %s/%s người có chỗ, %s team bị tách",
        direction,
        result.summary.assigned,
        result.summary.total_participants,
        result.summary.teams_split,
    )
    return result


def commit(
    db: Session,
    *,
    event: Event,
    direction: str,
    actor: User,
    force_reallocate: bool = False,
    seed: int | None = None,
    ip_address: str | None = None,
) -> tuple[AllocationResult, int]:
    """Chạy phân bổ và ghi vào `flight_assignments`. Trả về (kết quả, số bản ghi rác đã dọn).

    Tính LẠI trong transaction thay vì áp bản preview BTC đang xem: giữa lúc xem và lúc
    bấm, có thể đã có người huỷ đăng ký hoặc BTC vừa đổi sức chứa một chuyến.
    """
    _require_registration_closed(event)

    event_id, actor_id = event.id, actor.id

    with immediate_transaction(db):
        result = preview(
            db,
            event=event,
            direction=direction,
            force_reallocate=force_reallocate,
            seed=seed,
        )
        removed_stale = _write_assignments(
            db,
            event_id=event_id,
            direction=direction,
            result=result,
            actor_id=actor_id,
            force_reallocate=force_reallocate,
        )

        audit_service.log(
            db,
            action="flight.allocated",
            entity_type="flight_allocation",
            entity_id=event_id,
            actor_id=actor_id,
            event_id=event_id,
            after={
                "direction": direction,
                "seed": result.seed,
                "force_reallocate": force_reallocate,
                "assigned": result.summary.assigned,
                "unassigned": result.summary.unassigned,
                "teams_split": result.summary.teams_split,
                "shift_satisfaction_rate": result.summary.shift_satisfaction_rate,
                "score": result.summary.score,
                "removed_stale": removed_stale,
                "params": result.params,
            },
            ip_address=ip_address,
        )

    logger.info(
        "Đã ghi phân bổ %s: %s người, dọn %s bản ghi rác",
        direction,
        result.summary.assigned,
        removed_stale,
    )
    return result, removed_stale


def _write_assignments(
    db: Session,
    *,
    event_id: int,
    direction: str,
    result: AllocationResult,
    actor_id: int,
    force_reallocate: bool,
) -> int:
    """Thay thế các bản ghi phân bổ của một chiều.

    Bản ghi `manual` được giữ nguyên trừ khi `force_reallocate`. Bản ghi của người đã huỷ
    đăng ký bị xoá bất kể mode: để lại thì họ vẫn chiếm một ghế không ai ngồi, và mọi phép
    đếm slot sau đó đều sai.
    """
    existing = {
        row.registration_id: row
        for row in db.scalars(
            select(FlightAssignment)
            .join(Registration, Registration.id == FlightAssignment.registration_id)
            .where(Registration.event_id == event_id, FlightAssignment.direction == direction)
        )
    }
    still_participating = _participating_ids(db, event_id)

    removed_stale = 0
    for registration_id, row in existing.items():
        if registration_id not in still_participating:
            db.delete(row)
            removed_stale += 1
        elif force_reallocate or not row.is_manual:
            db.delete(row)
    db.flush()

    now = utcnow_iso()
    for assignment in result.assignments:
        # Bản ghi thủ công giữ nguyên nên không chèn lại (tránh vi phạm UNIQUE
        # (registration_id, direction)).
        if assignment.pinned and not force_reallocate:
            continue
        db.add(
            FlightAssignment(
                registration_id=assignment.registration_id,
                flight_id=assignment.flight_id,
                direction=direction,
                assignment_mode=AssignmentMode.AUTO,
                assigned_by=actor_id,
                assigned_at=now,
            )
        )
    db.flush()
    return removed_stale


def reset_allocation(
    db: Session,
    *,
    event: Event,
    direction: str,
    actor: User,
    reason: str,
    include_manual: bool = False,
    ip_address: str | None = None,
) -> dict[str, int]:
    """Gỡ mọi người khỏi chuyến bay của một chiều — trả chuyến về trống.

    Để BTC sửa được sức chứa: hạ số ghế dưới số người đang ngồi bị chặn (`flight_service`),
    nên muốn chỉnh lại số ghế thật sự mua được thì phải dọn phân bổ trước rồi chạy lại.
    Giữ bản ghi BTC gán tay trừ khi `include_manual` — xoá quyết định của con người phải là
    lựa chọn có ý thức, giống `force_reallocate` (docs/05 §5).
    """
    event_id, actor_id = event.id, actor.id

    with immediate_transaction(db):
        rows = db.scalars(
            select(FlightAssignment)
            .join(Registration, Registration.id == FlightAssignment.registration_id)
            .where(Registration.event_id == event_id, FlightAssignment.direction == direction)
        ).all()

        removed = 0
        kept_manual = 0
        for row in rows:
            if row.is_manual and not include_manual:
                kept_manual += 1
                continue
            db.delete(row)
            removed += 1
        db.flush()

        audit_service.log(
            db,
            action="flight_allocation.reset",
            entity_type="flight_allocation",
            entity_id=event_id,
            actor_id=actor_id,
            event_id=event_id,
            before={"assignments": len(rows)},
            after={
                "direction": direction,
                "removed": removed,
                "kept_manual": kept_manual,
                "include_manual": include_manual,
            },
            reason=reason,
            ip_address=ip_address,
        )

    logger.info(
        "Đã bỏ phân bổ %s: xoá %s, giữ %s bản ghi thủ công", direction, removed, kept_manual
    )
    return {"removed": removed, "kept_manual": kept_manual}


# --- Danh sách phân bổ ---


def list_assignments(
    db: Session,
    *,
    event_id: int,
    direction: str | None = None,
    flight_id: int | None = None,
    team_id: int | None = None,
    mode: str | None = None,
    shift_mismatch: bool | None = None,
    missing_documents: bool | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    query = (
        select(FlightAssignment)
        .join(Registration, Registration.id == FlightAssignment.registration_id)
        .join(User, User.id == Registration.user_id)
        .join(Flight, Flight.id == FlightAssignment.flight_id)
        .where(Registration.event_id == event_id)
        .options(
            selectinload(FlightAssignment.flight).selectinload(Flight.shift),
            selectinload(FlightAssignment.registration)
            .selectinload(Registration.user)
            .selectinload(User.team),
            selectinload(FlightAssignment.registration).selectinload(Registration.shift),
        )
    )

    if direction:
        query = query.where(FlightAssignment.direction == direction)
    if flight_id is not None:
        query = query.where(FlightAssignment.flight_id == flight_id)
    if team_id is not None:
        query = query.where(User.team_id == team_id)
    if mode:
        query = query.where(FlightAssignment.assignment_mode == mode)
    if missing_documents is not None:
        missing = or_(
            User.id_card_number.is_(None),
            User.id_card_number == "",
            User.date_of_birth.is_(None),
        )
        query = query.where(missing if missing_documents else ~missing)
    if shift_mismatch is not None:
        # Lệch ca = có nguyện vọng và ca của chuyến khác nguyện vọng đó.
        mismatch = Registration.shift_id.is_not(None) & (
            Flight.shift_id != Registration.shift_id
        )
        query = query.where(mismatch if shift_mismatch else ~mismatch)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(
            or_(
                User.full_name.like(pattern),
                User.employee_code.like(pattern),
                Flight.flight_code.like(pattern),
            )
        )

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(
        query.order_by(Flight.departure_time, User.full_name).limit(limit).offset(offset)
    ).all()
    return [_to_row(row) for row in rows], total


def _to_row(assignment: FlightAssignment) -> dict[str, Any]:
    registration = assignment.registration
    user = registration.user
    flight = assignment.flight
    requested = registration.shift

    return {
        "id": assignment.id,
        "registration_id": registration.id,
        "user_id": user.id,
        "full_name": user.full_name,
        "employee_code": user.employee_code,
        "team_id": user.team_id,
        "team_name": user.team.name if user.team else None,
        "flight_id": flight.id,
        "flight_code": flight.flight_code,
        "direction": assignment.direction,
        "flight_shift_id": flight.shift_id,
        "requested_shift_id": registration.shift_id,
        "requested_shift_code": requested.code if requested else None,
        "shift_mismatch": bool(registration.shift_id) and flight.shift_id != registration.shift_id,
        "shift_locked": registration.is_shift_locked,
        "seat_number": assignment.seat_number,
        "ticket_code": assignment.ticket_code,
        "assignment_mode": assignment.assignment_mode,
        "assigned_at": assignment.assigned_at,
        "assigned_by": assignment.assigned_by,
        "note": assignment.note,
        "has_flight_documents": user.can_fly,
    }


# --- Điều chỉnh thủ công ---


def move_assignment(
    db: Session,
    *,
    event: Event,
    assignment_id: int,
    flight_id: int,
    reason: str,
    actor: User,
    ip_address: str | None = None,
) -> tuple[list[dict[str, Any]], list[Flag]]:
    """Chuyển một người sang chuyến khác. Trả về (dòng đã đổi, cảnh báo)."""
    event_id, actor_id = event.id, actor.id

    with immediate_transaction(db):
        assignment = _require_assignment(db, event_id=event_id, assignment_id=assignment_id)
        target = _require_target_flight(
            db, event_id=event_id, flight_id=flight_id, direction=assignment.direction
        )

        if assignment.flight_id == target.id:
            raise ConflictError(
                f"Người này đã ở chuyến {target.flight_code}.",
                code="ALREADY_ON_FLIGHT",
                details={"flight_id": target.id},
            )

        _require_free_seats(db, target=target, needed=1, moving_in=[assignment.registration_id])
        warnings = _move_warnings(db, assignments=[assignment], target=target)
        rows = [_apply_move(db, assignment, target, actor_id)]

        audit_service.log(
            db,
            action="flight_assignment.moved",
            entity_type="flight_assignment",
            entity_id=assignment.id,
            actor_id=actor_id,
            event_id=event_id,
            before={"flight_id": rows[0]["previous_flight_id"]},
            after={"flight_id": target.id, "assignment_mode": AssignmentMode.MANUAL},
            reason=reason,
            ip_address=ip_address,
        )

    return [_to_row(assignment)], warnings


def bulk_move(
    db: Session,
    *,
    event: Event,
    registration_ids: list[int],
    flight_id: int,
    reason: str,
    actor: User,
    ip_address: str | None = None,
) -> tuple[list[dict[str, Any]], list[Flag], int]:
    """Chuyển cả nhóm sang một chuyến. Người chưa có phân bổ thì tạo mới.

    Kiểm tra sức chứa cho CẢ nhóm trước khi ghi: chuyển từng người một rồi hết chỗ giữa
    đường sẽ để lại một nửa nhóm ở chuyến cũ — trạng thái không ai muốn xử lý bằng tay.
    """
    event_id, actor_id = event.id, actor.id
    unique_ids = list(dict.fromkeys(registration_ids))

    with immediate_transaction(db):
        target = _require_target_flight(db, event_id=event_id, flight_id=flight_id)
        registrations = _require_registrations(db, event_id=event_id, registration_ids=unique_ids)

        existing = {
            row.registration_id: row
            for row in db.scalars(
                select(FlightAssignment).where(
                    FlightAssignment.registration_id.in_(unique_ids),
                    FlightAssignment.direction == target.direction,
                )
            )
        }

        moving = [
            registration_id
            for registration_id in unique_ids
            if existing.get(registration_id) is None
            or existing[registration_id].flight_id != target.id
        ]
        if not moving:
            raise ConflictError(
                f"Tất cả {len(unique_ids)} người đã ở chuyến {target.flight_code}.",
                code="ALREADY_ON_FLIGHT",
                details={"flight_id": target.id},
            )

        _require_free_seats(db, target=target, needed=len(moving), moving_in=moving)

        touched = [existing[rid] for rid in moving if rid in existing]
        warnings = _move_warnings(db, assignments=touched, target=target, extra_ids=moving)

        now = utcnow_iso()
        created = 0
        rows = []
        for registration_id in moving:
            assignment = existing.get(registration_id)
            if assignment is None:
                assignment = FlightAssignment(
                    registration_id=registration_id,
                    flight_id=target.id,
                    direction=target.direction,
                    assignment_mode=AssignmentMode.MANUAL,
                    assigned_by=actor_id,
                    assigned_at=now,
                )
                db.add(assignment)
                created += 1
            else:
                _apply_move(db, assignment, target, actor_id)
            rows.append(assignment)
        db.flush()

        audit_service.log(
            db,
            action="flight_assignment.bulk_moved",
            entity_type="flight_assignment",
            entity_id=target.id,
            actor_id=actor_id,
            event_id=event_id,
            after={
                "flight_id": target.id,
                "registration_ids": moving,
                "moved": len(moving) - created,
                "created": created,
            },
            reason=reason,
            ip_address=ip_address,
        )

    # Nạp lại quan hệ để dựng response sau khi transaction đã commit.
    fresh = [
        _require_assignment(db, event_id=event_id, assignment_id=row.id) for row in rows
    ]
    return [_to_row(row) for row in fresh], warnings, created


def remove_assignment(
    db: Session,
    *,
    event: Event,
    assignment_id: int,
    reason: str,
    actor: User,
    ip_address: str | None = None,
) -> None:
    """Bỏ phân bổ của một người — họ trở lại trạng thái chưa có chỗ."""
    event_id, actor_id = event.id, actor.id

    with immediate_transaction(db):
        assignment = _require_assignment(db, event_id=event_id, assignment_id=assignment_id)
        snapshot = {
            "registration_id": assignment.registration_id,
            "flight_id": assignment.flight_id,
            "direction": assignment.direction,
            "assignment_mode": assignment.assignment_mode,
        }
        db.delete(assignment)
        db.flush()

        audit_service.log(
            db,
            action="flight_assignment.removed",
            entity_type="flight_assignment",
            entity_id=assignment_id,
            actor_id=actor_id,
            event_id=event_id,
            before=snapshot,
            reason=reason,
            ip_address=ip_address,
        )


# --- Kiểm tra và cảnh báo ---


def _require_registration_closed(event: Event) -> None:
    """Chỉ ghi kết quả khi đăng ký đã đóng.

    Ghi trong lúc CBNV còn đăng ký nghĩa là kết quả lạc hậu ngay lúc ghi xong, và người
    đăng ký sau sẽ không có chỗ mà không ai để ý.
    """
    # Luật nằm ở event_service để phân bổ bay và phân xe dùng chung một bản.
    event_service.require_registration_closed(event)


def _require_assignment(db: Session, *, event_id: int, assignment_id: int) -> FlightAssignment:
    assignment = db.scalar(
        select(FlightAssignment)
        .join(Registration, Registration.id == FlightAssignment.registration_id)
        .where(FlightAssignment.id == assignment_id, Registration.event_id == event_id)
        .options(
            selectinload(FlightAssignment.flight).selectinload(Flight.shift),
            selectinload(FlightAssignment.registration)
            .selectinload(Registration.user)
            .selectinload(User.team),
            selectinload(FlightAssignment.registration).selectinload(Registration.shift),
        )
    )
    if assignment is None:
        raise NotFoundError(
            f"Không tìm thấy phân bổ #{assignment_id} trong kỳ này.",
            code="ASSIGNMENT_NOT_FOUND",
        )
    return assignment


def _require_target_flight(
    db: Session, *, event_id: int, flight_id: int, direction: str | None = None
) -> Flight:
    flight = flight_service.get_flight(db, event_id=event_id, flight_id=flight_id)
    if not flight.is_active:
        raise ConflictError(
            f"Chuyến {flight.flight_code} đang tắt, không xếp người vào được.",
            code="FLIGHT_INACTIVE",
            details={"flight_id": flight.id},
        )
    if direction is not None and flight.direction != direction:
        raise AppError(
            f"Chuyến {flight.flight_code} thuộc chiều {flight.direction}, không phải "
            f"{direction}. Mỗi người chỉ có một chuyến cho mỗi chiều.",
            code="DIRECTION_MISMATCH",
            details={"flight_direction": flight.direction, "expected": direction},
        )
    return flight


def _require_registrations(
    db: Session, *, event_id: int, registration_ids: list[int]
) -> list[Registration]:
    rows = db.scalars(
        select(Registration).where(
            Registration.id.in_(registration_ids),
            Registration.event_id == event_id,
            Registration.status == RegistrationStatus.SUBMITTED,
            Registration.is_participating.is_(True),
        )
    ).all()
    found = {row.id for row in rows}
    missing = [rid for rid in registration_ids if rid not in found]
    if missing:
        raise NotFoundError(
            "Có đăng ký không thuộc kỳ này, đã huỷ, hoặc không tham gia: "
            + ", ".join(str(rid) for rid in missing),
            code="REGISTRATION_NOT_FOUND",
            details={"missing": missing},
        )
    return list(rows)


def _require_free_seats(
    db: Session, *, target: Flight, needed: int, moving_in: list[int]
) -> None:
    """Đếm lại chỗ trống ngay trong transaction rồi mới cho ghi (docs/05 §5)."""
    occupied = (
        db.scalar(
            select(func.count())
            .select_from(FlightAssignment)
            .where(
                FlightAssignment.flight_id == target.id,
                FlightAssignment.registration_id.not_in(moving_in),
            )
        )
        or 0
    )
    remaining = target.usable_capacity - occupied
    if remaining < needed:
        raise ConflictError(
            f"Chuyến {target.flight_code} chỉ còn {max(remaining, 0)} chỗ, cần {needed}.",
            code="FLIGHT_CAPACITY_EXCEEDED",
            details={
                "flight_id": target.id,
                "remaining": max(remaining, 0),
                "requested": needed,
            },
        )


def _move_warnings(
    db: Session,
    *,
    assignments: list[FlightAssignment],
    target: Flight,
    extra_ids: list[int] | None = None,
) -> list[Flag]:
    """Cảnh báo KHÔNG chặn: lệch ca, làm team tách thêm, người thiếu giấy tờ, xe lệch giờ bay."""
    warnings: list[Flag] = []
    registration_ids = list({a.registration_id for a in assignments} | set(extra_ids or []))
    if not registration_ids:
        return warnings

    registrations = db.scalars(
        select(Registration)
        .where(Registration.id.in_(registration_ids))
        .options(selectinload(Registration.user).selectinload(User.team))
    ).all()

    for registration in sorted(registrations, key=lambda r: r.id):
        user = registration.user

        if registration.shift_id and target.shift_id != registration.shift_id:
            warnings.append(
                Flag(
                    type=WARN_SHIFT_MISMATCH,
                    severity=SEVERITY_WARNING,
                    message=(
                        f"{user.full_name} xin ca khác nhưng được chuyển sang chuyến "
                        f"{target.flight_code}."
                    ),
                    registration_id=registration.id,
                    team_id=user.team_id,
                    flight_id=target.id,
                )
            )
            if registration.is_shift_locked:
                warnings[-1] = Flag(
                    type="SHIFT_LOCKED_VIOLATION",
                    severity=SEVERITY_WARNING,
                    message=(
                        f"{user.full_name} bị KHOÁ ca nhưng đang được chuyển sang chuyến "
                        f"{target.flight_code} khác ca. Kiểm tra lại trước khi công bố."
                    ),
                    registration_id=registration.id,
                    team_id=user.team_id,
                    flight_id=target.id,
                )

        if not user.can_fly:
            warnings.append(
                Flag(
                    type=WARN_MISSING_ID_CARD,
                    severity=SEVERITY_WARNING,
                    message=f"{user.full_name} còn thiếu CCCD hoặc ngày sinh để xuất vé.",
                    registration_id=registration.id,
                    team_id=user.team_id,
                )
            )

    names = {registration.id: registration.user for registration in registrations}
    for item in transport_timing_service.rider_bus_conflicts(
        db, registration_ids=registration_ids, flight=target
    ):
        user = names[item["registration_id"]]
        warnings.append(
            Flag(
                type=WARN_BUS_TIME_MISMATCH,
                severity=SEVERITY_WARNING,
                message=(
                    f"{user.full_name} đang ở xe {item['bus_code']} ({item['trip_leg_name']}): "
                    f"{item['reason']}. Chuyển người này sang xe khác trước khi công bố."
                ),
                registration_id=item["registration_id"],
                team_id=user.team_id,
                flight_id=target.id,
                details={"bus_id": item["bus_id"], "trip_leg_id": item["trip_leg_id"]},
            )
        )

    warnings.extend(_split_warnings(db, registrations=registrations, target=target))
    return warnings


def _split_warnings(
    db: Session, *, registrations: list[Registration], target: Flight
) -> list[Flag]:
    """Cảnh báo khi thao tác làm một team bị tách thêm."""
    team_ids = {r.user.team_id for r in registrations if r.user.team_id}
    if not team_ids:
        return []

    moving_ids = {r.id for r in registrations}
    warnings = []

    for team_id in sorted(team_ids):
        rows = db.execute(
            select(FlightAssignment.registration_id, FlightAssignment.flight_id)
            .join(Registration, Registration.id == FlightAssignment.registration_id)
            .join(User, User.id == Registration.user_id)
            .where(
                Registration.event_id == target.event_id,
                FlightAssignment.direction == target.direction,
                User.team_id == team_id,
            )
        ).all()

        before = {flight_id for _registration_id, flight_id in rows}
        after = {
            target.id if registration_id in moving_ids else flight_id
            for registration_id, flight_id in rows
        }
        after |= {target.id}

        if len(after) > len(before):
            team_name = next(
                (r.user.team.name for r in registrations if r.user.team_id == team_id and r.user.team),
                f"Team #{team_id}",
            )
            warnings.append(
                Flag(
                    type=WARN_TEAM_SPLIT,
                    severity=SEVERITY_WARNING,
                    message=(
                        f"Thao tác này làm team {team_name} bị tách thành {len(after)} chuyến "
                        f"(trước đó {len(before)})."
                    ),
                    team_id=team_id,
                    flight_id=target.id,
                    details={"flights_before": len(before), "flights_after": len(after)},
                )
            )
    return warnings


# --- Nội bộ ---


def _apply_move(
    db: Session, assignment: FlightAssignment, target: Flight, actor_id: int
) -> dict[str, Any]:
    previous_flight_id = assignment.flight_id
    assignment.flight_id = target.id
    # Đánh dấu manual: lần chạy auto sau phải tôn trọng quyết định này (docs/05 §5).
    assignment.assignment_mode = AssignmentMode.MANUAL
    assignment.assigned_by = actor_id
    assignment.assigned_at = utcnow_iso()
    db.flush()
    return {"previous_flight_id": previous_flight_id}


def _participating_ids(db: Session, event_id: int) -> set[int]:
    return set(
        db.scalars(
            select(Registration.id).where(
                Registration.event_id == event_id,
                Registration.status == RegistrationStatus.SUBMITTED,
                Registration.is_participating.is_(True),
            )
        ).all()
    )


def shift_codes(db: Session, event_id: int) -> dict[int, str]:
    """id ca -> mã ca, dùng cho phần hiển thị."""
    return {
        shift.id: shift.code
        for shift in db.scalars(select(Shift).where(Shift.event_id == event_id))
    }
