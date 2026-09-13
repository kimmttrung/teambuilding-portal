"""Dashboard và nhật ký thay đổi cho BTC (docs/04-api-spec.md §10)."""

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import ActiveEvent, DbSession, require_admin
from app.schemas.common import Page
from app.schemas.dashboard import AuditLogOut, DashboardOut
from app.services import audit_service, dashboard_service

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/dashboard", response_model=DashboardOut, summary="Số liệu tổng quan cho BTC")
def get_dashboard(event: ActiveEvent, db: DbSession) -> DashboardOut:
    return DashboardOut(**dashboard_service.build_dashboard(db, event=event))


@router.get("/audit-logs", response_model=Page[AuditLogOut], summary="Nhật ký thay đổi")
def list_audit_logs(
    db: DbSession,
    event_id: int | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    actor_id: int | None = None,
    action: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> Page[AuditLogOut]:
    rows, total = audit_service.list_logs(
        db,
        event_id=event_id,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor_id,
        action=action,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return Page(
        items=[AuditLogOut(**dashboard_service.audit_row(row)) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )
