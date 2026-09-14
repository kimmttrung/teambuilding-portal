# backend/app/rag/guard.py
"""Lớp chặn trước và sau khi gọi mô hình.

Đây là lớp phụ. Lớp bảo vệ CHÍNH nằm ở kiến trúc (ADR-004): knowledge base không chứa dữ liệu cá nhân và
trợ lý không có tool nào đọc DB — bẻ được prompt cũng không có gì để lấy. Guard thêm hai việc:

1. `check_question`: câu tấn công prompt / hỏi thông tin cá nhân của người khác → từ chối NGAY, không gửi
   câu hỏi lên Gemini (vừa đỡ lộ, vừa đỡ tốn quota). Câu hỏi hành trình của chính mình → chỉ sang trang
   Hành trình, vì trợ lý không đọc dữ liệu cá nhân.
2. `StreamRedactor`: che dãy số giống CCCD/CMND và số điện thoại không có trong tài liệu, ngay trong lúc
   stream — kể cả khi con số bị cắt làm hai mảnh.

So khớp trên chữ đã bỏ dấu (`text.normalize`) nên "số điện thoại" và "so dien thoai" như nhau.
"""

import re
from dataclasses import dataclass

from app.rag.text import normalize

INJECTION_REPLY = (
    "Mình chỉ hỗ trợ câu hỏi về chương trình Team Building và không thay đổi được nguyên tắc hoạt động. "
    "Bạn muốn hỏi gì về lịch trình, khách sạn hay Gala Dinner?"
)
PRIVACY_REPLY = (
    "Vì lý do bảo mật, mình không cung cấp thông tin cá nhân của bất kỳ ai (CCCD, số điện thoại, ngày sinh, "
    "chỗ ở, chuyến bay hay chỗ ngồi của một người cụ thể). Bạn có thể hỏi mình về lịch trình, chuyến bay, xe, "
    "khách sạn, Gala Dinner hay quy định chung nhé."
)
OWN_JOURNEY_REPLY = (
    "Để bảo vệ dữ liệu cá nhân, mình không tra cứu thông tin riêng của từng người. Chuyến bay, xe, phòng và "
    "chỗ ngồi Gala **của bạn** nằm ở mục **Hành trình của tôi** (menu Hành trình) — hiện sau khi Ban tổ chức "
    "công bố. Thông tin hồ sơ (CCCD, số điện thoại) xem và sửa ở mục **Hồ sơ cá nhân**."
)

_INJECTION = [
    r"bo qua (moi |tat ca |cac |het )?(huong dan|chi dan|quy tac|nguyen tac|lenh|yeu cau)",
    r"\bignore (all |the |any )?(previous|above|prior|instructions)",
    r"system prompt|prompt he thong|(in|hien) ra (huong dan|prompt|cau lenh)",
    r"\b(select|insert|update|delete|drop)\b.{0,40}\b(from|into|table|users|where)\b",
    r"\bunion\s+select\b",
    r"\b(dong vai|gia vo|pretend|act as|jailbreak|developer mode)\b",
]
# Trường luôn là dữ liệu cá nhân, dù của ai.
_PERSONAL_FIELD = (
    r"(cccd|cmnd|can cuoc|ho chieu|so dinh danh|ngay sinh|sinh nhat|so dien thoai|\bsdt\b|\bso dt\b|dien thoai"
    r"|zalo|email|dia chi nha|dia chi|mat khau|luong|thu nhap)"
)
# Hỏi thông tin liên hệ của tổ chức là hợp lệ: "số điện thoại khách sạn", "email BTC".
_ORG = r"(khach san|resort|le tan|\bbtc\b|ban to chuc|hotline|nha xe|hang bay|san bay|cong ty|nha hang)"
_OTHER_PERSON = (
    r"\b(cua|cho|ve)\s+(anh|chi|em|ban|ong|ba|co|chu|nguoi|nhan vien|cbnv|dong nghiep|sep|moi nguoi|tat ca|ca team|team)\b"
    r"|\b(truong xe|tai xe|truong nhom|truong phong|dong nghiep|nhan vien|thanh vien|hanh khach)\b"
)
# Tên riêng: "anh Trung", "chị Lan" (chữ hoa sau danh xưng) hoặc họ tên đủ ba chữ viết hoa.
_TITLE_NAME = re.compile(r"\b(anh|chị|chi|em|bạn|ban|cô|co|chú|chu|ông|ong|bà|ba|sếp|sep)\s+(\w+)", re.IGNORECASE)
_FULL_NAME = re.compile(r"\b(\w+)\s+(\w+)\s+(\w+)\b")
_VALUE_ASK = r"(la gi|la bao nhieu|bao nhieu|la so|so may|cho (toi|minh|em|tui) (xin|biet|xem)|\bxin\b|tra cuu|tim giup|cho biet)"
_LISTING = r"(danh sach|toan bo|tat ca|liet ke|xuat|in ra).{0,25}(nhan vien|cbnv|thanh vien|nguoi tham gia|hanh khach|so dien thoai|cccd|email|phong|nguoi)"
_WHO = r"\bai (o|ngoi|di|bay|cung|chung|nam|dang ky)\b"
_MINE = r"\b(toi|minh|em|tui|tao)\b"
# "ban" trần không có ở đây: bỏ dấu thì "bàn" (bàn tiệc) và "bạn" giống hệt nhau.
_JOURNEY = r"(chuyen bay|bay chuyen|chuyen nao|\bxe\b|phong|\bghe\b|ngoi ban|ban tiec|ban so|ban nao|cho ngoi|hanh trinh|diem don|gio tap trung)"
_QUESTION = r"(nao|may|o dau|\bgi\b|bao gio|luc nao|khi nao|chua|the nao|\?)"


@dataclass(frozen=True)
class GuardDecision:
    allowed: bool
    reason: str | None = None  # prompt_injection | personal_data | own_journey
    reply: str | None = None


def check_question(question: str) -> GuardDecision:
    q = normalize(question)
    if any(re.search(pattern, q) for pattern in _INJECTION):
        return GuardDecision(False, "prompt_injection", INJECTION_REPLY)
    if re.search(_LISTING, q) or re.search(_WHO, q):
        return GuardDecision(False, "personal_data", PRIVACY_REPLY)

    org = re.search(_ORG, q)
    mine = re.search(_MINE, q)
    other = _mentions_person(question, q)

    # Trường cá nhân (CCCD, SĐT, ngày sinh…): của người khác → từ chối; của mình → chỉ sang Hồ sơ/Hành trình.
    if re.search(_PERSONAL_FIELD, q) and not org:
        if other:
            return GuardDecision(False, "personal_data", PRIVACY_REPLY)
        if re.search(_VALUE_ASK, q):
            return GuardDecision(False, "own_journey", OWN_JOURNEY_REPLY) if mine else GuardDecision(False, "personal_data", PRIVACY_REPLY)

    # Hành trình của một người cụ thể (chuyến bay, xe, phòng, ghế).
    if re.search(_JOURNEY, q) and not org:
        if other and not mine:
            return GuardDecision(False, "personal_data", PRIVACY_REPLY)
        if mine and re.search(_QUESTION, q):
            return GuardDecision(False, "own_journey", OWN_JOURNEY_REPLY)
    return GuardDecision(True)


def _mentions_person(question: str, normalized: str) -> bool:
    if re.search(_OTHER_PERSON, normalized):
        return True
    if any(match.group(2)[:1].isupper() for match in _TITLE_NAME.finditer(question)):
        return True
    # "Nguyễn Thị Lan": ba chữ liền nhau đều viết hoa, không phải đầu câu kiểu "Gala Dinner" (hai chữ).
    return any(all(word[:1].isupper() for word in match.groups()) for match in _FULL_NAME.finditer(question))


# --- Che số nhạy cảm trong câu trả lời ---

_ID_NUMBER = re.compile(r"(?<!\d)(?:\d{12}|\d{9})(?!\d)")
_PHONE = re.compile(r"(?<![\d+])(?:\+84|84|0)(?:[\s.\-]?\d){8,10}(?!\d)")
_NUMBERISH_TAIL = re.compile(r"[+\d][\d\s.\-]*$")


def phone_key(text: str) -> str:
    digits = re.sub(r"\D", "", text)
    return "0" + digits[2:] if digits.startswith("84") else digits


def allowed_numbers(texts: list[str]) -> frozenset[str]:
    """Số điện thoại xuất hiện sẵn trong tài liệu (lễ tân khách sạn) được phép nhắc lại."""
    return frozenset(phone_key(match.group()) for text in texts for match in _PHONE.finditer(text))


def redact(text: str, allowed: frozenset[str] = frozenset()) -> str:
    text = _PHONE.sub(lambda match: match.group() if phone_key(match.group()) in allowed else "[số điện thoại đã ẩn]", text)
    return _ID_NUMBER.sub("[số giấy tờ đã ẩn]", text)


class StreamRedactor:
    """Che số trên luồng chữ. Giữ lại phần đuôi trông như con số đang viết dở cho tới khi chắc chắn."""

    MAX_HOLD = 24

    def __init__(self, allowed: frozenset[str] = frozenset()) -> None:
        self._allowed = allowed
        self._pending = ""

    def feed(self, piece: str) -> str:
        text = self._pending + piece
        match = _NUMBERISH_TAIL.search(text)
        cut = match.start() if match and len(text) - match.start() <= self.MAX_HOLD else len(text)
        self._pending = text[cut:]
        return redact(text[:cut], self._allowed)

    def flush(self) -> str:
        text, self._pending = self._pending, ""
        return redact(text, self._allowed)
