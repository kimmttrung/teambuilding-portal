"""Xem và điều chỉnh phân xe bằng tay (docs/04-api-spec.md §7).

Mọi thao tác chuyển người đánh dấu `assignment_mode='manual'` (lần chạy auto sau giữ
nguyên), ghi audit log kèm lý do bắt buộc, chặn cứng khi xe đủ chỗ.
"""

from fastapi import APIRouter, Depends, Query, Request

from app.core.dependencies import (
    ActiveEvent,
    AdminUser,
    DbSession,
    get_client_ip,
    require_admin,
)
from app.schemas.bus import BusAssignmentOut, BusMoveRequest, BusMoveResponse
from app.schemas.common import Page
from app.services import bus_service

router = APIRouter(
    prefix="/bus-assignments",
    tags=["bus-assignments"],
    dependencies=[Depends(require_admin)],
)


@router.get("", response_model=Page[BusAssignmentOut], summary="Danh sách phân xe")
def list_assignments(
    event: ActiveEvent,
    db: DbSession,
    trip_leg_id: int | None = None,
    bus_id: int | None = None,
    team_id: int | None = None,
    q: str | None = Query(default=None, description="Tìm theo tên, mã NV hoặc mã xe"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> Page[BusAssignmentOut]:
    rows, total = bus_service.list_assignments(
        db,
        event_id=event.id,
        trip_leg_id=trip_leg_id,
        bus_id=bus_id,
        team_id=team_id,
        search=q,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return Page(
        items=[BusAssignmentOut(**row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch("/{assignment_id}", response_model=BusMoveResponse, summary="Chuyển người sang xe khác")
def move_assignment(
    assignment_id: int,
    payload: BusMoveRequest,
    event: ActiveEvent,
    db: DbSession,
    actor: AdminUser,
    request: Request,
) -> BusMoveResponse:
    row, warnings = bus_service.move_assignment(
        db,
        event=event,
        assignment_id=assignment_id,
        bus_id=payload.bus_id,
        reason=payload.reason,
        actor=actor,
        ip_address=get_client_ip(request),
    )
    return BusMoveResponse(
        assignment=BusAssignmentOut(**row),
        warnings=[flag.__dict__ for flag in warnings],
    )
