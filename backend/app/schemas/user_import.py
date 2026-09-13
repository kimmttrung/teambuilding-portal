"""Schema import danh sách CBNV từ Excel (bước 21)."""

from pydantic import BaseModel, Field

from app.schemas.accommodation import ImportRowError


class CreatedAccount(BaseModel):
    """Tài khoản vừa tạo kèm mật khẩu tạm — chỉ có trong response của lần ghi thật."""

    employee_code: str
    full_name: str
    email: str
    temporary_password: str


class UserImportResult(BaseModel):
    dry_run: bool
    committed: bool = False
    total_rows: int
    valid_rows: int
    error_count: int
    errors: list[ImportRowError] = Field(default_factory=list)
    to_create: int = 0
    to_update: int = 0
    unchanged: int = 0
    created_accounts: list[CreatedAccount] = Field(default_factory=list)
