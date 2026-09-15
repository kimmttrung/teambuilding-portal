"""Đăng ký tham gia, nhu cầu xe theo chặng và bằng chứng đồng ý quy định."""

import json
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import CancellationMode, CancellationStatus, RegistrationStatus, sql_in

if TYPE_CHECKING:
    from app.models.accommodation import RoomAssignment
    from app.models.event import Event
    from app.models.flight import FlightAssignment, Shift
    from app.models.transportation import BusAssignment, PickupPoint, TripLeg
    from app.models.user import User


class Registration(Base, TimestampMixin):
    """Một CBNV đăng ký cho một kỳ Team Building.

    Đây là "hộ chiếu" của người đó trong kỳ: mọi bảng phân bổ đều trỏ về registration_id
    chứ không trỏ về user_id, để dữ liệu các kỳ không lẫn vào nhau.
    """

    __tablename__ = "registrations"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_registrations_event_user"),
        CheckConstraint(f"status IN {sql_in(RegistrationStatus)}", name="status_valid"),
        CheckConstraint("companion_count >= 0", name="companion_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    is_participating: Mapped[bool] = mapped_column(nullable=False)
    not_participating_reason: Mapped[str | None] = mapped_column(String(512))

    # Nguyện vọng ca, KHÔNG phải cam kết - thuật toán cố đáp ứng nhưng có thể lệch.
    shift_id: Mapped[int | None] = mapped_column(ForeignKey("shifts.id"), index=True)
    # BTC bật cờ này cho trường hợp bắt buộc đúng ca (ví dụ nhân sự trực giao dịch).
    is_shift_locked: Mapped[bool] = mapped_column(nullable=False, default=False)
    departure_location_id: Mapped[int | None] = mapped_column(ForeignKey("work_locations.id"))

    wish_note: Mapped[str | None] = mapped_column(Text)
    companion_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=RegistrationStatus.SUBMITTED, index=True
    )
    submitted_at: Mapped[str | None] = mapped_column(String(32))
    cancelled_at: Mapped[str | None] = mapped_column(String(32))
    cancel_reason: Mapped[str | None] = mapped_column(String(512))
    # Huỷ sau hạn đăng ký -> đánh dấu để BTC xử lý phí phạt theo quy định.
    penalty_applied: Mapped[bool] = mapped_column(nullable=False, default=False)

    event: Mapped["Event"] = relationship(back_populates="registrations")
    user: Mapped["User"] = relationship(back_populates="registrations")
    shift: Mapped["Shift | None"] = relationship()
    bus_needs: Mapped[list["RegistrationBusNeed"]] = relationship(
        back_populates="registration", cascade="all, delete-orphan"
    )
    flight_assignments: Mapped[list["FlightAssignment"]] = relationship(
        back_populates="registration", cascade="all, delete-orphan"
    )
    bus_assignments: Mapped[list["BusAssignment"]] = relationship(
        back_populates="registration", cascade="all, delete-orphan"
    )
    room_assignment: Mapped["RoomAssignment | None"] = relationship(
        back_populates="registration", cascade="all, delete-orphan", uselist=False
    )

    @property
    def is_active_participant(self) -> bool:
        """Chỉ người này mới được đưa vào thuật toán phân bổ."""
        return self.is_participating and self.status == RegistrationStatus.SUBMITTED

    def __repr__(self) -> str:
        return f"<Registration event={self.event_id} user={self.user_id}>"


class RegistrationBusNeed(Base):
    """Nhu cầu đi xe của một người cho MỘT chặng.

    Một dòng cho mỗi chặng thay vì 4 cột bus_1..bus_4, để thêm/bớt chặng chỉ là
    thêm/bớt dữ liệu (docs/00-review-of-draft.md §2.3).
    """

    __tablename__ = "registration_bus_needs"
    __table_args__ = (
        UniqueConstraint(
            "registration_id", "trip_leg_id", name="uq_bus_needs_registration_leg"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    registration_id: Mapped[int] = mapped_column(
        ForeignKey("registrations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trip_leg_id: Mapped[int] = mapped_column(
        ForeignKey("trip_legs.id"), nullable=False, index=True
    )
    needs_bus: Mapped[bool] = mapped_column(nullable=False, default=False)
    pickup_point_id: Mapped[int | None] = mapped_column(ForeignKey("pickup_points.id"))
    note: Mapped[str | None] = mapped_column(String(512))

    registration: Mapped["Registration"] = relationship(back_populates="bus_needs")
    trip_leg: Mapped["TripLeg"] = relationship()
    pickup_point: Mapped["PickupPoint | None"] = relationship()

    def __repr__(self) -> str:
        return f"<BusNeed reg={self.registration_id} leg={self.trip_leg_id} {self.needs_bus}>"


class Consent(Base):
    """Bằng chứng CBNV đã đọc và đồng ý quy định phiên bản nào, lúc nào.

    Quy định có điều khoản phí phạt khi huỷ sai hạn, nên phải lưu được version cụ thể
    chứ không chỉ một cờ boolean (docs/09-security.md §7).
    """

    __tablename__ = "consents"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "event_id", "terms_version", name="uq_consents_user_event_version"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    terms_version: Mapped[str] = mapped_column(String(16), nullable=False)
    agreed_at: Mapped[str] = mapped_column(String(32), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(512))

    def __repr__(self) -> str:
        return f"<Consent user={self.user_id} {self.terms_version}>"


class RegistrationCancellation(Base, TimestampMixin):
    """Một lần huỷ đăng ký: CBNV tự huỷ, CBNV xin huỷ chờ BTC duyệt, hoặc BTC huỷ thay.

    Bảng riêng thay vì thêm cột vào `registrations`: một người có thể xin huỷ, bị từ chối rồi xin
    lại — BTC cần đủ lịch sử (ai, lúc nào, lý do, giai đoạn, ai duyệt, phí phạt, đã gỡ gì),
    không chỉ lần cuối.
    """

    __tablename__ = "registration_cancellations"
    __table_args__ = (
        CheckConstraint(f"mode IN {sql_in(CancellationMode)}", name="mode_valid"),
        CheckConstraint(f"status IN {sql_in(CancellationStatus)}", name="status_valid"),
        # Mỗi đăng ký tối đa một yêu cầu đang chờ: hai lần bấm đồng thời không tạo hai yêu cầu.
        Index(
            "uq_registration_cancellations_pending",
            "registration_id",
            unique=True,
            sqlite_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    registration_id: Mapped[int] = mapped_column(
        ForeignKey("registrations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(512), nullable=False)
    # Trạng thái kỳ lúc gửi — BTC biết người này huỷ ở giai đoạn nào.
    event_status: Mapped[str] = mapped_column(String(32), nullable=False)
    after_deadline: Mapped[bool] = mapped_column(nullable=False, default=False)
    requested_at: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[str | None] = mapped_column(String(32))
    decision_note: Mapped[str | None] = mapped_column(String(1000))
    # Quyết định phí phạt của BTC theo quy định công ty (tự huỷ: theo hạn đăng ký).
    penalty_applied: Mapped[bool] = mapped_column(nullable=False, default=False)
    penalty_note: Mapped[str | None] = mapped_column(String(512))
    # JSON {"flights": [...], "buses": [...], "room": [...], "gala": [...], "roles": [...]}
    released_items: Mapped[str | None] = mapped_column(Text)

    registration: Mapped["Registration"] = relationship()
    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    decider: Mapped["User | None"] = relationship(foreign_keys=[decided_by])

    @property
    def released(self) -> dict[str, list[str]]:
        if not self.released_items:
            return {}
        try:
            return json.loads(self.released_items)
        except ValueError:
            return {}

    def __repr__(self) -> str:
        return f"<RegistrationCancellation reg={self.registration_id} {self.mode}/{self.status}>"
