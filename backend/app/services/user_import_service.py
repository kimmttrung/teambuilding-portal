"""Import danh sách CBNV từ Excel (bước 21).

Cùng hai nguyên tắc với import phân phòng: **tất cả hoặc không gì cả** (còn lỗi là không ghi dòng
nào, trả lỗi kèm SỐ DÒNG Excel) và **xem trước mặc định**.

- Khớp người theo Mã NV, không có thì theo Email. Có rồi thì cập nhật, chưa có thì tạo mới.
- **Ô trống = giữ nguyên.** File nhân sự thường thiếu vài cột; một ô trống không được xoá số điện
  thoại CBNV đã tự khai.
- Import **không cấp quyền Ban tổ chức và không sửa tài khoản Ban tổ chức** — việc đó làm ở màn hình
  Quản lý CBNV, nơi phân quyền theo từng người.
- Tài khoản mới có mật khẩu tạm, trả về MỘT lần trong response của lần ghi thật, bắt đổi khi đăng
  nhập lần đầu. Không gửi mật khẩu qua email: nội dung email được lưu lại trong nhật ký email.
"""

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import immediate_transaction
from app.core.exceptions import AppError
from app.core.security import generate_password, hash_password
from app.models.enums import ADMIN_ROLES, UserRole
from app.models.org import Department, Team, WorkLocation
from app.models.user import User
from app.services import audit_service
from app.services.excel import build_aliases, normalize, parse_date, read_rows
from app.services.export_service import GENDER_LABELS, ROLE_LABELS

logger = logging.getLogger(__name__)

MAX_ERRORS_RETURNED = 200
EMPLOYEE_CODE_RE = re.compile(r"^[A-Za-z0-9._-]{2,32}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

COLUMN_ALIASES = build_aliases(
    {
        "employee_code": {"Mã NV", "Mã nhân viên", "employee_code"},
        "full_name": {"Họ tên", "Họ và tên", "full_name", "name"},
        "email": {"Email", "Email công ty", "e-mail"},
        "gender": {"Giới tính", "gender"},
        "phone": {"SĐT", "Số điện thoại", "Điện thoại", "phone"},
        "team": {"Team", "Nhóm", "team"},
        "department": {"Phòng ban", "Khối", "department"},
        "work_location": {"Nơi làm việc", "Văn phòng", "work_location"},
        "job_title": {"Chức danh", "Chức vụ", "job_title"},
        "join_date": {"Ngày vào làm", "join_date"},
        "role": {"Vai trò", "role"},
        "date_of_birth": {"Ngày sinh", "date_of_birth"},
        "id_card_number": {"Số CCCD/Hộ chiếu", "Số CCCD", "CCCD", "CMND", "id_card_number"},
    }
)

GENDER_VALUES = {
    **{normalize(label): value for value, label in GENDER_LABELS.items()},
    "male": "male",
    "female": "female",
    "other": "other",
}
ROLE_VALUES = {
    **{normalize(label): value for value, label in ROLE_LABELS.items()},
    **{normalize(role.value): role.value for role in UserRole},
    "nhan vien": UserRole.EMPLOYEE.value,
}


def import_users(
    db: Session, *, content: bytes, actor: User, dry_run: bool = True, ip_address: str | None = None
) -> dict[str, Any]:
    rows = read_rows(content, aliases=COLUMN_ALIASES, validate_header=_check_header)
    actor_id = actor.id

    planned, errors = _plan(db, rows)
    if dry_run:
        return _result(rows, planned, errors, dry_run=True, committed=False)
    if errors:
        raise _validation_error(_result(rows, planned, errors, dry_run=False, committed=False))

    # bcrypt 12 vòng ~0,25 s/lần: băm song song NGOÀI transaction, để 100 tài khoản mới không giữ
    # khoá ghi của SQLite cả chục giây.
    credentials = _prepare_passwords(sum(1 for item in planned if item["user"] is None))

    with immediate_transaction(db):
        planned, errors = _plan(db, rows)
        result = _result(rows, planned, errors, dry_run=False, committed=not errors)
        if errors:
            raise _validation_error(result)

        accounts, created_ids = _apply(db, planned, credentials)
        audit_service.log(
            db,
            action="user.imported",
            entity_type="user_import",
            actor_id=actor_id,
            after={
                "total_rows": result["total_rows"],
                "created": result["to_create"],
                "updated": result["to_update"],
                "unchanged": result["unchanged"],
                "created_ids": created_ids,
            },
            ip_address=ip_address,
        )

    logger.info("Import CBNV: tạo %s, cập nhật %s", result["to_create"], result["to_update"])
    return {**result, "created_accounts": accounts}


# --- Kiểm tra ---


def _check_header(mapping: dict[str, int], cells: list[str]) -> None:
    missing = [label for name, label in (("employee_code", "Mã NV"), ("full_name", "Họ tên"), ("email", "Email")) if name not in mapping]
    if missing:
        raise AppError(
            "File thiếu cột bắt buộc: " + ", ".join(missing) + ". Cột tuỳ chọn: Giới tính, SĐT, Team, "
            "Phòng ban, Nơi làm việc, Chức danh, Ngày vào làm, Vai trò, Ngày sinh, Số CCCD/Hộ chiếu.",
            code="MISSING_COLUMNS",
            details={"found": [cell for cell in cells if cell], "missing": missing},
        )


def _plan(db: Session, rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    teams = _lookup(db.scalars(select(Team)).all())
    departments = _lookup(db.scalars(select(Department)).all())
    locations = _lookup(db.scalars(select(WorkLocation)).all())
    users = db.scalars(select(User)).all()
    by_code = {user.employee_code.upper(): user for user in users if user.employee_code}
    by_email = {user.email.lower(): user for user in users}

    planned: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    seen_codes: dict[str, int] = {}
    seen_emails: dict[str, int] = {}

    for record in rows:
        row = record["row"]
        problems: list[dict[str, Any]] = []

        def problem(code: str, message: str, row: int = row, problems: list = problems) -> None:
            problems.append({"row": row, "code": code, "message": message})

        employee_code = record.get("employee_code", "").strip()
        full_name = " ".join(record.get("full_name", "").split())
        email = record.get("email", "").strip().lower()
        label = employee_code or email or f"Dòng {row}"

        if not employee_code:
            problem("MISSING_EMPLOYEE_CODE", f"Dòng {row}: thiếu Mã NV.")
        elif not EMPLOYEE_CODE_RE.match(employee_code):
            problem("INVALID_EMPLOYEE_CODE", f"Mã NV '{employee_code}' không hợp lệ (2-32 ký tự: chữ, số, dấu chấm, gạch).")
        if not full_name:
            problem("MISSING_FULL_NAME", f"{label}: thiếu họ tên.")
        if not email:
            problem("MISSING_EMAIL", f"{label}: thiếu email.")
        elif not EMAIL_RE.match(email):
            problem("INVALID_EMAIL", f"{label}: email '{email}' không hợp lệ.")

        code_key = employee_code.upper()
        if employee_code and code_key in seen_codes:
            problem("DUPLICATE_IN_FILE", f"Mã NV {employee_code} trùng với dòng {seen_codes[code_key]}.")
        elif email and email in seen_emails:
            problem("DUPLICATE_IN_FILE", f"Email {email} trùng với dòng {seen_emails[email]}.")
        if employee_code:
            seen_codes.setdefault(code_key, row)
        if email:
            seen_emails.setdefault(email, row)

        target = by_code.get(code_key) if employee_code else None
        owner = by_email.get(email) if email else None
        if target is None and owner is not None:
            if owner.employee_code and owner.employee_code.upper() != code_key:
                problem("EMAIL_TAKEN", f"{label}: email {email} đang là tài khoản mã NV {owner.employee_code}.")
            else:
                target = owner
        elif target is not None and owner is not None and owner.id != target.id:
            problem("EMAIL_TAKEN", f"{label}: email {email} đang là tài khoản của {owner.full_name}.")

        values: dict[str, Any] = {"employee_code": employee_code, "full_name": full_name, "email": email}

        gender_text = record.get("gender", "")
        if gender_text:
            gender = GENDER_VALUES.get(normalize(gender_text))
            if gender is None:
                problem("INVALID_GENDER", f"{label}: giới tính '{gender_text}' không hợp lệ — dùng Nam, Nữ hoặc Khác.")
            else:
                values["gender"] = gender

        phone = _clean_phone(record.get("phone", ""))
        if phone:
            if len(phone) > 32:
                problem("INVALID_PHONE", f"{label}: số điện thoại quá dài.")
            else:
                values["phone"] = phone

        for field, lookup, code, noun in (
            ("team", teams, "TEAM_NOT_FOUND", "team"),
            ("department", departments, "DEPARTMENT_NOT_FOUND", "phòng ban"),
            ("work_location", locations, "WORK_LOCATION_NOT_FOUND", "nơi làm việc"),
        ):
            text = record.get(field, "")
            if text:
                found = lookup.get(normalize(text))
                if found is None:
                    problem(code, f"{label}: không có {noun} '{text}' (ghi theo mã hoặc tên).")
                else:
                    values[f"{field}_id"] = found.id

        job_title = record.get("job_title", "").strip()
        if job_title:
            if len(job_title) > 128:
                problem("INVALID_JOB_TITLE", f"{label}: chức danh quá dài (tối đa 128 ký tự).")
            else:
                values["job_title"] = job_title

        for field, noun in (("join_date", "Ngày vào làm"), ("date_of_birth", "Ngày sinh")):
            text = record.get(field, "")
            if text:
                parsed = parse_date(text)
                if parsed is None:
                    problem("INVALID_DATE", f"{label}: {noun} '{text}' không đọc được — dùng dạng 31/12/1995.")
                else:
                    values[field] = parsed

        id_card = record.get("id_card_number", "").replace(" ", "")
        if id_card:
            if len(id_card) > 32:
                problem("INVALID_ID_CARD", f"{label}: số CCCD/hộ chiếu quá dài.")
            else:
                values["id_card_number"] = id_card

        role_text = record.get("role", "")
        if role_text:
            role = ROLE_VALUES.get(normalize(role_text))
            if role is None:
                problem("INVALID_ROLE", f"{label}: vai trò '{role_text}' không hợp lệ — dùng CBNV hoặc Trưởng nhóm.")
            elif role in ADMIN_ROLES and (target is None or target.role != role):
                problem(
                    "ROLE_NOT_ALLOWED",
                    f"{label}: import không cấp quyền Ban tổ chức — đổi vai trò trong màn hình Quản lý CBNV.",
                )
            else:
                values["role"] = role

        if problems:
            errors.extend(problems)
            continue

        if target is None:
            values.setdefault("role", UserRole.EMPLOYEE.value)
            planned.append({"row": row, "user": None, "values": values})
            continue

        changes = {field: value for field, value in values.items() if getattr(target, field) != value}
        if changes and target.role in ADMIN_ROLES:
            errors.append(
                {
                    "row": row,
                    "code": "ADMIN_ACCOUNT_PROTECTED",
                    "message": f"{label}: tài khoản Ban tổ chức không sửa qua import — dùng màn hình Quản lý CBNV.",
                }
            )
            continue
        planned.append({"row": row, "user": target, "values": changes})

    errors.sort(key=lambda error: (error["row"], error["code"]))
    return planned, errors


# --- Ghi ---


def _prepare_passwords(count: int) -> list[tuple[str, str]]:
    if count <= 0:
        return []
    passwords = [generate_password() for _ in range(count)]
    with ThreadPoolExecutor(max_workers=min(8, count)) as pool:
        hashes = list(pool.map(hash_password, passwords))
    return list(zip(passwords, hashes, strict=True))


def _apply(
    db: Session, planned: list[dict[str, Any]], credentials: list[tuple[str, str]]
) -> tuple[list[dict[str, str]], list[int]]:
    accounts: list[dict[str, str]] = []
    created: list[User] = []
    pool = list(credentials)

    for item in planned:
        if item["user"] is not None:
            for field, value in item["values"].items():
                setattr(item["user"], field, value)
            continue
        if pool:
            password, password_hash = pool.pop()
        else:  # dữ liệu đổi giữa lúc kiểm tra và lúc ghi, có thêm người mới
            password = generate_password()
            password_hash = hash_password(password)
        user = User(**item["values"], password_hash=password_hash, must_change_password=True, is_active=True)
        db.add(user)
        created.append(user)
        accounts.append(
            {
                "employee_code": user.employee_code,
                "full_name": user.full_name,
                "email": user.email,
                "temporary_password": password,
            }
        )
    db.flush()
    return accounts, [user.id for user in created]


def _result(rows, planned, errors, *, dry_run: bool, committed: bool) -> dict[str, Any]:
    to_create = sum(1 for item in planned if item["user"] is None)
    to_update = sum(1 for item in planned if item["user"] is not None and item["values"])
    return {
        "dry_run": dry_run,
        "committed": committed,
        "total_rows": len(rows),
        "valid_rows": len(planned),
        "error_count": len(errors),
        "errors": errors[:MAX_ERRORS_RETURNED],
        "to_create": to_create,
        "to_update": to_update,
        "unchanged": len(planned) - to_create - to_update,
        "created_accounts": [],
    }


def _validation_error(result: dict[str, Any]) -> AppError:
    return AppError(
        f"File còn {result['error_count']} dòng lỗi nên chưa ghi dòng nào. Sửa rồi import lại.",
        code="IMPORT_VALIDATION_FAILED",
        details=result,
    )


def _lookup(items) -> dict[str, Any]:
    mapping: dict[str, Any] = {}
    for item in items:
        for key in (item.code, item.name):
            if key:
                mapping.setdefault(normalize(key), item)
    return mapping


def _clean_phone(text: str) -> str:
    """Excel hay lưu số điện thoại thành số và mất số 0 đầu: 912345678 -> 0912345678."""
    compact = re.sub(r"[\s.]", "", text or "")
    if compact.isdigit() and len(compact) == 9:
        compact = "0" + compact
    return compact
