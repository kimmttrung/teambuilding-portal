"""Xếp phòng tự động: xem trước và ghi (docs/05 §7). Cùng khuôn với chuyến bay và xe.

- Xem trước (dry-run) không ghi gì, chạy lúc nào cũng được.
- Ghi thật cần kỳ đã đóng đăng ký, chạy lại thuật toán TRONG `BEGIN IMMEDIATE` (dữ liệu có thể
  đã đổi từ lúc xem trước), giữ bản ghi xếp tay trừ khi `force_reallocate`, và ghi audit log.
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import immediate_transaction
from app.core.timeutils import utcnow_iso
from app.models.accommodation import Hotel, Room, RoomAssignment
from app.models.enums import AssignmentMode, RegistrationStatus
from app.models.event import Event
from app.models.registration import Registration
from app.models.user import User
from app.services import audit_service, event_service
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
) -> tuple[RoomAllocationResult, int]:
    """Chạy lại thuật toán và ghi trong một transaction. Trả về (kết quả, số bản ghi rác đã dọn)."""
    event_service.require_registration_closed(event)
    event_id, actor_id = event.id, actor.id

    with immediate_transaction(db):
        current = db.get(Event, event_id)
        result = preview(db, event=current, force_reallocate=force_reallocate)
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
    event_rooms = select(Room.id).join(Hotel, Hotel.id == Room.hotel_id).where(Hotel.event_id == event_id)
    existing = db.scalars(select(RoomAssignment).where(RoomAssignment.room_id.in_(event_rooms))).all()
    participants = set(
        db.scalars(
            select(Registration.id).where(
                Registration.event_id == event_id,
                Registration.status == RegistrationStatus.SUBMITTED,
                Registration.is_participating.is_(True),
            )
        ).all()
    )

    removed_stale = 0
    for row in existing:
        if row.registration_id not in participants:
            db.delete(row)
            removed_stale += 1
        elif force_reallocate or row.assignment_mode != AssignmentMode.MANUAL:
            db.delete(row)
    # Xoá trước khi chèn: registration_id là UNIQUE trong room_assignments.
    db.flush()

    now = utcnow_iso()
    for bed in result.assignments:
        if bed.pinned and not force_reallocate:
            continue
        db.add(
            RoomAssignment(
                registration_id=bed.registration_id,
                room_id=bed.room_id,
                is_room_captain=bed.is_room_captain,
                assignment_mode=AssignmentMode.AUTO,
                assigned_by=actor_id,
                assigned_at=now,
            )
        )
    db.flush()
    return removed_stale
