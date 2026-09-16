"""Schema cho tài liệu chương trình (`policy_documents`): FAQ và hướng dẫn.

Nội dung là markdown và đi thẳng vào vector store của chatbot — chỉ chứa thông tin công khai.
"""

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PolicyDocType


class PolicyDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int | None
    doc_type: PolicyDocType
    title: str
    content: str
    version: str
    is_indexed: bool
    updated_at: str

    # Suy ra, không lưu trong bảng: tài liệu dùng chung áp cho mọi kỳ nên BTC không sửa được.
    is_shared: bool = False
    can_edit: bool = True


class PolicyDocumentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_type: PolicyDocType
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)
    version: str = Field(default="v1", max_length=16)


class PolicyDocumentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_type: PolicyDocType | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    content: str | None = Field(default=None, min_length=1)
    version: str | None = Field(default=None, max_length=16)
