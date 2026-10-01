"""Xếp phòng tự động: xem trước và ghi (docs/05 §7). Cùng khuôn với chuyến bay và xe.

- Xem trước (dry-run) không ghi gì, chạy lúc nào cũng được.
- Ghi thật cần kỳ đã đóng đăng ký, chạy lại thuật toán TRONG `BEGIN IMMEDIATE` (dữ liệu có thể
  đã đổi từ lúc xem trước), giữ bản ghi xếp tay trừ khi `force_reallocate`, và ghi audit log.
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import immediate_transaction
from app.core.exceptions import ConflictError
from app.core.timeutils import utcnow_iso
from app.models.enums import AssignmentMode
from app.models.event import Event
from app.models.registration import Registration
from app.models.user import User
from app.services import audit_service, event_service
from app.services.accommodation_service import clear_room_assignment
from app.services.allocator.room_loader import load_room_guests, load_room_params, load_room_slots
from app.services.allocator.room_types import RoomAllocationResult
from app.services.allocator.rooms import allocate_rooms

logger = logging.getLogger(__name__)


def preview(db: Session, *, event: Event, force_reallocate: bool = False) -> RoomAllocationResult:
    return allocate_rooms(
        guests=load_room_guests(db, event_id=event.id, keep_manual=not force_reallocate),
        rooms=load_room_slots(db, event_id=event.id),
        params=load_room_params(db, event_id=event.id),
    )


def commit(
    db: Session,
    *,
    event: Event,
    actor: User,
    force_reallocate: bool = False,
    ip_address: str | None = None,
    expected_assignments: list[dict] | None = None,
) -> tuple[RoomAllocationResult, int]:
    """Chạy lại thuật toán và ghi trong một transaction. Trả về (kết quả, số bản ghi rác đã dọn)."""
    event_service.require_registration_closed(event)
    event_id, actor_id = event.id, actor.id

    with immediate_transaction(db):
        current = db.get(Event, event_id)
        db.refresh(current)
        event_service.require_registration_closed(current)
        result = preview(db, event=current, force_reallocate=force_reallocate)
        if expected_assignments is not None:
            actual = {
                (bed.registration_id, bed.room_id, bed.is_room_captain, bed.pinned)
                for bed in result.assignments
            }
            expected = {
                (bed["registration_id"], bed["room_id"], bed["is_room_captain"], bed["pinned"])
                for bed in expected_assignments
            }
            if expected != actual or len(expected) != len(expected_assignments):
                raise ConflictError(
                    "Dữ liệu phân phòng đã thay đổi. Xem trước lại trước khi áp dụng.",
                    code="ROOM_ALLOCATION_PREVIEW_STALE",
                )
        removed_stale = _write_assignments(
            db,
            event_id=event_id,
            result=result,
            actor_id=actor_id,
            force_reallocate=force_reallocate,
        )
        audit_service.log(
            db,
            action="room.allocated",
            entity_type="room_allocation",
            entity_id=event_id,
            actor_id=actor_id,
            event_id=event_id,
            after={
                "force_reallocate": force_reallocate,
                "assigned": result.summary.assigned,
                "unassigned": result.summary.unassigned,
                "rooms_used": result.summary.rooms_used,
                "same_team_rate": result.summary.same_team_rate,
                "removed_stale": removed_stale,
            },
            ip_address=ip_address,
        )

    logger.info(
        "Đã ghi xếp phòng: %s người, %s phòng, dọn %s bản ghi rác",
        result.summary.assigned,
        result.summary.rooms_used,
        removed_stale,
    )
    return result, removed_stale


def _write_assignments(
    db: Session,
    *,
    event_id: int,
    result: RoomAllocationResult,
    actor_id: int,
    force_reallocate: bool,
) -> int:
    """Thay phân phòng của cả kỳ.

    Người không còn tham gia bị xoá bản ghi bất kể mode — để lại là họ chiếm giường không ai ngủ.
    """
    registrations = db.scalars(select(Registration).where(Registration.event_id == event_id)).all()
    by_id = {row.id: row for row in registrations}
    removed_stale = 0
    for row in registrations:
        if row.room_id is None:
            continue
        if not row.is_active_participant:
            clear_room_assignment(row)
            removed_stale += 1
        elif force_reallocate or row.room_mode != AssignmentMode.MANUAL:
            clear_room_assignment(row)

    now = utcnow_iso()
    for bed in result.assignments:
        if bed.pinned and not force_reallocate:
            continue
        row = by_id[bed.registration_id]
        row.room_id = bed.room_id
        row.is_room_captain = bed.is_room_captain
        row.room_mode = AssignmentMode.AUTO
        row.room_assigned_by = actor_id
        row.room_assigned_at = now
        row.room_note = None
    db.flush()
    return removed_stale
