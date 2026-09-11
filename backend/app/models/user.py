"""Người dùng hệ thống (CBNV, Team Leader, BTC, Super Admin)."""

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import ADMIN_ROLES, Gender, UserRole, sql_in

if TYPE_CHECKING:
    from app.models.org import Department, Team, WorkLocation
    from app.models.registration import Registration


class User(Base, TimestampMixin):
    """Hồ sơ CBNV.

    Gộp cả tài khoản đăng nhập và hồ sơ nhân sự vì nguồn dữ liệu ở MVP là import Excel.
    Khi cắm SSO, `sso_subject` giữ định danh từ Azure AD và `password_hash` để trống.

    Nhóm trường nhạy cảm (id_card_*, date_of_birth, address, health_note) chỉ chính chủ
    và admin đọc được - xem docs/09-security.md §4.
    """

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(f"role IN {sql_in(UserRole)}", name="role_valid"),
        CheckConstraint(
            f"gender IS NULL OR gender IN {sql_in(Gender)}", name="gender_valid"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # --- Định danh & đăng nhập ---
    employee_code: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    sso_subject: Mapped[str | None] = mapped_column(String(255), unique=True)
    role: Mapped[str] = mapped_column(
        String(32), nullable=False, default=UserRole.EMPLOYEE, index=True
    )

    # --- Hồ sơ cá nhân ---
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(String(512))
    phone: Mapped[str | None] = mapped_column(String(32))
    personal_email: Mapped[str | None] = mapped_column(String(255))
    gender: Mapped[str | None] = mapped_column(String(16))  # dùng để phân phòng
    date_of_birth: Mapped[str | None] = mapped_column(String(10))  # YYYY-MM-DD, cần cho vé bay
    address: Mapped[str | None] = mapped_column(String(512))

    # --- Thông tin công việc ---
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), index=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"))
    work_location_id: Mapped[int | None] = mapped_column(ForeignKey("work_locations.id"))
    job_title: Mapped[str | None] = mapped_column(String(128))
    join_date: Mapped[str | None] = mapped_column(String(10))

    # --- Giấy tờ để xuất vé máy bay ---
    id_card_number: Mapped[str | None] = mapped_column(String(32))
    id_card_type: Mapped[str | None] = mapped_column(String(16))  # cccd | passport
    id_card_issue_date: Mapped[str | None] = mapped_column(String(10))
    id_card_issue_place: Mapped[str | None] = mapped_column(String(255))

    # --- Hậu cần ---
    shirt_size: Mapped[str | None] = mapped_column(String(8))
    dietary_restriction: Mapped[str | None] = mapped_column(String(255))
    health_note: Mapped[str | None] = mapped_column(Text)
    emergency_contact_name: Mapped[str | None] = mapped_column(String(255))
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(32))

    # --- Trạng thái tài khoản ---
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True, index=True)
    must_change_password: Mapped[bool] = mapped_column(nullable=False, default=False)
    last_login_at: Mapped[str | None] = mapped_column(String(32))
    # Chống dò mật khẩu: khoá tạm sau nhiều lần sai liên tiếp.
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[str | None] = mapped_column(String(32))

    team: Mapped["Team | None"] = relationship(
        back_populates="members", foreign_keys=[team_id]
    )
    department: Mapped["Department | None"] = relationship()
    work_location: Mapped["WorkLocation | None"] = relationship()
    registrations: Mapped[list["Registration"]] = relationship(back_populates="user")

    # --- Tiện ích ---

    @property
    def is_admin(self) -> bool:
        return self.role in ADMIN_ROLES

    @property
    def can_fly(self) -> bool:
        """Đủ giấy tờ để BTC xuất vé máy bay chưa.

        Thiếu là chặn được ngay từ dashboard thay vì phát hiện lúc ra sân bay.
        """
        return bool(self.id_card_number and self.date_of_birth and self.full_name)

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role})>"
