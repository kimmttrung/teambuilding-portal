# backend/app/rag/embeddings.py
"""Embedding chạy LOCAL bằng fastembed (ONNX) — không tốn quota API, chạy offline, không cần torch.

Mô hình mặc định `paraphrase-multilingual-MiniLM-L12-v2`: đa ngôn ngữ (có tiếng Việt), 384 chiều, ~220 MB,
tải về một lần vào `EMBEDDING_CACHE_DIR`. KHÔNG dùng `all-MiniLM-L6-v2`: mô hình đó chỉ hiểu tiếng Anh.
"""

import threading
import warnings
from pathlib import Path
from typing import Protocol


class Embedder(Protocol):
    name: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class FastEmbedEmbedder:
    def __init__(self, model_name: str, cache_dir: Path) -> None:
        self.name = model_name
        self._cache_dir = cache_dir
        self._model = None
        self._lock = threading.Lock()

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return [[float(value) for value in vector] for vector in self._load().embed(texts)]

    def _load(self):
        # Nạp lười + khoá: lần đầu mất vài chục giây (tải mô hình), hai request đồng thời không nạp hai lần.
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from fastembed import TextEmbedding

                    self._cache_dir.mkdir(parents=True, exist_ok=True)
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", UserWarning)  # cảnh báo đổi cách pooling của fastembed
                        self._model = TextEmbedding(self.name, cache_dir=str(self._cache_dir))
        return self._model
