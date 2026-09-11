"""Tiện ích thời gian.

Quy ước toàn hệ thống: lưu UTC dạng ISO-8601 (`2026-09-11T14:30:00+00:00`),
chỉ đổi sang Asia/Ho_Chi_Minh khi hiển thị ở frontend.

Chuỗi ISO cùng định dạng so sánh được bằng toán tử chuỗi, nhưng dùng hàm ở đây
để ý định rõ ràng và tránh so sánh nhầm chuỗi khác offset.
"""

from datetime import UTC, datetime, timedelta

ISO_FORMAT_NOTE = "UTC ISO-8601, giây làm tròn"


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


def is_expired(value: str | None) -> bool:
    """True nếu mốc thời gian đã qua. None coi như chưa hết hạn (không đặt hạn)."""
    if not value:
        return False
    return from_iso(value) <= utcnow()
