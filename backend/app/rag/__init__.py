# backend/app/rag/__init__.py
"""Chatbot RAG "Tibi" (docs/06-rag-chatbot.md, docs/11-rag-backend-guide.md).

Luồng: câu hỏi → guard (chặn câu hỏi về dữ liệu cá nhân / tấn công prompt) → retrieve từ vector store
(chỉ tài liệu CÔNG KHAI) → prompt → Gemini stream → che số nhạy cảm → SSE.

Quy tắc phụ thuộc: `api → services → rag → models`. Module trong `rag` không import `api`.
"""
