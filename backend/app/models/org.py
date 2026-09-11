"""Master data cơ cấu tổ chức: phòng ban, địa điểm làm việc, team."""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class Department(Base):
    """Phòng ban/khối. BTC cấu hình, CBNV chọn từ danh sách - không nhập tự do."""

    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)

    teams: Mapped[list["Team"]] = relationship(back_populates="department")

    def __repr__(self) -> str:
        return f"<Department {self.code}>"


class WorkLocation(Base):
    """Địa điểm làm việc: HN, HCM, ... Quyết định điểm đón và chặng xe nội thành."""

    __tablename__ = "work_locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str | None] = mapped_column(String(128))
    airport_code: Mapped[str | None] = mapped_column(String(8))  # HAN, SGN
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<WorkLocation {self.code}>"


class Team(Base, TimestampMixin):
    """Đơn vị nhỏ nhất của nghiệp vụ phân bổ.

    Thuật toán cố giữ người cùng team đi cùng chuyến bay/xe, và team là đơn vị
    bốc thăm chọn chỗ Gala Dinner.
    """

    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"))

    # Cố ý KHÔNG đặt ForeignKey tới users.id: users.team_id đã trỏ ngược về teams.id,
    # thêm FK ở đây tạo vòng lặp mà SQLite không ALTER TABLE thêm constraint được.
    # Ràng buộc "leader phải là user có thật" kiểm tra ở service layer.
    leader_user_id: Mapped[int | None] = mapped_column(Integer, index=True)

    color: Mapped[str | None] = mapped_column(String(16))  # màu hiển thị trên sơ đồ Gala
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)

    department: Mapped["Department | None"] = relationship(back_populates="teams")
    members: Mapped[list["User"]] = relationship(
        back_populates="team", foreign_keys="User.team_id"
    )

    def __repr__(self) -> str:
        return f"<Team {self.code}>"
