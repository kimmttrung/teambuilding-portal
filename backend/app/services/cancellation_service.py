"""Huỷ đăng ký theo giai đoạn của kỳ (docs/04-api-spec.md §4.3).

| Giai đoạn kỳ                                        | CBNV                 | Hệ thống / BTC                                           |
|-----------------------------------------------------|----------------------|----------------------------------------------------------|
| Trước công bố (mở / đóng đăng ký, đang phân bổ)     | Tự huỷ               | Huỷ ngay, gỡ vé bay / xe / phòng / ghế Gala, báo BTC     |
| Đã công bố                                          | Gửi yêu cầu huỷ      | Giữ nguyên chỗ, báo BTC; BTC duyệt (gỡ chỗ, quyết phí phạt) hoặc từ chối |
| Từ khi chương trình bắt đầu                         | Không tự huỷ được    | Liên hệ BTC; BTC huỷ ngoại lệ                            |

Mọi lần huỷ — kể cả tự huỷ — để lại một dòng `registration_cancellations`, để BTC xem một chỗ là biết
ai huỷ, lúc nào, lý do gì, ở giai đoạn nào và hệ thống đã gỡ những gì.

Gỡ chỗ phải nằm cùng transaction với việc đổi trạng thái đăng ký: trước đây huỷ chỉ đổi trạng thái, bản
ghi phân bổ ở lại thành "ghế ma" — chuyến bay, phòng báo đầy trong khi người đó không đi.
"""

import json
import logging
from typing import Any

from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.database import immediate_transaction
from app.core.exceptions import ConflictError, NotFoundError
from app.core.timeutils import is_expired, iso_in, utcnow_iso
from app.models.accommodation import Room, RoomAssignment
from app.models.enums import (
    ADMIN_ROLES,
    CancellationMode,
    CancellationStatus,
    EventStatus,
    FlightDirection,
    RegistrationStatus,
)
from app.models.event import Event
from app.models.flight import FlightAssignment
from app.models.gala import GalaSeat, GalaSeatAssignment
from app.models.org import Team
from app.models.registration import Registration, RegistrationCancellation
from app.models.transportation import Bus, BusAssignment
from app.models.user import User
from app.services import (
    audit_service,
    email_service,
    email_templates,
    event_service,
    registration_service,
    team_leader_service,
)

logger = logging.getLogger(__name__)

# CBNV được làm gì với đăng ký của mình ở giai đoạn hiện tại (frontend dựa vào đây, không tự suy luật).
POLICY_SELF = "self"
POLICY_REQUEST = "request"
POLICY_CONTACT_BTC = "contact_btc"

RELATED_TYPE = "registration_cancellation"
NOTICE_TEMPLATE = "cancellation_notice_admin"
REQUESTED_TEMPLATE = "cancellation_requested"
DECIDED_TEMPLATE = "cancellation_decided"
REREGISTERED_TEMPLATE = "registration_reregistered_admin"
EMAIL_TEMPLATES = frozenset({NOTICE_TEMPLATE, REQUESTED_TEMPLATE, DECIDED_TEMPLATE, REREGISTERED_TEMPLATE})

RECENT_SELF_HOURS = 24 * 7

DIRECTION_LABELS = {FlightDirection.OUTBOUND: "Chiều đi", FlightDirection.RETURN: "Chiều về"}
RELEASED_LABELS = {
    "flights": "Vé máy bay",
    "buses": "Xe",
    "room": "Phòng",
    "gala": "Ghế Gala",
    "roles": "Bỏ vai trò",
}

Jobs = list[dict[str, Any]]


# --- Luật theo giai đoạn ---


def cancel_policy(event: Event, registration: Registration | None) -> str | None:
    """`None` khi không còn gì để huỷ (chưa đăng ký hoặc đã huỷ)."""
    if registration is None or registration.status == RegistrationStatus.CANCELLED:
        return None
    status = EventStatus(event.status)
    if status.at_least(EventStatus.EVENT_STARTED):
        return POLICY_CONTACT_BTC
    # Người đã báo "không tham gia" không có vé / phòng nào để giữ — không cần BTC duyệt.
    if status == EventStatus.INFORMATION_PUBLISHED and registration.is_participating:
        return POLICY_REQUEST
    return POLICY_SELF


def _ensure_policy(policy: str | None, expected: str) -> None:
    if policy == expected:
        return
    if policy is None:
        raise ConflictError("Đăng ký này đã huỷ rồi.", code="ALREADY_CANCELLED")
    if policy == POLICY_CONTACT_BTC:
        raise ConflictError(
            "Chương trình đã bắt đầu nên không huỷ được trên hệ thống. "
            "Vui lòng liên hệ Ban tổ chức để xử lý ngoại lệ.",
            code="EVENT_ALREADY_STARTED",
        )
    if policy == POLICY_REQUEST:
        raise ConflictError(
            "Ban tổ chức đã công bố vé máy bay, xe và phòng. Hãy gửi yêu cầu huỷ để Ban tổ chức duyệt.",
            code="CANCELLATION_REQUIRES_APPROVAL",
        )
    raise ConflictError(
        "Thông tin chưa được công bố nên bạn tự huỷ được ngay, không cần gửi yêu cầu.",
        code="SELF_CANCEL_AVAILABLE",
    )


# --- CBNV ---


def self_cancel(
    db: Session,
    *,
    event: Event,
    user: User,
    registration: Registration,
    reason: str,
    ip_address: str | None = None,
) -> tuple[Registration, Jobs]:
    """Tự huỷ trước khi công bố: huỷ ngay, gỡ mọi chỗ đã xếp, báo BTC.

    Cờ phí phạt theo quy định CBNV đã đồng ý: huỷ sau hạn đăng ký thì thuộc diện phí phạt.
    """
    _ensure_policy(cancel_policy(event, registration), POLICY_SELF)
    event_id, registration_id, user_id = event.id, registration.id, user.id

    with immediate_transaction(db):
        event = db.get(Event, event_id)
        registration = db.get(Registration, registration_id)
        # Kiểm tra lại trong khoá ghi: BTC có thể vừa bấm công bố giữa hai lần đọc.
        _ensure_policy(cancel_policy(event, registration), POLICY_SELF)

        now = utcnow_iso()
        after_deadline = is_expired(event.registration_closes_at)
        penalty = after_deadline and registration.is_participating
        before = audit_service.snapshot(registration, registration_service.AUDITED_FIELDS)

        # Chụp trước khi gỡ: sau release thì leader_user_id đã null, mail BTC sẽ mất cảnh báo.
        was_leader = (
            db.scalar(select(Team.id).where(Team.leader_user_id == registration.user_id))
            is not None
        )
        released = release_allocations(db, registration)
        _mark_cancelled(db, event, registration, reason=reason, penalty_applied=penalty, at=now)
        cancellation = RegistrationCancellation(
            event_id=event_id,
            registration_id=registration_id,
            user_id=user_id,
            mode=CancellationMode.SELF,
            status=CancellationStatus.APPROVED,
            reason=reason,
            event_status=event.status,
            after_deadline=after_deadline,
            requested_at=now,
            decided_at=now,
            penalty_applied=penalty,
            released_items=_dump(released),
        )
        db.add(cancellation)
        db.flush()

        audit_service.log(
            db,
            action="registration.cancelled",
            entity_type="registration",
            entity_id=registration_id,
            actor_id=user_id,
            event_id=event_id,
            before=before,
            after={
                "status": registration.status,
                "penalty_applied": penalty,
                "released": released,
                "cancellation_id": cancellation.id,
            },
            reason=reason,
            ip_address=ip_address,
        )
        jobs = [_registration_email(db, event, registration)]
        jobs += _notify_organizers(db, event, cancellation, kind="self", is_team_leader=was_leader)

    db.refresh(registration)
    logger.info("Tự huỷ đăng ký #%s (phí phạt=%s, gỡ %s)", registration_id, penalty, list(released))
    return registration, jobs


def request_cancellation(
    db: Session,
    *,
    event: Event,
    user: User,
    registration: Registration,
    reason: str,
    ip_address: str | None = None,
) -> tuple[Registration, Jobs]:
    """Xin huỷ sau công bố: chưa gỡ gì, chỉ ghi yêu cầu và báo BTC."""
    _ensure_policy(cancel_policy(event, registration), POLICY_REQUEST)
    event_id, registration_id, user_id = event.id, registration.id, user.id

    try:
        with immediate_transaction(db):
            event = db.get(Event, event_id)
            registration = db.get(Registration, registration_id)
            _ensure_policy(cancel_policy(event, registration), POLICY_REQUEST)
            if _pending(db, registration_id) is not None:
                raise _already_pending()

            cancellation = RegistrationCancellation(
                event_id=event_id,
                registration_id=registration_id,
                user_id=user_id,
                mode=CancellationMode.REQUEST,
                status=CancellationStatus.PENDING,
                reason=reason,
                event_status=event.status,
                after_deadline=is_expired(event.registration_closes_at),
                requested_at=utcnow_iso(),
            )
            db.add(cancellation)
            db.flush()

            audit_service.log(
                db,
                action="registration.cancellation_requested",
                entity_type="registration",
                entity_id=registration_id,
                actor_id=user_id,
                event_id=event_id,
                after={"cancellation_id": cancellation.id, "status": cancellation.status},
                reason=reason,
                ip_address=ip_address,
            )
            jobs = [_cancellation_email(db, event, cancellation, cancellation.user, REQUESTED_TEMPLATE, "requested")]
            jobs += _notify_organizers(db, event, cancellation, kind="request")
    except IntegrityError as exc:
        # Hai lần bấm đồng thời: index "một yêu cầu đang chờ / đăng ký" chặn lần thứ hai.
        raise _already_pending() from exc

    db.refresh(registration)
    return registration, jobs


def withdraw_request(
    db: Session,
    *,
    event: Event,
    user: User,
    registration: Registration,
    ip_address: str | None = None,
) -> tuple[Registration, Jobs]:
    event_id, registration_id, user_id = event.id, registration.id, user.id

    with immediate_transaction(db):
        event = db.get(Event, event_id)
        cancellation = _pending(db, registration_id)
        if cancellation is None:
            raise ConflictError(
                "Không có yêu cầu huỷ nào đang chờ duyệt.", code="CANCELLATION_NOT_PENDING"
            )
        cancellation.status = CancellationStatus.WITHDRAWN
        cancellation.decided_by = user_id
        cancellation.decided_at = utcnow_iso()
        db.flush()

        audit_service.log(
            db,
            action="registration.cancellation_withdrawn",
            entity_type="registration",
            entity_id=registration_id,
            actor_id=user_id,
            event_id=event_id,
            after={"cancellation_id": cancellation.id, "status": cancellation.status},
            ip_address=ip_address,
        )
        jobs = _notify_organizers(db, event, cancellation, kind="withdrawn")

    registration = db.get(Registration, registration_id)
    db.refresh(registration)
    return registration, jobs


# --- BTC ---


def approve(
    db: Session,
    *,
    event: Event,
    actor: User,
    cancellation_id: int,
    penalty_applied: bool,
    penalty_note: str | None = None,
    decision_note: str | None = None,
    new_leader_user_id: int | None = None,
    ip_address: str | None = None,
) -> tuple[dict[str, Any], Jobs]:
    """Duyệt yêu cầu huỷ: huỷ đăng ký, gỡ mọi chỗ, lưu quyết định phí phạt, báo CBNV.

    Người huỷ là Trưởng nhóm thì BTC chọn luôn người thay (`new_leader_user_id`) — cùng transaction,
    chỉ định lỗi thì việc huỷ cũng không được ghi.
    """
    event_id, actor_id = event.id, actor.id

    with immediate_transaction(db):
        event = db.get(Event, event_id)
        cancellation = _require_pending(db, event_id, cancellation_id)
        registration = cancellation.registration
        if registration.status == RegistrationStatus.CANCELLED:
            raise ConflictError("Đăng ký này đã huỷ rồi.", code="ALREADY_CANCELLED")

        now = utcnow_iso()
        before = audit_service.snapshot(registration, registration_service.AUDITED_FIELDS)
        led_team_ids = [team.id for team in team_leader_service.teams_led_by(db, registration.user_id)]
        released = release_allocations(db, registration)
        new_leader = _replace_leader(
            db,
            event_id=event_id,
            led_team_ids=led_team_ids,
            new_leader_user_id=new_leader_user_id,
            actor_id=actor_id,
            ip_address=ip_address,
        )
        _mark_cancelled(
            db, event, registration, reason=cancellation.reason, penalty_applied=penalty_applied, at=now
        )
        _decide(
            cancellation,
            status=CancellationStatus.APPROVED,
            actor_id=actor_id,
            at=now,
            decision_note=decision_note,
            penalty_applied=penalty_applied,
            penalty_note=penalty_note if penalty_applied else None,
            released=released,
        )

        audit_service.log(
            db,
            action="registration.cancellation_approved",
            entity_type="registration",
            entity_id=registration.id,
            actor_id=actor_id,
            event_id=event_id,
            before=before,
            after={
                "cancellation_id": cancellation.id,
                "status": registration.status,
                "penalty_applied": penalty_applied,
                "penalty_note": cancellation.penalty_note,
                "released": released,
                "new_leader": new_leader,
            },
            reason=decision_note or cancellation.reason,
            ip_address=ip_address,
        )
        jobs = [_cancellation_email(db, event, cancellation, cancellation.user, DECIDED_TEMPLATE, "decided")]

    return get_row(db, event_id, cancellation_id), jobs


def reject(
    db: Session,
    *,
    event: Event,
    actor: User,
    cancellation_id: int,
    decision_note: str,
    ip_address: str | None = None,
) -> tuple[dict[str, Any], Jobs]:
    """Từ chối: đăng ký và mọi chỗ đã xếp giữ nguyên; CBNV nhận lý do."""
    event_id, actor_id = event.id, actor.id

    with immediate_transaction(db):
        event = db.get(Event, event_id)
        cancellation = _require_pending(db, event_id, cancellation_id)
        _decide(
            cancellation,
            status=CancellationStatus.REJECTED,
            actor_id=actor_id,
            at=utcnow_iso(),
            decision_note=decision_note,
            penalty_applied=False,
            penalty_note=None,
            released=None,
        )
        audit_service.log(
            db,
            action="registration.cancellation_rejected",
            entity_type="registration",
            entity_id=cancellation.registration_id,
            actor_id=actor_id,
            event_id=event_id,
            after={"cancellation_id": cancellation.id, "status": cancellation.status},
            reason=decision_note,
            ip_address=ip_address,
        )
        jobs = [_cancellation_email(db, event, cancellation, cancellation.user, DECIDED_TEMPLATE, "decided")]

    return get_row(db, event_id, cancellation_id), jobs


def admin_cancel(
    db: Session,
    *,
    event: Event,
    actor: User,
    registration_id: int,
    reason: str,
    penalty_applied: bool,
    penalty_note: str | None = None,
    new_leader_user_id: int | None = None,
    ip_address: str | None = None,
) -> tuple[dict[str, Any], Jobs]:
    """BTC huỷ thay CBNV — lối ngoại lệ, dùng được cả khi chương trình đã bắt đầu.

    Người đó đang có yêu cầu chờ duyệt thì coi như duyệt luôn yêu cầu đó, không tạo dòng thứ hai.
    """
    event_id, actor_id = event.id, actor.id

    with immediate_transaction(db):
        event = db.get(Event, event_id)
        registration = db.scalar(
            select(Registration).where(
                Registration.id == registration_id, Registration.event_id == event_id
            )
        )
        if registration is None:
            raise NotFoundError(
                f"Không tìm thấy đăng ký #{registration_id} trong kỳ này.",
                code="REGISTRATION_NOT_FOUND",
            )
        if registration.status == RegistrationStatus.CANCELLED:
            raise ConflictError("Đăng ký này đã huỷ rồi.", code="ALREADY_CANCELLED")
        if event.status == EventStatus.COMPLETED:
            raise ConflictError(
                "Kỳ đã kết thúc, không huỷ đăng ký được nữa.", code="EVENT_COMPLETED"
            )

        now = utcnow_iso()
        before = audit_service.snapshot(registration, registration_service.AUDITED_FIELDS)
        led_team_ids = [team.id for team in team_leader_service.teams_led_by(db, registration.user_id)]
        released = release_allocations(db, registration)
        new_leader = _replace_leader(
            db,
            event_id=event_id,
            led_team_ids=led_team_ids,
            new_leader_user_id=new_leader_user_id,
            actor_id=actor_id,
            ip_address=ip_address,
        )
        _mark_cancelled(db, event, registration, reason=reason, penalty_applied=penalty_applied, at=now)

        cancellation = _pending(db, registration.id)
        if cancellation is None:
            cancellation = RegistrationCancellation(
                event_id=event_id,
                registration_id=registration.id,
                user_id=registration.user_id,
                mode=CancellationMode.ADMIN,
                status=CancellationStatus.PENDING,
                reason=reason,
                event_status=event.status,
                after_deadline=is_expired(event.registration_closes_at),
                requested_at=now,
            )
            db.add(cancellation)
            decision_note = None
        else:
            decision_note = reason
        _decide(
            cancellation,
            status=CancellationStatus.APPROVED,
            actor_id=actor_id,
            at=now,
            decision_note=decision_note,
            penalty_applied=penalty_applied,
            penalty_note=penalty_note if penalty_applied else None,
            released=released,
        )
        db.flush()

        audit_service.log(
            db,
            action="registration.cancelled_by_admin",
            entity_type="registration",
            entity_id=registration.id,
            actor_id=actor_id,
            event_id=event_id,
            before=before,
            after={
                "cancellation_id": cancellation.id,
                "status": registration.status,
                "penalty_applied": penalty_applied,
                "released": released,
                "new_leader": new_leader,
            },
            reason=reason,
            ip_address=ip_address,
        )
        jobs = [_cancellation_email(db, event, cancellation, cancellation.user, DECIDED_TEMPLATE, "decided")]
        cancellation_id = cancellation.id

    return get_row(db, event_id, cancellation_id), jobs


# --- Gỡ chỗ đã xếp ---


def release_allocations(db: Session, registration: Registration) -> dict[str, list[str]]:
    """Xoá mọi bản ghi phân bổ của một đăng ký, trả mô tả những gì đã gỡ (để audit + báo BTC).

    Ghế Gala được trả hẳn về sơ đồ (không giữ lại cho team): team đã ít đi một người tham gia.
    Người này đang là Trưởng xe thì bỏ luôn vai trò — không để hành khách gọi cho người không đi.
    Người này đang là Trưởng nhóm (`teams.leader_user_id`) thì gỡ luôn chức và hạ vai trò về CBNV — nếu
    không họ huỷ rồi vẫn giữ/xác nhận/gán ghế Gala cho cả team. BTC chỉ định người thay trên dashboard
    hoặc ngay khi duyệt huỷ (team_leader_service).
    """
    released: dict[str, list[str]] = {key: [] for key in RELEASED_LABELS}

    for assignment in db.scalars(
        select(FlightAssignment)
        .where(FlightAssignment.registration_id == registration.id)
        .options(selectinload(FlightAssignment.flight))
    ):
        direction = DIRECTION_LABELS.get(assignment.direction, assignment.direction)
        released["flights"].append(f"{assignment.flight.flight_code} ({direction})")
        db.delete(assignment)

    for assignment in db.scalars(
        select(BusAssignment)
        .where(BusAssignment.registration_id == registration.id)
        .options(selectinload(BusAssignment.bus).selectinload(Bus.trip_leg))
    ):
        released["buses"].append(f"{assignment.bus.bus_code} – {assignment.bus.trip_leg.name}")
        db.delete(assignment)

    room = db.scalar(
        select(RoomAssignment)
        .where(RoomAssignment.registration_id == registration.id)
        .options(selectinload(RoomAssignment.room).selectinload(Room.hotel))
    )
    if room is not None:
        captain = " (trưởng phòng)" if room.is_room_captain else ""
        released["room"].append(f"Phòng {room.room.room_number} – {room.room.hotel.name}{captain}")
        db.delete(room)

    seat = db.scalar(
        select(GalaSeatAssignment)
        .where(GalaSeatAssignment.registration_id == registration.id)
        .options(selectinload(GalaSeatAssignment.seat).selectinload(GalaSeat.table))
    )
    if seat is not None:
        released["gala"].append(f"Bàn {seat.seat.table.table_code} – ghế {seat.seat.seat_number}")
        db.delete(seat)

    for bus in db.scalars(
        select(Bus).where(Bus.event_id == registration.event_id, Bus.leader_user_id == registration.user_id)
    ):
        released["roles"].append(f"Trưởng xe {bus.bus_code}")
        bus.leader_user_id = None
        bus.leader_name = None
        bus.leader_phone = None

    for team_name in team_leader_service.remove_leadership(db, registration.user):
        released["roles"].append(f"Trưởng nhóm {team_name}")

    db.flush()
    return {key: items for key, items in released.items() if items}


def released_lines(released: dict[str, list[str]]) -> list[str]:
    return [
        f"{label}: {', '.join(released[key])}" for key, label in RELEASED_LABELS.items() if released.get(key)
    ]


# --- Truy vấn ---


def latest_for(db: Session, registration_id: int) -> RegistrationCancellation | None:
    return db.scalar(
        select(RegistrationCancellation)
        .where(RegistrationCancellation.registration_id == registration_id)
        .order_by(RegistrationCancellation.id.desc())
        .limit(1)
    )


def brief(cancellation: RegistrationCancellation | None) -> dict[str, Any] | None:
    if cancellation is None:
        return None
    return {
        "id": cancellation.id,
        "mode": cancellation.mode,
        "status": cancellation.status,
        "reason": cancellation.reason,
        "requested_at": cancellation.requested_at,
        "decided_at": cancellation.decided_at,
        "decision_note": cancellation.decision_note,
        "penalty_applied": cancellation.penalty_applied,
        "penalty_note": cancellation.penalty_note,
    }


def list_cancellations(
    db: Session,
    *,
    event_id: int,
    status: str | None = None,
    mode: str | None = None,
    search: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    conditions = [RegistrationCancellation.event_id == event_id]
    if status:
        conditions.append(RegistrationCancellation.status == status)
    if mode:
        conditions.append(RegistrationCancellation.mode == mode)
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        conditions.append(
            or_(User.full_name.ilike(pattern), User.email.ilike(pattern), User.employee_code.ilike(pattern))
        )

    base = select(RegistrationCancellation).join(User, User.id == RegistrationCancellation.user_id).where(*conditions)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(
        base.order_by(
            # Việc cần BTC xử lý lên đầu, còn lại mới nhất trước.
            case((RegistrationCancellation.status == CancellationStatus.PENDING, 0), else_=1),
            RegistrationCancellation.requested_at.desc(),
            RegistrationCancellation.id.desc(),
        )
        .limit(limit)
        .offset(offset)
        .options(*_row_options())
    ).all()
    leaders = _leader_ids(db, [row.user_id for row in rows])
    return [cancellation_row(row, is_team_leader=row.user_id in leaders) for row in rows], total


def get_row(db: Session, event_id: int, cancellation_id: int) -> dict[str, Any]:
    cancellation = db.scalar(
        select(RegistrationCancellation)
        .where(RegistrationCancellation.id == cancellation_id, RegistrationCancellation.event_id == event_id)
        .options(*_row_options())
    )
    if cancellation is None:
        raise _not_found(cancellation_id)
    return cancellation_row(cancellation, is_team_leader=cancellation.user_id in _leader_ids(db, [cancellation.user_id]))


def cancellation_row(
    cancellation: RegistrationCancellation, *, is_team_leader: bool = False
) -> dict[str, Any]:
    person = cancellation.user
    return {
        **brief(cancellation),
        "registration_id": cancellation.registration_id,
        "event_status": cancellation.event_status,
        "event_status_label": event_service.status_label(EventStatus(cancellation.event_status)),
        "after_deadline": cancellation.after_deadline,
        "decided_by_name": cancellation.decider.full_name if cancellation.decider else None,
        "released": cancellation.released,
        "reregistered_at": _reregistered_at(cancellation),
        "user": {
            "id": person.id,
            "employee_code": person.employee_code,
            "full_name": person.full_name,
            "email": person.email,
            "team_id": person.team_id,
            "team_name": person.team.name if person.team else None,
            "is_team_leader": is_team_leader,
        },
    }


def dashboard_counts(db: Session, *, event_id: int) -> dict[str, int]:
    pending = db.scalar(
        select(func.count(RegistrationCancellation.id)).where(
            RegistrationCancellation.event_id == event_id,
            RegistrationCancellation.status == CancellationStatus.PENDING,
        )
    )
    self_recent = db.scalar(
        select(func.count(RegistrationCancellation.id)).where(
            RegistrationCancellation.event_id == event_id,
            RegistrationCancellation.mode == CancellationMode.SELF,
            RegistrationCancellation.requested_at >= iso_in(hours=-RECENT_SELF_HOURS),
        )
    )
    # Đăng ký lại sau khi đã huỷ (đăng ký hiện tại gửi SAU lần huỷ được duyệt) — BTC phải xếp chỗ lại.
    reregistered_recent = db.scalar(
        select(func.count(func.distinct(Registration.id)))
        .join(RegistrationCancellation, RegistrationCancellation.registration_id == Registration.id)
        .where(
            Registration.event_id == event_id,
            Registration.status == RegistrationStatus.SUBMITTED,
            RegistrationCancellation.status == CancellationStatus.APPROVED,
            # `>=`: đăng ký lại ngay trong cùng giây với lúc huỷ vẫn phải tính. Không lẫn được với lần
            # đăng ký gốc — huỷ được duyệt luôn chuyển đăng ký sang `cancelled`.
            Registration.submitted_at >= RegistrationCancellation.decided_at,
            Registration.submitted_at >= iso_in(hours=-RECENT_SELF_HOURS),
        )
    )
    return {
        "pending": pending or 0,
        "self_recent": self_recent or 0,
        "reregistered_recent": reregistered_recent or 0,
    }


def notify_reregistered(
    db: Session, *, event: Event, registration: Registration, ip_address: str | None = None
) -> Jobs:
    """CBNV đã huỷ đăng ký lại khi BTC đã đóng đăng ký (đang xếp chỗ): ghi audit và báo BTC để xếp lại.

    Gọi sau khi đăng ký đã commit — đây là thông báo, không phải trạng thái nghiệp vụ.
    """
    event_id, registration_id = event.id, registration.id
    with immediate_transaction(db):
        event = db.get(Event, event_id)
        registration = db.get(Registration, registration_id)
        cancellation = latest_for(db, registration_id)
        if cancellation is None:
            return []
        audit_service.log(
            db,
            action="registration.reregistered",
            entity_type="registration",
            entity_id=registration_id,
            actor_id=registration.user_id,
            event_id=event_id,
            after={"cancellation_id": cancellation.id, "event_status": event.status},
            ip_address=ip_address,
        )
        jobs = [
            _cancellation_email(db, event, cancellation, organizer, REREGISTERED_TEMPLATE, "reregistered")
            for organizer in _organizers(db)
            if organizer.email
        ]
    return jobs


def rebuild_email_context(
    db: Session, *, template: str, cancellation: RegistrationCancellation, user: User
) -> dict[str, Any] | None:
    """Context để gửi lại một thư lỗi, hoặc `None` khi thư đó không còn đúng nữa."""
    event = db.get(Event, cancellation.event_id)
    if template == NOTICE_TEMPLATE:
        if user.role not in ADMIN_ROLES:
            return None
        if cancellation.mode == CancellationMode.SELF:
            if _reregistered_at(cancellation):
                return None  # người này đã đăng ký lại — báo "đã huỷ" lúc này là sai
            kind = "self"
        elif cancellation.status == CancellationStatus.PENDING:
            kind = "request"
        elif cancellation.status == CancellationStatus.WITHDRAWN:
            kind = "withdrawn"
        else:
            return None  # BTC đã xử lý xong, nhắc lại là thừa
    elif template == REQUESTED_TEMPLATE:
        if cancellation.user_id != user.id or cancellation.status != CancellationStatus.PENDING:
            return None
        kind = "requested"
    elif template == DECIDED_TEMPLATE:
        decided = cancellation.status in (CancellationStatus.APPROVED, CancellationStatus.REJECTED)
        if cancellation.user_id != user.id or not decided or cancellation.mode == CancellationMode.SELF:
            return None
        kind = "decided"
    elif template == REREGISTERED_TEMPLATE:
        still_back = (
            _reregistered_at(cancellation) is not None
            and cancellation.registration.status == RegistrationStatus.SUBMITTED
        )
        if user.role not in ADMIN_ROLES or not still_back:
            return None
        kind = "reregistered"
    else:
        return None
    return _context(db, event, cancellation, user, kind)


# --- Nội bộ ---


def _row_options() -> tuple:
    return (
        selectinload(RegistrationCancellation.user).selectinload(User.team),
        selectinload(RegistrationCancellation.decider),
        selectinload(RegistrationCancellation.registration),
    )


def _reregistered_at(cancellation: RegistrationCancellation) -> str | None:
    """Lúc CBNV đăng ký lại sau lần huỷ này (đăng ký hiện tại gửi sau khi huỷ có hiệu lực), nếu có."""
    registration = cancellation.registration
    if (
        cancellation.status != CancellationStatus.APPROVED
        or registration is None
        or registration.status != RegistrationStatus.SUBMITTED
        or not registration.submitted_at
        or not cancellation.decided_at
        or registration.submitted_at < cancellation.decided_at
    ):
        return None
    return registration.submitted_at


def _replace_leader(
    db: Session,
    *,
    event_id: int,
    led_team_ids: list[int],
    new_leader_user_id: int | None,
    actor_id: int,
    ip_address: str | None,
) -> dict[str, Any] | None:
    """Chỉ định Trưởng nhóm thay người vừa huỷ, trong transaction huỷ đang mở."""
    if new_leader_user_id is None:
        return None
    if not led_team_ids:
        raise ConflictError(
            "Người huỷ không phải Trưởng nhóm nên không cần chỉ định người thay.", code="NOT_TEAM_LEADER"
        )
    candidate = db.get(User, new_leader_user_id)
    team_id = (
        candidate.team_id
        if candidate is not None and candidate.team_id in led_team_ids
        else led_team_ids[0]
    )
    return team_leader_service.apply(
        db,
        event_id=event_id,
        team_id=team_id,
        user_id=new_leader_user_id,
        actor_id=actor_id,
        ip_address=ip_address,
        reason="Thay Trưởng nhóm đã huỷ đăng ký",
    )


def _leader_ids(db: Session, user_ids: list[int]) -> set[int]:
    """Những user đang là Trưởng nhóm (`teams.leader_user_id`) — để BTC thấy ngay trên danh sách huỷ."""
    if not user_ids:
        return set()
    return set(
        db.scalars(select(Team.leader_user_id).where(Team.leader_user_id.in_(user_ids))).all()
    )


def _pending(db: Session, registration_id: int) -> RegistrationCancellation | None:
    return db.scalar(
        select(RegistrationCancellation).where(
            RegistrationCancellation.registration_id == registration_id,
            RegistrationCancellation.status == CancellationStatus.PENDING,
        )
    )


def _require_pending(db: Session, event_id: int, cancellation_id: int) -> RegistrationCancellation:
    cancellation = db.scalar(
        select(RegistrationCancellation).where(
            RegistrationCancellation.id == cancellation_id, RegistrationCancellation.event_id == event_id
        )
    )
    if cancellation is None:
        raise _not_found(cancellation_id)
    if cancellation.status != CancellationStatus.PENDING:
        raise ConflictError(
            "Yêu cầu huỷ này đã được xử lý hoặc CBNV đã rút.", code="CANCELLATION_NOT_PENDING"
        )
    return cancellation


def _decide(
    cancellation: RegistrationCancellation,
    *,
    status: CancellationStatus,
    actor_id: int,
    at: str,
    decision_note: str | None,
    penalty_applied: bool,
    penalty_note: str | None,
    released: dict[str, list[str]] | None,
) -> None:
    cancellation.status = status
    cancellation.decided_by = actor_id
    cancellation.decided_at = at
    cancellation.decision_note = decision_note or None
    cancellation.penalty_applied = penalty_applied
    cancellation.penalty_note = penalty_note or None
    if released is not None:
        cancellation.released_items = _dump(released)


def _mark_cancelled(
    db: Session, event: Event, registration: Registration, *, reason: str, penalty_applied: bool, at: str
) -> None:
    registration.status = RegistrationStatus.CANCELLED
    registration.cancelled_at = at
    registration.cancel_reason = reason
    registration.penalty_applied = penalty_applied
    registration_service.clear_bus_needs(db, registration)
    db.flush()


def _organizers(db: Session) -> list[User]:
    return list(
        db.scalars(
            select(User).where(User.role.in_(ADMIN_ROLES), User.is_active.is_(True)).order_by(User.id)
        )
    )


def _notify_organizers(
    db: Session,
    event: Event,
    cancellation: RegistrationCancellation,
    *,
    kind: str,
    is_team_leader: bool | None = None,
) -> Jobs:
    """Mỗi người BTC một thư riêng (có `user_id`) — nhật ký email và gửi lại theo từng người."""
    return [
        _cancellation_email(db, event, cancellation, organizer, NOTICE_TEMPLATE, kind, is_team_leader=is_team_leader)
        for organizer in _organizers(db)
        if organizer.email
    ]


def _cancellation_email(
    db: Session,
    event: Event,
    cancellation: RegistrationCancellation,
    recipient: User,
    template: str,
    kind: str,
    *,
    is_team_leader: bool | None = None,
) -> dict[str, Any]:
    context = _context(db, event, cancellation, recipient, kind, is_team_leader=is_team_leader)
    entry = email_service.enqueue(
        db,
        template=template,
        to_email=recipient.email,
        context=context,
        user_id=recipient.id,
        related_type=RELATED_TYPE,
        related_id=cancellation.id,
    )
    db.flush()
    return {"log_id": entry.id, "context": context}


def _registration_email(db: Session, event: Event, registration: Registration) -> dict[str, Any]:
    """Thư "đã huỷ" cho chính CBNV — dùng lại mẫu `registration_cancelled` sẵn có."""
    user = registration.user
    context = email_templates.registration_context(
        event=event,
        user=user,
        registration=registration,
        missing_profile_fields=registration_service.missing_profile_fields(user),
    )
    entry = email_service.enqueue(
        db,
        template="registration_cancelled",
        to_email=user.email,
        context=context,
        user_id=user.id,
        related_type="registration",
        related_id=registration.id,
    )
    db.flush()
    return {"log_id": entry.id, "context": context}


def _context(
    db: Session,
    event: Event,
    cancellation: RegistrationCancellation,
    recipient: User,
    kind: str,
    *,
    is_team_leader: bool | None = None,
) -> dict[str, Any]:
    if is_team_leader is None:
        is_leader = (
            db.scalar(select(Team.id).where(Team.leader_user_id == cancellation.user_id))
            is not None
        )
    else:
        is_leader = is_team_leader
    reregistered = kind == "reregistered"
    return email_templates.cancellation_context(
        event=event,
        cancellation=cancellation,
        recipient=recipient,
        kind=kind,
        # Thư "đăng ký lại" nói giai đoạn HIỆN TẠI của kỳ, các thư khác nói giai đoạn lúc huỷ.
        event_status_label=event_service.status_label(
            EventStatus(event.status if reregistered else cancellation.event_status)
        ),
        released_lines=released_lines(cancellation.released),
        is_team_leader=is_leader,
        reregistered_at=_reregistered_at(cancellation) if reregistered else None,
    )


def _dump(released: dict[str, list[str]]) -> str:
    return json.dumps(released, ensure_ascii=False)


def _already_pending() -> ConflictError:
    return ConflictError(
        "Bạn đã gửi yêu cầu huỷ, đang chờ Ban tổ chức duyệt.", code="CANCELLATION_PENDING"
    )


def _not_found(cancellation_id: int) -> NotFoundError:
    return NotFoundError(
        f"Không tìm thấy yêu cầu huỷ #{cancellation_id} trong kỳ này.", code="CANCELLATION_NOT_FOUND"
    )
