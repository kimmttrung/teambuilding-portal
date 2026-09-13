"""Schema dashboard BTC (docs/04-api-spec.md §10)."""

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.email import EmailLogStats
from app.schemas.registration import RegistrationStats


class NextStatus(BaseModel):
    status: str
    label: str
    is_forward: bool
    # Bước lùi làm đổi thứ CBNV đang thấy → phải nêu lý do (event_service).
    requires_reason: bool


class DashboardEvent(BaseModel):
    id: int
    code: str
    name: str
    destination: str | None = None
    start_date: str
    end_date: str
    status: str
    status_label: str
    registration_closes_at: str | None = None
    is_published: bool
    next_statuses: list[NextStatus] = Field(default_factory=list)


class TeamParticipation(BaseModel):
    team_id: int | None = None
    code: str | None = None
    name: str
    color: str | None = None
    members: int
    submitted: int
    participating: int
    not_participating: int
    cancelled: int
    not_submitted: int
    response_rate: float
    participation_rate: float


class FlightProgress(BaseModel):
    direction: str
    flights: int
    usable_capacity: int
    assigned: int
    # Người tham gia CHƯA có chuyến ở chiều này — khác `usable - assigned` (ghế trống).
    unassigned: int
    remaining: int
    shortfall: int


class BusLegProgress(BaseModel):
    trip_leg_id: int
    code: str
    name: str
    direction: str
    demand: int
    buses: int
    capacity: int
    assigned: int
    unassigned: int
    shortfall: int


class RoomProgress(BaseModel):
    participants: int
    assigned: int
    unassigned: int
    total_beds: int
    uncovered: int


class GalaProgress(BaseModel):
    configured: bool
    tables: int
    seats: int
    assigned: int


class ChecklistItem(BaseModel):
    key: str
    label: str
    done: bool
    # False = nên làm nhưng không chặn công bố (ví dụ email lỗi).
    required: bool = True
    detail: str | None = None
    link: str | None = None


class ActivityItem(BaseModel):
    id: int
    action: str
    entity_type: str
    entity_id: int | None = None
    actor_name: str | None = None
    reason: str | None = None
    created_at: str


class DashboardOut(BaseModel):
    generated_at: str
    event: DashboardEvent
    registrations: RegistrationStats
    teams: list[TeamParticipation]
    flights: list[FlightProgress]
    buses: list[BusLegProgress]
    rooms: RoomProgress
    gala: GalaProgress
    emails: EmailLogStats
    checklist: list[ChecklistItem]
    ready_to_publish: bool
    recent_activity: list[ActivityItem]


class AuditLogOut(BaseModel):
    id: int
    event_id: int | None = None
    actor_id: int | None = None
    actor_name: str | None = None
    action: str
    entity_type: str
    entity_id: int | None = None
    before: Any = None
    after: Any = None
    reason: str | None = None
    ip_address: str | None = None
    created_at: str
