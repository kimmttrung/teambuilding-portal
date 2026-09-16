"""Schema chỉ định Trưởng nhóm (docs/04-api-spec.md §4.3)."""

from pydantic import BaseModel, ConfigDict


class TeamLeaderIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: int


class TeamLeaderOut(BaseModel):
    team_id: int
    team_name: str
    leader_user_id: int
    leader_name: str
    previous_leader_user_id: int | None = None
