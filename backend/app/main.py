"""Điểm khởi tạo ứng dụng FastAPI."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import settings
from app.core.database import check_database
from app.core.exceptions import register_exception_handlers

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Chuẩn bị khi khởi động, dọn dẹp khi tắt."""
    settings.ensure_directories()
    db_status = check_database()
    if not db_status.get("connected"):
        logger.error("Không kết nối được database: %s", db_status.get("error"))
    elif not db_status.get("foreign_keys"):
        # Không dừng app, nhưng phải kêu to: FK tắt = dữ liệu mồ côi trong im lặng.
        logger.error("PRAGMA foreign_keys đang TẮT — kiểm tra lại app/core/database.py")
    else:
        logger.info(
            "Database sẵn sàng: %s (journal_mode=%s)",
            db_status.get("path"),
            db_status.get("journal_mode"),
        )
    logger.info("%s %s khởi động ở môi trường %s", settings.APP_NAME, settings.APP_VERSION, settings.APP_ENV)
    yield
    logger.info("Đang tắt ứng dụng")


def create_app() -> FastAPI:
    show_docs = not settings.is_production
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Hệ thống quản lý Team Building — đăng ký, phân bổ chuyến bay/xe/phòng, "
        "Gala Dinner và hành trình cá nhân.",
        docs_url="/docs" if show_docs else None,
        redoc_url="/redoc" if show_docs else None,
        openapi_url="/openapi.json" if show_docs else None,
        lifespan=lifespan,
    )

    # Ở production frontend và backend chung một origin (nginx proxy) nên CORS không cần thiết;
    # cấu hình này phục vụ lúc dev chạy Vite ở cổng 5173.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.API_PREFIX)

    # Ảnh avatar CBNV tải lên. Thư mục riêng, không nằm trong source code.
    settings.ensure_directories()
    app.mount("/uploads", StaticFiles(directory=settings.upload_path), name="uploads")

    @app.get("/", include_in_schema=False)
    def root() -> dict:
        return {
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs" if show_docs else None,
            "api": settings.API_PREFIX,
        }

    return app


app = create_app()
