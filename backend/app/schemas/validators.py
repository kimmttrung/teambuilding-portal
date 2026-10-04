"""Luật kiểm dữ liệu dùng chung cho mọi schema nhận từ client.

Một chỗ duy nhất: trước đây hồ sơ cá nhân kiểm số điện thoại còn form của BTC và import Excel thì
không, nên cùng một cột trong DB có nơi chặn chữ, nơi nhận chữ (đợt kiểm thử F11). Schema chỉ khai
kiểu (`MobilePhone`, `HttpUrl`…); service nào phải so với dữ liệu ĐANG LƯU thì gọi thẳng các hàm
`check_*` ở cuối file.
"""

import re
from datetime import date, datetime
from typing import Annotated

from pydantic import AfterValidator, Field

MIN_AGE = 18
MAX_AGE = 70

_MOBILE = re.compile(r"0\d{9,10}")
_CONTACT_ALLOWED = re.compile(r"[0-9+()\-.\s]+")
_CLOCK = re.compile(r"([01]\d|2[0-3]):[0-5]\d")


# --- Số điện thoại ---


def check_mobile_phone(value: str) -> str:
    """Di động Việt Nam: 10–11 số, bắt đầu bằng 0. Dấu cách / chấm / gạch chỉ để dễ đọc."""
    if not _MOBILE.fullmatch(re.sub(r"[\s.-]", "", value)):
        raise ValueError("Số điện thoại phải là 10-11 số và bắt đầu bằng 0")
    return value.strip()


def check_contact_phone(value: str) -> str:
    """Số liên hệ của tổ chức (lễ tân, tổng đài): có thể là số bàn, có mã vùng hoặc +84."""
    digits = re.sub(r"\D", "", value)
    if not _CONTACT_ALLOWED.fullmatch(value) or not 8 <= len(digits) <= 15:
        raise ValueError("Số điện thoại chỉ gồm 8-15 chữ số (cho phép dấu cách, +, -, ., ngoặc)")
    return value.strip()


# --- Ngày, giờ ---


def check_calendar_date(value: str) -> str:
    """`YYYY-MM-DD` và phải là ngày có thật — regex một mình vẫn nhận 2027-02-31."""
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Ngày không tồn tại trong lịch.") from exc
    return value


def check_past_date(value: str) -> str:
    check_calendar_date(value)
    if date.fromisoformat(value) > date.today():
        raise ValueError("Ngày không thể ở tương lai")
    return value


def check_birth_date(value: str) -> str:
    """Ngày sinh của CBNV: tuổi từ 18 đến 70 tính tới hôm nay."""
    check_past_date(value)
    born = date.fromisoformat(value)
    today = date.today()
    age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    if not MIN_AGE <= age <= MAX_AGE:
        raise ValueError(f"Ngày sinh không hợp lệ: tuổi phải từ {MIN_AGE} đến {MAX_AGE}")
    return value


def check_clock_time(value: str) -> str:
    if not _CLOCK.fullmatch(value):
        raise ValueError("Giờ phải có dạng HH:MM, từ 00:00 đến 23:59")
    return value


def check_iso_datetime_tz(value: str) -> str:
    """ISO-8601 CÓ múi giờ, chuẩn hoá về UTC.

    Thiếu múi giờ thì server coi là UTC trong khi người nhập nghĩ giờ Việt Nam — lệch 7 tiếng mà
    không ai báo lỗi.
    """
    from app.core.timeutils import to_iso

    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            "Thời gian phải là ISO-8601 có múi giờ, ví dụ 2026-10-15T06:30:00+07:00"
        ) from exc
    if parsed.tzinfo is None:
        raise ValueError("Thời gian thiếu múi giờ, ví dụ 2026-10-15T06:30:00+07:00")
    return to_iso(parsed)


# --- Liên kết ---


def check_http_url(value: str) -> str:
    """Chỉ nhận http(s): `javascript:` hay `data:` trong href là mã chạy khi người dùng bấm."""
    value = value.strip()
    if not re.match(r"^https?://[^\s]+$", value, flags=re.IGNORECASE):
        raise ValueError("Liên kết phải bắt đầu bằng http:// hoặc https://")
    return value


# --- Giấy tờ ---


def check_id_card(number: str, id_card_type: str | None) -> None:
    """Số giấy tờ phải khớp loại: CCCD 12 số (CMND cũ 9 số), hộ chiếu 6–12 chữ và số.

    Chưa biết loại thì nhận bất kỳ dạng nào trong hai dạng trên — nhưng không nhận chuỗi tuỳ ý:
    số giấy tờ sai là không xuất được vé máy bay.
    """
    compact = re.sub(r"\s", "", number)
    is_cccd = bool(re.fullmatch(r"(?:\d{9}|\d{12})", compact))
    is_passport = bool(re.fullmatch(r"[A-Za-z0-9]{6,12}", compact))
    if id_card_type == "passport":
        if not is_passport:
            raise ValueError("Số hộ chiếu gồm 6-12 chữ và số")
    elif id_card_type == "cccd":
        if not is_cccd:
            raise ValueError("Số CCCD gồm 12 số (CMND cũ 9 số)")
    elif not (is_cccd or is_passport):
        raise ValueError("Số giấy tờ không hợp lệ: CCCD 12 số hoặc hộ chiếu 6-12 chữ và số")


def check_issue_after_birth(issue_date: str | None, birth_date: str | None) -> None:
    if issue_date and birth_date and issue_date < birth_date:
        raise ValueError("Ngày cấp giấy tờ không thể trước ngày sinh")


# --- Kiểu dùng trong schema ---

MobilePhone = Annotated[str, Field(max_length=32), AfterValidator(check_mobile_phone)]
ContactPhone = Annotated[str, Field(max_length=32), AfterValidator(check_contact_phone)]
CalendarDate = Annotated[
    str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$"), AfterValidator(check_calendar_date)
]
PastDate = Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$"), AfterValidator(check_past_date)]
BirthDate = Annotated[
    str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$"), AfterValidator(check_birth_date)
]
ClockTime = Annotated[str, AfterValidator(check_clock_time)]
IsoDateTimeTz = Annotated[str, AfterValidator(check_iso_datetime_tz)]
HttpUrl = Annotated[str, Field(max_length=512), AfterValidator(check_http_url)]
