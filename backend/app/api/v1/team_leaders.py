"""Chỉ định Trưởng nhóm — BTC dùng khi Trưởng nhóm huỷ tham gia (docs/04 §4.3)."""

from fastapi import APIRouter, Depends, Request

from app.core.dependencies import ActiveEvent, AdminUser, DbSession, get_client_ip, require_admin
from app.schemas.team_leader import TeamLeaderIn, TeamLeaderOut
from app.services import team_leader_service

router = APIRouter(prefix="/admin/teams", tags=["teams"], dependencies=[Depends(require_admin)])


@router.put(
    "/{team_id}/leader",
    response_model=TeamLeaderOut,
    summary="Chỉ định Trưởng nhóm (thành viên team đang tham gia kỳ)",
)
def assign_leader(
    team_id: int,
    payload: TeamLeaderIn,
    event: ActiveEvent,
    db: DbSession,
    actor: AdminUser,
    request: Request,
) -> TeamLeaderOut:
    result = team_leader_service.assign(
        db,
        event=event,
        actor=actor,
        team_id=team_id,
        user_id=payload.user_id,
        ip_address=get_client_ip(request),
    )
    return TeamLeaderOut(**result)
