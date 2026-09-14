# backend/app/rag/text.py
"""Xử lý chữ tiếng Việt dùng chung: bỏ dấu để so khớp, tách từ khoá."""

import re
import unicodedata

# Từ quá phổ biến, khớp được thì cũng không nói lên tài liệu nào liên quan.
STOPWORDS = frozenset(
    "la va cua co khong nhung cac mot nhu the nao gi o tai cho voi thi ma de duoc bi "
    "toi minh ban em anh chi a nhe vay ha nao may bao nhieu khi luc".split()
)


def normalize(text: str) -> str:
    """'Gala Dinner ở ĐÂU?' -> 'gala dinner o dau?'. Bỏ dấu, chữ thường, gộp khoảng trắng."""
    value = (text or "").lower().replace("đ", "d")
    value = unicodedata.normalize("NFD", value)
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    return " ".join(value.split())


def keywords(text: str) -> set[str]:
    """Từ khoá có nghĩa (≥ 2 ký tự, không phải stopword), đã bỏ dấu."""
    return {token for token in re.findall(r"[a-z0-9]+", normalize(text)) if len(token) >= 2 and token not in STOPWORDS}


def keyword_score(query: str, document: str) -> float:
    """Tỉ lệ từ khoá của câu hỏi có mặt trong tài liệu (0–1).

    Bù cho embedding ở những từ riêng: mã chuyến "VN1234", tên sảnh "Pearl", "check-in".
    """
    wanted = keywords(query)
    if not wanted:
        return 0.0
    return len(wanted & keywords(document)) / len(wanted)
