"""Schema cho lịch trình chương trình (itinerary_items) — BTC quản lý, CBNV đọc qua journey."""

from pydantic import BaseModel, ConfigDict, Field

DAY_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
CLOCK_PATTERN = r"^([01][0-9]|2[0-3]):[0-5][0-9]$"


class ItineraryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    day_date: str
    start_time: str | None
    end_time: str | None
    title: str
    description: str | None
    location: str | None
    audience: str
    trip_leg_id: int | None = None
    trip_leg_name: str | None = None
    display_order: int


class ItineraryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day_date: str = Field(pattern=DAY_PATTERN)
    start_time: str | None = Field(default=None, pattern=CLOCK_PATTERN)
    end_time: str | None = Field(default=None, pattern=CLOCK_PATTERN)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    location: str | None = Field(default=None, max_length=255)
    audience: str = Field(default="all", min_length=1, max_length=32)
    # Mốc chỉ dành cho người đi xe chặng này (tập trung tại điểm đón). None = mốc chung.
    trip_leg_id: int | None = None
    display_order: int | None = Field(default=None, ge=0)


class ItineraryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day_date: str | None = Field(default=None, pattern=DAY_PATTERN)
    start_time: str | None = Field(default=None, pattern=CLOCK_PATTERN)
    end_time: str | None = Field(default=None, pattern=CLOCK_PATTERN)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    location: str | None = Field(default=None, max_length=255)
    audience: str | None = Field(default=None, min_length=1, max_length=32)
    trip_leg_id: int | None = None
    display_order: int | None = Field(default=None, ge=0)


class ItineraryReorder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day_date: str = Field(pattern=DAY_PATTERN)
    ordered_ids: list[int] = Field(min_length=1)
