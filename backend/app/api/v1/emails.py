"""Nhật ký email cho BTC (docs/04-api-spec.md §10).

Chỉ đọc: email được gửi tự động theo nghiệp vụ, không ai gửi tay từ đây.
Toàn bộ router dành riêng cho BTC — nội dung mail chứa thông tin cá nhân của CBNV.
"""

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import DbSession, require_admin
from app.models.enums import EmailStatus
from app.models.notification import EmailLog
from app.schemas.common import Page
from app.schemas.email import EmailLogOut, EmailLogStats
from app.services import email_service
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


def _to_schema(row: EmailLog) -> EmailLogOut:
    return EmailLogOut.model_validate(row).model_copy(
        update={"template_label": TEMPLATE_LABELS.get(row.template, row.template)}
    )
