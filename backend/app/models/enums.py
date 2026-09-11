"""Các giá trị enum dùng trong DB.

Lưu dạng TEXT trong SQLite (SQLite không có kiểu ENUM). Dùng StrEnum để so sánh
được như chuỗi bình thường: `registration.status == RegistrationStatus.SUBMITTED`.
"""

from enum import StrEnum


class EventStatus(StrEnum):
    """Vòng đời một kỳ Team Building. Xem docs/01-requirements.md §3."""

    DRAFT = "draft"
    REGISTRATION_OPEN = "registration_open"
    REGISTRATION_CLOSED = "registration_closed"
    ALLOCATION_PROCESSING = "allocation_processing"
    INFORMATION_PUBLISHED = "information_published"
    EVENT_STARTED = "event_started"
    COMPLETED = "completed"

    @property
    def order(self) -> int:
        return _EVENT_STATUS_ORDER[self]

    def at_least(self, other: "EventStatus") -> bool:
        """True nếu trạng thái này bằng hoặc sau `other` trong vòng đời.

        Dùng cho quy tắc "My Journey chỉ hiển thị từ information_published trở đi".
        """
        return self.order >= other.order


_EVENT_STATUS_ORDER = {status: index for index, status in enumerate(EventStatus)}


class UserRole(StrEnum):
    EMPLOYEE = "employee"
    TEAM_LEADER = "team_leader"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


ADMIN_ROLES = frozenset({UserRole.ADMIN, UserRole.SUPER_ADMIN})


class Gender(StrEnum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class RegistrationStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    CANCELLED = "cancelled"


class FlightDirection(StrEnum):
    OUTBOUND = "outbound"  # chiều đi
    RETURN = "return"  # chiều về


class AssignmentMode(StrEnum):
    """Ai tạo bản ghi phân bổ này.

    MANUAL được auto allocation tôn trọng, không ghi đè (trừ khi force_reallocate).
    """

    AUTO = "auto"
    MANUAL = "manual"


class RoomGenderPolicy(StrEnum):
    ANY = "any"
    MALE = "male"
    FEMALE = "female"


class GalaSelectionStatus(StrEnum):
    CLOSED = "closed"
    DRAWING = "drawing"  # đang bốc thăm thứ tự
    OPEN = "open"  # đang cho các team chọn ghế
    FINALIZED = "finalized"


class DrawStatus(StrEnum):
    WAITING = "waiting"
    ACTIVE = "active"
    DONE = "done"
    SKIPPED = "skipped"


class AnnouncementSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    URGENT = "urgent"


class AnnouncementTarget(StrEnum):
    ALL = "all"
    TEAM = "team"
    FLIGHT = "flight"
    BUS = "bus"
    USER = "user"


class EmailStatus(StrEnum):
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"


class PolicyDocType(StrEnum):
    TERMS = "terms"
    FAQ = "faq"
    GUIDE = "guide"
    ITINERARY = "itinerary"


class ChatRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


def values(enum_cls: type[StrEnum]) -> tuple[str, ...]:
    """Danh sách giá trị của enum."""
    return tuple(member.value for member in enum_cls)


def sql_in(enum_cls: type[StrEnum]) -> str:
    """Sinh mệnh đề IN cho CHECK constraint: "('draft', 'completed')".

    Không dùng repr(tuple) vì tuple 1 phần tử sẽ có dấu phẩy thừa -> SQL lỗi.
    """
    return "(" + ", ".join(f"'{member.value}'" for member in enum_cls) + ")"
