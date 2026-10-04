# backend/tests/rag_fakes.py
"""Bản giả cho test RAG: không tải mô hình embedding, không gọi Gemini."""

import hashlib
import math

from app.rag.llm import LLMError
from app.rag.text import keywords


class HashEmbedder:
    """Embedding giả, tất định: túi từ khoá băm vào 256 chiều. Câu chung từ khoá thì gần nhau."""

    name = "test-hash-embedder"

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            vector = [0.0] * 256
            for token in keywords(text):
                vector[int(hashlib.md5(token.encode()).hexdigest(), 16) % 256] += 1.0
            norm = math.sqrt(sum(value * value for value in vector)) or 1.0
            vectors.append([value / norm for value in vector])
        return vectors


class FakeLLM:
    """Trả lời theo kịch bản, ghi lại mọi thứ được gửi lên để test kiểm tra không lộ dữ liệu."""

    name = "fake-llm"
    configured = True

    def __init__(self, pieces: list[str] | None = None, error: LLMError | None = None) -> None:
        self.pieces = pieces or ["Gala Dinner diễn ra ", "tại **Sảnh Pearl**."]
        self.error = error
        self.calls: list[dict] = []

    async def stream(self, *, system, turns, hits):
        self.calls.append({"system": system, "turns": turns, "hits": hits})
        if self.error:
            raise self.error
        for piece in self.pieces:
            yield piece
