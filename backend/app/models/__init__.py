"""Gom toàn bộ ORM model.

Alembic autogenerate chỉ thấy bảng nào đã được import ở đây — thêm model mới
mà quên import thì migration sẽ lặng lẽ bỏ sót bảng đó.
"""

from app.models.accommodation import Hotel, Room, RoomAssignment
from app.models.audit import AuditLog
from app.models.base import Base, TimestampMixin, utcnow_iso
from app.models.chat import ChatMessage, ChatSession
from app.models.content import Announcement, ItineraryItem, PolicyDocument
from app.models.event import DEFAULT_EVENT_SETTINGS, Event, EventSetting
from app.models.flight import Flight, FlightAssignment, Shift
from app.models.gala import (
    GalaDrawOrder,
    GalaLayout,
    GalaSeat,
    GalaSeatAssignment,
    GalaSeatHold,
    GalaTable,
)
from app.models.notification import EmailLog
from app.models.org import Department, Team, WorkLocation
from app.models.registration import Consent, Registration, RegistrationBusNeed
from app.models.transportation import Bus, BusAssignment, PickupPoint, TripLeg
from app.models.user import User

__all__ = [
    "DEFAULT_EVENT_SETTINGS",
    "Announcement",
    "AuditLog",
    "Base",
    "Bus",
    "BusAssignment",
    "ChatMessage",
    "ChatSession",
    "Consent",
    "Department",
    "EmailLog",
    "Event",
    "EventSetting",
    "Flight",
    "FlightAssignment",
    "GalaDrawOrder",
    "GalaLayout",
    "GalaSeat",
    "GalaSeatAssignment",
    "GalaSeatHold",
    "GalaTable",
    "Hotel",
    "ItineraryItem",
    "PickupPoint",
    "PolicyDocument",
    "Registration",
    "RegistrationBusNeed",
    "Room",
    "RoomAssignment",
    "Shift",
    "Team",
    "TimestampMixin",
    "TripLeg",
    "User",
    "WorkLocation",
    "utcnow_iso",
]
