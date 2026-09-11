"""Lỗi nghiệp vụ và handler chuẩn hoá khuôn dạng lỗi trả về.

Mọi lỗi ra khỏi API đều có dạng:
    {"error": {"code": "...", "message": "...", "details": {...}}}
Xem docs/04-api-spec.md §1.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Lỗi nghiệp vụ có mã và thông điệp tiếng Việt cho người dùng cuối."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "APP_ERROR"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"


class PermissionDeniedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "PERMISSION_DENIED"


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "UNAUTHORIZED"


class ConflictError(AppError):
    """Xung đột trạng thái: vượt slot, ghế đã bị chiếm, sai trạng thái chương trình."""

    status_code = status.HTTP_409_CONFLICT
    code = "CONFLICT"


class CapacityExceededError(ConflictError):
    code = "CAPACITY_EXCEEDED"


class InvalidEventStatusError(ConflictError):
    code = "INVALID_EVENT_STATUS"


def _error_body(code: str, message: str, details: dict | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def register_exception_handlers(app: FastAPI) -> None:
    """Gắn handler để mọi loại lỗi đều trả cùng một khuôn."""

    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,  # HTTP_422_UNPROCESSABLE_CONTENT — hằng số cũ đã deprecated
            content=_error_body(
                "VALIDATION_ERROR",
                "Dữ liệu gửi lên không hợp lệ.",
                {"fields": _format_validation_errors(exc)},
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(
                _HTTP_CODE_NAMES.get(exc.status_code, "HTTP_ERROR"),
                str(exc.detail),
            ),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Lỗi không lường trước tại %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body(
                "INTERNAL_ERROR",
                "Hệ thống gặp lỗi không mong muốn. Vui lòng thử lại hoặc báo BTC.",
            ),
        )


def _format_validation_errors(exc: RequestValidationError) -> list[dict]:
    """Rút gọn lỗi Pydantic thành danh sách {field, message} cho frontend."""
    return [
        {
            "field": ".".join(str(part) for part in error.get("loc", []) if part != "body"),
            "message": error.get("msg", ""),
        }
        for error in exc.errors()
    ]


_HTTP_CODE_NAMES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "PERMISSION_DENIED",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    429: "RATE_LIMITED",
}
