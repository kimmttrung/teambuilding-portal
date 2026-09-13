"""Email nhắc việc BTC chủ động gửi (thiếu giấy tờ, chưa đăng ký).

Luồng hai bước giống phân bổ: GET xem trước ai sẽ nhận, POST mới gửi.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, Request

from app.core.dependencies import ActiveEvent, AdminUser, DbSession, get_client_ip, require_admin
from app.models.enums import ReminderKind
from app.schemas.reminder import ReminderPreview, ReminderSendRequest, ReminderSendResult
from app.services import email_service, reminder_service

router = APIRouter(
    prefix="/admin/reminders",
    tags=["reminders"],
    dependencies=[Depends(require_admin)],
)


@router.get("/{kind}", response_model=ReminderPreview, summary="Xem trước người nhận email nhắc")
def preview_reminder(kind: ReminderKind, event: ActiveEvent, db: DbSession) -> ReminderPreview:
    return ReminderPreview(**reminder_service.preview(db, event=event, kind=kind))


@router.post("/{kind}", response_model=ReminderSendResult, summary="Gửi email nhắc")
def send_reminder(
    kind: ReminderKind,
    payload: ReminderSendRequest,
    actor: AdminUser,
    event: ActiveEvent,
    db: DbSession,
    request: Request,
    background_tasks: BackgroundTasks,
) -> ReminderSendResult:
    result, jobs = reminder_service.send(
        db,
        event=event,
        kind=kind,
        actor=actor,
        user_ids=payload.user_ids,
        include_recently_reminded=payload.include_recently_reminded,
        ip_address=get_client_ip(request),
    )
    # Transaction đã commit trong service: giờ mới gửi thật, sau khi response trả về.
    for job in jobs:
        background_tasks.add_task(email_service.deliver_queued_async, **job)
    return ReminderSendResult(**result)
