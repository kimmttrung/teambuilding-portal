"""Schema cho tra cứu vị trí một người trong kỳ (BTC).

Không có CCCD / ngày sinh / ghi chú sức khoẻ: màn hình này để biết chỗ ngồi, không phải xem hồ sơ.
"""

from pydantic import BaseModel, ConfigDict, Field


class PersonSearchItem(BaseModel):
    """Một dòng gợi ý trong ô tìm người."""

    user_id: int
    full_name: str
    email: str
    employee_code: str | None
    team_name: str | None
    registration_status: str | None
    is_participating: bool


class LocatedFlight(BaseModel):
    flight_id: int
    flight_code: str
    airline: str | None
    departure_airport: str
    arrival_airport: str
    departure_time: str
    arrival_time: str
    seat_number: str | None
    assignment_mode: str


class LocatedFlights(BaseModel):
    # `return` là từ khoá của Python nên không đặt tên thuộc tính như vậy được. Dùng alias để JSON ra
    # đúng `"return"`, giống `/journey/me` — frontend không phải nhớ một tên riêng cho màn hình này.
    model_config = ConfigDict(populate_by_name=True)

    outbound: LocatedFlight | None = None
    return_: LocatedFlight | None = Field(default=None, alias="return")


class LocatedBusLeg(BaseModel):
    """Một chặng. `bus_id` rỗng = chặng này chưa xếp xe — khác hẳn với "kỳ không có chặng này"."""

    trip_leg_id: int
    leg_code: str
    leg_name: str
    direction: str
    bus_id: int | None
    bus_code: str | None
    pickup_point_id: int | None
    pickup_name: str | None
    departure_time: str | None
    assignment_mode: str | None


class LocatedRoom(BaseModel):
    room_id: int
    room_number: str
    floor: str | None
    room_type: str | None
    hotel_id: int
    hotel_name: str
    is_room_captain: bool
    assignment_mode: str


class LocatedGalaSeat(BaseModel):
    seat_id: int
    seat_number: int
    table_id: int
    table_code: str
    table_name: str | None


class PersonLocation(BaseModel):
    user_id: int
    full_name: str
    email: str
    employee_code: str | None
    phone: str | None
    team_id: int | None
    team_name: str | None
    team_color: str | None

    registration_id: int | None
    registration_status: str | None
    is_participating: bool

    shift: dict | None = None
    flights: LocatedFlights
    buses: list[LocatedBusLeg]
    room: LocatedRoom | None = None
    gala: LocatedGalaSeat | None = None
