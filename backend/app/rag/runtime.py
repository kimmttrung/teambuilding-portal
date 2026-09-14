# backend/app/rag/runtime.py
"""Đối tượng dùng chung toàn tiến trình: vector store và LLM.

Tạo một lần (nạp mô hình embedding tốn vài chục giây, mở ChromaDB tốn tài nguyên), dùng làm FastAPI
dependency để test thay bằng bản giả: `app.dependency_overrides[get_vector_store] = lambda: fake`.
"""

import threading
from functools import lru_cache

from app.core.config import settings
from app.rag.embeddings import FastEmbedEmbedder
from app.rag.llm import LLM, ExtractiveLLM, GeminiLLM
from app.rag.vector_store import VectorStore

_store_lock = threading.Lock()
_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                embedder = FastEmbedEmbedder(settings.EMBEDDING_MODEL, settings.embedding_cache_path)
                _store = VectorStore(settings.chroma_path, embedder)
    return _store


@lru_cache
def get_llm() -> LLM:
    if not settings.GEMINI_API_KEY.strip():
        return ExtractiveLLM()
    return GeminiLLM(
        api_key=settings.GEMINI_API_KEY,
        model=settings.LLM_MODEL,
        max_output_tokens=settings.LLM_MAX_TOKENS,
        temperature=settings.LLM_TEMPERATURE,
        thinking_level=settings.LLM_THINKING_LEVEL,
    )
