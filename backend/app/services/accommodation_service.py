"""Nghiệp vụ khách sạn, phòng và phân phòng.

Ràng buộc cứng (docs/05 §7): không vượt sức chứa phòng và đúng `gender_policy`.
Xếp tay, import Excel và xếp tự động dùng cùng các cột phân phòng trên registrations.

Cùng các luật với chuyến bay và xe:
- Chỗ trống luôn TÍNH từ `registrations.room_id`, không lưu cột.
- Không hạ sức chứa dưới số người đang ở, không xoá phòng/khách sạn còn người.
- Ghi phân phòng trong `BEGIN IMMEDIATE`, đếm lại chỗ ngay trong transaction.
- Mọi thay đổi có audit log.
"""

import logging
from typing import Any

from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.database import immediate_transaction
from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.core.timeutils import from_iso, utcnow_iso
from app.models.accommodation import Hotel, Room
from app.models.enums import AssignmentMode, Gender, RegistrationStatus, RoomGenderPolicy
from app.models.event import Event
from app.models.registration import Registration
from app.models.user import User
from app.services import audit_service

logger = logging.getLogger(__name__)

HOTEL_FIELDS = ["name", "address", "phone", "check_in_at", "check_out_at", "map_url", "note"]
ROOM_FIELDS = ["room_number", "room_type", "capacity", "floor", "gender_policy", "note"]
POLICY_LABELS = {
    RoomGenderPolicy.MALE: "nam",
    RoomGenderPolicy.FEMALE: "nữ",
    RoomGenderPolicy.ANY: "mọi giới tính",
}


# --- Giới tính: dùng chung cho xếp tay và import ---


def gender_violation(policy: str, gender: str | None) -> str | None:
    """Mã lỗi nếu người có `gender` không được ở phòng `policy`; None nếu hợp lệ.

    Người chưa khai giới tính (hoặc khai "khác") chỉ vào được phòng 'any': không thể đoán
    thay họ mà xếp vào phòng nam hay phòng nữ.
    """
    if policy == RoomGenderPolicy.ANY:
        return None
    if gender not in (Gender.MALE, Gender.FEMALE):
        return "MISSING_GENDER"
    return None if gender == policy else "GENDER_POLICY_VIOLATION"


def gender_message(code: str, full_name: str, room_number: str, policy: str) -> str:
    label = POLICY_LABELS.get(policy, policy)
    if code == "MISSING_GENDER":
        return (
            f"{full_name} chưa khai giới tính nam/nữ nên không xếp vào phòng chỉ dành cho {label} "
            "được. Dùng phòng không giới hạn giới tính, hoặc bổ sung hồ sơ trước."
        )
    return f"Phòng {room_number} chỉ dành cho {label}, không xếp {full_name} vào được."


# --- Khách sạn ---


def list_hotels(db: Session, *, event_id: int) -> list[tuple[Hotel, int, int, int]]:
    """(khách sạn, số phòng, số giường, số người đã xếp)."""
    hotels = db.scalars(select(Hotel).where(Hotel.event_id == event_id).order_by(Hotel.name)).all()
    return [(hotel, *hotel_stats(db, hotel.id)) for hotel in hotels]


def hotel_stats(db: Session, hotel_id: int) -> tuple[int, int, int]:
    rooms, beds = db.execute(
        select(func.count(Room.id), func.coalesce(func.sum(Room.capacity), 0)).where(
            Room.hotel_id == hotel_id
        )
    ).one()
    assigned = (
        db.scalar(
            select(func.count(Registration.id))
            .join(Room, Room.id == Registration.room_id)
            .where(Room.hotel_id == hotel_id)
        )
        or 0
    )
    return rooms or 0, beds or 0, assigned


def get_hotel(db: Session, *, event_id: int, hotel_id: int) -> Hotel:
    hotel = db.scalar(select(Hotel).where(Hotel.id == hotel_id, Hotel.event_id == event_id))
    if hotel is None:
        raise NotFoundError(
            f"Không tìm thấy khách sạn #{hotel_id} trong kỳ này.", code="HOTEL_NOT_FOUND"
        )
    return hotel


def create_hotel(
    db: Session, *, event: Event, data: dict[str, Any], actor: User, ip_address: str | None = None
) -> Hotel:
    hotel = Hotel(event_id=event.id, **data)
    db.add(hotel)
    db.flush()
    audit_service.log(
        db,
        action="hotel.created",
        entity_type="hotel",
        entity_id=hotel.id,
        actor_id=actor.id,
        event_id=event.id,
        after=audit_service.snapshot(hotel, HOTEL_FIELDS),
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(hotel)
    return hotel


def update_hotel(
    db: Session,
    *,
    event: Event,
    hotel: Hotel,
    data: dict[str, Any],
    actor: User,
    ip_address: str | None = None,
) -> Hotel:
    with immediate_transaction(db):
        if not data:
            return hotel

        check_in = data.get("check_in_at", hotel.check_in_at)
        check_out = data.get("check_out_at", hotel.check_out_at)
        if check_in and check_out and from_iso(check_out) <= from_iso(check_in):
            raise AppError(
                "Giờ trả phòng phải sau giờ nhận phòng.",
                code="INVALID_HOTEL_TIME",
                details={"check_in_at": check_in, "check_out_at": check_out},
            )

        before = audit_service.snapshot(hotel, HOTEL_FIELDS)
        for field, value in data.items():
            setattr(hotel, field, value)
        db.flush()
        audit_service.log(
            db,
            action="hotel.updated",
            entity_type="hotel",
            entity_id=hotel.id,
            actor_id=actor.id,
            event_id=event.id,
            before=before,
            after=audit_service.diff(before, audit_service.snapshot(hotel, HOTEL_FIELDS)),
            ip_address=ip_address,
        )
        db.refresh(hotel)
        return hotel


def delete_hotel(
    db: Session, *, event: Event, hotel: Hotel, actor: User, ip_address: str | None = None
) -> None:
    """Xoá khách sạn cùng phòng trống; không xoá đăng ký khi khách sạn còn người."""
    with immediate_transaction(db):
        _rooms, _beds, assigned = hotel_stats(db, hotel.id)
        if assigned:
            raise ConflictError(
                f"Khách sạn {hotel.name} còn {assigned} người đang được xếp phòng. "
                "Bỏ phân phòng của họ trước khi xoá.",
                code="HOTEL_HAS_OCCUPANTS",
                details={"assigned_count": assigned},
            )

        snapshot = audit_service.snapshot(hotel, HOTEL_FIELDS)
        hotel_id = hotel.id
        db.delete(hotel)
        db.flush()
        audit_service.log(
            db,
            action="hotel.deleted",
            entity_type="hotel",
            entity_id=hotel_id,
            actor_id=actor.id,
            event_id=event.id,
            before=snapshot,
            ip_address=ip_address,
        )


# --- Phòng ---


def _occupancy_subquery():
    return (
        select(
            Registration.room_id,
            func.count(Registration.id).label("occupied"),
            func.max(case((Registration.is_room_captain.is_(True), 1), else_=0)).label(
                "has_captain"
            ),
        )
        .group_by(Registration.room_id)
        .subquery()
    )


def list_rooms(
    db: Session,
    *,
    event_id: int,
    hotel_id: int | None = None,
    gender_policy: str | None = None,
    available_only: bool = False,
    search: str | None = None,
) -> list[tuple[Room, int, bool]]:
    """(phòng, số người đang ở, đã có trưởng phòng chưa) — đếm gộp, không N+1."""
    occupancy = _occupancy_subquery()
    occupied = func.coalesce(occupancy.c.occupied, 0)

    query = (
        select(Room, occupied, func.coalesce(occupancy.c.has_captain, 0))
        .join(Hotel, Hotel.id == Room.hotel_id)
        .outerjoin(occupancy, occupancy.c.room_id == Room.id)
        .where(Hotel.event_id == event_id)
        .options(selectinload(Room.hotel))
    )
    if hotel_id is not None:
        query = query.where(Room.hotel_id == hotel_id)
    if gender_policy:
        query = query.where(Room.gender_policy == gender_policy)
    if available_only:
        query = query.where(occupied < Room.capacity)
    if search:
        query = query.where(Room.room_number.like(f"%{search.strip()}%"))

    rows = db.execute(query.order_by(Hotel.name, Room.floor, Room.room_number)).all()
    return [(room, count, bool(captain)) for room, count, captain in rows]


def get_room(db: Session, *, event_id: int, room_id: int) -> Room:
    room = db.scalar(
        select(Room)
        .join(Hotel, Hotel.id == Room.hotel_id)
        .where(Room.id == room_id, Hotel.event_id == event_id)
        .options(selectinload(Room.hotel))
    )
    if room is None:
        raise NotFoundError(f"Không tìm thấy phòng #{room_id} trong kỳ này.", code="ROOM_NOT_FOUND")
    return room


def room_occupancy(db: Session, room_id: int) -> tuple[int, bool]:
    occupied, captains = db.execute(
        select(
            func.count(Registration.id),
            func.coalesce(func.sum(case((Registration.is_room_captain.is_(True), 1), else_=0)), 0),
        ).where(Registration.room_id == room_id)
    ).one()
    return occupied or 0, bool(captains)


def create_room(
    db: Session, *, event: Event, data: dict[str, Any], actor: User, ip_address: str | None = None
) -> Room:
    get_hotel(db, event_id=event.id, hotel_id=data["hotel_id"])

    room = Room(**data)
    db.add(room)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise _duplicate_room(data.get("room_number")) from exc

    audit_service.log(
        db,
        action="room.created",
        entity_type="room",
        entity_id=room.id,
        actor_id=actor.id,
        event_id=event.id,
        after=audit_service.snapshot(room, ROOM_FIELDS),
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(room)
    return room


def update_room(
    db: Session,
    *,
    event: Event,
    room: Room,
    data: dict[str, Any],
    actor: User,
    ip_address: str | None = None,
) -> Room:
    with immediate_transaction(db):
        if not data:
            return room

        occupants = db.scalars(
            select(Registration)
            .where(Registration.room_id == room.id)
            .options(selectinload(Registration.user))
        ).all()

        if "capacity" in data and data["capacity"] < len(occupants):
            raise ConflictError(
                f"Phòng {room.room_number} đang có {len(occupants)} người, không thể hạ sức chứa "
                f"xuống {data['capacity']}.",
                code="CAPACITY_BELOW_OCCUPIED",
                details={"occupied": len(occupants), "capacity": data["capacity"]},
            )

        if data.get("gender_policy") is not None:
            conflicts = [
                assignment.user.full_name
                for assignment in occupants
                if gender_violation(data["gender_policy"], assignment.user.gender)
            ]
            if conflicts:
                raise ConflictError(
                    f"Không đổi được phòng {room.room_number} sang dành cho "
                    f"{POLICY_LABELS.get(data['gender_policy'], data['gender_policy'])}: "
                    f"{', '.join(conflicts)} đang ở trong phòng.",
                    code="GENDER_POLICY_CONFLICT",
                    details={"occupants": conflicts},
                )

        before = audit_service.snapshot(room, ROOM_FIELDS)
        for field, value in data.items():
            setattr(room, field, value)
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            raise _duplicate_room(data.get("room_number")) from exc

        audit_service.log(
            db,
            action="room.updated",
            entity_type="room",
            entity_id=room.id,
            actor_id=actor.id,
            event_id=event.id,
            before=before,
            after=audit_service.diff(before, audit_service.snapshot(room, ROOM_FIELDS)),
            ip_address=ip_address,
        )
        db.refresh(room)
        return room


def delete_room(
    db: Session, *, event: Event, room: Room, actor: User, ip_address: str | None = None
) -> None:
    with immediate_transaction(db):
        occupied, _captain = room_occupancy(db, room.id)
        if occupied:
            raise ConflictError(
                f"Phòng {room.room_number} còn {occupied} người. Bỏ phân phòng trước khi xoá.",
                code="ROOM_HAS_OCCUPANTS",
                details={"occupied": occupied},
            )

        snapshot = audit_service.snapshot(room, ROOM_FIELDS)
        room_id = room.id
        db.delete(room)
        db.flush()
        audit_service.log(
            db,
            action="room.deleted",
            entity_type="room",
            entity_id=room_id,
            actor_id=actor.id,
            event_id=event.id,
            before=snapshot,
            ip_address=ip_address,
        )


def list_occupants(db: Session, *, room: Room) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(Registration)
        .where(Registration.room_id == room.id, Registration.event_id == room.hotel.event_id)
        .options(selectinload(Registration.user).selectinload(User.team))
    ).all()

    occupants = []
    for row in rows:
        user = row.user
        occupants.append(
            {
                "assignment_id": row.id,
                "registration_id": row.id,
                "user_id": user.id,
                "full_name": user.full_name,
                "employee_code": user.employee_code,
                "gender": user.gender,
                "team_id": user.team_id,
                "team_name": user.team.name if user.team else None,
                "is_room_captain": row.is_room_captain,
                "assignment_mode": row.room_mode,
                "assigned_at": row.room_assigned_at,
                "dietary_restriction": user.dietary_restriction,
                "has_health_note": bool(user.health_note),
            }
        )
    occupants.sort(key=lambda item: (not item["is_room_captain"], item["full_name"]))
    return occupants


# --- Tổng quan giường ---


def summary(db: Session, *, event_id: int) -> dict[str, Any]:
    """Giường theo loại phòng so với người tham gia theo giới tính.

    Tổng giường đủ chưa chắc đã đủ: phòng nam không nhận nữ. Phải so từng giới, rồi mới dùng
    phòng 'any' bù vào chỗ thiếu — `uncovered` là số người chắc chắn không có giường hợp lệ.
    """
    participant_filter = (
        Registration.event_id == event_id,
        Registration.status == RegistrationStatus.SUBMITTED,
        Registration.is_participating.is_(True),
    )
    by_gender = {
        gender: count
        for gender, count in db.execute(
            select(User.gender, func.count(Registration.id))
            .join(User, User.id == Registration.user_id)
            .where(*participant_filter)
            .group_by(User.gender)
        ).all()
    }
    participants = sum(by_gender.values())
    needs_any = sum(
        count for gender, count in by_gender.items() if gender not in (Gender.MALE, Gender.FEMALE)
    )

    rooms = {
        policy: (count, beds or 0)
        for policy, count, beds in db.execute(
            select(Room.gender_policy, func.count(Room.id), func.sum(Room.capacity))
            .join(Hotel, Hotel.id == Room.hotel_id)
            .where(Hotel.event_id == event_id)
            .group_by(Room.gender_policy)
        ).all()
    }
    occupied = {
        policy: count
        for policy, count in db.execute(
            select(Room.gender_policy, func.count(Registration.id))
            .join(Registration, Registration.room_id == Room.id)
            .join(Hotel, Hotel.id == Room.hotel_id)
            .where(Hotel.event_id == event_id, *participant_filter)
            .group_by(Room.gender_policy)
        ).all()
    }
    assigned = (
        db.scalar(
            select(func.count(Registration.id))
            .join(Room, Room.id == Registration.room_id)
            .join(Hotel, Hotel.id == Room.hotel_id)
            .where(*participant_filter, Hotel.event_id == event_id)
        )
        or 0
    )

    loads = []
    shortfalls = {}
    for policy in (RoomGenderPolicy.MALE, RoomGenderPolicy.FEMALE, RoomGenderPolicy.ANY):
        room_count, beds = rooms.get(policy, (0, 0))
        people = needs_any if policy == RoomGenderPolicy.ANY else by_gender.get(policy, 0)
        shortfalls[policy] = max(people - beds, 0)
        loads.append(
            {
                "gender_policy": policy,
                "rooms": room_count,
                "beds": beds,
                "occupied": occupied.get(policy, 0),
                "remaining": beds - occupied.get(policy, 0),
                "participants": people,
                "shortfall": shortfalls[policy],
            }
        )

    any_beds = rooms.get(RoomGenderPolicy.ANY, (0, 0))[1]
    uncovered = max(
        shortfalls[RoomGenderPolicy.MALE]
        + shortfalls[RoomGenderPolicy.FEMALE]
        + needs_any
        - any_beds,
        0,
    )

    return {
        "participants": participants,
        "assigned": assigned,
        "unassigned": max(participants - assigned, 0),
        "total_beds": sum(beds for _count, beds in rooms.values()),
        "uncovered": uncovered,
        "by_policy": loads,
    }


# --- Phân phòng ---


def list_unassigned(
    db: Session,
    *,
    event_id: int,
    gender: str | None = None,
    team_id: int | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    query = (
        select(Registration)
        .join(User, User.id == Registration.user_id)
        .where(
            Registration.event_id == event_id,
            Registration.status == RegistrationStatus.SUBMITTED,
            Registration.is_participating.is_(True),
            Registration.room_id.is_(None),
        )
        .options(selectinload(Registration.user).selectinload(User.team))
    )
    if gender == "unknown":
        query = query.where(
            or_(User.gender.is_(None), User.gender.not_in((Gender.MALE, Gender.FEMALE)))
        )
    elif gender is not None:
        query = query.where(User.gender == gender)
    if team_id is not None:
        query = query.where(User.team_id == team_id)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(or_(User.full_name.like(pattern), User.employee_code.like(pattern)))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(
        query.order_by(User.full_name, Registration.id).limit(limit).offset(offset)
    ).all()
    return [
        {
            "registration_id": row.id,
            "user_id": row.user_id,
            "full_name": row.user.full_name,
            "employee_code": row.user.employee_code,
            "gender": row.user.gender,
            "team_id": row.user.team_id,
            "team_name": row.user.team.name if row.user.team else None,
        }
        for row in rows
    ], total


def list_assignments(
    db: Session,
    *,
    event_id: int,
    hotel_id: int | None = None,
    room_id: int | None = None,
    team_id: int | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    query = (
        select(Registration)
        .join(Room, Room.id == Registration.room_id)
        .join(Hotel, Hotel.id == Room.hotel_id)
        .join(User, User.id == Registration.user_id)
        .where(Hotel.event_id == event_id, Registration.event_id == event_id)
        .options(
            selectinload(Registration.room).selectinload(Room.hotel),
            selectinload(Registration.user).selectinload(User.team),
        )
    )
    if hotel_id is not None:
        query = query.where(Room.hotel_id == hotel_id)
    if room_id is not None:
        query = query.where(Registration.room_id == room_id)
    if team_id is not None:
        query = query.where(User.team_id == team_id)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(
            or_(
                User.full_name.like(pattern),
                User.employee_code.like(pattern),
                Room.room_number.like(pattern),
            )
        )

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(
        query.order_by(Hotel.name, Room.room_number, User.full_name).limit(limit).offset(offset)
    ).all()
    return [_assignment_row(row) for row in rows], total


def assign(
    db: Session,
    *,
    event: Event,
    registration_id: int,
    room_id: int,
    actor: User,
    is_room_captain: bool = False,
    replace_existing: bool = False,
    reason: str | None = None,
    ip_address: str | None = None,
) -> tuple[dict[str, Any], int | None]:
    """Xếp một người vào phòng. Trả về (dòng phân phòng, id phòng cũ nếu là chuyển phòng)."""
    reason = validate_reason(reason) if reason is not None else None
    event_id, actor_id = event.id, actor.id

    with immediate_transaction(db):
        registration = _require_participating(
            db, event_id=event_id, registration_id=registration_id
        )
        user = registration.user
        room = get_room(db, event_id=event_id, room_id=room_id)

        violation = gender_violation(room.gender_policy, user.gender)
        if violation:
            raise AppError(
                gender_message(violation, user.full_name, room.room_number, room.gender_policy),
                code=violation,
                details={"gender_policy": room.gender_policy, "gender": user.gender},
            )

        existing = registration if registration.room_id is not None else None
        same_room = existing is not None and existing.room_id == room.id

        if same_room and bool(existing.is_room_captain) == is_room_captain:
            raise ConflictError(
                f"{user.full_name} đã ở phòng {room.room_number}.",
                code="ALREADY_IN_ROOM",
                details={"room_id": room.id},
            )
        if existing is not None and not same_room and not replace_existing:
            raise ConflictError(
                f"{user.full_name} đang ở phòng {existing.room.room_number}. Bật "
                "'replace_existing' nếu muốn chuyển sang phòng mới.",
                code="ALREADY_HAS_ROOM",
                details={"room_id": existing.room_id, "room_number": existing.room.room_number},
            )

        if not same_room:
            occupied = (
                db.scalar(
                    select(func.count(Registration.id)).where(
                        Registration.room_id == room.id,
                        Registration.id != registration.id,
                    )
                )
                or 0
            )
            if occupied >= room.capacity:
                raise ConflictError(
                    f"Phòng {room.room_number} đã đủ {room.capacity} người.",
                    code="ROOM_FULL",
                    details={"room_id": room.id, "capacity": room.capacity, "occupied": occupied},
                )

        now = utcnow_iso()
        moved_from = existing.room_id if existing is not None and not same_room else None
        if existing is None:
            action = "room_assignment.created"
        elif same_room:
            action = "room_assignment.captain_changed"
        else:
            action = "room_assignment.moved"
        existing = registration
        existing.room_id = room.id
        existing.is_room_captain = is_room_captain
        existing.room_mode = AssignmentMode.MANUAL
        existing.room_assigned_by = actor_id
        existing.room_assigned_at = now
        existing.room_note = reason
        db.flush()

        if is_room_captain:
            _clear_other_captains(db, room_id=room.id, keep_registration_id=registration.id)
        db.expire(existing, ["room"])

        audit_service.log(
            db,
            action=action,
            entity_type="room_assignment",
            entity_id=existing.id,
            actor_id=actor_id,
            event_id=event_id,
            before={"room_id": moved_from} if moved_from else None,
            after={"room_id": room.id, "is_room_captain": is_room_captain},
            reason=reason,
            ip_address=ip_address,
        )
        row = _assignment_row(existing)

    return row, moved_from


def remove_assignment(
    db: Session,
    *,
    event: Event,
    assignment_id: int,
    reason: str,
    actor: User,
    ip_address: str | None = None,
) -> None:
    reason = validate_reason(reason)
    event_id, actor_id = event.id, actor.id
    with immediate_transaction(db):
        assignment = _require_assignment(db, event_id=event_id, assignment_id=assignment_id)
        snapshot = {
            "registration_id": assignment.id,
            "room_id": assignment.room_id,
            "is_room_captain": assignment.is_room_captain,
        }
        clear_room_assignment(assignment)
        db.flush()
        audit_service.log(
            db,
            action="room_assignment.removed",
            entity_type="room_assignment",
            entity_id=assignment_id,
            actor_id=actor_id,
            event_id=event_id,
            before=snapshot,
            reason=reason,
            ip_address=ip_address,
        )


# --- Nội bộ ---


def _require_participating(db: Session, *, event_id: int, registration_id: int) -> Registration:
    registration = db.scalar(
        select(Registration)
        .where(
            Registration.id == registration_id,
            Registration.event_id == event_id,
            Registration.status == RegistrationStatus.SUBMITTED,
            Registration.is_participating.is_(True),
        )
        .options(selectinload(Registration.user).selectinload(User.team))
    )
    if registration is None:
        raise NotFoundError(
            f"Không tìm thấy đăng ký tham gia #{registration_id} "
            "(đã huỷ, không tham gia, hoặc thuộc kỳ khác).",
            code="REGISTRATION_NOT_FOUND",
        )
    return registration


def _require_assignment(db: Session, *, event_id: int, assignment_id: int) -> Registration:
    assignment = db.scalar(
        select(Registration)
        .join(Room, Room.id == Registration.room_id)
        .join(Hotel, Hotel.id == Room.hotel_id)
        .where(
            Registration.id == assignment_id,
            Registration.event_id == event_id,
            Hotel.event_id == event_id,
        )
    )
    if assignment is None:
        raise NotFoundError(
            f"Không tìm thấy phân phòng #{assignment_id} trong kỳ này.",
            code="ASSIGNMENT_NOT_FOUND",
        )
    return assignment


def _clear_other_captains(db: Session, *, room_id: int, keep_registration_id: int) -> None:
    """Mỗi phòng một trưởng phòng: đặt người mới thì bỏ cờ của người cũ."""
    others = db.scalars(
        select(Registration).where(
            Registration.room_id == room_id,
            Registration.id != keep_registration_id,
            Registration.is_room_captain.is_(True),
        )
    ).all()
    for other in others:
        other.is_room_captain = False
    db.flush()


def _assignment_row(assignment: Registration) -> dict[str, Any]:
    user = assignment.user
    room = assignment.room
    return {
        "id": assignment.id,
        "registration_id": assignment.id,
        "user_id": user.id,
        "full_name": user.full_name,
        "employee_code": user.employee_code,
        "gender": user.gender,
        "team_id": user.team_id,
        "team_name": user.team.name if user.team else None,
        "room_id": room.id,
        "room_number": room.room_number,
        "hotel_id": room.hotel_id,
        "hotel_name": room.hotel.name,
        "is_room_captain": assignment.is_room_captain,
        "assignment_mode": assignment.room_mode,
        "assigned_at": assignment.room_assigned_at,
    }


def _duplicate_room(room_number: str | None) -> ConflictError:
    return ConflictError(
        f"Phòng '{room_number}' đã có ở khách sạn này.",
        code="ROOM_NUMBER_DUPLICATED",
        details={"room_number": room_number},
    )


def clear_room_assignment(registration: Registration) -> None:
    """Nhả giường, giữ nguyên đăng ký và các phân bổ bay/xe khác."""
    registration.room_id = None
    registration.is_room_captain = False
    registration.room_mode = None
    registration.room_assigned_by = None
    registration.room_assigned_at = None
    registration.room_note = None


def validate_reason(reason: str) -> str:
    reason = reason.strip()
    if not 3 <= len(reason) <= 500:
        raise AppError("Lý do cần từ 3 đến 500 ký tự.", code="ROOM_REASON_INVALID", status_code=422)
    return reason
