"""Nghiệp vụ đăng ký tham gia Team Building.

Ba việc phải làm nguyên khối trong một transaction: ghi đăng ký, ghi nhu cầu xe
từng chặng, ghi bằng chứng đồng ý quy định. Thiếu một mảnh là dữ liệu không dùng
được: đăng ký không có consent thì không đòi phí phạt được, không có bus_needs
thì thuật toán phân xe không biết ai cần xe.
"""

import logging
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.core.timeutils import is_expired, utcnow_iso
from app.models.enums import EventStatus, RegistrationStatus
from app.models.event import Event
from app.models.flight import Shift
from app.models.org import WorkLocation
from app.models.registration import Consent, Registration, RegistrationBusNeed
from app.models.transportation import PickupPoint, TripLeg
from app.models.user import User
from app.services import audit_service

logger = logging.getLogger(__name__)

# Không có đủ những trường này thì BTC không xuất được vé máy bay và không phân
# phòng theo giới được — chặn ngay lúc đăng ký thay vì phát hiện lúc ra sân bay.
REQUIRED_PROFILE_FIELDS: dict[str, str] = {
    "date_of_birth": "Ngày sinh",
    "id_card_number": "Số CCCD/Hộ chiếu",
    "phone": "Số điện thoại",
    "gender": "Giới tính",
}

AUDITED_FIELDS = [
    "is_participating",
    "shift_id",
    "departure_location_id",
    "companion_count",
    "status",
    "wish_note",
]


# --- Truy vấn ---


def get_registration(db: Session, *, event_id: int, user_id: int) -> Registration | None:
    return db.scalar(
        select(Registration)
        .where(Registration.event_id == event_id, Registration.user_id == user_id)
        .options(selectinload(Registration.bus_needs), selectinload(Registration.shift))
    )


def require_registration(db: Session, *, event_id: int, user_id: int) -> Registration:
    registration = get_registration(db, event_id=event_id, user_id=user_id)
    if registration is None:
        raise NotFoundError(
            "Bạn chưa đăng ký cho kỳ Team Building này.", code="REGISTRATION_NOT_FOUND"
        )
    return registration


# --- Ghi ---


def submit(
    db: Session,
    *,
    event: Event,
    user: User,
    data: dict[str, Any],
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> Registration:
    """Tạo đăng ký mới, hoặc kích hoạt lại đăng ký đã huỷ."""
    _require_open(event)

    existing = get_registration(db, event_id=event.id, user_id=user.id)
    if existing and existing.status != RegistrationStatus.CANCELLED:
        raise ConflictError(
            "Bạn đã đăng ký rồi. Dùng chức năng chỉnh sửa để thay đổi thông tin.",
            code="ALREADY_REGISTERED",
            details={"registration_id": existing.id},
        )

    _apply_profile_patch(db, user, data.get("profile_patch"))
    is_participating = data["is_participating"]

    if is_participating:
        _check_profile_complete(user)
        _check_terms_version(event, data.get("agreed_terms_version"))
        _validate_shift(db, event, data.get("shift_id"))
        _validate_location(db, data.get("departure_location_id"))

    registration = existing or Registration(event_id=event.id, user_id=user.id)
    registration.is_participating = is_participating
    registration.not_participating_reason = (
        None if is_participating else data.get("not_participating_reason")
    )
    registration.shift_id = data.get("shift_id") if is_participating else None
    registration.departure_location_id = (
        data.get("departure_location_id") or user.work_location_id
    )
    registration.wish_note = data.get("wish_note")
    registration.companion_count = data.get("companion_count", 0)
    registration.status = RegistrationStatus.SUBMITTED
    registration.submitted_at = utcnow_iso()
    # Kích hoạt lại sau khi huỷ: xoá dấu vết huỷ cũ để dữ liệu không mâu thuẫn.
    registration.cancelled_at = None
    registration.cancel_reason = None
    registration.penalty_applied = False

    db.add(registration)
    db.flush()

    _replace_bus_needs(db, event, registration, data.get("bus_needs") or [])
    if is_participating:
        _record_consent(
            db,
            event=event,
            user=user,
            version=data["agreed_terms_version"],
            ip_address=ip_address,
            user_agent=user_agent,
        )

    audit_service.log(
        db,
        action="registration.submitted",
        entity_type="registration",
        entity_id=registration.id,
        actor_id=user.id,
        event_id=event.id,
        after=audit_service.snapshot(registration, AUDITED_FIELDS),
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(registration)
    logger.info("Đăng ký: %s (tham gia=%s)", user.email, is_participating)
    return registration


def update(
    db: Session,
    *,
    event: Event,
    user: User,
    registration: Registration,
    data: dict[str, Any],
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> Registration:
    """Sửa đăng ký khi chương trình còn mở."""
    _require_open(event)
    if registration.status == RegistrationStatus.CANCELLED:
        raise ConflictError(
            "Đăng ký đã huỷ. Hãy đăng ký lại từ đầu.", code="REGISTRATION_CANCELLED"
        )

    before = audit_service.snapshot(registration, AUDITED_FIELDS)
    _apply_profile_patch(db, user, data.get("profile_patch"))

    will_participate = data.get("is_participating", registration.is_participating)
    if will_participate:
        _check_profile_complete(user)
        if "agreed_terms_version" in data and data["agreed_terms_version"]:
            _check_terms_version(event, data["agreed_terms_version"])
            _record_consent(
                db,
                event=event,
                user=user,
                version=data["agreed_terms_version"],
                ip_address=ip_address,
                user_agent=user_agent,
            )
        if "shift_id" in data:
            _validate_shift(db, event, data["shift_id"])
        if "departure_location_id" in data:
            _validate_location(db, data["departure_location_id"])

    for field in (
        "is_participating",
        "not_participating_reason",
        "shift_id",
        "departure_location_id",
        "wish_note",
        "companion_count",
    ):
        if field in data:
            setattr(registration, field, data[field])

    if not will_participate:
        # Chuyển sang không tham gia: dọn sạch nguyện vọng ca và nhu cầu xe,
        # tránh để lại dữ liệu rác làm thuật toán đếm nhầm.
        registration.shift_id = None
        _replace_bus_needs(db, event, registration, [])
    elif data.get("bus_needs") is not None:
        _replace_bus_needs(db, event, registration, data["bus_needs"])

    db.flush()
    after = audit_service.snapshot(registration, AUDITED_FIELDS)
    audit_service.log(
        db,
        action="registration.updated",
        entity_type="registration",
        entity_id=registration.id,
        actor_id=user.id,
        event_id=event.id,
        before=before,
        after=audit_service.diff(before, after),
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(registration)
    return registration


def cancel(
    db: Session,
    *,
    event: Event,
    user: User,
    registration: Registration,
    reason: str,
    ip_address: str | None = None,
) -> Registration:
    """Huỷ đăng ký.

    Huỷ sau hạn đăng ký thì đánh cờ `penalty_applied` theo quy định về phí phạt —
    hệ thống chỉ đánh dấu, việc thu phí do BTC quyết định.
    """
    if registration.status == RegistrationStatus.CANCELLED:
        raise ConflictError("Đăng ký này đã huỷ rồi.", code="ALREADY_CANCELLED")
    if EventStatus(event.status).at_least(EventStatus.EVENT_STARTED):
        raise ConflictError(
            "Chương trình đã bắt đầu, không huỷ được trên hệ thống. Vui lòng liên hệ BTC.",
            code="EVENT_ALREADY_STARTED",
        )

    before = audit_service.snapshot(registration, AUDITED_FIELDS)
    after_deadline = is_expired(event.registration_closes_at)

    registration.status = RegistrationStatus.CANCELLED
    registration.cancelled_at = utcnow_iso()
    registration.cancel_reason = reason
    registration.penalty_applied = after_deadline and registration.is_participating
    _replace_bus_needs(db, event, registration, [])
    db.flush()

    audit_service.log(
        db,
        action="registration.cancelled",
        entity_type="registration",
        entity_id=registration.id,
        actor_id=user.id,
        event_id=event.id,
        before=before,
        after={
            "status": registration.status,
            "penalty_applied": registration.penalty_applied,
        },
        reason=reason,
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(registration)
    logger.info(
        "Huỷ đăng ký: %s (phí phạt=%s)", user.email, registration.penalty_applied
    )
    return registration


# --- Danh sách cho BTC ---


def list_registrations(
    db: Session,
    *,
    event_id: int,
    search: str | None = None,
    team_id: int | None = None,
    shift_id: int | None = None,
    status: str | None = None,
    is_participating: bool | None = None,
    missing_documents: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Registration], int]:
    query = (
        select(Registration)
        .join(User, User.id == Registration.user_id)
        .where(Registration.event_id == event_id)
    )

    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(
            or_(
                User.full_name.like(pattern),
                User.email.like(pattern),
                User.employee_code.like(pattern),
            )
        )
    if team_id is not None:
        query = query.where(User.team_id == team_id)
    if shift_id is not None:
        query = query.where(Registration.shift_id == shift_id)
    if status is not None:
        query = query.where(Registration.status == status)
    if is_participating is not None:
        query = query.where(Registration.is_participating.is_(is_participating))
    if missing_documents:
        # Thiếu giấy tờ = không xuất được vé. BTC cần lọc riêng nhóm này để nhắc.
        query = query.where(
            or_(
                User.id_card_number.is_(None),
                User.id_card_number == "",
                User.date_of_birth.is_(None),
            )
        )

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = list(
        db.scalars(
            query.order_by(User.full_name)
            .limit(limit)
            .offset(offset)
            .options(
                selectinload(Registration.bus_needs),
                selectinload(Registration.shift),
                selectinload(Registration.user).selectinload(User.team),
            )
        )
    )
    return rows, total


def get_stats(db: Session, *, event_id: int) -> dict[str, Any]:
    """Số liệu tổng quan cho dashboard BTC."""
    total_users = (
        db.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True))) or 0
    )
    base = select(func.count()).select_from(Registration).where(Registration.event_id == event_id)

    submitted = db.scalar(base.where(Registration.status == RegistrationStatus.SUBMITTED)) or 0
    cancelled = db.scalar(base.where(Registration.status == RegistrationStatus.CANCELLED)) or 0
    participating = (
        db.scalar(
            base.where(
                Registration.status == RegistrationStatus.SUBMITTED,
                Registration.is_participating.is_(True),
            )
        )
        or 0
    )

    by_shift = {
        code: count
        for code, count in db.execute(
            select(Shift.code, func.count(Registration.id))
            .join(Registration, Registration.shift_id == Shift.id)
            .where(
                Registration.event_id == event_id,
                Registration.status == RegistrationStatus.SUBMITTED,
                Registration.is_participating.is_(True),
            )
            .group_by(Shift.code)
        ).all()
    }

    bus_demand = {
        code: count
        for code, count in db.execute(
            select(TripLeg.code, func.count(RegistrationBusNeed.id))
            .join(RegistrationBusNeed, RegistrationBusNeed.trip_leg_id == TripLeg.id)
            .join(Registration, Registration.id == RegistrationBusNeed.registration_id)
            .where(
                Registration.event_id == event_id,
                Registration.status == RegistrationStatus.SUBMITTED,
                RegistrationBusNeed.needs_bus.is_(True),
            )
            .group_by(TripLeg.code)
        ).all()
    }

    missing_documents = (
        db.scalar(
            select(func.count())
            .select_from(Registration)
            .join(User, User.id == Registration.user_id)
            .where(
                Registration.event_id == event_id,
                Registration.status == RegistrationStatus.SUBMITTED,
                Registration.is_participating.is_(True),
                or_(
                    User.id_card_number.is_(None),
                    User.id_card_number == "",
                    User.date_of_birth.is_(None),
                ),
            )
        )
        or 0
    )

    return {
        "total_users": total_users,
        "submitted": submitted,
        "not_submitted": max(total_users - submitted - cancelled, 0),
        "participating": participating,
        "not_participating": submitted - participating,
        "cancelled": cancelled,
        "by_shift": by_shift,
        "bus_demand_by_leg": bus_demand,
        "missing_flight_documents": missing_documents,
    }


def get_consent_version(db: Session, *, event_id: int, user_id: int) -> str | None:
    consent = db.scalar(
        select(Consent)
        .where(Consent.event_id == event_id, Consent.user_id == user_id)
        .order_by(Consent.id.desc())
    )
    return consent.terms_version if consent else None


def can_edit(event: Event, registration: Registration) -> bool:
    return (
        event.status == EventStatus.REGISTRATION_OPEN
        and registration.status != RegistrationStatus.CANCELLED
    )


# --- Kiểm tra & nội bộ ---


def _require_open(event: Event) -> None:
    if event.status != EventStatus.REGISTRATION_OPEN:
        raise ConflictError(
            "Thời gian đăng ký đã đóng, không thay đổi được nữa. Liên hệ BTC nếu cần hỗ trợ.",
            code="REGISTRATION_CLOSED",
            details={"event_status": event.status},
        )


def _check_terms_version(event: Event, agreed_version: str | None) -> None:
    """Chặn trường hợp người dùng mở form từ trước khi BTC sửa quy định."""
    if agreed_version != event.terms_version:
        raise ConflictError(
            "Quy định chương trình đã được cập nhật. Vui lòng tải lại trang, "
            "đọc bản mới và xác nhận lại.",
            code="TERMS_VERSION_MISMATCH",
            details={"current_version": event.terms_version, "your_version": agreed_version},
        )


def missing_profile_fields(user: User) -> list[str]:
    """Nhãn những trường hồ sơ còn thiếu để BTC xuất được vé.

    Công khai (không phải `_private`) vì ngoài việc chặn đăng ký, email xác nhận cũng
    nhắc CBNV bổ sung — hai nơi phải dùng CÙNG một danh sách, không được lệch nhau.
    """
    return [
        label
        for field, label in REQUIRED_PROFILE_FIELDS.items()
        if not getattr(user, field, None)
    ]


def _check_profile_complete(user: User) -> None:
    missing = missing_profile_fields(user)
    if missing:
        raise AppError(
            "Thiếu thông tin bắt buộc để BTC xuất vé máy bay và bố trí phòng: "
            + ", ".join(missing)
            + ".",
            code="MISSING_PROFILE_FIELDS",
            details={"missing_fields": missing},
        )


def _validate_shift(db: Session, event: Event, shift_id: int | None) -> None:
    if shift_id is None:
        raise AppError("Vui lòng chọn ca đi.", code="SHIFT_REQUIRED")
    shift = db.get(Shift, shift_id)
    if shift is None or shift.event_id != event.id:
        raise NotFoundError("Ca đi không hợp lệ.", code="SHIFT_NOT_FOUND")


def _validate_location(db: Session, location_id: int | None) -> None:
    if location_id is not None and db.get(WorkLocation, location_id) is None:
        raise NotFoundError("Địa điểm xuất phát không hợp lệ.", code="LOCATION_NOT_FOUND")


def _replace_bus_needs(
    db: Session, event: Event, registration: Registration, needs: list[dict[str, Any]]
) -> None:
    """Ghi đè toàn bộ nhu cầu xe.

    Thay vì sửa từng dòng: form gửi lên trạng thái đầy đủ của cả 4 chặng, ghi đè
    là cách duy nhất đảm bảo bỏ tick một chặng thì dòng cũ biến mất.
    """
    for existing in list(registration.bus_needs):
        db.delete(existing)
    db.flush()

    if not needs:
        return

    valid_legs = {
        leg.id: leg
        for leg in db.scalars(select(TripLeg).where(TripLeg.event_id == event.id))
    }
    seen: set[int] = set()

    for need in needs:
        leg_id = need["trip_leg_id"]
        if leg_id not in valid_legs:
            raise NotFoundError(
                f"Chặng #{leg_id} không thuộc kỳ Team Building này.", code="TRIP_LEG_NOT_FOUND"
            )
        if leg_id in seen:
            raise ConflictError(
                f"Chặng '{valid_legs[leg_id].name}' bị khai báo hai lần.",
                code="DUPLICATE_TRIP_LEG",
            )
        seen.add(leg_id)

        pickup_point_id = need.get("pickup_point_id")
        if pickup_point_id is not None:
            point = db.get(PickupPoint, pickup_point_id)
            if point is None or point.event_id != event.id:
                raise NotFoundError(
                    "Điểm đón không hợp lệ.", code="PICKUP_POINT_NOT_FOUND"
                )

        db.add(
            RegistrationBusNeed(
                registration_id=registration.id,
                trip_leg_id=leg_id,
                needs_bus=need.get("needs_bus", False),
                # Không đi xe thì điểm đón vô nghĩa, bỏ đi cho dữ liệu sạch.
                pickup_point_id=pickup_point_id if need.get("needs_bus") else None,
                note=need.get("note"),
            )
        )
    db.flush()


def _record_consent(
    db: Session,
    *,
    event: Event,
    user: User,
    version: str,
    ip_address: str | None,
    user_agent: str | None,
) -> None:
    """Ghi bằng chứng đồng ý. Mỗi (user, event, version) chỉ một bản ghi."""
    existing = db.scalar(
        select(Consent).where(
            Consent.user_id == user.id,
            Consent.event_id == event.id,
            Consent.terms_version == version,
        )
    )
    if existing:
        return
    db.add(
        Consent(
            user_id=user.id,
            event_id=event.id,
            terms_version=version,
            agreed_at=utcnow_iso(),
            ip_address=ip_address,
            user_agent=(user_agent or "")[:512] or None,
        )
    )
    db.flush()


def _apply_profile_patch(db: Session, user: User, patch: dict[str, Any] | None) -> None:
    if not patch:
        return
    for field, value in patch.items():
        setattr(user, field, value)
    db.flush()
