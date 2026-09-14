# backend/app/rag/vector_store.py
"""Vector store ChromaDB: một collection `tb_public_knowledge`, lọc theo `event_id`.

Chỉ chứa chunk từ `knowledge.build_documents` — tài liệu công khai. Không có API nào ghi dữ liệu khác vào đây.

Xếp hạng lai: điểm = 0.7 × độ tương đồng vector (cosine) + 0.3 × tỉ lệ từ khoá khớp. Embedding hiểu
"hủy đăng ký có mất tiền không" ≈ "phí huỷ"; từ khoá bắt những từ riêng embedding hay bỏ lỡ
("VN1234", "check-in", "Pearl").
"""

import logging
import threading
from dataclasses import dataclass
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.rag.chunking import Chunk
from app.rag.embeddings import Embedder
from app.rag.text import keyword_score

logger = logging.getLogger(__name__)

COLLECTION = "tb_public_knowledge"
VECTOR_WEIGHT = 0.7
KEYWORD_WEIGHT = 0.3


@dataclass(frozen=True)
class SearchHit:
    source_type: str
    source_id: str
    title: str
    heading: str
    text: str
    score: float
    vector_score: float
    keyword_score: float


class VectorStore:
    def __init__(self, path: Path, embedder: Embedder) -> None:
        path.mkdir(parents=True, exist_ok=True)
        self._embedder = embedder
        self._lock = threading.Lock()
        # Tắt telemetry: không gửi thông tin sử dụng ra ngoài.
        self._client = chromadb.PersistentClient(path=str(path), settings=ChromaSettings(anonymized_telemetry=False))
        self._collection = self._open_collection()

    def _open_collection(self):
        collection = self._client.get_or_create_collection(
            COLLECTION, metadata={"hnsw:space": "cosine", "embedding_model": self._embedder.name}
        )
        # Đổi mô hình embedding thì vector cũ vô nghĩa (khác số chiều / khác không gian): xoá để nạp lại.
        if (collection.metadata or {}).get("embedding_model") != self._embedder.name:
            logger.warning("Đổi mô hình embedding → xoá collection %s, cần re-index", COLLECTION)
            self._client.delete_collection(COLLECTION)
            collection = self._client.create_collection(
                COLLECTION, metadata={"hnsw:space": "cosine", "embedding_model": self._embedder.name}
            )
        return collection

    def replace_event(self, event_id: int, chunks: list[Chunk]) -> int:
        """Xoá toàn bộ chunk cũ của kỳ rồi nạp bộ mới — tài liệu bị xoá ở DB cũng biến khỏi vector store."""
        vectors = self._embedder.embed([chunk.embedding_text for chunk in chunks])
        with self._lock:
            self._collection.delete(where={"event_id": event_id})
            if chunks:
                self._collection.add(
                    ids=[f"{event_id}:{chunk.source_id}:{chunk.index}" for chunk in chunks],
                    embeddings=vectors,
                    documents=[chunk.text for chunk in chunks],
                    metadatas=[
                        {
                            "event_id": event_id,
                            "source_type": chunk.source_type,
                            "source_id": chunk.source_id,
                            "title": chunk.title,
                            "heading": chunk.heading,
                        }
                        for chunk in chunks
                    ],
                )
        return len(chunks)

    def count(self, event_id: int) -> int:
        return len(self._collection.get(where={"event_id": event_id}, include=[])["ids"])

    def search(self, query: str, *, event_id: int, top_k: int, threshold: float) -> list[SearchHit]:
        total = self.count(event_id)
        if total == 0 or not query.strip():
            return []
        result = self._collection.query(
            query_embeddings=self._embedder.embed([query]),
            n_results=min(total, top_k * 3),  # lấy dư rồi xếp lại bằng điểm lai
            where={"event_id": event_id},
            include=["documents", "metadatas", "distances"],
        )
        hits = []
        for text, meta, distance in zip(result["documents"][0], result["metadatas"][0], result["distances"][0], strict=True):
            vector = max(0.0, 1.0 - float(distance))  # cosine distance → similarity
            keyword = keyword_score(query, f"{meta['title']} {meta['heading']} {text}")
            score = VECTOR_WEIGHT * vector + KEYWORD_WEIGHT * keyword
            if score >= threshold:
                hits.append(
                    SearchHit(meta["source_type"], meta["source_id"], meta["title"], meta["heading"], text,
                              round(score, 4), round(vector, 4), round(keyword, 4))
                )
        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:top_k]
