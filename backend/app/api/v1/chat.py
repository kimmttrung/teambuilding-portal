# backend/app/api/v1/chat.py
"""Chatbot RAG "Tibi" (docs/04-api-spec.md §11).

- 🟢 Mọi người đăng nhập: hỏi (SSE), xem/xoá lịch sử của CHÍNH mình.
- 🔴 BTC: xem trạng thái knowledge base, nạp lại (re-index).

`POST /chat` trả `text/event-stream`, lần lượt các sự kiện:
    session {session_id, title} → sources [{index, title, source_type}] → delta {text} … → done {message_id, latency_ms, refused}
    Lỗi giữa chừng: error {code, message} rồi đóng luồng.
Lỗi xảy ra TRƯỚC khi stream (429 hỏi quá nhanh, 404 phiên không phải của mình, 422) trả JSON như mọi API khác.
"""

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from app.core.dependencies import ActiveEvent, AdminUser, CurrentUser, DbSession, get_client_ip, require_admin
from app.rag.llm import LLM
from app.rag.runtime import get_llm, get_vector_store
from app.rag.vector_store import VectorStore
from app.schemas.chat import ChatMessageOut, ChatRequest, ChatSessionOut, ChatStatusOut, RagReindexOut, RagStatusOut
from app.services import chat_service, rag_index_service

router = APIRouter(prefix="/chat", tags=["chat"])
admin_router = APIRouter(prefix="/admin/rag", tags=["chat"], dependencies=[Depends(require_admin)])


@router.get("/status", response_model=ChatStatusOut, summary="Trợ lý đã sẵn sàng chưa")
def get_status(
    event: ActiveEvent, db: DbSession, user: CurrentUser,
    store: VectorStore = Depends(get_vector_store), llm: LLM = Depends(get_llm),
) -> ChatStatusOut:
    return ChatStatusOut(**rag_index_service.status(db, event=event, store=store, llm=llm))


@router.post("", summary="Hỏi trợ lý (SSE stream)")
async def ask(
    payload: ChatRequest,
    event: ActiveEvent,
    db: DbSession,
    user: CurrentUser,
    store: VectorStore = Depends(get_vector_store),
    llm: LLM = Depends(get_llm),
) -> StreamingResponse:
    prepared = await run_in_threadpool(
        chat_service.prepare, db, user=user, event=event, session_id=payload.session_id, message=payload.message
    )
    return StreamingResponse(
        _sse(chat_service.stream_answer(prepared, store=store, llm=llm)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _sse(events: AsyncIterator[tuple[str, Any]]) -> AsyncIterator[str]:
    async for name, data in events:
        yield f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/sessions", response_model=list[ChatSessionOut], summary="Cuộc trò chuyện của tôi")
def list_sessions(db: DbSession, user: CurrentUser) -> list[ChatSessionOut]:
    return [ChatSessionOut(**row) for row in chat_service.list_sessions(db, user_id=user.id)]


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageOut], summary="Tin nhắn của một cuộc trò chuyện")
def list_messages(session_id: int, db: DbSession, user: CurrentUser) -> list[ChatMessageOut]:
    return [ChatMessageOut(**row) for row in chat_service.list_messages(db, user_id=user.id, session_id=session_id)]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Xoá cuộc trò chuyện")
def delete_session(session_id: int, db: DbSession, user: CurrentUser) -> None:
    chat_service.delete_session(db, user_id=user.id, session_id=session_id)


# --- BTC ---


@admin_router.get("/status", response_model=RagStatusOut, summary="Trạng thái knowledge base")
def admin_status(
    event: ActiveEvent, db: DbSession, store: VectorStore = Depends(get_vector_store), llm: LLM = Depends(get_llm)
) -> RagStatusOut:
    return RagStatusOut(**rag_index_service.status(db, event=event, store=store, llm=llm))


@admin_router.post("/reindex", response_model=RagReindexOut, summary="Nạp lại knowledge base của kỳ đang chạy")
def reindex(
    event: ActiveEvent, db: DbSession, actor: AdminUser, request: Request, store: VectorStore = Depends(get_vector_store)
) -> RagReindexOut:
    return RagReindexOut(
        **rag_index_service.reindex(db, event=event, store=store, actor=actor, ip_address=get_client_ip(request))
    )
