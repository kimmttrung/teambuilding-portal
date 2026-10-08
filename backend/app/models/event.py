"""Kỳ Team Building và cấu hình theo kỳ."""

from typing import TYPE_CHECKING

from sqlalchemy import JSON, CheckConstraint, String, Text
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import EventStatus, sql_in

if TYPE_CHECKING:
    from app.models.flight import Flight, Shift
    from app.models.registration import Registration
    from app.models.transportation import TripLeg


class Event(Base, TimestampMixin):
    """Một kỳ Team Building.

    Mọi dữ liệu nghiệp vụ đều gắn event_id để chạy được nhiều kỳ trên cùng hệ thống
    mà không phải xoá dữ liệu cũ (docs/01-requirements.md §5 - Configurable).
    """

    __tablename__ = "events"
    __table_args__ = (CheckConstraint(f"status IN {sql_in(EventStatus)}", name="status_valid"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    destination: Mapped[str | None] = mapped_column(String(255))
    start_date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    end_date: Mapped[str] = mapped_column(String(10), nullable=False)

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=EventStatus.DRAFT, index=True
    )
    registration_opens_at: Mapped[str | None] = mapped_column(String(32))
    registration_closes_at: Mapped[str | None] = mapped_column(String(32))

    # Bằng chứng đồng ý nằm trên registrations; lịch sử nằm trong audit_logs.
    terms_version: Mapped[str] = mapped_column(String(16), nullable=False, default="v1")
    terms_content: Mapped[str | None] = mapped_column(Text)

    # Chỉ một event được active tại một thời điểm (kiểm tra ở service layer).
    is_active: Mapped[bool] = mapped_column(default=False, nullable=False, index=True)

    settings: Mapped[dict] = mapped_column(
        MutableDict.as_mutable(JSON), nullable=False, default=dict, server_default="{}"
    )
    shifts: Mapped[list["Shift"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    trip_legs: Mapped[list["TripLeg"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    flights: Mapped[list["Flight"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    registrations: Mapped[list["Registration"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )

    @property
    def status_enum(self) -> EventStatus:
        return EventStatus(self.status)

    def __repr__(self) -> str:
        return f"<Event {self.code} ({self.status})>"


# Giá trị mặc định khi tạo event mới. Đổi được qua API mà không cần sửa code.
DEFAULT_EVENT_SETTINGS: dict[str, tuple[str, str]] = {
    "allocation.team_weight": ("10", "Điểm thưởng khi giữ người cùng team trên một chuyến"),
    "allocation.shift_weight": ("6", "Điểm thưởng khi đáp ứng đúng ca nguyện vọng"),
    "allocation.split_penalty": ("25", "Điểm phạt mỗi lần một team bị tách thêm một mảnh"),
    "allocation.max_split_per_team": ("2", "Số mảnh tối đa một team bị tách"),
    "allocation.min_chunk_size": ("3", "Mảnh cắt vì hết ghế không nên nhỏ hơn số này"),
    "allocation.fit_weight": (
        "10",
        "Điểm thưởng tối đa khi xếp vừa khít một chuyến (tính theo tỉ lệ ghế còn trống)",
    ),
    "allocation.shift_split_percent": (
        "30",
        "Không còn giữ người ở sai ca khi chuyến đúng ca còn ghế. Giá trị này không chặn việc đó.",
    ),
    "rooms.team_weight": ("10", "Điểm thưởng mỗi cặp cùng team ở chung phòng"),
    "rooms.flight_weight": ("4", "Điểm thưởng mỗi cặp cùng chuyến bay chiều đi ở chung phòng"),
    "rooms.department_weight": ("1", "Điểm thưởng mỗi cặp cùng phòng ban ở chung phòng"),
    "transport.to_airport_buffer_minutes": (
        "30",
        "Xe ra sân bay phải xuất phát trước giờ cất cánh ít nhất ngần này phút "
        "(đi đường + làm thủ tục)",
    ),
    "transport.from_airport_late_minutes": (
        "5",
        "Xe đón ở sân bay được phép tới muộn nhiều nhất ngần này phút so với giờ hạ cánh "
        "(tới sớm rồi chờ thì luôn được)",
    ),
    "transport.from_airport_min_wait_minutes": (
        "30",
        "Xe đón chỉ rời sân bay sau giờ hạ cánh ít nhất ngần này phút (khách xuống máy bay, "
        "lấy hành lý)",
    ),
    "transport.from_airport_max_wait_minutes": (
        "45",
        "Xe đón không chờ quá ngần này phút sau giờ hạ cánh; ai ra muộn hơn phải tự lo "
        "(0 = không giới hạn)",
    ),
    "transport.self_transport_lead_minutes": (
        "90",
        "Người KHÔNG đi xe của BTC cần có mặt ở sân bay trước giờ bay ngần này phút "
        "(chỉ dùng để nhắc trong lịch trình)",
    ),
    "gala.hold_seconds": ("120", "Thời gian giữ ghế tạm trước khi xác nhận"),
    "gala.turn_seconds": ("300", "Thời gian mỗi lượt chọn ghế của một team"),
}


def default_settings() -> dict:
    """Cấu hình mặc định của một kỳ, đã parse sẵn như cột `events.settings` lưu."""
    import json

    return {key: json.loads(value) for key, (value, _description) in DEFAULT_EVENT_SETTINGS.items()}
