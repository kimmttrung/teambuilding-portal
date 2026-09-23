"""Điều chỉnh phân bổ chuyến bay bằng tay (docs/04-api-spec.md §5, docs/05 §5).

Thuật toán xếp được ~95% trường hợp; 5% còn lại là ngoại lệ con người phải quyết (vợ chồng
muốn bay cùng, người đi công tác nối chuyến). Vì vậy mọi thao tác ở đây:
- đánh dấu `assignment_mode='manual'` để lần chạy auto sau không ghi đè,
- ghi audit log kèm **lý do bắt buộc**,
- chặn cứng khi vượt sức chứa, chỉ **cảnh báo** khi lệch ca hoặc làm team tách thêm.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status

from app.api.v1.email_jobs import JourneyTracker, send_journey_notices
from app.core.dependencies import (
    ActiveEvent,
    AdminUser,
    DbSession,
    Notify,
    get_client_ip,
    require_admin,
)
from app.models.enums import AssignmentMode, FlightDirection
from app.schemas.common import Page
from app.schemas.flight_allocation import (
    BulkMoveRequest,
    FlightAssignmentOut,
    MoveRequest,
    MoveResponse,
)
from app.services import flight_allocation_service

router = APIRouter(
    prefix="/flight-assignments",
    tags=["flight-assignments"],
    dependencies=[Depends(require_admin)],
)


@router.get("", response_model=Page[FlightAssignmentOut], summary="Danh sách phân bổ")
def list_assignments(
    event: ActiveEvent,
    db: DbSession,
    direction: FlightDirection | None = None,
    flight_id: int | None = None,
    team_id: int | None = None,
    mode: AssignmentMode | None = None,
    shift_mismatch: bool | None = Query(
        default=None, description="Chỉ lấy người đang bay lệch ca nguyện vọng"
    ),
    missing_documents: bool | None = Query(
        default=None, description="Chỉ lấy người thiếu CCCD/ngày sinh"
    ),
    q: str | None = Query(default=None, description="Tìm theo tên, mã NV hoặc mã chuyến"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> Page[FlightAssignmentOut]:
    rows, total = flight_allocation_service.list_assignments(
        db,
        event_id=event.id,
        direction=direction.value if direction else None,
        flight_id=flight_id,
        team_id=team_id,
        mode=mode.value if mode else None,
        shift_mismatch=shift_mismatch,
        missing_documents=missing_documents,
        search=q,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return Page(
        items=[FlightAssignmentOut(**row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch("/{assignment_id}", response_model=MoveResponse, summary="Chuyển một người")
def move_assignment(
    background_tasks: BackgroundTasks,
    assignment_id: int,
    payload: MoveRequest,
    event: ActiveEvent,
    db: DbSession,
    actor: AdminUser,
    request: Request,
    notify: Notify = False,
) -> MoveResponse:
    tracker = JourneyTracker(db, event, notify=notify)
    rows, warnings = flight_allocation_service.move_assignment(
        db,
        event=event,
        assignment_id=assignment_id,
        flight_id=payload.flight_id,
        reason=payload.reason,
        actor=actor,
        ip_address=get_client_ip(request),
    )
    send_journey_notices(background_tasks, tracker, actor, request, "flight_assignment.moved")
    return MoveResponse(
        moved=len(rows),
        assignments=[FlightAssignmentOut(**row) for row in rows],
        warnings=[flag.__dict__ for flag in warnings],
    )


@router.post("/bulk-move", response_model=MoveResponse, summary="Chuyển cả nhóm")
def bulk_move(
    background_tasks: BackgroundTasks,
    payload: BulkMoveRequest,
    event: ActiveEvent,
    db: DbSession,
    actor: AdminUser,
    request: Request,
    notify: Notify = False,
) -> MoveResponse:
    """Chuyển nhiều người sang một chuyến. Người chưa có phân bổ sẽ được tạo mới.

    Sức chứa kiểm cho cả nhóm: thiếu chỗ thì không ai bị chuyển, thay vì chuyển được
    một nửa rồi dừng.
    """
    tracker = JourneyTracker(db, event, notify=notify)
    rows, warnings, created = flight_allocation_service.bulk_move(
        db,
        event=event,
        registration_ids=payload.registration_ids,
        flight_id=payload.flight_id,
        reason=payload.reason,
        actor=actor,
        ip_address=get_client_ip(request),
    )
    send_journey_notices(background_tasks, tracker, actor, request, "flight_assignment.bulk_moved")
    return MoveResponse(
        moved=len(rows) - created,
        created=created,
        assignments=[FlightAssignmentOut(**row) for row in rows],
        warnings=[flag.__dict__ for flag in warnings],
    )


@router.delete(
    "/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Bỏ phân bổ"
)
def remove_assignment(
    background_tasks: BackgroundTasks,
    assignment_id: int,
    event: ActiveEvent,
    db: DbSession,
    actor: AdminUser,
    request: Request,
    reason: str = Query(min_length=3, max_length=500, description="Lý do bỏ phân bổ"),
    notify: Notify = False,
) -> None:
    tracker = JourneyTracker(db, event, notify=notify)
    flight_allocation_service.remove_assignment(
        db,
        event=event,
        assignment_id=assignment_id,
        reason=reason,
        actor=actor,
        ip_address=get_client_ip(request),
    )
    send_journey_notices(background_tasks, tracker, actor, request, "flight_assignment.removed")
