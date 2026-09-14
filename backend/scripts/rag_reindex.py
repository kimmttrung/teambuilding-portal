# backend/scripts/rag_reindex.py
"""Nạp knowledge base của kỳ đang chạy vào vector store, rồi thử vài câu hỏi.

    py -3.13 scripts/rag_reindex.py                      # nạp lại
    py -3.13 scripts/rag_reindex.py --ask "Gala ở đâu?"  # nạp lại + xem tài liệu tìm được cho câu hỏi

Lần đầu tải mô hình embedding (~220 MB) vào data/models — mất khoảng một phút.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.core.database import session_scope  # noqa: E402
from app.rag.runtime import get_vector_store  # noqa: E402
from app.services import event_service, rag_index_service  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Nạp knowledge base cho trợ lý")
    parser.add_argument("--ask", action="append", default=[], help="Câu hỏi thử (lặp lại được)")
    args = parser.parse_args()

    store = get_vector_store()
    with session_scope() as db:
        event = event_service.get_active_event(db)
        if event is None:
            print("Chưa có kỳ nào đang chạy.")
            return 1
        # Copy ra biến thường TRƯỚC khi ra khỏi `with` (CLAUDE.md cạm bẫy #10).
        event_id, event_name = event.id, event.name
        result = rag_index_service.reindex(db, event=event, store=store)

    print(f"Kỳ: {event_name}")
    print(f"Tài liệu: {result['documents']} {result['by_source']}")
    print(f"Chunk: {result['chunks']} · {result['duration_ms']} ms · có thông tin hậu cần: {result['published_logistics']}")

    for question in args.ask:
        print(f"\n? {question}")
        hits = store.search(question, event_id=event_id, top_k=settings.RAG_TOP_K, threshold=settings.RAG_SCORE_THRESHOLD)
        if not hits:
            print("  (không có tài liệu nào vượt ngưỡng)")
        for hit in hits:
            print(f"  {hit.score:.2f} (vector {hit.vector_score:.2f}, từ khoá {hit.keyword_score:.2f}) · {hit.title} — {hit.heading}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
