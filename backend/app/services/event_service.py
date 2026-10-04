"""Nghiệp vụ kỳ Team Building: tạo, cấu hình, chuyển trạng thái.

Chuyển trạng thái là thao tác nhạy cảm nhất của BTC — nó quyết định CBNV còn sửa được
đăng ký không, và thông tin phân bổ đã hiện ra chưa. Vì vậy mọi lần chuyển đều
kiểm tra hợp lệ và ghi audit log.
"""

import json
import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.core.timeutils import utcnow_iso
from app.models.content import Content
from app.models.enums import ADMIN_ROLES, EventStatus, PolicyDocType, RegistrationStatus
from app.models.event import DEFAULT_EVENT_SETTINGS, Event, default_settings
from app.models.flight import Shift
from app.models.registration import Registration
from app.models.transportation import TripLeg
from app.models.user import User
from app.schemas.event import check_registration_window
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

# Từ lúc chương trình bắt đầu, cấu hình kỳ (thông tin, quy định, ca bay, chặng, điểm đón, trọng số)
# chỉ còn để xem: CBNV đang đi theo đúng những gì đã công bố, sửa lúc này là hai bên nhìn hai bản.
CONFIG_LOCKED_STATUSES = {EventStatus.EVENT_STARTED, EventStatus.COMPLETED}

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


# --- Khoá cấu hình ---


def is_config_locked(event: Event) -> bool:
    return EventStatus(event.status) in CONFIG_LOCKED_STATUSES


def require_config_editable(event: Event) -> None:
    """Chặn sửa cấu hình kỳ khi chương trình đang diễn ra hoặc đã kết thúc.

    Một chỗ duy nhất cho thông tin kỳ, cấu hình và master data theo kỳ để mã lỗi không lệch nhau.
    Tài liệu cho Tibi không qua đây: BTC vẫn cần bổ sung giải đáp trong lúc sự kiện chạy.
    """
    current = EventStatus(event.status)
    if current not in CONFIG_LOCKED_STATUSES:
        return
    if current == EventStatus.COMPLETED:
        message = "Chương trình đã kết thúc nên không sửa cấu hình kỳ được nữa."
    else:
        message = (
            "Chương trình đang diễn ra nên không sửa cấu hình kỳ được nữa. Cần sửa thì lùi "
            f"trạng thái về '{_label(EventStatus.INFORMATION_PUBLISHED)}' trước."
        )
    raise ConflictError(
        message, code="EVENT_CONFIG_LOCKED", details={"current_status": current.value}
    )


# --- Tạo & sửa ---


def create_event(db: Session, *, data: dict, actor: User, ip_address: str | None = None) -> Event:
    if db.scalar(select(Event).where(Event.code == data["code"])):
        raise ConflictError(
            f"Mã kỳ '{data['code']}' đã tồn tại.", code="EVENT_CODE_DUPLICATED"
        )
    _validate_dates(data.get("start_date"), data.get("end_date"))

    event = Event(
        **data, status=EventStatus.DRAFT, is_active=False, settings=default_settings()
    )
    db.add(event)
    db.flush()

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
    restoring_terms: bool = False,
) -> tuple[Event, list[dict]]:
    """Sửa thông tin kỳ. Trả (kỳ, việc gửi email) — email chỉ khi `notify` (BTC tích ô gửi)."""
    from app.services import change_notice_service

    require_config_editable(event)
    before = audit_service.snapshot(event, AUDITED_EVENT_FIELDS)

    if "start_date" in data or "end_date" in data:
        _validate_dates(
            data.get("start_date", event.start_date), data.get("end_date", event.end_date)
        )
    if {"registration_opens_at", "registration_closes_at", "start_date"} & set(data):
        # Request sửa kỳ thường chỉ mang một mốc — phải gộp với mốc đang lưu rồi mới so được.
        try:
            check_registration_window(
                data.get("registration_opens_at", event.registration_opens_at),
                data.get("registration_closes_at", event.registration_closes_at),
                data.get("start_date", event.start_date),
            )
        except ValueError as exc:
            raise AppError(
                str(exc), code="INVALID_REGISTRATION_WINDOW", status_code=422
            ) from exc
    # Sửa nội dung quy định sau khi đã có người đồng ý -> phải lên version mới,
    # nếu không thì bản consent đã lưu không còn khớp văn bản thực tế.
    if data.get("terms_content") and data.get("terms_version") == event.terms_version:
        if _has_consents(db, event.id):
            raise ConflictError(
                "Đã có CBNV đồng ý quy định phiên bản này. Sửa nội dung thì phải đặt "
                "terms_version mới (ví dụ v2) để bản đồng ý cũ vẫn đúng với văn bản cũ.",
                code="TERMS_VERSION_REQUIRED",
            )

    new_version = data.get("terms_version")
    if new_version and new_version != event.terms_version:
        # Quay lại dùng một số phiên bản mà đã có người đồng ý thì chữ ký đó trỏ sang văn bản khác.
        # `restoring_terms`: dùng lại nguyên văn bản lưu trữ của chính phiên bản đó nên chữ ký vẫn đúng.
        if not restoring_terms and _has_consents(db, event.id, version=new_version):
            raise ConflictError(
                f"Phiên bản '{new_version}' đã có CBNV đồng ý trước đây. Đặt một phiên bản mới "
                "chưa từng dùng.",
                code="TERMS_VERSION_REUSED",
            )
        _archive_terms(db, event)

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

    if new_status == EventStatus.INFORMATION_PUBLISHED and current == EventStatus.ALLOCATION_PROCESSING:
        blockers = publish_blockers(db, event)
        if blockers:
            raise ConflictError(
                "Chưa công bố được vì phân bổ chưa xong: "
                + "; ".join(item["summary"] for item in blockers)
                + ".",
                code="PUBLISH_REQUIREMENTS_UNMET",
                details={"blockers": blockers},
            )

    if new_status == EventStatus.INFORMATION_PUBLISHED:
        # Import trong hàm: transport_timing_service đọc nhiều model, import ở đầu file vòng lại.
        from app.services import transport_timing_service

        mismatches = transport_timing_service.event_mismatches(db, event_id=event.id)
        if mismatches:
            people = sorted({item["full_name"] for item in mismatches})
            raise ConflictError(
                f"{len(people)} người có xe đưa đón lệch giờ chuyến bay của chính họ "
                f"({', '.join(people[:3])}{' …' if len(people) > 3 else ''}). Công bố lúc này thì "
                "lịch trình trên My Journey mâu thuẫn — CBNV thấy xe chạy sau giờ cất cánh. "
                "Sửa giờ xe hoặc chuyển hành khách trong màn hình Xe đưa đón rồi công bố lại.",
                code="TRANSPORT_TIME_MISMATCH",
                details={
                    "count": len(mismatches),
                    "people": len(people),
                    "items": mismatches[:20],
                },
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


PUBLISH_NAMES = 20


def publish_blockers(db: Session, event: Event) -> list[dict]:
    """Những gì còn thiếu khiến kỳ CHƯA được công bố. Rỗng = công bố được.

    Luật của BTC: công bố là công bố trọn gói. Mỗi người tham gia phải có chuyến bay hai chiều, xe ở
    mọi chặng họ đăng ký đi xe, phòng, và ghế Gala. Thiếu một thứ là CBNV mở My Journey thấy thiếu
    đúng thứ đó, và BTC nhận điện thoại hỏi.

    Một hàm cho cả chỗ chặn lẫn checklist trên dashboard, để hai nơi không đếm hai kiểu.
    """
    # Import trong hàm: gala_service import ngược event_service.
    from app.models.flight import FlightAssignment
    from app.models.registration import RegistrationLeg
    from app.services import gala_service

    people = dict(
        db.execute(
            select(Registration.id, User.full_name)
            .join(User, User.id == Registration.user_id)
            .where(
                Registration.event_id == event.id,
                Registration.is_participating.is_(True),
                Registration.status == RegistrationStatus.SUBMITTED,
            )
            .order_by(User.full_name)
        ).all()
    )
    if not people:
        return [
            {
                "key": "participants",
                "summary": "chưa có ai xác nhận tham gia",
                "count": 0,
                "names": [],
                "link": "/admin/registrations",
            }
        ]

    def item(key: str, noun: str, missing_ids: set[int], link: str) -> dict | None:
        if not missing_ids:
            return None
        names = [name for registration_id, name in people.items() if registration_id in missing_ids]
        return {
            "key": key,
            "summary": f"{len(names)} người chưa có {noun}",
            "count": len(names),
            "names": names[:PUBLISH_NAMES],
            "link": link,
        }

    everyone = set(people)
    blockers: list[dict | None] = []
    for direction, noun in (("outbound", "chuyến bay chiều đi"), ("return", "chuyến bay chiều về")):
        assigned = set(
            db.scalars(
                select(FlightAssignment.registration_id).where(
                    FlightAssignment.registration_id.in_(everyone),
                    FlightAssignment.direction == direction,
                )
            )
        )
        blockers.append(item(f"flight_{direction}", noun, everyone - assigned, "/admin/flights/board"))

    without_bus = set(
        db.scalars(
            select(RegistrationLeg.registration_id).where(
                RegistrationLeg.registration_id.in_(everyone),
                RegistrationLeg.needs_bus.is_(True),
                RegistrationLeg.bus_id.is_(None),
            )
        )
    )
    blockers.append(item("bus", "xe ở chặng đã đăng ký đi xe", without_bus, "/admin/buses"))

    without_room = set(
        db.scalars(
            select(Registration.id).where(Registration.id.in_(everyone), Registration.room_id.is_(None))
        )
    )
    blockers.append(item("room", "phòng", without_room, "/admin/rooms"))

    gaps = gala_service.seating_gaps(db, event_id=event.id)
    if gaps is None:
        blockers.append(
            {
                "key": "gala",
                "summary": "chưa dựng sơ đồ Gala",
                "count": len(people),
                "names": [],
                "link": "/admin/gala",
            }
        )
    elif gaps["unseated"]:
        blockers.append(
            {
                "key": "gala",
                "summary": f"{gaps['unseated']} người chưa có ghế Gala",
                "count": gaps["unseated"],
                "names": [
                    f"{team['team_name']} {team['seats']}/{team['participants']}"
                    for team in gaps["teams_missing"]
                ][:PUBLISH_NAMES],
                "link": "/admin/gala",
            }
        )
    return [entry for entry in blockers if entry]


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
    """Toàn bộ khoá cấu hình, khoá chưa lưu trong `events.settings` thì trả **giá trị mặc định**.

    Kỳ tạo trước khi một khoá được thêm vào code sẽ thiếu khoá đó. Chỉ trả những gì đã lưu thì màn
    hình cấu hình không hiện các khoá đó ra, hoặc tệ hơn: hiện ô trống rồi lưu đè thành 0 — đổi lặng
    lẽ cách thuật toán xếp phòng chạy.
    """
    stored = get_event(db, event_id).settings or {}
    return {
        key: {"value": _parse_value(stored.get(key, value)), "description": description}
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
    require_config_editable(event)
    unknown = set(values) - set(DEFAULT_EVENT_SETTINGS)
    if unknown:
        raise ConflictError(
            "Có khoá cấu hình không hợp lệ: " + ", ".join(sorted(unknown)),
            code="UNKNOWN_SETTING_KEY",
            details={"unknown": sorted(unknown), "valid": sorted(DEFAULT_EVENT_SETTINGS)},
        )
    # Mọi nơi đọc cấu hình đều `int(...)` rồi lặng lẽ lùi về mặc định khi hỏng — lưu được "abc" là
    # BTC tưởng đã đổi trong khi thuật toán vẫn chạy số cũ.
    invalid = sorted(key for key, value in values.items() if not _is_whole_number(value))
    if invalid:
        raise AppError(
            "Giá trị cấu hình phải là số nguyên không âm: " + ", ".join(invalid),
            code="INVALID_SETTING_VALUE",
            status_code=422,
            details={"invalid": invalid},
        )

    stored = dict(event.settings or {})
    _check_setting_ranges({**get_setting_values(stored), **values})
    before = {key: _parse_value(stored[key]) for key in values if key in stored}
    # Gán dict mới thay vì sửa tại chỗ: chắc chắn SQLAlchemy ghi cột JSON xuống.
    event.settings = {**stored, **values}
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


# Khoảng hợp lệ của từng khoá. Số nguyên nào cũng lưu được thì "giữ ghế 0 giây" hay "tách ca
# 500%" lọt vào, rồi nơi đọc lặng lẽ lùi về mặc định — BTC tưởng đã đổi mà thuật toán chạy số cũ.
SETTING_RANGES: dict[str, tuple[int, int]] = {
    "allocation.team_weight": (0, 1000),
    "allocation.shift_weight": (0, 1000),
    "allocation.split_penalty": (0, 1000),
    "allocation.max_split_per_team": (1, 10),
    "allocation.min_chunk_size": (1, 50),
    "allocation.fit_weight": (0, 1000),
    "allocation.shift_split_percent": (0, 100),
    "rooms.team_weight": (0, 1000),
    "rooms.flight_weight": (0, 1000),
    "rooms.department_weight": (0, 1000),
    "transport.to_airport_buffer_minutes": (0, 600),
    "transport.from_airport_late_minutes": (0, 600),
    "transport.from_airport_min_wait_minutes": (0, 600),
    "transport.from_airport_max_wait_minutes": (0, 600),
    "transport.self_transport_lead_minutes": (0, 600),
    "gala.hold_seconds": (30, 900),
    "gala.turn_seconds": (60, 3600),
}


def get_setting_values(stored: dict) -> dict[str, object]:
    """Giá trị hiệu lực của mọi khoá: đã lưu thì lấy đã lưu, chưa thì lấy mặc định."""
    return {
        key: _parse_value(stored.get(key, value)) for key, (value, _) in DEFAULT_EVENT_SETTINGS.items()
    }


def _check_setting_ranges(effective: dict[str, object]) -> None:
    """`effective` = cấu hình sẽ có hiệu lực sau lần lưu này (đã gộp giá trị cũ)."""
    out_of_range = {
        key: {"value": effective[key], "min": low, "max": high}
        for key, (low, high) in SETTING_RANGES.items()
        if isinstance(effective.get(key), int) and not low <= effective[key] <= high
    }
    if out_of_range:
        raise AppError(
            "Giá trị cấu hình ngoài khoảng cho phép: "
            + "; ".join(
                f"{key} phải từ {item['min']} đến {item['max']}" for key, item in sorted(out_of_range.items())
            ),
            code="INVALID_SETTING_VALUE",
            status_code=422,
            details={"out_of_range": out_of_range},
        )
    min_wait = effective.get("transport.from_airport_min_wait_minutes")
    max_wait = effective.get("transport.from_airport_max_wait_minutes")
    if isinstance(min_wait, int) and isinstance(max_wait, int) and 0 < max_wait < min_wait:
        raise AppError(
            "Xe đón chờ lâu nhất phải bằng 0 (không giới hạn) hoặc không nhỏ hơn thời gian chờ ít nhất "
            f"({min_wait} phút).",
            code="INVALID_SETTING_VALUE",
            status_code=422,
            details={"min_wait": min_wait, "max_wait": max_wait},
        )


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


def _has_consents(db: Session, event_id: int, *, version: str | None = None) -> bool:
    query = (
        select(func.count())
        .select_from(Registration)
        .where(Registration.event_id == event_id, Registration.consent_version.is_not(None))
    )
    if version is not None:
        query = query.where(Registration.consent_version == version)
    return bool(db.scalar(query))


# --- Lịch sử quy định ---
#
# `events.terms_content` chỉ giữ bản HIỆN HÀNH. Bản cũ được chép sang `contents`
# (kind='document', doc_type='terms', version=<bản cũ>) ngay trước khi bị ghi đè — không thì người
# đã đồng ý v1 còn `consent_version='v1'` mà không còn văn bản v1 nào để đối chiếu.


def _terms_rows(db: Session, event_id: int) -> list[Content]:
    return list(
        db.scalars(
            select(Content)
            .where(
                Content.kind == "document",
                Content.event_id == event_id,
                Content.doc_type == PolicyDocType.TERMS,
            )
            .order_by(Content.updated_at.desc(), Content.id.desc())
        )
    )


def _archive_terms(db: Session, event: Event) -> None:
    """Chép bản quy định đang dùng vào lịch sử. Gọi TRƯỚC khi gán phiên bản / nội dung mới."""
    if not (event.terms_content or "").strip():
        return
    existing = next(
        (row for row in _terms_rows(db, event.id) if row.version == event.terms_version), None
    )
    if existing is None:
        existing = Content(
            kind="document",
            event_id=event.id,
            doc_type=PolicyDocType.TERMS,
            version=event.terms_version,
            title="",
            content="",
        )
        db.add(existing)
    existing.title = f"Quy định {event.name} – bản {event.terms_version}"
    existing.content = event.terms_content
    existing.updated_at = utcnow_iso()  # = lúc bản này bị thay


def use_terms_version(
    db: Session,
    *,
    event: Event,
    version: str,
    actor: User,
    notify: bool = False,
    ip_address: str | None = None,
) -> tuple[Event, list[dict]]:
    """Chọn lại một bản quy định cũ làm bản đang dùng — đúng nguyên văn đã lưu trữ.

    Bản đang dùng lúc này được chép vào lịch sử trước (trong `update_event`), nên đổi qua đổi lại
    không mất bản nào.
    """
    row = next((item for item in _terms_rows(db, event.id) if item.version == version), None)
    if row is None or version == event.terms_version:
        raise NotFoundError(
            f"Không tìm thấy bản quy định '{version}' trong các bản trước của kỳ này.",
            code="TERMS_VERSION_NOT_FOUND",
        )
    return update_event(
        db,
        event=event,
        data={"terms_version": row.version, "terms_content": row.content},
        actor=actor,
        notify=notify,
        ip_address=ip_address,
        restoring_terms=True,
    )


def list_terms_versions(db: Session, event: Event) -> list[dict]:
    """Bản quy định đang dùng (đứng đầu) rồi các bản đã bị thay, kèm số người đã đồng ý từng bản."""
    consents = dict(
        db.execute(
            select(Registration.consent_version, func.count())
            .where(Registration.event_id == event.id, Registration.consent_version.is_not(None))
            .group_by(Registration.consent_version)
        ).all()
    )
    current = {
        "version": event.terms_version,
        "content": event.terms_content or "",
        "replaced_at": None,
        "consent_count": consents.get(event.terms_version, 0),
        "is_current": True,
    }
    return [current] + [
        {
            "version": row.version,
            "content": row.content,
            "replaced_at": row.updated_at,
            "consent_count": consents.get(row.version, 0),
            "is_current": False,
        }
        for row in _terms_rows(db, event.id)
        # Dòng trùng phiên bản hiện hành (seed tạo sẵn một dòng như vậy) không phải "bản trước".
        if row.version != event.terms_version
    ]


def _validate_dates(start_date: str | None, end_date: str | None) -> None:
    if start_date and end_date and end_date < start_date:
        raise ConflictError(
            "Ngày kết thúc phải sau ngày bắt đầu.", code="INVALID_DATE_RANGE"
        )


def _parse_value(raw):
    """Giá trị mặc định trong code là chuỗi JSON; giá trị đã lưu trong `events.settings` đã parse sẵn."""
    if not isinstance(raw, str):
        return raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _is_whole_number(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


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
