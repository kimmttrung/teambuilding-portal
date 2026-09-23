"""Nghiệp vụ kỳ Team Building: tạo, cấu hình, chuyển trạng thái.

Chuyển trạng thái là thao tác nhạy cảm nhất của BTC — nó quyết định CBNV còn sửa được
đăng ký không, và thông tin phân bổ đã hiện ra chưa. Vì vậy mọi lần chuyển đều
kiểm tra hợp lệ và ghi audit log.
"""

import json
import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models.enums import ADMIN_ROLES, EventStatus, RegistrationStatus
from app.models.event import DEFAULT_EVENT_SETTINGS, Event, EventSetting
from app.models.flight import Shift
from app.models.registration import Registration
from app.models.transportation import TripLeg
from app.models.user import User
from app.services import audit_service

logger = logging.getLogger(__name__)

# Chuyển trạng thái nào là hợp lệ. Cố ý KHÔNG cho nhảy cóc:
# đóng đăng ký rồi mới phân bổ, phân bổ xong mới công bố.
ALLOWED_TRANSITIONS: dict[EventStatus, set[EventStatus]] = {
    EventStatus.DRAFT: {EventStatus.REGISTRATION_OPEN},
    EventStatus.REGISTRATION_OPEN: {EventStatus.DRAFT, EventStatus.REGISTRATION_CLOSED},
    EventStatus.REGISTRATION_CLOSED: {
        EventStatus.REGISTRATION_OPEN,  # mở lại cho người đăng ký muộn
        EventStatus.ALLOCATION_PROCESSING,
    },
    EventStatus.ALLOCATION_PROCESSING: {
        EventStatus.REGISTRATION_CLOSED,  # quay lại nếu cần sửa dữ liệu nguồn
        EventStatus.INFORMATION_PUBLISHED,
    },
    EventStatus.INFORMATION_PUBLISHED: {
        EventStatus.ALLOCATION_PROCESSING,  # thu hồi công bố để chỉnh
        EventStatus.EVENT_STARTED,
    },
    EventStatus.EVENT_STARTED: {
        EventStatus.COMPLETED,
        EventStatus.INFORMATION_PUBLISHED,  # bấm nhầm, hoặc cần xếp lại ghế Gala / xe trước giờ đi
    },
    EventStatus.COMPLETED: set(),
}

# Lý do khi chuyển trạng thái (kể cả bước lùi) là TUỲ CHỌN: bắt buộc nhập làm BTC chậm tay đúng
# lúc cần sửa gấp. Có lý do thì ghi audit và in vào email báo CBNV ("Ghi chú của BTC").

AUDITED_EVENT_FIELDS = [
    "code",
    "name",
    "destination",
    "start_date",
    "end_date",
    "status",
    "registration_opens_at",
    "registration_closes_at",
    "terms_version",
    "is_active",
]


# --- Truy vấn ---


def get_active_event(db: Session) -> Event | None:
    return db.scalar(select(Event).where(Event.is_active.is_(True)))


def get_event(db: Session, event_id: int) -> Event:
    event = db.get(Event, event_id)
    if event is None:
        raise NotFoundError(f"Không tìm thấy kỳ Team Building #{event_id}.")
    return event


def list_events(db: Session) -> list[Event]:
    return list(db.scalars(select(Event).order_by(Event.start_date.desc())))


def list_selectable_events(db: Session, *, viewer: User) -> list[Event]:
    """Các kỳ người này được phép chọn qua `X-Event-Id` (docs/13 task 6).

    Cùng một luật với `dependencies.get_active_event`: BTC thấy mọi kỳ kể cả bản nháp, CBNV chỉ thấy
    kỳ đã công bố ra ngoài. Hai nơi lệch nhau thì bộ chọn kỳ hiện ra kỳ mà chọn vào lại 404.
    """
    query = select(Event).order_by(Event.start_date.desc())
    if viewer.role not in ADMIN_ROLES:
        query = query.where(Event.status != EventStatus.DRAFT)
    return list(db.scalars(query))


# --- Tạo & sửa ---


def create_event(db: Session, *, data: dict, actor: User, ip_address: str | None = None) -> Event:
    if db.scalar(select(Event).where(Event.code == data["code"])):
        raise ConflictError(
            f"Mã kỳ '{data['code']}' đã tồn tại.", code="EVENT_CODE_DUPLICATED"
        )
    _validate_dates(data.get("start_date"), data.get("end_date"))

    event = Event(**data, status=EventStatus.DRAFT, is_active=False)
    db.add(event)
    db.flush()

    for key, (value, description) in DEFAULT_EVENT_SETTINGS.items():
        db.add(EventSetting(event_id=event.id, key=key, value=value, description=description))

    audit_service.log(
        db,
        action="event.created",
        entity_type="event",
        entity_id=event.id,
        actor_id=actor.id,
        event_id=event.id,
        after=audit_service.snapshot(event, AUDITED_EVENT_FIELDS),
        ip_address=ip_address,
    )
    db.commit()
    return event


def update_event(
    db: Session,
    *,
    event: Event,
    data: dict,
    actor: User,
    notify: bool = False,
    ip_address: str | None = None,
) -> tuple[Event, list[dict]]:
    """Sửa thông tin kỳ. Trả (kỳ, việc gửi email) — email chỉ khi `notify` (BTC tích ô gửi)."""
    from app.services import change_notice_service

    before = audit_service.snapshot(event, AUDITED_EVENT_FIELDS)

    if "start_date" in data or "end_date" in data:
        _validate_dates(
            data.get("start_date", event.start_date), data.get("end_date", event.end_date)
        )
    # Sửa nội dung quy định sau khi đã có người đồng ý -> phải lên version mới,
    # nếu không thì bản consent đã lưu không còn khớp văn bản thực tế.
    if data.get("terms_content") and data.get("terms_version") == event.terms_version:
        if _has_consents(db, event.id):
            raise ConflictError(
                "Đã có CBNV đồng ý quy định phiên bản này. Sửa nội dung thì phải đặt "
                "terms_version mới (ví dụ v2) để bản đồng ý cũ vẫn đúng với văn bản cũ.",
                code="TERMS_VERSION_REQUIRED",
            )

    for field, value in data.items():
        setattr(event, field, value)
    db.flush()

    after = audit_service.snapshot(event, AUDITED_EVENT_FIELDS)
    audit = audit_service.log(
        db,
        action="event.updated",
        entity_type="event",
        entity_id=event.id,
        actor_id=actor.id,
        event_id=event.id,
        before=before,
        after=audit_service.diff(before, after),
        ip_address=ip_address,
    )
    db.flush()
    jobs = (
        change_notice_service.queue_event_info_change(db, event=event, before=before, audit=audit)
        if notify
        else []
    )
    db.commit()
    return event, jobs


def activate_event(
    db: Session, *, event: Event, actor: User, ip_address: str | None = None
) -> Event:
    """Đặt kỳ này làm kỳ đang chạy, tự tắt các kỳ khác.

    Bất biến: chỉ một kỳ `is_active` tại một thời điểm — nếu không, `/events/active`
    và toàn bộ dependency `ActiveEvent` sẽ trả về kỳ tuỳ tiện.
    """
    previously_active = get_active_event(db)
    if previously_active and previously_active.id != event.id:
        previously_active.is_active = False

    event.is_active = True
    db.flush()

    audit_service.log(
        db,
        action="event.activated",
        entity_type="event",
        entity_id=event.id,
        actor_id=actor.id,
        event_id=event.id,
        before={"previous_active_event": previously_active.code if previously_active else None},
        after={"active_event": event.code},
        ip_address=ip_address,
    )
    db.commit()
    return event


# --- Chuyển trạng thái ---


def change_status(
    db: Session,
    *,
    event: Event,
    new_status: EventStatus,
    actor: User,
    reason: str | None = None,
    notify: bool = False,
    ip_address: str | None = None,
) -> tuple[Event, list[dict]]:
    """Chuyển trạng thái. Trả (kỳ, việc gửi email cho BackgroundTask — rỗng khi `notify=False`).

    Email báo CBNV được `enqueue` cùng transaction với audit: chuyển thất bại thì không có thư.
    """
    from app.services import change_notice_service  # change_notice_service đọc nhãn ở đây

    current = EventStatus(event.status)
    new_status = EventStatus(new_status)
    reason = (reason or "").strip() or None

    if current == new_status:
        raise ConflictError(
            f"Chương trình đang ở trạng thái '{current}' rồi.", code="STATUS_UNCHANGED"
        )

    allowed = ALLOWED_TRANSITIONS[current]
    if new_status not in allowed:
        raise ConflictError(
            f"Không thể chuyển từ '{_label(current)}' sang '{_label(new_status)}'.",
            code="INVALID_STATUS_TRANSITION",
            details={
                "current": current.value,
                "requested": new_status.value,
                "allowed": sorted(status.value for status in allowed),
            },
        )

    _check_preconditions(db, event, current=current, new_status=new_status)

    event.status = new_status
    db.flush()

    audit = audit_service.log(
        db,
        action="event.status_changed",
        entity_type="event",
        entity_id=event.id,
        actor_id=actor.id,
        event_id=event.id,
        before={"status": current.value},
        after={"status": new_status.value},
        reason=reason,
        ip_address=ip_address,
    )
    db.flush()
    jobs = (
        change_notice_service.queue_status_change(db, event=event, previous=current, audit=audit)
        if notify
        else []
    )
    db.commit()
    logger.info(
        "Kỳ %s chuyển %s -> %s bởi %s, xếp %d email",
        event.code, current, new_status, actor.email, len(jobs),
    )
    return event, jobs


def _check_preconditions(
    db: Session, event: Event, *, current: EventStatus, new_status: EventStatus
) -> None:
    """Chặn những lần chuyển trạng thái chắc chắn gây rắc rối về sau.

    Chỉ áp dụng cho bước TIẾN. Bước lùi (thu hồi công bố để chỉnh sửa) luôn phải
    thực hiện được — nếu không BTC sẽ mắc kẹt đúng lúc cần sửa gấp nhất.
    """
    if new_status == EventStatus.REGISTRATION_OPEN and current == EventStatus.DRAFT:
        missing = []
        if not db.scalar(select(func.count()).select_from(Shift).where(Shift.event_id == event.id)):
            missing.append("ca bay (shifts)")
        if not db.scalar(
            select(func.count()).select_from(TripLeg).where(TripLeg.event_id == event.id)
        ):
            missing.append("chặng xe (trip_legs)")
        if missing:
            raise ConflictError(
                "Chưa cấu hình xong master data nên không mở đăng ký được: "
                + ", ".join(missing)
                + ". CBNV sẽ không có gì để chọn trong form đăng ký.",
                code="MASTER_DATA_MISSING",
                details={"missing": missing},
            )

    if (
        new_status == EventStatus.ALLOCATION_PROCESSING
        and current == EventStatus.REGISTRATION_CLOSED
    ):
        participants = _count_participants(db, event.id)
        if participants == 0:
            raise ConflictError(
                "Chưa có ai đăng ký tham gia, không có gì để phân bổ.",
                code="NO_PARTICIPANTS",
            )

    if new_status == EventStatus.EVENT_STARTED:
        # Import trong hàm: gala_service import event_service (cấu hình kỳ) — import ở đầu file sẽ vòng.
        from app.services import gala_service

        gaps = gala_service.seating_gaps(db, event_id=event.id)
        if gaps is not None:
            problems = []
            if gaps["selection_status"] == "open":
                problems.append("các team vẫn đang chọn ghế")
            if gaps["teams_missing"]:
                problems.append(
                    f"{len(gaps['teams_missing'])} team chưa đủ ghế ("
                    + ", ".join(f"{item['team_name']} {item['seats']}/{item['participants']}" for item in gaps["teams_missing"])
                    + ")"
                )
            if gaps["unseated"]:
                problems.append(f"{gaps['unseated']} người tham gia chưa được xếp vào ghế cụ thể")
            if problems:
                raise ConflictError(
                    "Chưa xếp xong chỗ ngồi Gala nên chưa bắt đầu sự kiện được: "
                    + "; ".join(problems)
                    + ". Mở lại chọn ghế hoặc xếp ghế trong màn hình Gala Dinner.",
                    code="GALA_SEATING_INCOMPLETE",
                    details=gaps,
                )


def require_registration_closed(event: Event) -> None:
    """Chỉ ghi kết quả phân bổ (chuyến bay, xe) khi đăng ký đã đóng.

    Ghi trong lúc CBNV còn đăng ký thì kết quả lạc hậu ngay lúc ghi xong, và người đăng ký
    sau sẽ không có chỗ mà không ai để ý. Xem trước (dry-run) thì không cần luật này.
    Một chỗ duy nhất cho mọi loại phân bổ để thông điệp và mã lỗi không lệch nhau.
    """
    if not EventStatus(event.status).at_least(EventStatus.REGISTRATION_CLOSED):
        raise ConflictError(
            "Phải đóng đăng ký trước khi ghi kết quả phân bổ. Đổi trạng thái kỳ sang "
            "'registration_closed' rồi chạy lại. Xem trước (dry_run) thì không cần.",
            code="REGISTRATION_STILL_OPEN",
            details={"current_status": event.status},
        )


# --- Cấu hình ---


def get_settings(db: Session, event_id: int) -> dict[str, dict]:
    """Toàn bộ khoá cấu hình, khoá chưa có dòng trong DB thì trả **giá trị mặc định**.

    Kỳ tạo trước khi một khoá được thêm vào code sẽ thiếu dòng đó (DB thật đang thiếu 3 khoá
    `rooms.*`). Chỉ trả những gì có trong bảng thì màn hình cấu hình không hiện các khoá đó ra, hoặc
    tệ hơn: hiện ô trống rồi lưu đè thành 0 — đổi lặng lẽ cách thuật toán xếp phòng chạy.
    """
    stored = {
        row.key: {"value": _parse_value(row.value), "description": row.description}
        for row in db.scalars(select(EventSetting).where(EventSetting.event_id == event_id))
    }
    return {
        key: stored.get(key, {"value": _parse_value(value), "description": description})
        for key, (value, description) in DEFAULT_EVENT_SETTINGS.items()
    }


def update_settings(
    db: Session,
    *,
    event: Event,
    values: dict[str, object],
    actor: User,
    ip_address: str | None = None,
) -> dict[str, dict]:
    """Cập nhật cấu hình. Khoá lạ bị từ chối thay vì lưu âm thầm rồi không có tác dụng."""
    unknown = set(values) - set(DEFAULT_EVENT_SETTINGS)
    if unknown:
        raise ConflictError(
            "Có khoá cấu hình không hợp lệ: " + ", ".join(sorted(unknown)),
            code="UNKNOWN_SETTING_KEY",
            details={"unknown": sorted(unknown), "valid": sorted(DEFAULT_EVENT_SETTINGS)},
        )

    existing = {
        row.key: row
        for row in db.scalars(select(EventSetting).where(EventSetting.event_id == event.id))
    }
    before = {key: _parse_value(row.value) for key, row in existing.items() if key in values}

    for key, value in values.items():
        serialized = json.dumps(value, ensure_ascii=False)
        if key in existing:
            existing[key].value = serialized
        else:
            db.add(
                EventSetting(
                    event_id=event.id,
                    key=key,
                    value=serialized,
                    description=DEFAULT_EVENT_SETTINGS[key][1],
                )
            )
    db.flush()

    audit_service.log(
        db,
        action="event.settings_updated",
        entity_type="event_settings",
        entity_id=event.id,
        actor_id=actor.id,
        event_id=event.id,
        before=before,
        after=values,
        ip_address=ip_address,
    )
    db.commit()
    return get_settings(db, event.id)


# --- Thống kê nhanh cho màn hình trạng thái ---


def get_status_overview(db: Session, event: Event) -> dict:
    total_users = db.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True)))
    registered = db.scalar(
        select(func.count()).select_from(Registration).where(Registration.event_id == event.id)
    )
    participants = _count_participants(db, event.id)
    current = EventStatus(event.status)
    return {
        "status": current.value,
        "can_register": current == EventStatus.REGISTRATION_OPEN,
        "is_published": current.at_least(EventStatus.INFORMATION_PUBLISHED),
        "allowed_next_statuses": sorted(
            status.value for status in ALLOWED_TRANSITIONS[current]
        ),
        "total_users": total_users or 0,
        "registered": registered or 0,
        "not_registered": (total_users or 0) - (registered or 0),
        "participants": participants,
    }


# --- Nội bộ ---


def _count_participants(db: Session, event_id: int) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(Registration)
            .where(
                Registration.event_id == event_id,
                Registration.is_participating.is_(True),
                Registration.status == RegistrationStatus.SUBMITTED,
            )
        )
        or 0
    )


def _has_consents(db: Session, event_id: int) -> bool:
    from app.models.registration import Consent

    return bool(
        db.scalar(
            select(func.count()).select_from(Consent).where(Consent.event_id == event_id)
        )
    )


def _validate_dates(start_date: str | None, end_date: str | None) -> None:
    if start_date and end_date and end_date < start_date:
        raise ConflictError(
            "Ngày kết thúc phải sau ngày bắt đầu.", code="INVALID_DATE_RANGE"
        )


def _parse_value(raw: str):
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


_STATUS_LABELS = {
    EventStatus.DRAFT: "Nháp",
    EventStatus.REGISTRATION_OPEN: "Đang mở đăng ký",
    EventStatus.REGISTRATION_CLOSED: "Đã đóng đăng ký",
    EventStatus.ALLOCATION_PROCESSING: "Đang phân bổ",
    EventStatus.INFORMATION_PUBLISHED: "Đã công bố thông tin",
    EventStatus.EVENT_STARTED: "Đang diễn ra",
    EventStatus.COMPLETED: "Đã kết thúc",
}


def _label(status: EventStatus) -> str:
    return _STATUS_LABELS.get(status, status.value)


def status_label(status: str) -> str:
    """Nhãn tiếng Việt cho frontend hiển thị."""
    try:
        return _label(EventStatus(status))
    except ValueError:
        return status
