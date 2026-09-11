"""Kiểm thử hàm tiện ích của script seed.

Email sinh ra phải thuần ASCII: email chứa dấu tiếng Việt thì máy chủ SMTP
từ chối, và lỗi chỉ lộ ra ở bước gửi mail chứ không phải lúc tạo dữ liệu.
"""

from scripts.seed import strip_accents, unique_email

VIETNAMESE_NAMES = [
    "Nguyễn Văn Cường",
    "Đặng Thị Ngọc Ánh",
    "Vũ Đức Hưng",
    "Lý Thị Tuyết Mỵ",
    "Phạm Hữu Đạt",
    "Trần Thị Quỳnh Như",
    "Hoàng Xuân Thắng",
    "Đỗ Thị Ửng",
]


def test_strip_accents_removes_all_vietnamese_marks():
    for name in VIETNAMESE_NAMES:
        result = strip_accents(name)
        assert result.isascii(), f"{name} -> {result} vẫn còn ký tự ngoài ASCII"


def test_strip_accents_handles_d_with_stroke():
    """đ/Đ không phải dấu phụ nên chuẩn hoá Unicode không xử lý được, phải thay tay."""
    assert strip_accents("Đặng") == "Dang"
    assert strip_accents("đường") == "duong"


def test_generated_emails_are_ascii_and_unique():
    emails = [unique_email(name, index) for index, name in enumerate(VIETNAMESE_NAMES, start=1)]
    for email in emails:
        assert email.isascii(), email
        assert email.endswith("@company.vn")
        assert " " not in email
    assert len(set(emails)) == len(emails)


def test_email_format_follows_convention():
    """Quy ước: <tên><chữ cái đầu của họ><số thứ tự>@company.vn"""
    assert unique_email("Nguyễn Văn Cường", 7) == "cuongn007@company.vn"
