"""Schema xếp phòng tự động (docs/04-api-spec.md §6, docs/05 §7)."""

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.flight_allocation import FlagOut


class RoomAllocateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dry_run: bool = True
    force_reallocate: bool = False


class RoomGuestOut(BaseModel):
    registration_id: int
    full_name: str
    team_id: int | None = None
    team_name: str
    gender: str | None = None
    flight_code: str | None = None
    # true = BTC đã xếp tay, lần chạy này giữ nguyên.
    pinned: bool = False
    is_room_captain: bool = False


class RoomLoadOut(BaseModel):
    room_id: int
    room_number: str
    hotel_id: int
    hotel_name: str
    floor: str | None = None
    capacity: int
    gender_policy: str
    assigned: int
    remaining: int
    guests: list[RoomGuestOut] = Field(default_factory=list)


class RoomAllocationSummaryOut(BaseModel):
    total_guests: int
    assigned: int
    unassigned: int
    rooms_total: int
    rooms_used: int
    empty_beds: int
    same_team_rate: float
    same_flight_rate: float
    mixed_team_rooms: int
    score: int


class RoomAllocationResponse(BaseModel):
    dry_run: bool
    committed: bool = False
    summary: RoomAllocationSummaryOut
    rooms: list[RoomLoadOut]
    unassigned: list[RoomGuestOut]
    flags: list[FlagOut]
    params: dict
    # Bản ghi rác đã dọn khi ghi: người không còn tham gia.
    removed_stale: int = 0
