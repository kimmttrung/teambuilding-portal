# backend/app/schemas/chat.py
"""Schema chatbot RAG (docs/04-api-spec.md §11)."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_MESSAGE_LENGTH = 1000


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: int | None = None
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)

    @field_validator("message")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Câu hỏi đang trống.")
        return value


class ChatSource(BaseModel):
    index: int
    title: str
    source_type: str


class ChatSessionOut(BaseModel):
    id: int
    title: str | None
    created_at: str
    updated_at: str | None
    message_count: int


class ChatMessageOut(BaseModel):
    id: int
    role: str
    content: str
    sources: list[ChatSource] = Field(default_factory=list)
    created_at: str


class ChatStatusOut(BaseModel):
    enabled: bool
    llm_configured: bool
    model: str
    embedding_model: str
    indexed_chunks: int


class RagStatusOut(ChatStatusOut):
    last_indexed_at: str | None = None
    last_index_published_logistics: bool | None = None


class RagReindexOut(BaseModel):
    event_id: int
    documents: int
    chunks: int
    by_source: dict[str, int]
    published_logistics: bool
    duration_ms: int
