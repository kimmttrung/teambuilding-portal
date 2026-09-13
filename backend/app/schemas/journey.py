"""Schema My Journey — toàn bộ hành trình của một CBNV trong MỘT response (docs/04 §9).

Màn hình này được mở trên điện thoại ở sân bay, sóng yếu: một request thay vì sáu.
"""

from pydantic import BaseModel, ConfigDict, Field


class JourneyEvent(BaseModel):
    id: int
    code: str
    name: str
    status: str
    destination: str | None = None
    start_date: str
    end_date: str
    is_published: bool


class JourneyTeam(BaseModel):
    id: int
    name: str
    color: str | None = None


class JourneyProfile(BaseModel):
    user_id: int
    full_name: str
    display_name: str | None = None
    employee_code: str | None = None
    avatar_url: str | None = None
    phone: str | None = None
    team: JourneyTeam | None = None


class JourneyRegistration(BaseModel):
    status: str
    is_participating: bool
    requested_shift_code: str | None = None
    requested_shift_name: str | None = None


class JourneyFlight(BaseModel):
    flight_code: str
    airline: str | None = None
    direction: str
    shift_code: str | None = None
    departure_airport: str
    arrival_airport: str
    departure_time: str
    arrival_time: str
    seat_number: str | None = None
    ticket_code: str | None = None


class JourneyFlights(BaseModel):
    # "return" là từ khoá Python nên dùng alias; FastAPI serialize theo alias.
    model_config = ConfigDict(populate_by_name=True)

    outbound: JourneyFlight | None = None
    return_: JourneyFlight | None = Field(default=None, alias="return")


class JourneyTripLeg(BaseModel):
    id: int
    code: str
    name: str
    direction: str
    leg_date: str | None = None
    display_order: int = 0


class JourneyPlace(BaseModel):
    name: str
    address: str | None = None
    map_url: str | None = None


class JourneyContact(BaseModel):
    name: str
    phone: str | None = None


class JourneyBus(BaseModel):
    trip_leg: JourneyTripLeg
    bus_code: str
    plate_number: str | None = None
    gather_time: str | None = None
    departure_time: str | None = None
    pickup_point: JourneyPlace | None = None
    dropoff_point: str | None = None
    leader: JourneyContact | None = None
    driver: JourneyContact | None = None
    linked_flight_code: str | None = None


class JourneyRoommate(BaseModel):
    """Người ở cùng phòng: chỉ tên, team và số điện thoại — đủ để liên lạc, không hơn."""

    full_name: str
    phone: str | None = None
    team_name: str | None = None
    is_room_captain: bool = False


class JourneyAccommodation(BaseModel):
    hotel_name: str
    address: str | None = None
    phone: str | None = None
    map_url: str | None = None
    check_in_at: str | None = None
    check_out_at: str | None = None
    room_number: str
    room_type: str | None = None
    floor: str | None = None
    is_room_captain: bool = False
    roommates: list[JourneyRoommate] = Field(default_factory=list)


class JourneyGala(BaseModel):
    name: str
    venue: str | None = None
    starts_at: str | None = None
    table_code: str
    table_name: str | None = None
    seat_number: int


class JourneyItineraryItem(BaseModel):
    id: int
    day_date: str
    start_time: str | None = None
    end_time: str | None = None
    title: str
    description: str | None = None
    location: str | None = None
    audience: str


class JourneyAnnouncement(BaseModel):
    id: int
    title: str
    content: str
    severity: str
    published_at: str


class JourneyOut(BaseModel):
    event: JourneyEvent
    profile: JourneyProfile
    registration: JourneyRegistration | None = None
    flights: JourneyFlights = Field(default_factory=JourneyFlights)
    buses: list[JourneyBus] = Field(default_factory=list)
    accommodation: JourneyAccommodation | None = None
    gala: JourneyGala | None = None
    itinerary: list[JourneyItineraryItem] = Field(default_factory=list)
    announcements: list[JourneyAnnouncement] = Field(default_factory=list)
    # Phần chưa có dữ liệu: frontend hiện ô "đang chờ" thay vì báo lỗi (docs/04 §9).
    pending: list[str] = Field(default_factory=list)
    # Vì sao phần đó còn chờ: not_published | not_assigned | not_participating.
    # Không có trong đặc tả gốc — thêm vì "chưa công bố" và "BTC quên xếp bạn" cần hai
    # thông điệp khác nhau, nếu không CBNV thấy "đang chờ" mãi mà không biết phải hỏi ai.
    pending_reasons: dict[str, str] = Field(default_factory=dict)
