"""Luồng Server-Sent Events cho sơ đồ Gala.

Không đẩy dữ liệu sơ đồ qua SSE — chỉ đẩy "đã đổi" kèm phiên bản. Client nhận xong thì tải lại
`GET /gala/layout`, nơi duy nhất quyết định ai được thấy tên ai. Nhờ vậy luồng SSE giống nhau với
mọi người xem và không thể làm lộ dữ liệu cá nhân.

Phát hiện thay đổi bằng cách hỏi DB mỗi `interval` giây thay vì pub/sub trong bộ nhớ: chạy nhiều
worker uvicorn vẫn đúng, và mỗi nhịp hỏi cũng dọn hold/lượt hết hạn (`gala_service.refresh`).

Hàm tách khỏi FastAPI (nhận `poll`, `is_disconnected`, `sleep` từ ngoài) để test được mà không
cần mở kết nối HTTP dài.
"""

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 1.0
HEARTBEAT_SECONDS = 15.0
RETRY_MILLISECONDS = 3000


async def change_events(
    *,
    poll: Callable[[], Awaitable[str]],
    is_disconnected: Callable[[], Awaitable[bool]],
    interval: float = POLL_INTERVAL_SECONDS,
    heartbeat: float = HEARTBEAT_SECONDS,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> AsyncIterator[str]:
    # `retry` bảo trình duyệt tự nối lại sau 3 giây nếu mất kết nối.
    yield f"retry: {RETRY_MILLISECONDS}\n\n"
    last_version: str | None = None
    last_sent = clock()

    while not await is_disconnected():
        try:
            version = await poll()
        except Exception:  # DB bận một nhịp không được làm đứt luồng của mọi người đang xem
            logger.warning("Không đọc được trạng thái sơ đồ Gala, thử lại nhịp sau", exc_info=True)
            version = None

        if version is not None and version != last_version:
            last_version = version
            last_sent = clock()
            yield f"event: change\ndata: {json.dumps({'version': version})}\n\n"
        elif clock() - last_sent >= heartbeat:
            # Comment SSE: giữ kết nối qua proxy/nginx không bị cắt vì im lặng.
            last_sent = clock()
            yield ": ping\n\n"

        await sleep(interval)
