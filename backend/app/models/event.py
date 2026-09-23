"""Kỳ Team Building và cấu hình theo kỳ."""

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, UniqueConstraint
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
    __table_args__ = (
        CheckConstraint(f"status IN {sql_in(EventStatus)}", name="status_valid"),
    )

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

    # Phiên bản quy định đang áp dụng; CBNV đồng ý version nào được lưu ở bảng consents.
    terms_version: Mapped[str] = mapped_column(String(16), nullable=False, default="v1")
    terms_content: Mapped[str | None] = mapped_column(Text)

    banner_url: Mapped[str | None] = mapped_column(String(512))
    # Chỉ một event được active tại một thời điểm (kiểm tra ở service layer).
    is_active: Mapped[bool] = mapped_column(default=False, nullable=False, index=True)

    settings: Mapped[list["EventSetting"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
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


class EventSetting(Base):
    """Cấu hình mềm dạng key/value cho từng kỳ.

    Ví dụ: allocation.team_weight, allocation.shift_weight, gala.hold_seconds.
    Giá trị lưu JSON string để chứa được cả số, chuỗi lẫn object.
    """

    __tablename__ = "event_settings"
    __table_args__ = (UniqueConstraint("event_id", "key", name="uq_event_settings_event_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))

    event: Mapped["Event"] = relationship(back_populates="settings")

    def __repr__(self) -> str:
        return f"<EventSetting {self.key}={self.value}>"


# Giá trị mặc định khi tạo event mới. Đổi được qua API mà không cần sửa code.
DEFAULT_EVENT_SETTINGS: dict[str, tuple[str, str]] = {
    "allocation.team_weight": ("10", "Điểm thưởng khi giữ người cùng team trên một chuyến"),
    "allocation.shift_weight": ("6", "Điểm thưởng khi đáp ứng đúng ca nguyện vọng"),
    "allocation.split_penalty": ("25", "Điểm phạt mỗi lần một team bị tách thêm một mảnh"),
    "allocation.max_split_per_team": ("2", "Số mảnh tối đa một team bị tách"),
    "allocation.min_chunk_size": ("3", "Mảnh tách ra không được nhỏ hơn số này"),
    "allocation.fit_weight": (
        "10",
        "Điểm thưởng tối đa khi xếp vừa khít một chuyến (tính theo tỉ lệ ghế còn trống)",
    ),
    "allocation.shift_split_percent": (
        "30",
        "Tách team theo ca khi phe thiểu số chiếm ít nhất ngần này phần trăm (0 = không tách)",
    ),
    "rooms.team_weight": ("10", "Điểm thưởng mỗi cặp cùng team ở chung phòng"),
    "rooms.flight_weight": ("4", "Điểm thưởng mỗi cặp cùng chuyến bay chiều đi ở chung phòng"),
    "rooms.department_weight": ("1", "Điểm thưởng mỗi cặp cùng phòng ban ở chung phòng"),
    "transport.to_airport_buffer_minutes": (
        "30",
        "Xe ra sân bay phải xuất phát trước giờ cất cánh ít nhất ngần này phút "
        "(đi đường + làm thủ tục)",
    ),
    "transport.from_airport_buffer_minutes": (
        "30",
        "Xe đón ở sân bay chỉ chạy sau giờ hạ cánh ít nhất ngần này phút (xuống máy bay + lấy hành lý)",
    ),
    "gala.hold_seconds": ("120", "Thời gian giữ ghế tạm trước khi xác nhận"),
    "gala.turn_seconds": ("300", "Thời gian mỗi lượt chọn ghế của một team"),
}