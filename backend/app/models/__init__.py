"""Gom toàn bộ 27 bảng ORM của schema v2.

Khởi tạo DB mới từ Base.metadata, không chạy migration v1 lên schema v2.
Backend v1 cần refactor riêng; không giữ model giả cho những bảng đã bỏ.
"""

from app.models.accommodation import Hotel, Room
from app.models.audit import AuditLog
from app.models.auth import LoginAttempt, RefreshToken
from app.models.base import Base, TimestampMixin, utcnow_iso
from app.models.chat import ChatMessage
from app.models.content import Content, ItineraryItem
from app.models.event import DEFAULT_EVENT_SETTINGS, Event
from app.models.flight import Flight, FlightAssignment, Shift
from app.models.gala import (
    GalaDrawOrder,
    GalaLayout,
    GalaSeat,
    GalaTable,
)
from app.models.notification import EmailLog
from app.models.org import Department, Team, WorkLocation
from app.models.registration import (
    Registration,
    RegistrationCancellation,
    RegistrationLeg,
)
from app.models.transportation import Bus, PickupPoint, TripLeg
from app.models.user import User

__all__ = [
    "DEFAULT_EVENT_SETTINGS",
    "AuditLog",
    "Base",
    "RefreshToken",
    "Bus",
    "ChatMessage",
    "Content",
    "Department",
    "EmailLog",
    "Event",
    "Flight",
    "FlightAssignment",
    "GalaDrawOrder",
    "GalaLayout",
    "GalaSeat",
    "GalaTable",
    "Hotel",
    "ItineraryItem",
    "LoginAttempt",
    "PickupPoint",
    "Registration",
    "RegistrationLeg",
    "RegistrationCancellation",
    "Room",
    "Shift",
    "Team",
    "TimestampMixin",
    "TripLeg",
    "User",
    "WorkLocation",
    "utcnow_iso",
]
