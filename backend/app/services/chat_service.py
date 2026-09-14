# backend/app/services/chat_service.py
"""Hội thoại với trợ lý: phiên, lịch sử, giới hạn tần suất, và điều phối một lượt hỏi–đáp.

Một lượt hỏi chia hai nửa:
1. `prepare` (đồng bộ, trong request): giới hạn tần suất, lấy/tạo phiên, lấy lịch sử, lưu câu hỏi, chạy guard.
   Commit xong và trả dataclass thuần — không mang ORM object sang nửa sau.
2. `stream_answer` (async, trong lúc stream): retrieve → gọi LLM → che số → lưu câu trả lời bằng session
   RIÊNG (`session_scope`), vì session của request có thể đã đóng khi luồng còn chạy (CLAUDE.md cạm bẫy #10).
"""

import json
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import session_scope
from app.core.exceptions import AppError, NotFoundError
from app.core.timeutils import VN_TZ, to_iso, utcnow, utcnow_iso
from app.models.chat import ChatMessage, ChatSession
from app.models.enums import ChatRole, EventStatus
from app.models.event import Event
from app.models.user import User
from app.rag import guard, prompts
from app.rag.guard import GuardDecision, StreamRedactor
from app.rag.llm import LLM, LLMError
from app.rag.prompts import Turn
from app.rag.vector_store import VectorStore
from app.services.event_service import status_label

WEEKDAYS = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"]
TITLE_LENGTH = 60
SHORT_FOLLOW_UP_WORDS = 6


@dataclass(frozen=True)
class PreparedChat:
    session_id: int
    title: str
    question: str
    history: list[Turn]
    decision: GuardDecision
    event_id: int
    event_name: str
    event_status: str


# --- Chuẩn bị (đồng bộ, trong request) ---


def prepare(db: Session, *, user: User, event: Event, session_id: int | None, message: str) -> PreparedChat:
    user_id, event_id = user.id, event.id
    _ensure_rate_limit(db, user_id)

    session = _get_session(db, user_id=user_id, session_id=session_id) if session_id else None
    if session is None:
        session = ChatSession(user_id=user_id, event_id=event_id, title=_title(message), created_at=utcnow_iso())
        db.add(session)
        db.flush()

    history = _history(db, session.id)
    db.add(ChatMessage(session_id=session.id, role=ChatRole.USER, content=message, created_at=utcnow_iso()))
    prepared = PreparedChat(
        session_id=session.id,
        title=session.title or _title(message),
        question=message,
        history=history,
        decision=guard.check_question(message),
        event_id=event_id,
        event_name=event.name,
        event_status=event.status,
    )
    db.commit()
    return prepared


def _ensure_rate_limit(db: Session, user_id: int) -> None:
    since = to_iso(utcnow() - timedelta(minutes=10))
    sent = db.scalar(
        select(func.count(ChatMessage.id))
        .join(ChatSession, ChatSession.id == ChatMessage.session_id)
        .where(ChatSession.user_id == user_id, ChatMessage.role == ChatRole.USER, ChatMessage.created_at >= since)
    ) or 0
    # Đếm trong DB (không đếm trong bộ nhớ) để đúng cả khi chạy nhiều worker uvicorn.
    if sent >= settings.CHAT_RATE_LIMIT_PER_10MIN:
        raise AppError(
            f"Bạn đã hỏi {sent} câu trong 10 phút. Nghỉ tay một chút rồi hỏi tiếp nhé.",
            code="CHAT_RATE_LIMITED",
            status_code=429,
            details={"limit": settings.CHAT_RATE_LIMIT_PER_10MIN, "window_minutes": 10},
        )


def _get_session(db: Session, *, user_id: int, session_id: int) -> ChatSession:
    session = db.get(ChatSession, session_id)
    # Phiên của người khác trả 404 như không tồn tại — không xác nhận là có phiên đó.
    if session is None or session.user_id != user_id:
        raise NotFoundError("Không tìm thấy cuộc trò chuyện.", code="CHAT_SESSION_NOT_FOUND")
    return session


def _history(db: Session, session_id: int) -> list[Turn]:
    rows = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.id.desc())
        .limit(settings.CHAT_HISTORY_MESSAGES)
    ).all()
    turns = [Turn("assistant" if row.role == ChatRole.ASSISTANT else "user", row.content) for row in reversed(rows)]
    # Gemini đòi lượt đầu là của người dùng.
    while turns and turns[0].role != "user":
        turns.pop(0)
    return turns


def _title(message: str) -> str:
    text = " ".join(message.split())
    return text if len(text) <= TITLE_LENGTH else text[: TITLE_LENGTH - 1].rsplit(" ", 1)[0] + "…"


# --- Trả lời (async, trong lúc stream) ---


async def stream_answer(prepared: PreparedChat, *, store: VectorStore, llm: LLM) -> AsyncIterator[tuple[str, Any]]:
    started = time.perf_counter()
    yield "session", {"session_id": prepared.session_id, "title": prepared.title}

    if not prepared.decision.allowed:
        yield "delta", {"text": prepared.decision.reply}
        message_id = await run_in_threadpool(_save_answer, prepared.session_id, prepared.decision.reply, [], started)
        yield "done", {"message_id": message_id, "latency_ms": _elapsed(started), "refused": True, "reason": prepared.decision.reason}
        return

    hits = await run_in_threadpool(
        store.search,
        _retrieval_query(prepared),
        event_id=prepared.event_id,
        top_k=settings.RAG_TOP_K,
        threshold=settings.RAG_SCORE_THRESHOLD,
    )
    sources = prompts.sources(hits)
    yield "sources", sources

    if not hits:
        reply = prompts.NOT_FOUND_REPLY.format(contact=settings.CHAT_SUPPORT_CONTACT)
        yield "delta", {"text": reply}
        message_id = await run_in_threadpool(_save_answer, prepared.session_id, reply, [], started)
        yield "done", {"message_id": message_id, "latency_ms": _elapsed(started), "refused": False}
        return

    system = prompts.system_prompt(
        event_name=prepared.event_name,
        status=status_label(EventStatus(prepared.event_status)),
        today=_today(),
        contact=settings.CHAT_SUPPORT_CONTACT,
    )
    turns = [*prepared.history, Turn("user", prompts.user_message(prepared.question, hits))]
    redactor = StreamRedactor(guard.allowed_numbers([hit.text for hit in hits]))
    parts: list[str] = []
    try:
        async for piece in llm.stream(system=system, turns=turns, hits=hits):
            safe = redactor.feed(piece)
            if safe:
                parts.append(safe)
                yield "delta", {"text": safe}
        tail = redactor.flush()
        if tail:
            parts.append(tail)
            yield "delta", {"text": tail}
    except LLMError as exc:
        yield "error", {"code": exc.code, "message": exc.message}
        return

    answer = "".join(parts).strip()
    if not answer:
        answer = prompts.EMPTY_REPLY
        yield "delta", {"text": answer}
    message_id = await run_in_threadpool(_save_answer, prepared.session_id, answer, sources, started)
    yield "done", {"message_id": message_id, "latency_ms": _elapsed(started), "refused": False}


def _retrieval_query(prepared: PreparedChat) -> str:
    """Câu hỏi nối tiếp ngắn ("còn ngày 2 thì sao?") ghép với câu hỏi trước để tìm đúng tài liệu."""
    if len(prepared.question.split()) >= SHORT_FOLLOW_UP_WORDS:
        return prepared.question
    previous = next((turn.text for turn in reversed(prepared.history) if turn.role == "user"), "")
    return f"{previous} {prepared.question}".strip()


def _save_answer(session_id: int, content: str, sources: list[dict], started: float) -> int:
    with session_scope() as db:
        message = ChatMessage(
            session_id=session_id,
            role=ChatRole.ASSISTANT,
            content=content,
            sources=json.dumps(sources, ensure_ascii=False) if sources else None,
            latency_ms=_elapsed(started),
            created_at=utcnow_iso(),
        )
        db.add(message)
        db.flush()
        return message.id


def _elapsed(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _today() -> str:
    now = utcnow().astimezone(VN_TZ)
    return f"{WEEKDAYS[now.weekday()]}, {now:%d/%m/%Y}"


# --- Lịch sử cho giao diện ---


def list_sessions(db: Session, *, user_id: int) -> list[dict[str, Any]]:
    rows = db.execute(
        select(ChatSession, func.count(ChatMessage.id), func.max(ChatMessage.created_at))
        .outerjoin(ChatMessage, ChatMessage.session_id == ChatSession.id)
        .where(ChatSession.user_id == user_id)
        .group_by(ChatSession.id)
        .order_by(func.coalesce(func.max(ChatMessage.created_at), ChatSession.created_at).desc())
        .limit(50)
    ).all()
    return [
        {"id": session.id, "title": session.title, "created_at": session.created_at, "updated_at": last_at, "message_count": count}
        for session, count, last_at in rows
    ]


def list_messages(db: Session, *, user_id: int, session_id: int) -> list[dict[str, Any]]:
    session = _get_session(db, user_id=user_id, session_id=session_id)
    return [
        {
            "id": message.id,
            "role": message.role,
            "content": message.content,
            "sources": json.loads(message.sources) if message.sources else [],
            "created_at": message.created_at,
        }
        for message in session.messages
    ]


def delete_session(db: Session, *, user_id: int, session_id: int) -> None:
    db.delete(_get_session(db, user_id=user_id, session_id=session_id))
    db.commit()
