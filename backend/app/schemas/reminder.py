"""Schema email nhắc việc do BTC chủ động gửi."""

from pydantic import BaseModel, Field

from app.models.enums import ReminderKind


class ReminderRecipient(BaseModel):
    user_id: int
    full_name: str
    email: str
    employee_code: str | None = None
    team_name: str | None = None
    # Chỉ tên trường ("Số CCCD/Hộ chiếu"), không bao giờ là giá trị.
    missing_fields: list[str] = Field(default_factory=list)
    last_reminded_at: str | None = None
    # Đã nhắc trong khoảng chờ → mặc định bỏ qua để bấm nhầm hai lần không gửi hai lần.
    recently_reminded: bool = False


class ReminderPreview(BaseModel):
    kind: ReminderKind
    label: str
    template: str
    can_send: bool
    blocked_reason: str | None = None
    cooldown_hours: int
    email_enabled: bool
    total: int
    sendable: int
    recipients: list[ReminderRecipient]


class ReminderSendRequest(BaseModel):
    # None = mọi người đang cần nhắc. Danh sách = chỉ những người BTC tích chọn.
    user_ids: list[int] | None = Field(default=None, max_length=2000)
    include_recently_reminded: bool = False


class ReminderSkipped(BaseModel):
    user_id: int
    full_name: str | None = None
    # recently_reminded | not_eligible
    reason: str


class ReminderSendResult(BaseModel):
    kind: ReminderKind
    queued: int
    skipped: list[ReminderSkipped]
    email_enabled: bool
