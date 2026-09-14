"""Schema Gala Dinner: sơ đồ, bốc thăm, lượt chọn, giữ/xác nhận ghế (docs/04-api-spec.md §8)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.timeutils import from_iso

SeatState = Literal["available", "held_by_me", "held_by_other", "taken", "unavailable"]
StagePosition = Literal["top", "bottom", "left", "right"]
TABLE_CODE_PATTERN = r"^[A-Za-z0-9._-]{1,16}$"
MAX_SEATS_PER_HOLD = 30


def _check_iso(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        from_iso(value)
    except ValueError as exc:
        raise ValueError("Thời gian phải là ISO-8601, ví dụ 2026-10-16T11:30:00+00:00 (giờ UTC).") from exc
    return value


# --- Cấu hình sơ đồ (BTC) ---


class GalaLayoutIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    venue: str | None = Field(default=None, max_length=255)
    starts_at: str | None = None
    stage_position: StagePosition = "top"
    grid_width: int = Field(default=12, ge=4, le=40)
    grid_height: int = Field(default=10, ge=4, le=40)
    # Bỏ trống thì lấy theo cấu hình kỳ (`gala.turn_seconds`, `gala.hold_seconds`).
    turn_seconds: int | None = Field(default=None, ge=30, le=3600)
    hold_seconds: int | None = Field(default=None, ge=15, le=1800)

    _validate_starts_at = field_validator("starts_at")(_check_iso)


class GalaLayoutUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    venue: str | None = Field(default=None, max_length=255)
    starts_at: str | None = None
    stage_position: StagePosition | None = None
    grid_width: int | None = Field(default=None, ge=4, le=40)
    grid_height: int | None = Field(default=None, ge=4, le=40)
    turn_seconds: int | None = Field(default=None, ge=30, le=3600)
    hold_seconds: int | None = Field(default=None, ge=15, le=1800)

    _validate_starts_at = field_validator("starts_at")(_check_iso)


class GalaTableIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    table_code: str = Field(pattern=TABLE_CODE_PATTERN)
    table_name: str | None = Field(default=None, max_length=128)
    seat_count: int = Field(ge=1, le=24)
    pos_x: int = Field(ge=0)
    pos_y: int = Field(ge=0)
    is_vip: bool = False


class GalaTableUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    table_code: str | None = Field(default=None, pattern=TABLE_CODE_PATTERN)
    table_name: str | None = Field(default=None, max_length=128)
    seat_count: int | None = Field(default=None, ge=1, le=24)
    pos_x: int | None = Field(default=None, ge=0)
    pos_y: int | None = Field(default=None, ge=0)
    is_vip: bool | None = None
    is_available: bool | None = None


class DrawRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Bỏ trống = hệ thống tự sinh. Nhập lại seed cũ ra đúng thứ tự cũ (cùng danh sách team).
    seed: int | None = Field(default=None, ge=1, le=2_147_483_647)


class TurnNextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skip: bool = Field(default=False, description="true = bỏ lượt team đang chọn (ghi 'skipped')")


class SeatAdminUpdate(BaseModel):
    """BTC ép gán / gỡ / khoá ghế. Chỉ trường có gửi lên mới được áp dụng."""

    model_config = ConfigDict(extra="forbid")

    team_id: int | None = None  # null = gỡ ghế khỏi team
    registration_id: int | None = None  # null = bỏ gán người
    is_available: bool | None = None
    reason: str = Field(min_length=3, max_length=500)

    @model_validator(mode="after")
    def _has_change(self) -> "SeatAdminUpdate":
        if not ({"team_id", "registration_id", "is_available"} & self.model_fields_set):
            raise ValueError("Cần ít nhất một thay đổi: team_id, registration_id hoặc is_available.")
        if "is_available" in self.model_fields_set and self.is_available is None:
            raise ValueError("is_available phải là true hoặc false.")
        return self


# --- Thao tác của Trưởng nhóm ---


class SeatHoldRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seat_ids: list[int] = Field(min_length=1, max_length=MAX_SEATS_PER_HOLD)


class AssignMemberRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seat_id: int
    registration_id: int | None = None  # null = bỏ gán người khỏi ghế


# --- Response ---


class GalaSeatOut(BaseModel):
    id: int
    seat_number: int
    state: SeatState
    team_id: int | None = None
    team_name: str | None = None
    team_color: str | None = None
    # Chỉ có khi người xem là BTC hoặc cùng team sở hữu ghế (docs/09-security.md §4).
    registration_id: int | None = None
    occupant_name: str | None = None
    hold_expires_at: str | None = None


class GalaTableOut(BaseModel):
    id: int
    table_code: str
    table_name: str | None
    seat_count: int
    pos_x: int
    pos_y: int
    is_vip: bool
    is_available: bool
    available_seats: int
    seats: list[GalaSeatOut]


class GalaLayoutInfo(BaseModel):
    id: int
    name: str
    venue: str | None
    starts_at: str | None
    stage_position: str
    grid_width: int
    grid_height: int
    selection_status: str
    turn_seconds: int
    hold_seconds: int
    draw_seed: int | None = None  # chỉ BTC thấy


class DrawOrderOut(BaseModel):
    position: int
    team_id: int
    team_code: str
    team_name: str
    team_color: str | None
    leader_name: str | None = None
    quota: int
    confirmed: int
    held: int
    remaining: int
    status: str
    turn_started_at: str | None
    turn_ends_at: str | None


class DrawStateOut(BaseModel):
    selection_status: str
    draw_seed: int | None = None
    active_team_id: int | None
    active_turn_ends_at: str | None
    orders: list[DrawOrderOut]
    total_quota: int
    total_seats: int
    unteamed_participants: int
    server_time: str


class MyTeamOut(BaseModel):
    team_id: int
    team_name: str
    team_color: str | None
    is_leader: bool
    draw_position: int | None
    status: str | None
    quota: int
    confirmed: int
    held: int
    remaining: int
    is_my_turn: bool
    turn_ends_at: str | None
    hold_expires_at: str | None


class GalaTotals(BaseModel):
    seats: int
    available: int
    held: int
    taken: int
    unavailable: int


class GalaViewOut(BaseModel):
    layout: GalaLayoutInfo
    tables: list[GalaTableOut]
    draw: DrawStateOut
    my_team: MyTeamOut | None
    totals: GalaTotals
    can_manage: bool
    server_time: str


class HoldResultOut(BaseModel):
    seat_ids: list[int]
    expires_at: str
    quota: int
    confirmed: int
    held: int
    remaining: int


class ReleaseResultOut(BaseModel):
    released: int


class ConfirmResultOut(BaseModel):
    seat_ids: list[int]
    confirmed_total: int
    quota: int
    turn_finished: bool
    next_team_id: int | None


class AssignMemberOut(BaseModel):
    seat_id: int
    registration_id: int | None
    previous_seat_id: int | None


class AutoAssignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    team_id: int | None = Field(default=None, description="Chỉ BTC dùng; Trưởng nhóm luôn là team mình")
    reshuffle: bool = Field(default=False, description="true = xáo lại chỗ của mọi thành viên")


class AutoAssignOut(BaseModel):
    team_id: int
    placed: int
    unseated: int  # còn người chưa có ghế vì team thiếu ghế
    free_seats: int
    reshuffle: bool


class MyTurnOut(BaseModel):
    configured: bool
    is_leader: bool
    selection_status: str | None
    team_id: int | None
    team_name: str | None
    draw_position: int | None
    status: str | None
    is_my_turn: bool
    turn_ends_at: str | None
    teams_ahead: int | None
    active_team_name: str | None
    quota: int
    confirmed: int
    remaining: int
    server_time: str


class TeamMemberOut(BaseModel):
    registration_id: int
    user_id: int
    full_name: str
    employee_code: str | None
    avatar_url: str | None
    seat_id: int | None
    table_code: str | None
    seat_number: int | None
