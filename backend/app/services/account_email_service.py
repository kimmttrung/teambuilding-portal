"""Xếp thư tài khoản trong cùng transaction; mật khẩu chỉ tồn tại trong job gửi thư."""

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from app.services import email_service


def enqueue_credentials(db: Session, *, user: User, password: str, reset: bool = False) -> dict:
    context = {
        "full_name": user.full_name,
        "email": user.email,
        "temporary_password": password,
        "login_url": f"{settings.APP_PUBLIC_URL.rstrip('/')}/login",
        "reset": reset,
    }
    entry = email_service.enqueue(
        db,
        template="account_password_reset" if reset else "account_created",
        to_email=user.email,
        user_id=user.id,
        context=context,
        related_type="user",
        related_id=user.id,
    )
    db.flush()
    return {"log_id": entry.id, "context": context}
