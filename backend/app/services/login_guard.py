"""Rate limit đăng nhập theo IP (docs/09-security.md §5).

Vì sao cần, khi đã khoá theo tài khoản:
- Khoá theo tài khoản không chặn được kẻ rải **4 lần sai cho hàng trăm email** từ một IP —
  không tài khoản nào chạm ngưỡng nhưng danh sách mật khẩu yếu vẫn bị quét hết.
- Ngược lại, khoá theo tài khoản mà ngưỡng thấp thì ai biết email người khác là khoá được
  tài khoản người đó. Hai lớp bù cho nhau: lớp IP chặn trước, lớp tài khoản ngưỡng cao hơn.

Trạng thái nằm ở bảng `login_attempts` chứ không phải bộ nhớ tiến trình: uvicorn chạy nhiều
worker và container khởi động lại thường xuyên.

`check()` chạy **trước** khi so mật khẩu — kẻ dò không ép được server tính bcrypt (~100ms/lần).
"""

import logging

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.security import (
    ATTEMPT_RETENTION_HOURS,
    ATTEMPT_WINDOW_MINUTES,
    MAX_FAILED_PER_EMAIL_IP,
    MAX_FAILED_PER_IP,
)
from app.core.timeutils import from_iso, iso_in, utcnow, utcnow_iso
from app.models.auth import LoginAttempt

logger = logging.getLogger(__name__)

# Không xác định được IP (gọi thẳng, test, health check nội bộ) vẫn phải đếm — bỏ qua là
# tự chừa một cửa không giới hạn.
UNKNOWN_IP = "unknown"


class TooManyAttemptsError(AppError):
    """429. Cố ý KHÔNG nói đã sai bao nhiêu lần với email nào — đó cũng là thông tin."""

    status_code = 429
    code = "TOO_MANY_ATTEMPTS"


def normalize_email(email: str) -> str:
    return email.strip().lower()


def normalize_ip(ip_address: str | None) -> str:
    return (ip_address or "").strip()[:64] or UNKNOWN_IP


def check(db: Session, *, email: str, ip_address: str | None) -> None:
    """Chặn trước khi so mật khẩu. Ném TooManyAttemptsError nếu vượt ngưỡng."""
    email = normalize_email(email)
    ip = normalize_ip(ip_address)
    since = _window_start()

    per_email_ip, per_ip = _count_failures(db, email=email, ip=ip, since=since)

    if per_email_ip >= MAX_FAILED_PER_EMAIL_IP:
        logger.warning("Chặn đăng nhập: %s từ %s sai %d lần gần đây", email, ip, per_email_ip)
        raise _too_many(db, email=email, ip=ip, since=since)

    if per_ip >= MAX_FAILED_PER_IP:
        logger.warning("Chặn đăng nhập: IP %s sai %d lần với nhiều email", ip, per_ip)
        raise _too_many(db, email=None, ip=ip, since=since)


def record(db: Session, *, email: str, ip_address: str | None, succeeded: bool) -> None:
    """Ghi một lần thử. KHÔNG commit — chỗ gọi quyết định thời điểm commit.

    Mọi nhánh thất bại của `auth_service.login` phải commit sau khi gọi hàm này, nếu không
    session bị đóng mà chưa ghi thì bộ đếm đứng yên.
    """
    db.add(
        LoginAttempt(
            email=normalize_email(email),
            ip_address=normalize_ip(ip_address),
            succeeded=succeeded,
            attempted_at=utcnow_iso(),
        )
    )
    _purge_old(db)


def clear(db: Session, *, email: str) -> None:
    """Xoá bộ đếm của một email: đăng nhập thành công, BTC gỡ khoá, BTC đặt lại mật khẩu.

    KHÔNG commit. Xoá theo email (mọi IP) chứ không riêng IP đang dùng: người dùng thật
    vừa chứng minh được mình là chủ tài khoản thì không có lý do phạt các IP khác của họ.
    """
    db.execute(delete(LoginAttempt).where(LoginAttempt.email == normalize_email(email)))


# --- Nội bộ ---


def _window_start() -> str:
    return iso_in(minutes=-ATTEMPT_WINDOW_MINUTES)


def _count_failures(db: Session, *, email: str, ip: str, since: str) -> tuple[int, int]:
    """(số lần sai của email này từ IP này, số lần sai của IP này với mọi email)."""
    base = (
        select(func.count(LoginAttempt.id))
        .where(LoginAttempt.ip_address == ip)
        .where(LoginAttempt.succeeded.is_(False))
        .where(LoginAttempt.attempted_at >= since)
    )
    per_ip = db.scalar(base) or 0
    per_email_ip = db.scalar(base.where(LoginAttempt.email == email)) or 0
    return per_email_ip, per_ip


def _too_many(db: Session, *, email: str | None, ip: str, since: str) -> TooManyAttemptsError:
    """Dựng lỗi kèm số giây còn phải chờ, tính từ lần sai cũ nhất còn trong cửa sổ."""
    query = (
        select(func.min(LoginAttempt.attempted_at))
        .where(LoginAttempt.ip_address == ip)
        .where(LoginAttempt.succeeded.is_(False))
        .where(LoginAttempt.attempted_at >= since)
    )
    if email is not None:
        query = query.where(LoginAttempt.email == email)

    retry_after = _seconds_until_window_clears(db.scalar(query))
    minutes = max(1, -(-retry_after // 60))  # làm tròn lên, không bao giờ nói "0 phút"
    return TooManyAttemptsError(
        f"Đã nhập sai quá nhiều lần. Vui lòng chờ khoảng {minutes} phút rồi thử lại.",
        details={"retry_after_seconds": retry_after},
    )


def _seconds_until_window_clears(oldest_attempt: str | None) -> int:
    if not oldest_attempt:
        return ATTEMPT_WINDOW_MINUTES * 60
    expires_at = from_iso(oldest_attempt).timestamp() + ATTEMPT_WINDOW_MINUTES * 60
    return max(1, int(expires_at - utcnow().timestamp()))


def _purge_old(db: Session) -> None:
    """DELETE có index trên `attempted_at` nên rẻ; chạy mỗi lần ghi là đủ, khỏi job nền."""
    cutoff = iso_in(hours=-ATTEMPT_RETENTION_HOURS)
    db.execute(delete(LoginAttempt).where(LoginAttempt.attempted_at < cutoff))
