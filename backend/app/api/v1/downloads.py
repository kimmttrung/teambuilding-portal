"""Trả file cho trình duyệt tải về. Dùng chung cho mọi endpoint export."""

from urllib.parse import quote

from fastapi import Response

from app.services.excel import XLSX_MIME


def xlsx_response(content: bytes, filename: str) -> Response:
    return Response(
        content=content,
        media_type=XLSX_MIME,
        headers={
            "Content-Disposition": f"attachment; filename=\"{filename}\"; filename*=UTF-8''{quote(filename)}",
            # File có dữ liệu cá nhân: không để proxy hay trình duyệt giữ bản sao.
            "Cache-Control": "no-store",
        },
    )
