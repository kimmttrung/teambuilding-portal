"""Schema thông báo BTC gửi CBNV (announcements) — BTC quản lý, CBNV đọc qua journey."""

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AnnouncementSeverity, AnnouncementTarget


class AnnouncementRecipient(BaseModel):
    user_id: int
    full_name: str
    email: str
    team_name: str | None = None


class AnnouncementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    title: str
    content: str
    severity: AnnouncementSeverity
    target_type: AnnouncementTarget
    target_id: int | None
    # Tên dễ đọc của đối tượng nhận ("Tất cả CBNV", "Team X", ...) để khỏi tra id tay.
    target_label: str | None = None
    published_at: str | None
    send_email: bool
    recipient_count: int = 0


class AnnouncementIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)
    severity: AnnouncementSeverity = AnnouncementSeverity.INFO
    target_type: AnnouncementTarget = AnnouncementTarget.ALL
    target_id: int | None = None


class AnnouncementUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=255)
    content: str | None = Field(default=None, min_length=1)
    severity: AnnouncementSeverity | None = None
    target_type: AnnouncementTarget | None = None
    target_id: int | None = None


class AnnouncementPublish(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Đăng mà không tick thì thông báo chỉ hiện trong My Journey, không gửi mail.
    send_email: bool = False


class AnnouncementPublishResult(BaseModel):
    id: int
    published_at: str
    queued: int
    email_enabled: bool


class RecipientPreview(BaseModel):
    target_type: AnnouncementTarget
    target_id: int | None = None
    target_label: str
    total: int
    email_enabled: bool
    recipients: list[AnnouncementRecipient]
