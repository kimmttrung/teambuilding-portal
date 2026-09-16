"""Nghiệp vụ xác thực: đăng nhập, làm mới token, đăng xuất, đổi mật khẩu.

Không import gì từ tầng api — nhận Session và tham số thuần, trả về object.
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ConflictError, UnauthorizedError
from app.core.security import (
    LOCKOUT_MINUTES,
    MAX_FAILED_LOGINS,
    TOKEN_TYPE_REFRESH,
    TokenPair,
    create_token_pair,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.core.timeutils import is_expired, iso_in, utcnow_iso
from app.models.auth import RefreshToken
from app.models.user import User
from app.services import login_guard

logger = logging.getLogger(__name__)

# Dùng chung một thông điệp cho "sai email" và "sai mật khẩu": nói rõ email nào
# tồn tại là tự tay đưa cho người dò danh sách tài khoản có thật.
_INVALID_CREDENTIALS = "Email hoặc mật khẩu không đúng."


class AccountLockedError(UnauthorizedError):
    code = "ACCOUNT_LOCKED"


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.strip().lower()))


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def login(
    db: Session,
    *,
    email: str,
    password: str,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> tuple[User, TokenPair]:
    """Xác thực và phát hành cặp token."""
    # Lớp IP chạy TRƯỚC mọi thứ khác: không tra DB user, không tính bcrypt cho kẻ đang dò.
    login_guard.check(db, email=email, ip_address=ip_address)

    user = get_user_by_email(db, email)

    if user is None:
        # Vẫn băm một chuỗi giả để thời gian phản hồi không tiết lộ email có tồn tại hay không.
        verify_password(password, "$2b$12$" + "x" * 53)
        _record_attempt(db, email=email, ip_address=ip_address, succeeded=False)
        raise UnauthorizedError(_INVALID_CREDENTIALS, code="INVALID_CREDENTIALS")

    if user.locked_until and not is_expired(user.locked_until):
        # Vẫn tính là một lần sai: gõ cửa tài khoản đang khoá cũng là dò.
        _record_attempt(db, email=email, ip_address=ip_address, succeeded=False)
        raise AccountLockedError(
            f"Tài khoản đang bị khoá tạm do nhập sai quá {MAX_FAILED_LOGINS} lần. "
            f"Vui lòng thử lại sau {LOCKOUT_MINUTES} phút hoặc liên hệ BTC.",
            details={"locked_until": user.locked_until},
        )

    if not verify_password(password, user.password_hash):
        login_guard.record(db, email=email, ip_address=ip_address, succeeded=False)
        _register_failed_login(db, user)  # commit luôn cho cả dòng login_attempts vừa thêm
        raise UnauthorizedError(_INVALID_CREDENTIALS, code="INVALID_CREDENTIALS")

    if not user.is_active:
        # Kiểm tra SAU mật khẩu: trả lời trước là lộ email nào có trong hệ thống.
        # Mật khẩu đúng nên không tính là lần sai, nhưng vẫn ghi lại để có dấu vết.
        _record_attempt(db, email=email, ip_address=ip_address, succeeded=True)
        raise UnauthorizedError(
            "Tài khoản đã bị vô hiệu hoá. Vui lòng liên hệ BTC.", code="ACCOUNT_DISABLED"
        )

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = utcnow_iso()
    # Xoá trước rồi mới ghi: `clear` xoá theo email nên gọi ngược lại sẽ nuốt luôn dòng vừa ghi.
    login_guard.clear(db, email=email)
    login_guard.record(db, email=email, ip_address=ip_address, succeeded=True)

    tokens = _issue_tokens(db, user, user_agent=user_agent, ip_address=ip_address)
    db.commit()
    logger.info("Đăng nhập thành công: %s", user.email)
    return user, tokens


def refresh_tokens(
    db: Session,
    *,
    refresh_token: str,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> TokenPair:
    """Đổi refresh token lấy cặp token mới, đồng thời xoay vòng refresh token.

    Xoay vòng (rotation): token cũ bị thu hồi ngay. Nếu ai đó lấy cắp token và dùng
    lại sau khi chủ thật đã refresh, lần dùng đó sẽ thất bại.
    """
    payload = decode_token(refresh_token, expected_type=TOKEN_TYPE_REFRESH)
    stored = db.scalar(select(RefreshToken).where(RefreshToken.jti == payload.get("jti")))

    if stored is None:
        raise UnauthorizedError("Phiên đăng nhập không tồn tại.", code="SESSION_NOT_FOUND")
    if stored.revoked_at is not None:
        raise UnauthorizedError(
            "Phiên đăng nhập đã bị thu hồi. Vui lòng đăng nhập lại.", code="SESSION_REVOKED"
        )
    if is_expired(stored.expires_at):
        raise UnauthorizedError("Phiên đăng nhập đã hết hạn.", code="SESSION_EXPIRED")
    if stored.token_hash != hash_token(refresh_token):
        raise UnauthorizedError("Token không khớp.", code="TOKEN_INVALID")

    user = get_user_by_id(db, stored.user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("Tài khoản không còn hiệu lực.", code="ACCOUNT_DISABLED")

    _revoke(stored, reason="rotated")
    tokens = _issue_tokens(db, user, user_agent=user_agent, ip_address=ip_address)
    db.commit()
    return tokens


def logout(db: Session, *, user: User, refresh_token: str | None, all_devices: bool) -> int:
    """Thu hồi phiên. Trả về số phiên đã thu hồi."""
    query = select(RefreshToken).where(
        RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)
    )
    if not all_devices and refresh_token:
        try:
            payload = decode_token(refresh_token, expected_type=TOKEN_TYPE_REFRESH)
        except UnauthorizedError:
            return 0
        query = query.where(RefreshToken.jti == payload.get("jti"))

    sessions = list(db.scalars(query))
    for session in sessions:
        _revoke(session, reason="logout")
    db.commit()
    return len(sessions)


def change_password(db: Session, *, user: User, current_password: str, new_password: str) -> None:
    """Đổi mật khẩu và thu hồi toàn bộ phiên đang mở."""
    if not verify_password(current_password, user.password_hash):
        raise UnauthorizedError("Mật khẩu hiện tại không đúng.", code="INVALID_CREDENTIALS")
    if verify_password(new_password, user.password_hash):
        raise ConflictError(
            "Mật khẩu mới phải khác mật khẩu hiện tại.", code="PASSWORD_UNCHANGED"
        )

    try:
        user.password_hash = hash_password(new_password)
    except ValueError as exc:
        raise AppError(str(exc), code="PASSWORD_TOO_LONG") from exc

    user.must_change_password = False
    revoke_all_sessions(db, user_id=user.id, reason="password_changed")
    db.commit()
    logger.info("Đổi mật khẩu: %s", user.email)


def revoke_all_sessions(db: Session, *, user_id: int, reason: str) -> int:
    """Thu hồi mọi phiên của một người (đổi mật khẩu, admin khoá tài khoản)."""
    sessions = list(
        db.scalars(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
            )
        )
    )
    for session in sessions:
        _revoke(session, reason=reason)
    return len(sessions)


def purge_expired_sessions(db: Session) -> int:
    """Xoá phiên đã hết hạn để bảng không phình vô hạn."""
    expired = [
        session
        for session in db.scalars(select(RefreshToken))
        if is_expired(session.expires_at)
    ]
    for session in expired:
        db.delete(session)
    db.commit()
    return len(expired)


# --- Nội bộ ---


def _record_attempt(db: Session, *, email: str, ip_address: str | None, succeeded: bool) -> None:
    """Ghi lần thử rồi commit ngay — nhánh gọi hàm này ném lỗi liền sau đó.

    Không commit thì session bị đóng lúc request kết thúc và dòng vừa thêm biến mất,
    tức bộ đếm chống dò mật khẩu đứng yên.
    """
    login_guard.record(db, email=email, ip_address=ip_address, succeeded=succeeded)
    db.commit()


def _issue_tokens(
    db: Session, user: User, *, user_agent: str | None, ip_address: str | None
) -> TokenPair:
    tokens = create_token_pair(user.id, user.role)
    db.add(
        RefreshToken(
            user_id=user.id,
            jti=tokens.refresh_jti,
            token_hash=hash_token(tokens.refresh_token),
            issued_at=utcnow_iso(),
            expires_at=tokens.refresh_expires_at,
            user_agent=(user_agent or "")[:255] or None,
            ip_address=ip_address,
        )
    )
    return tokens


def _revoke(session: RefreshToken, *, reason: str) -> None:
    session.revoked_at = utcnow_iso()
    session.revoked_reason = reason


def _register_failed_login(db: Session, user: User) -> None:
    user.failed_login_count += 1
    if user.failed_login_count >= MAX_FAILED_LOGINS:
        user.locked_until = iso_in(minutes=LOCKOUT_MINUTES)
        logger.warning(
            "Khoá tạm tài khoản %s sau %d lần đăng nhập sai",
            user.email,
            user.failed_login_count,
        )
    db.commit()
