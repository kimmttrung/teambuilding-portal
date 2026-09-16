"""Chỉ định Trưởng nhóm (`teams.leader_user_id`).

Trưởng nhóm là người giữ / xác nhận / xếp ghế Gala cho cả team (gala_service.led_team), nên người được
chỉ định phải là thành viên team và đang xác nhận tham gia kỳ đang chạy. Trưởng nhóm huỷ đăng ký thì
`cancellation_service` gỡ chức ngay (`remove_leadership`); BTC chỉ định người khác qua `assign` — trên
dashboard, hoặc ngay trong hộp thoại duyệt huỷ (`apply`, cùng transaction với việc huỷ).

Vai trò tài khoản đi theo chức: được chỉ định thì `employee` → `team_leader`; mất chức và không còn dẫn
team nào thì `team_leader` → `employee`. Không bao giờ đụng tài khoản BTC / Quản trị.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import immediate_transaction
from app.core.exceptions import ConflictError, NotFoundError
from app.models.enums import ADMIN_ROLES, RegistrationStatus, UserRole
from app.models.event import Event
from app.models.org import Team
from app.models.registration import Registration
from app.models.user import User
from app.services import audit_service


def is_active_participant(db: Session, *, event_id: int, user_id: int) -> bool:
    return (
        db.scalar(
            select(Registration.id).where(
                Registration.event_id == event_id,
                Registration.user_id == user_id,
                Registration.status == RegistrationStatus.SUBMITTED,
                Registration.is_participating.is_(True),
            )
        )
        is not None
    )


def teams_led_by(db: Session, user_id: int) -> list[Team]:
    return list(db.scalars(select(Team).where(Team.leader_user_id == user_id).order_by(Team.id)))


def remove_leadership(db: Session, user: User) -> list[str]:
    """Gỡ mọi chức Trưởng nhóm của một người (khi huỷ đăng ký). Trả tên các team. Không commit."""
    names = []
    for team in teams_led_by(db, user.id):
        names.append(team.name)
        team.leader_user_id = None
    if names:
        db.flush()
        _demote_if_leading_nothing(db, user)
        db.flush()
    return names


def apply(
    db: Session,
    *,
    event_id: int,
    team_id: int,
    user_id: int,
    actor_id: int,
    ip_address: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    """Đổi Trưởng nhóm trong transaction đang mở (không commit) — lỗi thì cả transaction huỷ theo."""
    team = db.get(Team, team_id)
    if team is None or not team.is_active:
        raise NotFoundError(f"Không tìm thấy team #{team_id}.", code="TEAM_NOT_FOUND")
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise NotFoundError(f"Không tìm thấy CBNV #{user_id} đang hoạt động.", code="USER_NOT_FOUND")
    if user.role in ADMIN_ROLES:
        raise ConflictError(
            "Tài khoản Ban tổ chức không làm Trưởng nhóm được.", code="LEADER_IS_ORGANIZER"
        )
    if user.team_id != team.id:
        raise ConflictError(
            f"{user.full_name} không thuộc team {team.name}.", code="LEADER_NOT_IN_TEAM"
        )
    if not is_active_participant(db, event_id=event_id, user_id=user.id):
        raise ConflictError(
            f"{user.full_name} chưa xác nhận tham gia kỳ này. Trưởng nhóm phải là người đi để chọn "
            "ghế Gala cho team.",
            code="LEADER_NOT_PARTICIPATING",
        )
    previous_id = team.leader_user_id
    if previous_id == user.id:
        raise ConflictError(
            f"{user.full_name} đã là Trưởng nhóm của team {team.name}.", code="LEADER_UNCHANGED"
        )

    team.leader_user_id = user.id
    role_changes = []
    if user.role == UserRole.EMPLOYEE:
        user.role = UserRole.TEAM_LEADER
        role_changes.append({"user_id": user.id, "role": UserRole.TEAM_LEADER.value})
    db.flush()

    previous = db.get(User, previous_id) if previous_id is not None else None
    if previous is not None and _demote_if_leading_nothing(db, previous):
        role_changes.append({"user_id": previous.id, "role": UserRole.EMPLOYEE.value})

    audit_service.log(
        db,
        action="team.leader_changed",
        entity_type="team",
        entity_id=team.id,
        actor_id=actor_id,
        event_id=event_id,
        before={"leader_user_id": previous_id},
        after={"leader_user_id": user.id, "role_changes": role_changes},
        reason=reason,
        ip_address=ip_address,
    )
    db.flush()
    return {
        "team_id": team.id,
        "team_name": team.name,
        "leader_user_id": user.id,
        "leader_name": user.full_name,
        "previous_leader_user_id": previous_id,
    }


def assign(
    db: Session,
    *,
    event: Event,
    actor: User,
    team_id: int,
    user_id: int,
    ip_address: str | None = None,
) -> dict[str, Any]:
    event_id, actor_id = event.id, actor.id
    with immediate_transaction(db):
        result = apply(
            db,
            event_id=event_id,
            team_id=team_id,
            user_id=user_id,
            actor_id=actor_id,
            ip_address=ip_address,
        )
    return result


def _demote_if_leading_nothing(db: Session, user: User) -> bool:
    if user.role != UserRole.TEAM_LEADER:
        return False
    still_leads = db.scalar(
        select(Team.id).where(Team.leader_user_id == user.id, Team.is_active.is_(True))
    )
    if still_leads is not None:
        return False
    user.role = UserRole.EMPLOYEE
    return True
