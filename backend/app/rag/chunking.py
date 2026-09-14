# backend/app/rag/chunking.py
"""Cắt tài liệu markdown thành các đoạn (chunk) để embedding.

- Tách theo heading (#, ##, ###): mỗi mục một đoạn, giữ tiêu đề mục làm ngữ cảnh.
- Mục dài hơn `max_chars` thì tách tiếp theo khối văn bản (ngăn bởi dòng trống), rồi theo dòng — không
  cắt ngang câu. Một cặp hỏi–đáp trong FAQ vì vậy luôn nằm chung một đoạn.
- `overlap`: đoạn sau lặp lại phần cuối đoạn trước để câu trả lời nằm vắt qua ranh giới vẫn tìm thấy.
"""

import re
from dataclasses import dataclass

from app.rag.knowledge import KnowledgeDoc

HEADING = re.compile(r"^(#{1,3})\s+(.+?)\s*$")


@dataclass(frozen=True)
class Chunk:
    source_type: str
    source_id: str
    title: str
    heading: str
    text: str
    index: int  # thứ tự trong tài liệu, dùng làm một phần id

    @property
    def embedding_text(self) -> str:
        """Chữ đem đi embedding: kèm tên tài liệu + mục để đoạn ngắn vẫn đủ nghĩa."""
        header = self.title if not self.heading or self.heading == self.title else f"{self.title} — {self.heading}"
        return f"{header}\n{self.text}"


def chunk_document(doc: KnowledgeDoc, *, max_chars: int = 1200, overlap: int = 200) -> list[Chunk]:
    pieces: list[tuple[str, str]] = []
    for heading, body in _sections(doc.text):
        for text in _split(body, max_chars=max_chars, overlap=overlap):
            pieces.append((heading, text))
    return [
        Chunk(doc.source_type, doc.source_id, doc.title, heading or doc.title, text, index)
        for index, (heading, text) in enumerate(pieces)
    ]


def _sections(markdown: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, list[str]]] = [("", [])]
    for line in markdown.splitlines():
        match = HEADING.match(line)
        if match:
            sections.append((match.group(2), [line]))
        else:
            sections[-1][1].append(line)
    # Bỏ mục chỉ có mỗi dòng tiêu đề ("## Quy định" ngay trên "### 1. Đăng ký"): không có gì để tìm.
    return [
        (heading, "\n".join(lines).strip())
        for heading, lines in sections
        if any(line.strip() and not HEADING.match(line) for line in lines)
    ]


def _split(text: str, *, max_chars: int, overlap: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    # Đơn vị nhỏ nhất không cắt: khối văn bản; khối nào vẫn quá dài thì hạ xuống từng dòng.
    units: list[str] = []
    for block in re.split(r"\n\s*\n", text):
        block = block.strip()
        if not block:
            continue
        units.extend([block] if len(block) <= max_chars else [line for line in block.splitlines() if line.strip()])

    chunks: list[str] = []
    current = ""
    for unit in units:
        candidate = f"{current}\n\n{unit}" if current else unit
        if len(candidate) <= max_chars or not current:
            current = candidate
            continue
        chunks.append(current)
        tail = _tail(current, overlap)
        current = f"{tail}\n\n{unit}" if tail and len(tail) + len(unit) + 2 <= max_chars else unit
    if current:
        chunks.append(current)
    return chunks


def _tail(text: str, size: int) -> str:
    """Phần cuối ~`size` ký tự, bắt đầu ở đầu một dòng để không mở đoạn bằng nửa câu."""
    if size <= 0 or len(text) <= size:
        return ""
    cut = text.find("\n", len(text) - size)
    return text[cut + 1 :].strip() if cut != -1 else ""
