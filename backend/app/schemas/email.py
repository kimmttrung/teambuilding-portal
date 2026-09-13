"""Schema cho nhật ký email."""

from pydantic import BaseModel, ConfigDict

from app.models.enums import EmailStatus


class EmailLogOut(BaseModel):
    """Một dòng nhật ký email cho màn hình BTC.

    Có `body_preview` vì câu hỏi hay gặp nhất là "tôi không nhận được mail" — BTC
    phải đọc lại được nội dung đã gửi, không chỉ biết là đã gửi.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None = None
    to_email: str
    template: str
    template_label: str = ""
    subject: str
    body_preview: str | None = None
    status: EmailStatus
    error_message: str | None = None
    retry_count: int
    related_type: str | None = None
    related_id: int | None = None
    sent_at: str | None = None
    created_at: str
    # Dòng "queued" vì EMAIL_ENABLED=false: chỉ ghi log, sẽ không bao giờ tự gửi đi.
    is_dev_only: bool = False


class EmailResendRequest(BaseModel):
    # None = mọi thư đang lỗi. Danh sách = chỉ những thư này.
    ids: list[int] | None = None


class EmailResendSkipped(BaseModel):
    id: int
    # not_found | not_failed | no_recipient | no_longer_relevant | cannot_rebuild
    reason: str
    message: str


class EmailResendResult(BaseModel):
    queued: int
    skipped: list[EmailResendSkipped]
    email_enabled: bool


class EmailLogStats(BaseModel):
    total: int
    queued: int
    sent: int
    failed: int
    by_template: dict[str, int]
    # Mọi loại thư hệ thống có, kể cả loại chưa gửi lần nào — cho dropdown lọc.
    template_labels: dict[str, str] = {}
    # false = đang ở chế độ dev, mail chỉ ghi log chứ chưa gửi thật.
    email_enabled: bool
