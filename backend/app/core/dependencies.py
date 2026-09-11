"""FastAPI dependency dùng chung: lấy session, lấy user hiện tại, kiểm tra quyền.

Ba lớp phân quyền (docs/09-security.md §2):
    1. require_role(...)          — chặn theo vai trò
    2. ownership                  — endpoint tự kiểm tra dữ liệu có phải của mình không
    3. require_event_status(...)  — chặn theo trạng thái chương trình
"""

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import (
    InvalidEventStatusError,
    NotFoundError,
    PermissionDeniedError,
    UnauthorizedError,
)
from app.core.security import TOKEN_TYPE_ACCESS, decode_token
from app.models.enums import ADMIN_ROLES, EventStatus, UserRole
from app.models.event import Event
from app.models.user import User

# auto_error=False để tự ném lỗi đúng khuôn {"error": {...}} thay vì khuôn của Starlette.
bearer_scheme = HTTPBearer(auto_error=False, description="Dán access token vào đây")

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: DbSession,
) -> User:
    """Giải mã access token và nạp user tương ứng."""
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("Chưa đăng nhập.", code="NOT_AUTHENTICATED")

    payload = decode_token(credentials.credentials, expected_type=TOKEN_TYPE_ACCESS)
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise UnauthorizedError("Token thiếu thông tin người dùng.", code="TOKEN_INVALID") from exc

    user = db.get(User, user_id)
    if user is None:
        raise UnauthorizedError("Tài khoản không tồn tại.", code="ACCOUNT_NOT_FOUND")
    if not user.is_active:
        raise UnauthorizedError("Tài khoản đã bị vô hiệu hoá.", code="ACCOUNT_DISABLED")

    # Role trong token có thể cũ hơn thực tế nếu admin vừa đổi quyền; luôn tin database.
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: UserRole | str):
    """Dependency chặn theo vai trò.

    Dùng: `dependencies=[Depends(require_role(UserRole.ADMIN, UserRole.SUPER_ADMIN))]`
    """
    allowed = {str(role) for role in roles}

    def _check(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise PermissionDeniedError(
                "Bạn không có quyền thực hiện thao tác này.",
                details={"required_roles": sorted(allowed), "your_role": user.role},
            )
        return user

    return _check


require_admin = require_role(UserRole.ADMIN, UserRole.SUPER_ADMIN)
require_super_admin = require_role(UserRole.SUPER_ADMIN)
require_team_leader = require_role(UserRole.TEAM_LEADER, UserRole.ADMIN, UserRole.SUPER_ADMIN)

AdminUser = Annotated[User, Depends(require_admin)]
SuperAdminUser = Annotated[User, Depends(require_super_admin)]


def ensure_can_access_user(current_user: User, target_user_id: int) -> None:
    """Lớp 2: chặn IDOR.

    Gọi hàm này ở MỌI endpoint nhận user_id từ client. Thiếu một chỗ là CBNV xem
    được hồ sơ người khác chỉ bằng cách đổi số trên URL.
    """
    if current_user.id != target_user_id and current_user.role not in ADMIN_ROLES:
        raise PermissionDeniedError("Bạn chỉ xem được dữ liệu của chính mình.")


def get_active_event(db: DbSession) -> Event:
    """Kỳ Team Building đang hoạt động."""
    event = db.scalar(select(Event).where(Event.is_active.is_(True)))
    if event is None:
        raise NotFoundError(
            "Chưa có kỳ Team Building nào đang mở.", code="NO_ACTIVE_EVENT"
        )
    return event


ActiveEvent = Annotated[Event, Depends(get_active_event)]


def require_event_status(*statuses: EventStatus | str):
    """Lớp 3: chặn theo trạng thái chương trình.

    Ví dụ: nộp đăng ký chỉ hợp lệ khi event đang `registration_open`.
    """
    allowed = {str(status) for status in statuses}

    def _check(event: ActiveEvent) -> Event:
        if event.status not in allowed:
            raise InvalidEventStatusError(
                _status_message(event.status, allowed),
                details={"current_status": event.status, "required": sorted(allowed)},
            )
        return event

    return _check


def require_published_event(event: ActiveEvent) -> Event:
    """Thông tin phân bổ chỉ được xem sau khi BTC công bố."""
    if not EventStatus(event.status).at_least(EventStatus.INFORMATION_PUBLISHED):
        raise InvalidEventStatusError(
            "BTC chưa công bố thông tin phân bổ.",
            code="NOT_PUBLISHED",
            details={"current_status": event.status},
        )
    return event


def get_client_ip(request: Request) -> str | None:
    """IP client, có tính tới reverse proxy (nginx đặt X-Forwarded-For)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def _status_message(current: str, allowed: set[str]) -> str:
    if EventStatus.REGISTRATION_OPEN in allowed:
        return (
            "Thời gian đăng ký đã đóng."
            if current != EventStatus.DRAFT
            else "Chương trình chưa mở đăng ký."
        )
    return "Thao tác này không thực hiện được ở trạng thái hiện tại của chương trình."
