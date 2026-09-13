"""Import danh sách phân phòng từ Excel — MVP của docs/05 §7.

Hai nguyên tắc:

1. **Tất cả hoặc không gì cả.** File 120 dòng lỗi 3 dòng mà ghi 117 dòng thì BTC phải đi
   dò xem dòng nào đã vào, dòng nào chưa. Nên còn lỗi là không ghi dòng nào, và trả về
   danh sách lỗi kèm SỐ DÒNG trong Excel để sửa ngay trên file.
2. **Xem trước mặc định.** `dry_run=true` chỉ kiểm tra; bấm ghi thật mới ghi, và khi ghi
   thì kiểm tra LẠI trong `BEGIN IMMEDIATE` (dữ liệu có thể đã đổi từ lúc xem trước).

Cột được nhận diện theo tên (xem `excel.py`): "Mã NV", "ma nv", "employee_code" đều được.
"""

import logging
from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import immediate_transaction
from app.core.exceptions import AppError
from app.core.timeutils import utcnow_iso
from app.models.accommodation import Hotel, Room, RoomAssignment
from app.models.enums import AssignmentMode, RegistrationStatus
from app.models.event import Event
from app.models.registration import Registration
from app.models.user import User
from app.services import audit_service
from app.services.accommodation_service import gender_message, gender_violation
from app.services.excel import TRUTHY, build_aliases, normalize, read_rows

logger = logging.getLogger(__name__)

MAX_ERRORS_RETURNED = 200

COLUMN_ALIASES = build_aliases(
    {
        "employee_code": {"Mã NV", "Mã nhân viên", "employee_code", "employee code"},
        "email": {"Email", "Email công ty", "e-mail"},
        "room_number": {"Số phòng", "Phòng", "room", "room_number", "room number"},
        "hotel": {"Khách sạn", "hotel", "hotel_name", "hotel name"},
        "is_room_captain": {"Trưởng phòng", "room_captain", "is_room_captain", "captain"},
    }
)


# --- Đọc file ---


def parse_rows(content: bytes) -> list[dict[str, Any]]:
    """Đọc sheet đầu tiên thành danh sách dòng `{field: text, "row": số dòng Excel}`."""
    return read_rows(content, aliases=COLUMN_ALIASES, validate_header=_check_header)


def _check_header(mapping: dict[str, int], cells: list[str]) -> None:
    if "room_number" not in mapping or not ({"employee_code", "email"} & mapping.keys()):
        raise AppError(
            "File thiếu cột bắt buộc: cần 'Số phòng' và 'Mã NV' (hoặc 'Email'). "
            "Cột tuỳ chọn: 'Khách sạn', 'Trưởng phòng'.",
            code="MISSING_COLUMNS",
            details={"found": [cell for cell in cells if cell]},
        )


# --- Kiểm tra và lập kế hoạch ---


def _plan(
    db: Session, *, event_id: int, rows: list[dict[str, Any]], replace_existing: bool
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Kiểm tra từng dòng. Trả về (các dòng hợp lệ, các lỗi)."""
    hotels = db.scalars(select(Hotel).where(Hotel.event_id == event_id)).all()
    hotel_by_name = {normalize(hotel.name): hotel for hotel in hotels}

    rooms = db.scalars(
        select(Room).join(Hotel, Hotel.id == Room.hotel_id).where(Hotel.event_id == event_id)
    ).all()
    room_by_key = {(room.hotel_id, normalize(room.room_number)): room for room in rooms}
    room_by_id = {room.id: room for room in rooms}

    participants = db.scalars(
        select(Registration)
        .where(
            Registration.event_id == event_id,
            Registration.status == RegistrationStatus.SUBMITTED,
            Registration.is_participating.is_(True),
        )
        .options(selectinload(Registration.user))
    ).all()
    by_code = {
        registration.user.employee_code.upper(): registration
        for registration in participants
        if registration.user.employee_code
    }
    by_email = {registration.user.email.lower(): registration for registration in participants}

    # Để phân biệt "không có người này" với "có người nhưng không tham gia".
    known_codes = {
        code.upper() for code in db.scalars(select(User.employee_code)).all() if code
    }
    known_emails = {email.lower() for email in db.scalars(select(User.email)).all()}

    existing = {
        assignment.registration_id: assignment
        for assignment in db.scalars(
            select(RoomAssignment)
            .join(Room, Room.id == RoomAssignment.room_id)
            .join(Hotel, Hotel.id == Room.hotel_id)
            .where(Hotel.event_id == event_id)
        )
    }

    errors: list[dict[str, Any]] = []
    planned: list[dict[str, Any]] = []
    seen: dict[int, int] = {}

    def fail(row: int, code: str, message: str) -> None:
        errors.append({"row": row, "code": code, "message": message})

    for record in rows:
        row = record["row"]
        code = record.get("employee_code", "").strip().upper()
        email = record.get("email", "").strip().lower()
        label = code or email

        registration = by_code.get(code) if code else None
        if registration is None and email:
            registration = by_email.get(email)

        if registration is None:
            if not label:
                fail(row, "MISSING_IDENTIFIER", "Dòng thiếu cả Mã NV lẫn Email.")
            elif (code and code in known_codes) or (email and email in known_emails):
                fail(
                    row,
                    "NOT_PARTICIPATING",
                    f"{label} không có đăng ký tham gia hợp lệ trong kỳ này "
                    "(chưa đăng ký, không tham gia hoặc đã huỷ).",
                )
            else:
                fail(row, "USER_NOT_FOUND", f"Không tìm thấy CBNV {label}.")
            continue

        user = registration.user
        if registration.id in seen:
            fail(
                row,
                "DUPLICATE_IN_FILE",
                f"{user.full_name} xuất hiện lần nữa (đã có ở dòng {seen[registration.id]}).",
            )
            continue
        seen[registration.id] = row

        room_text = record.get("room_number", "")
        if not room_text:
            fail(row, "MISSING_ROOM", f"Dòng của {user.full_name} thiếu số phòng.")
            continue

        hotel_name = record.get("hotel", "").strip()
        if hotel_name:
            hotel = hotel_by_name.get(normalize(hotel_name))
            if hotel is None:
                fail(row, "HOTEL_NOT_FOUND", f"Không có khách sạn '{hotel_name}' trong kỳ này.")
                continue
        elif len(hotels) == 1:
            hotel = hotels[0]
        else:
            fail(
                row,
                "HOTEL_REQUIRED",
                "Kỳ này có nhiều khách sạn (hoặc chưa có khách sạn nào) — cột 'Khách sạn' không được để trống.",
            )
            continue

        room = room_by_key.get((hotel.id, normalize(room_text)))
        if room is None:
            fail(row, "ROOM_NOT_FOUND", f"Không có phòng {room_text} ở {hotel.name}.")
            continue

        violation = gender_violation(room.gender_policy, user.gender)
        if violation:
            fail(row, violation, gender_message(violation, user.full_name, room.room_number, room.gender_policy))
            continue

        current = existing.get(registration.id)
        if current is not None and current.room_id != room.id and not replace_existing:
            fail(
                row,
                "ALREADY_HAS_ROOM",
                f"{user.full_name} đang ở phòng {room_by_id[current.room_id].room_number}. "
                "Bật 'thay chỗ cũ' nếu muốn chuyển.",
            )
            continue

        planned.append(
            {
                "row": row,
                "registration": registration,
                "room": room,
                "captain": normalize(record.get("is_room_captain", "")) in TRUTHY,
                "current": current,
            }
        )

    planned = _check_capacity(planned, existing, room_by_id, fail)
    planned = _check_captains(planned, fail)
    errors.sort(key=lambda error: (error["row"], error["code"]))
    return planned, errors


def _check_capacity(planned, existing, room_by_id, fail) -> list[dict[str, Any]]:
    """Sức chứa tính trên trạng thái SAU import: người đang ở mà không có trong file thì ở lại,
    người có trong file chuyển đi thì nhả chỗ."""
    moving = {item["registration"].id for item in planned}
    final: dict[int, int] = defaultdict(int)
    for registration_id, assignment in existing.items():
        if registration_id not in moving:
            final[assignment.room_id] += 1
    for item in planned:
        final[item["room"].id] += 1

    over = {room_id for room_id, count in final.items() if count > room_by_id[room_id].capacity}
    kept = []
    for item in planned:
        room = item["room"]
        if room.id in over:
            fail(
                item["row"],
                "ROOM_OVER_CAPACITY",
                f"Phòng {room.room_number} chỉ có {room.capacity} chỗ nhưng sẽ có "
                f"{final[room.id]} người sau khi import.",
            )
        else:
            kept.append(item)
    return kept


def _check_captains(planned, fail) -> list[dict[str, Any]]:
    by_room: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for item in planned:
        if item["captain"]:
            by_room[item["room"].id].append(item)

    rejected = set()
    for items in by_room.values():
        for extra in items[1:]:
            fail(
                extra["row"],
                "CAPTAIN_CONFLICT",
                f"Phòng {extra['room'].room_number} có nhiều hơn một trưởng phòng trong file "
                f"(dòng {items[0]['row']} đã là trưởng phòng).",
            )
            rejected.add(extra["row"])
    return [item for item in planned if item["row"] not in rejected]


# --- Ghi ---


def import_room_assignments(
    db: Session,
    *,
    event: Event,
    content: bytes,
    actor: User,
    dry_run: bool = True,
    replace_existing: bool = False,
    ip_address: str | None = None,
) -> dict[str, Any]:
    rows = parse_rows(content)
    event_id, actor_id = event.id, actor.id

    if dry_run:
        planned, errors = _plan(db, event_id=event_id, rows=rows, replace_existing=replace_existing)
        return _result(rows, planned, errors, dry_run=True, committed=False)

    with immediate_transaction(db):
        planned, errors = _plan(db, event_id=event_id, rows=rows, replace_existing=replace_existing)
        result = _result(rows, planned, errors, dry_run=False, committed=not errors)
        if errors:
            raise AppError(
                f"File còn {len(errors)} dòng lỗi nên chưa ghi dòng nào. Sửa rồi import lại.",
                code="IMPORT_VALIDATION_FAILED",
                details=result,
            )

        _apply(db, planned, actor_id)
        audit_service.log(
            db,
            action="room.imported",
            entity_type="room_import",
            entity_id=event_id,
            actor_id=actor_id,
            event_id=event_id,
            after={
                "total_rows": result["total_rows"],
                "created": result["to_create"],
                "moved": result["to_move"],
                "unchanged": result["unchanged"],
                "replace_existing": replace_existing,
            },
            ip_address=ip_address,
        )

    logger.info(
        "Import phân phòng: %s tạo mới, %s chuyển phòng", result["to_create"], result["to_move"]
    )
    return result


def _apply(db: Session, planned: list[dict[str, Any]], actor_id: int) -> None:
    now = utcnow_iso()
    for item in planned:
        current, room = item["current"], item["room"]
        if current is None:
            db.add(
                RoomAssignment(
                    registration_id=item["registration"].id,
                    room_id=room.id,
                    is_room_captain=item["captain"],
                    assignment_mode=AssignmentMode.MANUAL,
                    assigned_by=actor_id,
                    assigned_at=now,
                )
            )
        elif current.room_id != room.id or bool(current.is_room_captain) != item["captain"]:
            current.room_id = room.id
            current.is_room_captain = item["captain"]
            current.assignment_mode = AssignmentMode.MANUAL
            current.assigned_by = actor_id
            current.assigned_at = now
    db.flush()

    # Mỗi phòng một trưởng phòng: file đặt trưởng phòng mới thì bỏ cờ của người cũ.
    for item in planned:
        if not item["captain"]:
            continue
        others = db.scalars(
            select(RoomAssignment).where(
                RoomAssignment.room_id == item["room"].id,
                RoomAssignment.registration_id != item["registration"].id,
                RoomAssignment.is_room_captain.is_(True),
            )
        ).all()
        for other in others:
            other.is_room_captain = False
    db.flush()


def _result(rows, planned, errors, *, dry_run: bool, committed: bool) -> dict[str, Any]:
    """Tính số liệu TRƯỚC khi ghi — sau khi ghi thì `current.room_id` đã đổi, đếm lại sẽ sai."""
    to_create = sum(1 for item in planned if item["current"] is None)
    to_move = sum(
        1 for item in planned if item["current"] is not None and item["current"].room_id != item["room"].id
    )
    return {
        "dry_run": dry_run,
        "committed": committed,
        "total_rows": len(rows),
        "valid_rows": len(planned),
        "error_count": len(errors),
        "errors": errors[:MAX_ERRORS_RETURNED],
        "to_create": to_create,
        "to_move": to_move,
        "unchanged": len(planned) - to_create - to_move,
    }
