"""Xếp / bỏ xếp phòng bằng tay (docs/04-api-spec.md §6). Chỉ BTC.

Ràng buộc cứng chặn ngay: đủ người, sai `gender_policy`. Người đã có phòng phải bật
`replace_existing` mới chuyển được — tránh ghi đè nhầm bằng một cú bấm.
"""

from fastapi import APIRouter, Depends, Query, Request, status

from app.core.dependencies import ActiveEvent, AdminUser, DbSession, get_client_ip, require_admin
from app.schemas.accommodation import RoomAssignIn, RoomAssignmentOut, RoomAssignResponse
from app.schemas.common import Page
from app.services import accommodation_service

router = APIRouter(
    prefix="/room-assignments",
    tags=["room-assignments"],
    dependencies=[Depends(require_admin)],
)


@router.get("", response_model=Page[RoomAssignmentOut], summary="Danh sách phân phòng")
def list_assignments(
    event: ActiveEvent,
    db: DbSession,
    hotel_id: int | None = None,
    room_id: int | None = None,
    team_id: int | None = None,
    q: str | None = Query(default=None, description="Tìm theo tên, mã NV hoặc số phòng"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> Page[RoomAssignmentOut]:
    rows, total = accommodation_service.list_assignments(
        db,
        event_id=event.id,
        hotel_id=hotel_id,
        room_id=room_id,
        team_id=team_id,
        search=q,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return Page(
        items=[RoomAssignmentOut(**row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=RoomAssignResponse, summary="Xếp một người vào phòng")
def assign(
    payload: RoomAssignIn, event: ActiveEvent, db: DbSession, actor: AdminUser, request: Request
) -> RoomAssignResponse:
    row, moved_from = accommodation_service.assign(
        db,
        event=event,
        registration_id=payload.registration_id,
        room_id=payload.room_id,
        actor=actor,
        is_room_captain=payload.is_room_captain,
        replace_existing=payload.replace_existing,
        reason=payload.reason,
        ip_address=get_client_ip(request),
    )
    return RoomAssignResponse(assignment=RoomAssignmentOut(**row), moved_from_room_id=moved_from)


@router.delete(
    "/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Bỏ xếp phòng"
)
def remove(
    assignment_id: int,
    event: ActiveEvent,
    db: DbSession,
    actor: AdminUser,
    request: Request,
    reason: str = Query(min_length=3, max_length=500, description="Lý do bỏ xếp phòng"),
) -> None:
    accommodation_service.remove_assignment(
        db,
        event=event,
        assignment_id=assignment_id,
        reason=reason,
        actor=actor,
        ip_address=get_client_ip(request),
    )
