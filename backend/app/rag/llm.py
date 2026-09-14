# backend/app/rag/llm.py
"""Gọi mô hình ngôn ngữ.

- `GeminiLLM`: Google Gemini qua SDK `google-genai` (gói miễn phí ở aistudio.google.com).
- `ExtractiveLLM`: chưa có `GEMINI_API_KEY` → trả lời bằng trích đoạn tài liệu, không gọi mạng. Để demo/CI
  chạy được và frontend không gãy khi thiếu key.

Lưu ý gói miễn phí: Google có thể dùng nội dung gửi lên để cải thiện sản phẩm. Vì vậy chỉ gửi câu hỏi +
tài liệu CÔNG KHAI — không bao giờ gửi dữ liệu cá nhân (guard + knowledge base đảm bảo điều đó).
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Protocol

from app.rag.prompts import Turn
from app.rag.vector_store import SearchHit

logger = logging.getLogger(__name__)


class LLMError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class LLM(Protocol):
    name: str
    configured: bool

    def stream(self, *, system: str, turns: list[Turn], hits: list[SearchHit]) -> AsyncIterator[str]: ...


class GeminiLLM:
    configured = True

    def __init__(self, *, api_key: str, model: str, max_output_tokens: int, temperature: float, thinking_level: str) -> None:
        from google import genai

        self.name = model
        self._client = genai.Client(api_key=api_key)
        self._max_output_tokens = max_output_tokens
        self._temperature = temperature
        self._thinking_level = thinking_level

    async def stream(self, *, system: str, turns: list[Turn], hits: list[SearchHit]) -> AsyncIterator[str]:
        from google.genai import errors, types

        contents = [
            types.Content(role="model" if turn.role == "assistant" else "user", parts=[types.Part.from_text(text=turn.text)])
            for turn in turns
        ]
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=self._temperature,
            max_output_tokens=self._max_output_tokens,
            # Hỏi đáp tra cứu không cần "suy nghĩ": 0 = tắt, trả lời nhanh và không đốt token (Gemini 2.5 Flash).
            thinking_config=types.ThinkingConfig(thinking_level=self._thinking_level),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),

        )
        try:
            response = await self._client.aio.models.generate_content_stream(model=self.name, contents=contents, config=config)
            async for chunk in response:
                if chunk.text:
                    yield chunk.text
        except errors.APIError as exc:
            logger.warning("Gemini lỗi %s %s: %s", exc.code, exc.status, exc.message)
            raise _to_llm_error(exc) from exc
        except (TimeoutError, OSError) as exc:
            raise LLMError("LLM_UNAVAILABLE", "Không kết nối được máy chủ AI. Thử lại sau ít phút.") from exc


def _to_llm_error(exc) -> LLMError:
    if exc.code == 404:
        return LLMError("LLM_NOT_CONFIGURED", "Model AI đang cấu hình không còn khả dụng. Báo Ban tổ chức đổi LLM_MODEL.")
    if exc.code == 429:
        return LLMError("LLM_QUOTA_EXCEEDED", "Trợ lý đang hết lượt miễn phí hoặc quá tải. Thử lại sau ít phút.")
    if exc.code in (400, 401, 403) and "key" in (exc.message or "").lower():
        return LLMError("LLM_NOT_CONFIGURED", "Khoá API của trợ lý không hợp lệ. Báo Ban tổ chức kiểm tra GEMINI_API_KEY.")
    if exc.code and exc.code >= 500:
        return LLMError("LLM_UNAVAILABLE", "Máy chủ AI đang gặp sự cố. Thử lại sau ít phút.")
    return LLMError("LLM_FAILED", "Trợ lý chưa trả lời được câu này. Thử hỏi lại theo cách khác nhé.")


class ExtractiveLLM:
    """Chế độ thử: không gọi AI, đưa ra đoạn tài liệu liên quan nhất."""

    name = "extractive"
    configured = False

    async def stream(self, *, system: str, turns: list[Turn], hits: list[SearchHit]) -> AsyncIterator[str]:
        parts = ["(Chế độ thử — chưa bật AI) Đây là thông tin liên quan nhất mình tìm được:\n"]
        for hit in hits[:2]:
            body = hit.text if len(hit.text) <= 600 else hit.text[:600].rsplit(" ", 1)[0] + "…"
            parts.append(f"\n**{hit.title}**\n{body}\n")
        for part in parts:
            yield part
            await asyncio.sleep(0)
