"""Health check — dùng cho Docker healthcheck và kiểm tra nhanh khi dev."""

from fastapi import APIRouter

from app.core.config import settings
from app.core.database import check_database

router = APIRouter(tags=["system"])


@router.get("/health", summary="Trạng thái hệ thống")
def health() -> dict:
    db_status = check_database()
    healthy = bool(db_status.get("connected")) and bool(db_status.get("foreign_keys"))
    return {
        "status": "ok" if healthy else "degraded",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "database": db_status,
    }


@router.get("/version", summary="Phiên bản ứng dụng")
def version() -> dict:
    return {"version": settings.APP_VERSION, "environment": settings.APP_ENV}
