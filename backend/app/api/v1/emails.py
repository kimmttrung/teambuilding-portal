"""Nhật ký email cho BTC (docs/04-api-spec.md §10).

Email do nghiệp vụ tự gửi (đăng ký, nhắc việc); ở đây BTC xem lại và gửi lại thư lỗi.
Toàn bộ router dành riêng cho BTC — nội dung mail chứa thông tin cá nhân của CBNV.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request

from app.core.dependencies import AdminUser, DbSession, get_client_ip, require_admin
from app.models.enums import EmailStatus
from app.models.notification import EmailLog
from app.schemas.common import Page
from app.schemas.email import EmailLogOut, EmailLogStats, EmailResendRequest, EmailResendResult
from app.services import email_resend_service, email_service
from app.services.email_templates import TEMPLATE_LABELS

router = APIRouter(
    prefix="/admin/email-logs",
    tags=["email-logs"],
    dependencies=[Depends(require_admin)],
)


@router.get("", response_model=Page[EmailLogOut], summary="Nhật ký email đã gửi")
def list_email_logs(
    db: DbSession,
    q: str | None = Query(default=None, description="Tìm theo email người nhận hoặc tiêu đề"),
    email_status: EmailStatus | None = Query(default=None, alias="status"),
    template: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> Page[EmailLogOut]:
    rows, total = email_service.list_logs(
        db,
        status=email_status.value if email_status else None,
        template=template,
        search=q,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return Page(
        items=[_to_schema(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/stats", response_model=EmailLogStats, summary="Thống kê email")
def get_email_stats(db: DbSession) -> EmailLogStats:
    return EmailLogStats(**email_service.get_stats(db))


@router.post("/resend", response_model=EmailResendResult, summary="Gửi lại thư lỗi")
def resend_emails(
    payload: EmailResendRequest,
    actor: AdminUser,
    db: DbSession,
    request: Request,
    background_tasks: BackgroundTasks,
) -> EmailResendResult:
    result, jobs = email_resend_service.resend(
        db, actor=actor, ids=payload.ids, ip_address=get_client_ip(request)
    )
    # Transaction đã commit trong service: giờ mới gửi thật, sau khi response trả về.
    for job in jobs:
        background_tasks.add_task(email_service.deliver_queued_async, **job)
    return EmailResendResult(**result)


def _to_schema(row: EmailLog) -> EmailLogOut:
    return EmailLogOut(
        **{
            **EmailLogOut.model_validate(row).model_dump(),
            "template_label": TEMPLATE_LABELS.get(row.template, row.template),
            "is_dev_only": row.status == EmailStatus.QUEUED
            and row.error_message == email_service.DEV_MODE_NOTE,
        }
    )
