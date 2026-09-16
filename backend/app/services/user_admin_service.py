"""Quản lý tài khoản CBNV cho BTC (docs/09-security.md §3).

Luật phân quyền, ngoài `require_admin` ở router:
- Tài khoản Ban tổ chức (admin, super_admin) chỉ super_admin sửa / khoá / đặt lại mật khẩu được.
  Không có luật này, một admin đổi email của super_admin rồi đặt lại mật khẩu là chiếm được quyền
  cao nhất.
- Đổi vai trò: chỉ super_admin (router chặn), và không ai tự đổi vai trò của chính mình.
- Không tự khoá hay tự đặt lại mật khẩu của chính mình — việc đó làm ở trang Hồ sơ.

Mật khẩu tạm do hệ thống sinh, trả về đúng một lần, bắt đổi ở lần đăng nhập đầu, không bao giờ
xuất hiện trong audit log. Khoá tài khoản hay đặt lại mật khẩu đều thu hồi mọi phiên đang mở.
"""

import logging
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, aliased, selectinload

from app.core.exceptions import AppError, ConflictError, NotFoundError, PermissionDeniedError
from app.core.security import generate_password, hash_password
from app.core.timeutils import is_expired
from app.models.enums import ADMIN_ROLES, RegistrationStatus, UserRole
from app.models.org import Department, Team, WorkLocation
from app.models.registration import Registration
from app.models.user import User
from app.services import audit_service, auth_service, login_guard

logger = logging.getLogger(__name__)

AUDITED_FIELDS = [
    "employee_code",
    "full_name",
    "email",
    "role",
    "is_active",
    "display_name",
    "phone",
    "personal_email",
    "gender",
    "date_of_birth",
    "address",
    "team_id",
    "department_id",
    "work_location_id",
    "job_title",
    "join_date",
    "id_card_number",
    "id_card_type",
    "id_card_issue_date",
    "id_card_issue_place",
    "shirt_size",
    "dietary_restriction",
    "health_note",
    "emergency_contact_name",
    "emergency_contact_phone",
]

REQUIRED_TEXT_FIELDS = {"full_name": "Họ tên", "email": "Email công ty"}


# --- Truy vấn ---


def list_users(
    db: Session,
    *,
    event_id: int | None,
    search: str | None = None,
    team_id: int | None = None,
    department_id: int | None = None,
    work_location_id: int | None = None,
    role: str | None = None,
    is_active: bool | None = None,
    missing_documents: bool | None = None,
    registration: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    reg = aliased(Registration)
    # Không có kỳ đang chạy thì không join được đăng ký nào (-1 không trùng id nào).
    query = select(User, reg).outerjoin(
        reg, and_(reg.user_id == User.id, reg.event_id == (event_id if event_id is not None else -1))
    )

    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(
            or_(User.full_name.like(pattern), User.email.like(pattern), User.employee_code.like(pattern))
        )
    for column, value in (
        (User.team_id, team_id),
        (User.department_id, department_id),
        (User.work_location_id, work_location_id),
        (User.role, role),
    ):
        if value is not None:
            query = query.where(column == value)
    if is_active is not None:
        query = query.where(User.is_active.is_(is_active))
    if missing_documents:
        query = query.where(
            or_(User.id_card_number.is_(None), User.id_card_number == "", User.date_of_birth.is_(None))
        )
    if registration:
        query = query.where(_registration_condition(reg, registration))

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.execute(
        query.order_by(User.full_name, User.id)
        .limit(limit)
        .offset(offset)
        .options(
            selectinload(User.team),
            selectinload(User.department),
            selectinload(User.work_location),
        )
    ).all()
    return [_list_row(user, registration_row) for user, registration_row in rows], total


def get_user(db: Session, user_id: int) -> User:
    user = db.scalar(
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.team), selectinload(User.department), selectinload(User.work_location))
    )
    if user is None:
        raise NotFoundError(f"Không tìm thấy CBNV #{user_id}.", code="USER_NOT_FOUND")
    return user


# --- Ghi ---


def create_user(
    db: Session, *, data: dict[str, Any], actor: User, ip_address: str | None = None
) -> tuple[User, str]:
    """Tạo tài khoản. Trả về (user, mật khẩu tạm) — mật khẩu chỉ có ở đây, không lưu bản rõ."""
    role = UserRole(data.get("role") or UserRole.EMPLOYEE)
    if role in ADMIN_ROLES and actor.role != UserRole.SUPER_ADMIN:
        raise PermissionDeniedError("Chỉ quản trị hệ thống mới tạo được tài khoản Ban tổ chức.")

    data = {**data, "role": role, "email": _clean_email(data["email"])}
    data["employee_code"] = (data.get("employee_code") or "").strip() or None
    _check_unique(db, email=data["email"], employee_code=data["employee_code"])
    _validate_refs(db, data)

    password = generate_password()
    user = User(**data, password_hash=hash_password(password), must_change_password=True, is_active=True)
    db.add(user)
    db.flush()

    audit_service.log(
        db,
        action="user.created",
        entity_type="user",
        entity_id=user.id,
        actor_id=actor.id,
        after=audit_service.snapshot(user, AUDITED_FIELDS),
        ip_address=ip_address,
    )
    db.commit()
    logger.info("BTC %s tạo tài khoản %s", actor.email, user.email)
    return get_user(db, user.id), password


def update_user(
    db: Session, *, user: User, data: dict[str, Any], actor: User, ip_address: str | None = None
) -> User:
    _ensure_can_manage(actor, user)
    if not data:
        return user

    for field, label in REQUIRED_TEXT_FIELDS.items():
        if field in data and not (data[field] or "").strip():
            raise AppError(f"{label} không được để trống.", code="REQUIRED_FIELD", details={"field": field})
    if "email" in data:
        data["email"] = _clean_email(data["email"])
    if "employee_code" in data:
        data["employee_code"] = (data["employee_code"] or "").strip() or None

    _check_unique(
        db, email=data.get("email"), employee_code=data.get("employee_code"), exclude_id=user.id
    )
    _validate_refs(db, data)

    before = audit_service.snapshot(user, AUDITED_FIELDS)
    for field, value in data.items():
        setattr(user, field, value)
    db.flush()
    audit_service.log(
        db,
        action="user.updated",
        entity_type="user",
        entity_id=user.id,
        actor_id=actor.id,
        before=before,
        after=audit_service.diff(before, audit_service.snapshot(user, AUDITED_FIELDS)),
        ip_address=ip_address,
    )
    db.commit()
    return get_user(db, user.id)


def change_role(
    db: Session,
    *,
    user: User,
    role: UserRole,
    actor: User,
    reason: str | None = None,
    ip_address: str | None = None,
) -> User:
    """Chỉ super_admin gọi được (router chặn)."""
    if user.id == actor.id:
        raise ConflictError(
            "Không tự đổi vai trò của chính mình — nhờ một quản trị hệ thống khác.",
            code="SELF_ROLE_CHANGE",
        )
    if user.role == role:
        raise ConflictError("Người này đã có vai trò đó.", code="ROLE_UNCHANGED")

    previous = user.role
    user.role = role
    db.flush()
    audit_service.log(
        db,
        action="user.role_changed",
        entity_type="user",
        entity_id=user.id,
        actor_id=actor.id,
        before={"role": previous},
        after={"role": role},
        reason=reason,
        ip_address=ip_address,
    )
    db.commit()
    return get_user(db, user.id)


def set_status(
    db: Session,
    *,
    user: User,
    is_active: bool,
    reason: str,
    actor: User,
    ip_address: str | None = None,
) -> User:
    if user.id == actor.id:
        raise ConflictError("Không tự khoá tài khoản của chính mình.", code="SELF_DEACTIVATION")
    _ensure_can_manage(actor, user)
    if user.is_active == is_active:
        raise ConflictError(
            "Tài khoản đang ở đúng trạng thái đó rồi.", code="STATUS_UNCHANGED"
        )

    user.is_active = is_active
    revoked = 0 if is_active else auth_service.revoke_all_sessions(db, user_id=user.id, reason="account_disabled")
    db.flush()
    audit_service.log(
        db,
        action="user.activated" if is_active else "user.deactivated",
        entity_type="user",
        entity_id=user.id,
        actor_id=actor.id,
        before={"is_active": not is_active},
        after={"is_active": is_active, "sessions_revoked": revoked},
        reason=reason,
        ip_address=ip_address,
    )
    db.commit()
    return get_user(db, user.id)


def reset_password(
    db: Session, *, user: User, actor: User, ip_address: str | None = None
) -> tuple[str, int]:
    """Sinh mật khẩu tạm mới, mở khoá đăng nhập, thu hồi mọi phiên. Trả về (mật khẩu, số phiên thu hồi)."""
    if user.id == actor.id:
        raise ConflictError("Đổi mật khẩu của chính mình ở trang Hồ sơ.", code="SELF_PASSWORD_RESET")
    _ensure_can_manage(actor, user)

    password = generate_password()
    user.password_hash = hash_password(password)
    user.must_change_password = True
    user.failed_login_count = 0
    user.locked_until = None
    # Cả bộ đếm theo IP nữa, nếu không thì người dùng cầm mật khẩu tạm vẫn ăn 429.
    login_guard.clear(db, email=user.email)
    revoked = auth_service.revoke_all_sessions(db, user_id=user.id, reason="password_reset")
    db.flush()
    audit_service.log(
        db,
        action="user.password_reset",
        entity_type="user",
        entity_id=user.id,
        actor_id=actor.id,
        after={"sessions_revoked": revoked, "must_change_password": True},
        ip_address=ip_address,
    )
    db.commit()
    logger.info("BTC %s đặt lại mật khẩu cho %s", actor.email, user.email)
    return password, revoked


def unlock(db: Session, *, user: User, actor: User, ip_address: str | None = None) -> User:
    """Gỡ khoá tạm do nhập sai mật khẩu nhiều lần, giữ nguyên mật khẩu."""
    _ensure_can_manage(actor, user)
    user.failed_login_count = 0
    user.locked_until = None
    # Gỡ nốt rate limit theo IP: gỡ mỗi khoá tài khoản thì người dùng vẫn bị 429.
    login_guard.clear(db, email=user.email)
    db.flush()
    audit_service.log(
        db,
        action="user.unlocked",
        entity_type="user",
        entity_id=user.id,
        actor_id=actor.id,
        ip_address=ip_address,
    )
    db.commit()
    return get_user(db, user.id)


# --- Nội bộ ---


def _registration_condition(reg, value: str):
    submitted = reg.status == RegistrationStatus.SUBMITTED
    return {
        "none": or_(reg.id.is_(None), reg.status == RegistrationStatus.DRAFT),
        "submitted": submitted,
        "participating": and_(submitted, reg.is_participating.is_(True)),
        "not_participating": and_(submitted, reg.is_participating.is_(False)),
        "cancelled": reg.status == RegistrationStatus.CANCELLED,
    }[value]


def _list_row(user: User, registration: Registration | None) -> dict[str, Any]:
    submitted = registration is not None and registration.status == RegistrationStatus.SUBMITTED
    return {
        "id": user.id,
        "employee_code": user.employee_code,
        "full_name": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "gender": user.gender,
        "role": user.role,
        "job_title": user.job_title,
        "team_id": user.team_id,
        "team_name": user.team.name if user.team else None,
        "department_id": user.department_id,
        "department_name": user.department.name if user.department else None,
        "work_location_id": user.work_location_id,
        "work_location_name": user.work_location.name if user.work_location else None,
        "is_active": user.is_active,
        "must_change_password": user.must_change_password,
        "is_locked": bool(user.locked_until and not is_expired(user.locked_until)),
        "last_login_at": user.last_login_at,
        "can_fly": user.can_fly,
        "registration_status": registration.status if registration else None,
        "is_participating": registration.is_participating if submitted else None,
    }


def _ensure_can_manage(actor: User, target: User) -> None:
    if target.role in ADMIN_ROLES and actor.role != UserRole.SUPER_ADMIN:
        raise PermissionDeniedError(
            "Tài khoản Ban tổ chức chỉ quản trị hệ thống (super admin) mới sửa được."
        )


def _clean_email(value: str | None) -> str:
    return (value or "").strip().lower()


def _check_unique(
    db: Session,
    *,
    email: str | None = None,
    employee_code: str | None = None,
    exclude_id: int | None = None,
) -> None:
    others = [User.id != exclude_id] if exclude_id is not None else []
    if email and db.scalar(select(User.id).where(func.lower(User.email) == email, *others)):
        raise ConflictError(
            f"Email {email} đã dùng cho tài khoản khác.", code="EMAIL_TAKEN", details={"email": email}
        )
    if employee_code and db.scalar(select(User.id).where(User.employee_code == employee_code, *others)):
        raise ConflictError(
            f"Mã nhân viên {employee_code} đã có.",
            code="EMPLOYEE_CODE_TAKEN",
            details={"employee_code": employee_code},
        )


def _validate_refs(db: Session, data: dict[str, Any]) -> None:
    for field, model, code, label in (
        ("team_id", Team, "TEAM_NOT_FOUND", "team"),
        ("department_id", Department, "DEPARTMENT_NOT_FOUND", "phòng ban"),
        ("work_location_id", WorkLocation, "WORK_LOCATION_NOT_FOUND", "nơi làm việc"),
    ):
        value = data.get(field)
        if value is not None and db.get(model, value) is None:
            raise NotFoundError(f"Không tìm thấy {label} #{value}.", code=code)
