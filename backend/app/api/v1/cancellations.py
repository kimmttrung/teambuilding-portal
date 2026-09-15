"""Huỷ đăng ký — phía BTC: xem ai huỷ, duyệt / từ chối yêu cầu, huỷ thay CBNV (docs/04 §4.3)."""

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status

from app.core.dependencies import ActiveEvent, AdminUser, DbSession, get_client_ip, require_admin
from app.models.enums import CancellationMode, CancellationStatus
from app.schemas.cancellation import (
    AdminCancelIn,
    CancellationApproveIn,
    CancellationOut,
    CancellationRejectIn,
)
from app.schemas.common import Page
from app.services import cancellation_service, email_service

router = APIRouter(
    prefix="/admin/cancellations",
    tags=["cancellations"],
    dependencies=[Depends(require_admin)],
)


def send_jobs(background_tasks: BackgroundTasks, jobs: list[dict]) -> None:
    """Thư đã ghi `queued` trong transaction — gửi thật sau khi response trả về."""
    for job in jobs:
        background_tasks.add_task(email_service.deliver_queued_async, **job)


@router.get("", response_model=Page[CancellationOut], summary="Danh sách huỷ đăng ký của kỳ")
def list_cancellations(
    event: ActiveEvent,
    db: DbSession,
    cancellation_status: CancellationStatus | None = Query(default=None, alias="status"),
    mode: CancellationMode | None = None,
    q: str | None = Query(default=None, description="Tìm theo tên, email, mã nhân viên"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[CancellationOut]:
    rows, total = cancellation_service.list_cancellations(
        db,
        event_id=event.id,
        status=cancellation_status.value if cancellation_status else None,
        mode=mode.value if mode else None,
        search=q,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return Page(
        items=[CancellationOut(**row) for row in rows], total=total, page=page, page_size=page_size
    )


@router.post(
    "",
    response_model=CancellationOut,
    status_code=status.HTTP_201_CREATED,
    summary="BTC huỷ đăng ký thay CBNV (ngoại lệ)",
)
def cancel_on_behalf(
    payload: AdminCancelIn,
    event: ActiveEvent,
    db: DbSession,
    actor: AdminUser,
    request: Request,
    background_tasks: BackgroundTasks,
) -> CancellationOut:
    row, jobs = cancellation_service.admin_cancel(
        db,
        event=event,
        actor=actor,
        registration_id=payload.registration_id,
        reason=payload.reason,
        penalty_applied=payload.penalty_applied,
        penalty_note=payload.penalty_note,
        ip_address=get_client_ip(request),
    )
    send_jobs(background_tasks, jobs)
    return CancellationOut(**row)


@router.post("/{cancellation_id}/approve", response_model=CancellationOut, summary="Duyệt yêu cầu huỷ")
def approve(
    cancellation_id: int,
    payload: CancellationApproveIn,
    event: ActiveEvent,
    db: DbSession,
    actor: AdminUser,
    request: Request,
    background_tasks: BackgroundTasks,
) -> CancellationOut:
    row, jobs = cancellation_service.approve(
        db,
        event=event,
        actor=actor,
        cancellation_id=cancellation_id,
        penalty_applied=payload.penalty_applied,
        penalty_note=payload.penalty_note,
        decision_note=payload.decision_note,
        ip_address=get_client_ip(request),
    )
    send_jobs(background_tasks, jobs)
    return CancellationOut(**row)


@router.post("/{cancellation_id}/reject", response_model=CancellationOut, summary="Từ chối yêu cầu huỷ")
def reject(
    cancellation_id: int,
    payload: CancellationRejectIn,
    event: ActiveEvent,
    db: DbSession,
    actor: AdminUser,
    request: Request,
    background_tasks: BackgroundTasks,
) -> CancellationOut:
    row, jobs = cancellation_service.reject(
        db,
        event=event,
        actor=actor,
        cancellation_id=cancellation_id,
        decision_note=payload.decision_note,
        ip_address=get_client_ip(request),
    )
    send_jobs(background_tasks, jobs)
    return CancellationOut(**row)
