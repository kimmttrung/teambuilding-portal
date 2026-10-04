"""Đăng ký tham gia, nhu cầu xe theo chặng và bằng chứng đồng ý quy định."""

import json
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import (
    AssignmentMode,
    CancellationMode,
    CancellationStatus,
    RegistrationStatus,
    sql_in,
)

if TYPE_CHECKING:
    from app.models.accommodation import Room
    from app.models.event import Event
    from app.models.flight import FlightAssignment, Shift
    from app.models.gala import GalaSeat
    from app.models.transportation import Bus, PickupPoint, TripLeg
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
        CheckConstraint(
            "room_mode IS NULL OR room_mode IN ('auto', 'manual')", name="room_mode_valid"
        ),
        CheckConstraint("room_id IS NOT NULL OR is_room_captain = 0", name="captain_has_room"),
        CheckConstraint(
            "(consent_version IS NULL AND consented_at IS NULL) OR "
            "(consent_version IS NOT NULL AND consented_at IS NOT NULL)",
            name="consent_complete",
        ),
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
    consent_version: Mapped[str | None] = mapped_column(String(16))
    consented_at: Mapped[str | None] = mapped_column(String(32))
    consent_ip: Mapped[str | None] = mapped_column(String(64))
    consent_user_agent: Mapped[str | None] = mapped_column(String(512))

    room_id: Mapped[int | None] = mapped_column(ForeignKey("rooms.id"), index=True)
    is_room_captain: Mapped[bool] = mapped_column(nullable=False, default=False)
    room_mode: Mapped[str | None] = mapped_column(String(16))
    room_assigned_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    room_assigned_at: Mapped[str | None] = mapped_column(String(32))
    room_note: Mapped[str | None] = mapped_column(String(512))
    room: Mapped["Room | None"] = relationship(back_populates="registrations")

    event: Mapped["Event"] = relationship(back_populates="registrations")
    user: Mapped["User"] = relationship(back_populates="registrations", foreign_keys=[user_id])
    shift: Mapped["Shift | None"] = relationship()
    legs: Mapped[list["RegistrationLeg"]] = relationship(
        back_populates="registration", cascade="all, delete-orphan"
    )
    flight_assignments: Mapped[list["FlightAssignment"]] = relationship(
        back_populates="registration", cascade="all, delete-orphan"
    )
    room_assigner: Mapped["User | None"] = relationship(foreign_keys=[room_assigned_by])
    gala_seat: Mapped["GalaSeat | None"] = relationship(back_populates="registration")
    cancellations: Mapped[list["RegistrationCancellation"]] = relationship(
        back_populates="registration",
        cascade="all, delete-orphan",
        order_by="RegistrationCancellation.id.desc()",
    )

    @property
    def latest_approved_cancellation(self) -> "RegistrationCancellation | None":
        if self.status != RegistrationStatus.CANCELLED:
            return None
        return next(
            (row for row in self.cancellations if row.status == CancellationStatus.APPROVED), None
        )

    @property
    def cancelled_at(self) -> str | None:
        row = self.latest_approved_cancellation
        return row.decided_at if row else None

    @property
    def cancel_reason(self) -> str | None:
        row = self.latest_approved_cancellation
        return row.reason if row else None

    @property
    def penalty_applied(self) -> bool:
        row = self.latest_approved_cancellation
        return bool(row and row.penalty_applied)

    @property
    def is_active_participant(self) -> bool:
        """Chỉ người này mới được đưa vào thuật toán phân bổ."""
        return self.is_participating and self.status == RegistrationStatus.SUBMITTED

    @property
    def bus_needs(self) -> list["RegistrationLeg"]:
        """Tên tương thích cho payload/API cũ; dữ liệu thật nằm ở `registration_legs`."""
        return self.legs

    def __repr__(self) -> str:
        return f"<Registration event={self.event_id} user={self.user_id}>"


class RegistrationLeg(Base):
    """Nhu cầu và phân xe của một người cho MỘT chặng; bus_id NULL = chưa xếp.

    Một dòng cho mỗi chặng thay vì 4 cột bus_1..bus_4, để thêm/bớt chặng chỉ là
    thêm/bớt dữ liệu (docs/00-review-of-draft.md §2.3).
    """

    __tablename__ = "registration_legs"
    __table_args__ = (
        UniqueConstraint(
            "registration_id", "trip_leg_id", name="uq_registration_legs_registration_leg"
        ),
        CheckConstraint("bus_id IS NULL OR needs_bus = 1", name="assigned_needs_bus"),
        CheckConstraint(
            "assignment_mode IS NULL OR assignment_mode IN ('auto', 'manual')", name="mode_valid"
        ),
        ForeignKeyConstraint(
            ["bus_id", "trip_leg_id"],
            ["buses.id", "buses.trip_leg_id"],
            name="fk_registration_legs_bus_leg",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    registration_id: Mapped[int] = mapped_column(
        ForeignKey("registrations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trip_leg_id: Mapped[int] = mapped_column(ForeignKey("trip_legs.id"), nullable=False, index=True)
    needs_bus: Mapped[bool] = mapped_column(nullable=False, default=False)
    pickup_point_id: Mapped[int | None] = mapped_column(ForeignKey("pickup_points.id"))
    note: Mapped[str | None] = mapped_column(String(512))
    bus_id: Mapped[int | None] = mapped_column(Integer, index=True)
    assignment_mode: Mapped[str | None] = mapped_column(String(16))
    assigned_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    assigned_at: Mapped[str | None] = mapped_column(String(32))
    assignment_note: Mapped[str | None] = mapped_column(Text)

    registration: Mapped["Registration"] = relationship(back_populates="legs")
    trip_leg: Mapped["TripLeg"] = relationship(foreign_keys=[trip_leg_id])
    pickup_point: Mapped["PickupPoint | None"] = relationship()
    bus: Mapped["Bus | None"] = relationship(
        back_populates="registration_legs",
        primaryjoin="and_(foreign(RegistrationLeg.bus_id) == Bus.id, "
        "RegistrationLeg.trip_leg_id == Bus.trip_leg_id)",
        foreign_keys=[bus_id],
    )
    assigner: Mapped["User | None"] = relationship(foreign_keys=[assigned_by])

    @property
    def is_manual(self) -> bool:
        return self.assignment_mode == AssignmentMode.MANUAL

    def __repr__(self) -> str:
        return f"<RegistrationLeg reg={self.registration_id} leg={self.trip_leg_id}>"


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

    registration: Mapped["Registration"] = relationship(back_populates="cancellations")
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
