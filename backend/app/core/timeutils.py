"""Tiện ích thời gian.

Quy ước toàn hệ thống: lưu UTC dạng ISO-8601 (`2026-09-11T14:30:00+00:00`),
chỉ đổi sang Asia/Ho_Chi_Minh khi hiển thị ở frontend.

Chuỗi ISO cùng định dạng so sánh được bằng toán tử chuỗi, nhưng dùng hàm ở đây
để ý định rõ ràng và tránh so sánh nhầm chuỗi khác offset.
"""

from datetime import UTC, datetime, timedelta, timezone

ISO_FORMAT_NOTE = "UTC ISO-8601, giây làm tròn"

# Việt Nam không có giờ mùa hè nên offset cố định +07:00 là chính xác tuyệt đối.
# Dùng offset thay vì ZoneInfo("Asia/Ho_Chi_Minh") để không phụ thuộc gói tzdata —
# Windows và image python-slim đều có thể thiếu cơ sở dữ liệu múi giờ IANA.
VN_TZ = timezone(timedelta(hours=7), name="Asia/Ho_Chi_Minh")


def utcnow() -> datetime:
    return datetime.now(UTC)


def to_iso(moment: datetime) -> str:
    """datetime -> chuỗi ISO UTC. Datetime naive được coi là UTC."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC).isoformat(timespec="seconds")


def utcnow_iso() -> str:
    return to_iso(utcnow())


def iso_in(*, seconds: int = 0, minutes: int = 0, hours: int = 0, days: int = 0) -> str:
    """Mốc thời gian tương lai dạng ISO. Dùng cho hạn token, hạn giữ ghế Gala."""
    return to_iso(utcnow() + timedelta(seconds=seconds, minutes=minutes, hours=hours, days=days))


def from_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def to_vn(value: str | datetime) -> datetime:
    """Chuỗi ISO (hoặc datetime) -> datetime theo giờ Việt Nam."""
    moment = from_iso(value) if isinstance(value, str) else value
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(VN_TZ)


def format_vn(value: str | datetime | None, *, with_time: bool = True) -> str:
    """Hiển thị cho người đọc (email, Excel, PDF): 15/10/2026 17:00.

    Backend lưu UTC; mọi thứ gửi ra ngoài cho CBNV đọc phải là giờ Việt Nam,
    nếu không họ đọc hạn đăng ký lệch 7 tiếng.
    """
    if not value:
        return "—"
    try:
        moment = to_vn(value)
    except ValueError:
        return str(value)
    return moment.strftime("%d/%m/%Y %H:%M") if with_time else moment.strftime("%d/%m/%Y")


def format_date_only(value: str | None) -> str:
    """Ngày dạng YYYY-MM-DD (cột date của DB) -> 15/10/2026, không đổi múi giờ."""
    if not value:
        return "—"
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return value


def is_expired(value: str | None) -> bool:
    """True nếu mốc thời gian đã qua. None coi như chưa hết hạn (không đặt hạn)."""
    if not value:
        return False
    return from_iso(value) <= utcnow()
