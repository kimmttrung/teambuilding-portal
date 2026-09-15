"""Schema huỷ đăng ký theo giai đoạn kỳ (docs/04-api-spec.md §4.3)."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models.enums import CancellationMode, CancellationStatus

Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=512)]
OptionalNote = Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=1000)]


class CancellationRequestIn(BaseModel):
    """CBNV xin huỷ sau khi BTC đã công bố."""

    model_config = ConfigDict(extra="forbid")

    reason: Reason


class CancellationApproveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Phí phạt do BTC quyết theo quy định công ty — hệ thống chỉ lưu quyết định và ghi chú.
    penalty_applied: bool = False
    penalty_note: Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=512)] = None
    decision_note: OptionalNote = None


class CancellationRejectIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Bắt buộc: CBNV cần biết vì sao vẫn phải đi.
    decision_note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=1000)]


class AdminCancelIn(BaseModel):
    """BTC huỷ thay CBNV — trường hợp ngoại lệ, kể cả khi chương trình đã bắt đầu."""

    model_config = ConfigDict(extra="forbid")

    registration_id: int
    reason: Reason
    penalty_applied: bool = False
    penalty_note: Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=512)] = None


class CancellationBrief(BaseModel):
    """Yêu cầu huỷ gần nhất — CBNV xem trạng thái yêu cầu của chính mình."""

    id: int
    mode: CancellationMode
    status: CancellationStatus
    reason: str
    requested_at: str
    decided_at: str | None = None
    decision_note: str | None = None
    penalty_applied: bool = False
    penalty_note: str | None = None


class CancellationPerson(BaseModel):
    id: int
    employee_code: str | None = None
    full_name: str
    email: str
    team_name: str | None = None


class CancellationOut(CancellationBrief):
    """Một lần huỷ trong danh sách của BTC: ai, lúc nào, lý do, giai đoạn, đã gỡ những gì."""

    registration_id: int
    event_status: str
    event_status_label: str
    after_deadline: bool
    decided_by_name: str | None = None
    released: dict[str, list[str]] = Field(default_factory=dict)
    user: CancellationPerson
