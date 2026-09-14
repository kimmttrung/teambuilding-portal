# backend/app/services/rag_index_service.py
"""Nạp knowledge base của một kỳ vào vector store (re-index).

Khi nào chạy: sau khi BTC sửa quy định/lịch trình/thông báo, và NHẤT LÀ ngay sau khi công bố thông tin —
lúc đó chuyến bay, xe, khách sạn, Gala mới được đưa vào knowledge base. Chạy lại bao nhiêu lần cũng được:
mỗi lần thay toàn bộ chunk của kỳ.
"""

import json
import time
from collections import Counter
from typing import Any

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.audit import AuditLog
from app.models.content import ItineraryItem, PolicyDocument
from app.models.enums import EventStatus
from app.models.event import Event
from app.models.user import User
from app.rag.chunking import chunk_document
from app.rag.knowledge import build_documents
from app.rag.llm import LLM
from app.rag.vector_store import VectorStore
from app.services import audit_service


def reindex(
    db: Session, *, event: Event, store: VectorStore, actor: User | None = None, ip_address: str | None = None
) -> dict[str, Any]:
    started = time.perf_counter()
    event_id = event.id
    published = EventStatus(event.status).at_least(EventStatus.INFORMATION_PUBLISHED)

    documents = build_documents(db, event)
    chunks = [chunk for doc in documents for chunk in chunk_document(doc, max_chars=settings.RAG_CHUNK_CHARS)]
    store.replace_event(event_id, chunks)

    db.execute(
        update(PolicyDocument)
        .where(or_(PolicyDocument.event_id == event_id, PolicyDocument.event_id.is_(None)))
        .values(is_indexed=True)
    )
    db.execute(update(ItineraryItem).where(ItineraryItem.event_id == event_id).values(is_indexed=True))

    result = {
        "event_id": event_id,
        "documents": len(documents),
        "chunks": len(chunks),
        "by_source": dict(Counter(doc.source_type for doc in documents)),
        "published_logistics": published,
        "duration_ms": int((time.perf_counter() - started) * 1000),
    }
    audit_service.log(
        db,
        action="rag.reindexed",
        entity_type="event",
        entity_id=event_id,
        actor_id=actor.id if actor else None,
        event_id=event_id,
        after={key: value for key, value in result.items() if key != "duration_ms"},
        ip_address=ip_address,
    )
    db.commit()
    return result


def status(db: Session, *, event: Event, store: VectorStore, llm: LLM) -> dict[str, Any]:
    last = db.scalar(
        select(AuditLog)
        .where(AuditLog.action == "rag.reindexed", AuditLog.event_id == event.id)
        .order_by(AuditLog.id.desc())
        .limit(1)
    )
    return {
        "enabled": True,
        "llm_configured": llm.configured,
        "model": llm.name,
        "embedding_model": settings.EMBEDDING_MODEL,
        "indexed_chunks": store.count(event.id),
        "last_indexed_at": last.created_at if last else None,
        "last_index_published_logistics": json.loads(last.after_data).get("published_logistics") if last and last.after_data else None,
    }
