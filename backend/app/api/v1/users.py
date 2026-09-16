"""Quản lý tài khoản CBNV cho BTC (docs/04-api-spec.md §10, docs/09-security.md §3).

Cả router dành cho BTC. Đổi vai trò chỉ super_admin. Tài khoản Ban tổ chức chỉ super_admin sửa
được — kiểm tra ở service vì phụ thuộc người bị sửa, không chỉ người sửa.

`/export` và `/import` khai báo TRƯỚC `/{user_id}`: FastAPI khớp route theo thứ tự, để sau thì
"export" bị hiểu là một user_id sai kiểu.
"""

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile, status

from app.api.v1.downloads import xlsx_response
from app.core.dependencies import (
    ActiveEvent,
    AdminUser,
    DbSession,
    SuperAdminUser,
    get_client_ip,
    require_admin,
)
from app.models.enums import UserRole
from app.schemas.common import Page
from app.schemas.user import UserAdmin
from app.schemas.user_admin import (
    PasswordResetOut,
    RegistrationFilter,
    UserAdminUpdate,
    UserCreate,
    UserCredentialsOut,
    UserListItem,
    UserRoleUpdate,
    UserStatusUpdate,
)
from app.schemas.user_import import UserImportResult
from app.services import export_service, user_admin_service, user_import_service

router = APIRouter(prefix="/admin/users", tags=["users"], dependencies=[Depends(require_admin)])


@router.get("", response_model=Page[UserListItem], summary="Danh sách CBNV")
def list_users(
    event: ActiveEvent,
    db: DbSession,
    q: str | None = Query(default=None, description="Tìm theo tên, email, mã nhân viên"),
    team_id: int | None = None,
    department_id: int | None = None,
    work_location_id: int | None = None,
    role: UserRole | None = None,
    is_active: bool | None = None,
    missing_documents: bool | None = Query(default=None, description="Chỉ người thiếu CCCD/ngày sinh"),
    registration: RegistrationFilter | None = Query(
        default=None, description="Đăng ký của kỳ đang chạy"
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> Page[UserListItem]:
    rows, total = user_admin_service.list_users(
        db,
        event_id=event.id,
        search=q,
        team_id=team_id,
        department_id=department_id,
        work_location_id=work_location_id,
        role=role.value if role else None,
        is_active=is_active,
        missing_documents=missing_documents,
        registration=registration,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return Page(items=[UserListItem(**row) for row in rows], total=total, page=page, page_size=page_size)


@router.get("/export", summary="Xuất danh sách CBNV (.xlsx)")
def export_users(
    event: ActiveEvent,
    db: DbSession,
    actor: AdminUser,
    request: Request,
    include_sensitive: bool = Query(
        default=False, description="Kèm ngày sinh, số CCCD, địa chỉ — ghi nhật ký là file nhạy cảm"
    ),
) -> Response:
    content, filename = export_service.export_users(
        db, event=event, actor=actor, include_sensitive=include_sensitive,
        ip_address=get_client_ip(request),
    )
    return xlsx_response(content, filename)


@router.post("/import", response_model=UserImportResult, summary="Import danh sách CBNV từ Excel")
async def import_users(
    db: DbSession,
    actor: AdminUser,
    request: Request,
    file: UploadFile = File(...),
    dry_run: bool = Query(default=True, description="true = chỉ kiểm tra, không ghi"),
) -> UserImportResult:
    """Cột bắt buộc: Mã NV, Họ tên, Email. Còn lỗi thì không ghi dòng nào. Ô trống giữ nguyên dữ liệu cũ."""
    content = await file.read()
    result = user_import_service.import_users(
        db, content=content, actor=actor, dry_run=dry_run, ip_address=get_client_ip(request)
    )
    return UserImportResult(**result)


@router.post(
    "",
    response_model=UserCredentialsOut,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo tài khoản CBNV (trả mật khẩu tạm một lần)",
)
def create_user(
    payload: UserCreate, db: DbSession, actor: AdminUser, request: Request
) -> UserCredentialsOut:
    user, password = user_admin_service.create_user(
        db, data=payload.model_dump(), actor=actor, ip_address=get_client_ip(request)
    )
    return UserCredentialsOut(user=UserAdmin.model_validate(user), temporary_password=password)


@router.get("/{user_id}", response_model=UserAdmin, summary="Hồ sơ đầy đủ của một CBNV")
def get_user(user_id: int, db: DbSession) -> UserAdmin:
    return UserAdmin.model_validate(user_admin_service.get_user(db, user_id))


@router.patch("/{user_id}", response_model=UserAdmin, summary="Sửa hồ sơ CBNV")
def update_user(
    user_id: int, payload: UserAdminUpdate, db: DbSession, actor: AdminUser, request: Request
) -> UserAdmin:
    user = user_admin_service.get_user(db, user_id)
    updated = user_admin_service.update_user(
        db,
        user=user,
        data=payload.model_dump(exclude_unset=True),
        actor=actor,
        ip_address=get_client_ip(request),
    )
    return UserAdmin.model_validate(updated)


@router.patch("/{user_id}/role", response_model=UserAdmin, summary="Đổi vai trò (chỉ super admin)")
def change_role(
    user_id: int, payload: UserRoleUpdate, db: DbSession, actor: SuperAdminUser, request: Request
) -> UserAdmin:
    user = user_admin_service.get_user(db, user_id)
    updated = user_admin_service.change_role(
        db,
        user=user,
        role=payload.role,
        actor=actor,
        reason=payload.reason,
        ip_address=get_client_ip(request),
    )
    return UserAdmin.model_validate(updated)


@router.patch("/{user_id}/status", response_model=UserAdmin, summary="Khoá / mở tài khoản")
def set_status(
    user_id: int, payload: UserStatusUpdate, db: DbSession, actor: AdminUser, request: Request
) -> UserAdmin:
    user = user_admin_service.get_user(db, user_id)
    updated = user_admin_service.set_status(
        db,
        user=user,
        is_active=payload.is_active,
        reason=payload.reason,
        actor=actor,
        ip_address=get_client_ip(request),
    )
    return UserAdmin.model_validate(updated)


@router.post(
    "/{user_id}/reset-password",
    response_model=PasswordResetOut,
    summary="Đặt lại mật khẩu (trả mật khẩu tạm một lần)",
)
def reset_password(user_id: int, db: DbSession, actor: AdminUser, request: Request) -> PasswordResetOut:
    user = user_admin_service.get_user(db, user_id)
    password, revoked = user_admin_service.reset_password(
        db, user=user, actor=actor, ip_address=get_client_ip(request)
    )
    return PasswordResetOut(temporary_password=password, sessions_revoked=revoked)


@router.post("/{user_id}/unlock", response_model=UserAdmin, summary="Gỡ khoá đăng nhập tạm")
def unlock(user_id: int, db: DbSession, actor: AdminUser, request: Request) -> UserAdmin:
    user = user_admin_service.get_user(db, user_id)
    return UserAdmin.model_validate(
        user_admin_service.unlock(db, user=user, actor=actor, ip_address=get_client_ip(request))
    )
