"""Xuất Excel cho BTC (bước 21).

- Chỉ BTC tải được (router chặn). MỖI lần tải ghi audit log kèm số dòng và việc file có dữ liệu cá
  nhân nhạy cảm (ngày sinh, CCCD) hay không — docs/09-security.md §7.4.
- Ô chữ luôn là chuỗi, không bao giờ thành công thức — xem `excel.py`.
- Tên cột trùng với cột các màn hình import đọc được, để BTC tải về, sửa rồi import lại: danh sách
  CBNV (`user_import_service`), phân phòng (`room_import_service`, sheet đầu tiên).
- Không bao giờ xuất ghi chú sức khoẻ: file Excel đi xa hơn màn hình rất nhiều.
"""

from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.timeutils import VN_TZ, format_vn, utcnow
from app.models.accommodation import Hotel, Room, RoomAssignment
from app.models.enums import FlightDirection, RegistrationStatus
from app.models.event import Event
from app.models.flight import Flight, FlightAssignment
from app.models.registration import Registration, RegistrationBusNeed
from app.models.transportation import BusAssignment, TripLeg
from app.models.user import User
from app.services import accommodation_service, audit_service, bus_service, event_service
from app.services.excel import Sheet, build_workbook, safe_filename

GENDER_LABELS = {"male": "Nam", "female": "Nữ", "other": "Khác"}
ROLE_LABELS = {
    "employee": "CBNV",
    "team_leader": "Trưởng nhóm",
    "admin": "Ban tổ chức",
    "super_admin": "Quản trị hệ thống",
}
ID_CARD_LABELS = {"cccd": "CCCD", "passport": "Hộ chiếu"}
REGISTRATION_LABELS = {"submitted": "Đã đăng ký", "cancelled": "Đã huỷ", "draft": "Nháp"}
DIRECTION_LABELS = {FlightDirection.OUTBOUND: "Chiều đi", FlightDirection.RETURN: "Chiều về"}
MODE_LABELS = {"auto": "Tự động", "manual": "BTC xếp tay"}
ROOM_TYPE_LABELS = {
    "single": "Phòng đơn",
    "twin": "Phòng 2 giường",
    "double": "Giường đôi",
    "triple": "Phòng 3 người",
    "quad": "Phòng 4 người",
}
POLICY_LABELS = {"male": "Nam", "female": "Nữ", "any": "Không giới hạn"}


# --- CBNV ---


def export_users(
    db: Session, *, actor: User, include_sensitive: bool = False, ip_address: str | None = None
) -> tuple[bytes, str]:
    event = event_service.get_active_event(db)
    registrations = _registrations_by_user(db, event.id) if event else {}
    users = db.scalars(
        select(User)
        .options(selectinload(User.team), selectinload(User.department), selectinload(User.work_location))
        .order_by(User.full_name, User.id)
    ).all()

    headers = [
        "Mã NV", "Họ tên", "Email", "Giới tính", "SĐT", "Team", "Phòng ban", "Nơi làm việc",
        "Chức danh", "Ngày vào làm", "Vai trò", "Tài khoản", "Đăng ký kỳ này",
    ]
    if include_sensitive:
        headers += [
            "Ngày sinh", "Loại giấy tờ", "Số CCCD/Hộ chiếu", "Địa chỉ",
            "Người liên hệ khẩn cấp", "SĐT liên hệ khẩn cấp",
        ]

    rows = []
    for user in users:
        row = [
            user.employee_code, user.full_name, user.email, GENDER_LABELS.get(user.gender, user.gender),
            user.phone, _name(user.team), _name(user.department), _name(user.work_location),
            user.job_title, user.join_date, ROLE_LABELS.get(user.role, user.role),
            "Hoạt động" if user.is_active else "Đã khoá", _registration_label(registrations.get(user.id)),
        ]
        if include_sensitive:
            row += [
                user.date_of_birth, ID_CARD_LABELS.get(user.id_card_type, user.id_card_type),
                user.id_card_number, user.address, user.emergency_contact_name, user.emergency_contact_phone,
            ]
        rows.append(row)

    content = build_workbook([Sheet("CBNV", headers, rows)])
    _record(db, actor=actor, kind="users", rows=len(rows), sensitive=include_sensitive, event=event, ip_address=ip_address)
    return content, filename("cbnv-day-du" if include_sensitive else "cbnv", event)


# --- Đăng ký ---


def export_registrations(
    db: Session, *, event: Event, actor: User, ip_address: str | None = None
) -> tuple[bytes, str]:
    legs = _legs(db, event.id)
    registrations = db.scalars(
        select(Registration)
        .join(User, User.id == Registration.user_id)
        .where(Registration.event_id == event.id)
        .options(
            selectinload(Registration.user).selectinload(User.team),
            selectinload(Registration.shift),
            selectinload(Registration.bus_needs).selectinload(RegistrationBusNeed.pickup_point),
        )
        .order_by(User.full_name, Registration.id)
    ).all()

    headers = [
        "Mã NV", "Họ tên", "Email", "SĐT", "Team", "Trạng thái", "Tham gia", "Lý do không tham gia",
        "Ca nguyện vọng", *[f"Xe: {leg.name}" for leg in legs], "Người đi cùng", "Mong muốn",
        "Gửi lúc", "Huỷ lúc", "Lý do huỷ", "Phí phạt", "Đủ giấy tờ bay",
    ]
    rows = []
    responded: set[int] = set()
    for registration in registrations:
        user = registration.user
        if registration.status in (RegistrationStatus.SUBMITTED, RegistrationStatus.CANCELLED):
            responded.add(user.id)
        participating = registration.status == RegistrationStatus.SUBMITTED and registration.is_participating
        needs = {need.trip_leg_id: need for need in registration.bus_needs}
        rows.append(
            [
                user.employee_code, user.full_name, user.email, user.phone, _name(user.team),
                REGISTRATION_LABELS.get(registration.status, registration.status),
                "Có" if registration.is_participating else "Không",
                registration.not_participating_reason,
                registration.shift.name if registration.shift else None,
                *[_bus_need_label(needs.get(leg.id), registration.is_participating) for leg in legs],
                registration.companion_count, registration.wish_note,
                _vn(registration.submitted_at), _vn(registration.cancelled_at), registration.cancel_reason,
                registration.penalty_applied, user.can_fly if participating else None,
            ]
        )

    missing = db.scalars(
        select(User)
        .where(User.is_active.is_(True))
        .options(selectinload(User.team))
        .order_by(User.full_name, User.id)
    ).all()
    missing_rows = [
        [user.employee_code, user.full_name, user.email, user.phone, _name(user.team)]
        for user in missing
        if user.id not in responded
    ]

    content = build_workbook(
        [
            Sheet("Đăng ký", headers, rows),
            Sheet("Chưa đăng ký", ["Mã NV", "Họ tên", "Email", "SĐT", "Team"], missing_rows),
        ]
    )
    _record(db, actor=actor, kind="registrations", rows=len(rows), sensitive=False, event=event, ip_address=ip_address)
    return content, filename("dang-ky", event)


# --- Chuyến bay ---


def export_flight_manifest(
    db: Session, *, event: Event, actor: User, ip_address: str | None = None
) -> tuple[bytes, str]:
    """Danh sách hành khách để đặt vé: có ngày sinh và số giấy tờ — luôn ghi nhật ký là file nhạy cảm."""
    flights = db.scalars(
        select(Flight)
        .where(Flight.event_id == event.id)
        .order_by(Flight.direction, Flight.departure_time, Flight.flight_code)
    ).all()
    assignments = db.scalars(
        select(FlightAssignment)
        .join(Flight, Flight.id == FlightAssignment.flight_id)
        .where(Flight.event_id == event.id)
        .options(selectinload(FlightAssignment.registration).selectinload(Registration.user).selectinload(User.team))
    ).all()
    by_flight: dict[int, list[FlightAssignment]] = defaultdict(list)
    for assignment in assignments:
        by_flight[assignment.flight_id].append(assignment)

    headers = [
        "Chuyến bay", "Hãng", "Khởi hành (giờ VN)", "Đến nơi (giờ VN)", "Sân bay đi", "Sân bay đến",
        "Mã NV", "Họ tên", "Giới tính", "Ngày sinh", "Loại giấy tờ", "Số CCCD/Hộ chiếu", "SĐT", "Team",
        "Số ghế", "Mã vé", "Nguồn xếp", "Đủ giấy tờ bay",
    ]
    sheets = []
    for direction in FlightDirection:
        rows = []
        for flight in (item for item in flights if item.direction == direction):
            info = [
                flight.flight_code, flight.airline, _vn(flight.departure_time), _vn(flight.arrival_time),
                flight.departure_airport, flight.arrival_airport,
            ]
            passengers = sorted(
                by_flight.get(flight.id, []),
                key=lambda item: (_name(item.registration.user.team) or "", item.registration.user.full_name),
            )
            if not passengers:
                rows.append(info)
            for assignment in passengers:
                user = assignment.registration.user
                rows.append(
                    [
                        *info, user.employee_code, user.full_name, GENDER_LABELS.get(user.gender, user.gender),
                        user.date_of_birth, ID_CARD_LABELS.get(user.id_card_type, user.id_card_type),
                        user.id_card_number, user.phone, _name(user.team), assignment.seat_number,
                        assignment.ticket_code, MODE_LABELS.get(assignment.assignment_mode), user.can_fly,
                    ]
                )
        sheets.append(Sheet(DIRECTION_LABELS[direction], headers, rows))

    assigned = {(item.registration_id, item.direction) for item in assignments}
    missing_rows = []
    for registration in _participants(db, event.id):
        user = registration.user
        for direction in FlightDirection:
            if (registration.id, direction) not in assigned:
                missing_rows.append(
                    [DIRECTION_LABELS[direction], user.employee_code, user.full_name, _name(user.team), user.phone, user.can_fly]
                )
    sheets.append(
        Sheet("Chưa có chuyến", ["Chiều", "Mã NV", "Họ tên", "Team", "SĐT", "Đủ giấy tờ bay"], missing_rows)
    )

    content = build_workbook(sheets)
    _record(db, actor=actor, kind="flight_manifest", rows=len(assignments), sensitive=True, event=event, ip_address=ip_address)
    return content, filename("danh-sach-bay", event)


# --- Xe ---


def export_buses(
    db: Session, *, event: Event, actor: User, ip_address: str | None = None
) -> tuple[bytes, str]:
    headers = [
        "Xe", "Biển số", "Tập trung (giờ VN)", "Xe chạy (giờ VN)", "Điểm đón của xe", "Chuyến bay của xe",
        "Trưởng xe", "SĐT Trưởng xe", "Tài xế", "SĐT tài xế",
        "Mã NV", "Họ tên", "SĐT", "Team", "Điểm đón đã chọn", "Chuyến bay của khách", "Nguồn xếp",
    ]
    empty_bus_info = [None] * 10
    sheets = []
    total = 0

    for leg in _legs(db, event.id):
        rows: list[list[Any]] = []
        for bus, _assigned in bus_service.list_buses(db, event_id=event.id, trip_leg_id=leg.id):
            info = [
                bus.bus_code, bus.plate_number, _vn(bus.gather_time), _vn(bus.departure_time),
                bus.pickup_point.name if bus.pickup_point else None,
                bus.linked_flight.flight_code if bus.linked_flight else None,
                bus.leader_name, bus.leader_phone, bus.driver_name, bus.driver_phone,
            ]
            passengers = bus_service.list_passengers(db, bus=bus)
            if not passengers:
                rows.append(info)
            for passenger in passengers:
                total += 1
                rows.append(
                    [
                        *info, passenger["employee_code"], passenger["full_name"], passenger["phone"],
                        passenger["team_name"], passenger["pickup_point_name"], passenger["flight_code"],
                        MODE_LABELS.get(passenger["assignment_mode"]),
                    ]
                )

        assigned_ids = set(
            db.scalars(select(BusAssignment.registration_id).where(BusAssignment.trip_leg_id == leg.id)).all()
        )
        riders = db.scalars(
            select(RegistrationBusNeed)
            .join(Registration, Registration.id == RegistrationBusNeed.registration_id)
            .join(User, User.id == Registration.user_id)
            .where(
                *_participant_filter(event.id),
                RegistrationBusNeed.trip_leg_id == leg.id,
                RegistrationBusNeed.needs_bus.is_(True),
            )
            .options(
                selectinload(RegistrationBusNeed.registration).selectinload(Registration.user).selectinload(User.team),
                selectinload(RegistrationBusNeed.pickup_point),
            )
            .order_by(User.full_name)
        ).all()
        for need in riders:
            if need.registration_id in assigned_ids:
                continue
            user = need.registration.user
            rows.append(
                [
                    "Chưa có xe", *empty_bus_info[1:], user.employee_code, user.full_name, user.phone,
                    _name(user.team), need.pickup_point.name if need.pickup_point else None, None, None,
                ]
            )
        sheets.append(Sheet(leg.name, headers, rows))

    content = build_workbook(sheets or [Sheet("Xe", headers)])
    _record(db, actor=actor, kind="buses", rows=total, sensitive=False, event=event, ip_address=ip_address)
    return content, filename("xe-dua-don", event)


# --- Phòng ---


def export_rooms(
    db: Session, *, event: Event, actor: User, ip_address: str | None = None
) -> tuple[bytes, str]:
    """Sheet đầu "Phân phòng" import lại được nguyên trạng qua màn hình Import phân phòng."""
    rooms = accommodation_service.list_rooms(db, event_id=event.id)
    assignments = db.scalars(
        select(RoomAssignment)
        .join(Room, Room.id == RoomAssignment.room_id)
        .join(Hotel, Hotel.id == Room.hotel_id)
        .where(Hotel.event_id == event.id)
        .options(selectinload(RoomAssignment.registration).selectinload(Registration.user).selectinload(User.team))
    ).all()
    by_room: dict[int, list[RoomAssignment]] = defaultdict(list)
    for assignment in assignments:
        by_room[assignment.room_id].append(assignment)

    room_headers = ["Khách sạn", "Tầng", "Số phòng", "Loại phòng", "Dành cho", "Sức chứa"]
    assigned_rows, empty_rows = [], []
    for room, _occupied, _captain in rooms:
        info = [
            room.hotel.name, room.floor, room.room_number, ROOM_TYPE_LABELS.get(room.room_type, room.room_type),
            POLICY_LABELS.get(room.gender_policy, room.gender_policy), room.capacity,
        ]
        occupants = sorted(
            by_room.get(room.id, []),
            key=lambda item: (not item.is_room_captain, item.registration.user.full_name),
        )
        if not occupants:
            empty_rows.append(info)
        for assignment in occupants:
            user = assignment.registration.user
            assigned_rows.append(
                [
                    *info, user.employee_code, user.email, user.full_name, GENDER_LABELS.get(user.gender, user.gender),
                    _name(user.team), "x" if assignment.is_room_captain else None, user.dietary_restriction,
                    MODE_LABELS.get(assignment.assignment_mode),
                ]
            )

    placed = {assignment.registration_id for assignment in assignments}
    unassigned_rows = [
        [registration.user.employee_code, registration.user.email, registration.user.full_name,
         GENDER_LABELS.get(registration.user.gender, registration.user.gender), _name(registration.user.team)]
        for registration in _participants(db, event.id)
        if registration.id not in placed
    ]

    content = build_workbook(
        [
            Sheet(
                "Phân phòng",
                [*room_headers, "Mã NV", "Email", "Họ tên", "Giới tính", "Team", "Trưởng phòng", "Ăn kiêng", "Nguồn xếp"],
                assigned_rows,
            ),
            Sheet("Phòng trống", room_headers, empty_rows),
            Sheet("Chưa có phòng", ["Mã NV", "Email", "Họ tên", "Giới tính", "Team"], unassigned_rows),
        ]
    )
    _record(db, actor=actor, kind="rooms", rows=len(assignments), sensitive=False, event=event, ip_address=ip_address)
    return content, filename("phan-phong", event)


# --- Nội bộ ---


def filename(stem: str, event: Event | None) -> str:
    stamp = utcnow().astimezone(VN_TZ).strftime("%Y%m%d-%H%M")
    base = f"{stem}-{event.code}" if event else stem
    return f"{safe_filename(base)}-{stamp}.xlsx"


def _record(
    db: Session,
    *,
    actor: User,
    kind: str,
    rows: int,
    sensitive: bool,
    event: Event | None,
    ip_address: str | None,
) -> None:
    event_id = event.id if event else None
    audit_service.log(
        db,
        action="export.downloaded",
        entity_type="export",
        entity_id=event_id,
        actor_id=actor.id,
        event_id=event_id,
        after={"kind": kind, "rows": rows, "sensitive": sensitive},
        ip_address=ip_address,
    )
    db.commit()


def _participant_filter(event_id: int) -> tuple:
    return (
        Registration.event_id == event_id,
        Registration.status == RegistrationStatus.SUBMITTED,
        Registration.is_participating.is_(True),
    )


def _participants(db: Session, event_id: int) -> list[Registration]:
    return list(
        db.scalars(
            select(Registration)
            .join(User, User.id == Registration.user_id)
            .where(*_participant_filter(event_id))
            .options(selectinload(Registration.user).selectinload(User.team))
            .order_by(User.full_name, Registration.id)
        )
    )


def _registrations_by_user(db: Session, event_id: int) -> dict[int, Registration]:
    return {
        registration.user_id: registration
        for registration in db.scalars(select(Registration).where(Registration.event_id == event_id))
    }


def _legs(db: Session, event_id: int) -> list[TripLeg]:
    return list(
        db.scalars(select(TripLeg).where(TripLeg.event_id == event_id).order_by(TripLeg.display_order, TripLeg.id))
    )


def _registration_label(registration: Registration | None) -> str:
    if registration is None or registration.status == RegistrationStatus.DRAFT:
        return "Chưa đăng ký"
    if registration.status == RegistrationStatus.CANCELLED:
        return "Đã huỷ"
    return "Tham gia" if registration.is_participating else "Không tham gia"


def _bus_need_label(need: RegistrationBusNeed | None, participating: bool) -> str | None:
    if need is not None and need.needs_bus:
        return f"Có — {need.pickup_point.name}" if need.pickup_point else "Có"
    return "Không" if participating else None


def _name(item) -> str | None:
    return item.name if item is not None else None


def _vn(value: str | None) -> str | None:
    return format_vn(value) if value else None
