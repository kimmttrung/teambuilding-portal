"""Endpoint xác thực và hồ sơ cá nhân."""

import secrets
from pathlib import Path

from fastapi import APIRouter, File, Request, UploadFile, status

from app.core.config import settings
from app.core.dependencies import CurrentUser, DbSession, get_client_ip
from app.core.exceptions import AppError
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    RefreshResponse,
    TokenResponse,
)
from app.schemas.user import UserProfileUpdate, UserSelf
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

# Chữ ký đầu file (magic bytes). Không tin phần mở rộng hay Content-Type do client gửi.
IMAGE_SIGNATURES: dict[bytes, str] = {
    b"\xff\xd8\xff": ".jpg",
    b"\x89PNG\r\n\x1a\n": ".png",
    b"RIFF": ".webp",  # còn kiểm tra thêm "WEBP" ở byte 8-12
}


@router.post("/login", response_model=TokenResponse, summary="Đăng nhập")
def login(payload: LoginRequest, request: Request, db: DbSession) -> TokenResponse:
    user, tokens = auth_service.login(
        db,
        email=payload.email,
        password=payload.password,
        user_agent=request.headers.get("user-agent"),
        ip_address=get_client_ip(request),
    )
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
        user=_to_self_schema(user),
    )


@router.post("/refresh", response_model=RefreshResponse, summary="Làm mới access token")
def refresh(payload: RefreshRequest, request: Request, db: DbSession) -> RefreshResponse:
    tokens = auth_service.refresh_tokens(
        db,
        refresh_token=payload.refresh_token,
        user_agent=request.headers.get("user-agent"),
        ip_address=get_client_ip(request),
    )
    return RefreshResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
    )


@router.post("/logout", response_model=MessageResponse, summary="Đăng xuất")
def logout(payload: LogoutRequest, user: CurrentUser, db: DbSession) -> MessageResponse:
    count = auth_service.logout(
        db, user=user, refresh_token=payload.refresh_token, all_devices=payload.all_devices
    )
    return MessageResponse(message=f"Đã đăng xuất {count} phiên.")


@router.get("/me", response_model=UserSelf, summary="Hồ sơ của tôi")
def me(user: CurrentUser) -> UserSelf:
    return _to_self_schema(user)


@router.patch("/me", response_model=UserSelf, summary="Cập nhật hồ sơ của tôi")
def update_me(payload: UserProfileUpdate, user: CurrentUser, db: DbSession) -> UserSelf:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return _to_self_schema(user)


@router.post("/change-password", response_model=MessageResponse, summary="Đổi mật khẩu")
def change_password(
    payload: ChangePasswordRequest, user: CurrentUser, db: DbSession
) -> MessageResponse:
    auth_service.change_password(
        db,
        user=user,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    return MessageResponse(
        message="Đổi mật khẩu thành công. Mọi thiết bị khác đã bị đăng xuất."
    )


@router.post(
    "/me/avatar",
    response_model=UserSelf,
    status_code=status.HTTP_201_CREATED,
    summary="Tải ảnh đại diện",
)
async def upload_avatar(
    user: CurrentUser, db: DbSession, file: UploadFile = File(...)
) -> UserSelf:
    content = await file.read()
    extension = _validate_image(content)

    settings.upload_path.mkdir(parents=True, exist_ok=True)
    filename = f"avatar_{user.id}_{secrets.token_hex(6)}{extension}"
    (settings.upload_path / filename).write_bytes(content)

    _remove_old_avatar(user.avatar_url)
    user.avatar_url = f"/uploads/{filename}"
    db.commit()
    db.refresh(user)
    return _to_self_schema(user)


# --- Nội bộ ---


def _validate_image(content: bytes) -> str:
    """Kiểm tra kích thước và chữ ký file, trả về phần mở rộng an toàn."""
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if not content:
        raise AppError("File rỗng.", code="EMPTY_FILE")
    if len(content) > max_bytes:
        raise AppError(
            f"Ảnh vượt quá {settings.MAX_UPLOAD_MB}MB.",
            code="FILE_TOO_LARGE",
            details={"max_mb": settings.MAX_UPLOAD_MB, "actual_bytes": len(content)},
        )

    for signature, extension in IMAGE_SIGNATURES.items():
        if not content.startswith(signature):
            continue
        if extension == ".webp" and content[8:12] != b"WEBP":
            continue
        return extension

    raise AppError(
        "Chỉ chấp nhận ảnh JPG, PNG hoặc WEBP.",
        code="UNSUPPORTED_FILE_TYPE",
    )


def _remove_old_avatar(avatar_url: str | None) -> None:
    """Xoá ảnh cũ để thư mục upload không phình theo mỗi lần đổi ảnh."""
    if not avatar_url or not avatar_url.startswith("/uploads/"):
        return
    old_file = settings.upload_path / Path(avatar_url).name
    if old_file.is_file():
        old_file.unlink(missing_ok=True)


def _to_self_schema(user) -> UserSelf:
    data = UserSelf.model_validate(user)
    # can_fly là thuộc tính suy ra, không phải cột — gán thủ công sau khi validate.
    return data.model_copy(update={"can_fly": user.can_fly})
