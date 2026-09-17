"""BTC tra cứu "người này đang ở đâu" (docs/13 task 7)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.accommodation import Hotel, Room, RoomAssignment
from app.models.enums import EventStatus, FlightDirection, RegistrationStatus, UserRole
from app.models.event import Event
from app.models.flight import Flight, FlightAssignment, Shift
from app.models.gala import GalaLayout, GalaSeat, GalaSeatAssignment, GalaTable
from app.models.org import Team
from app.models.registration import Registration
from app.models.transportation import Bus, BusAssignment, PickupPoint, TripLeg

URL = "/api/v1/admin/people"
NOW = "2026-09-12T04:00:00+00:00"


@pytest.fixture
def world(db: Session, make_user) -> dict:
    """Một người được xếp đủ mọi thứ, một người đã huỷ, và kỳ đang ở giai đoạn CHƯA công bố."""
    event = Event(
        code="TB2026", name="Team Building 2026", start_date="2026-10-15", end_date="2026-10-17",
        # Cố ý: BTC phải tra cứu được trong lúc đang phân bổ, trước khi công bố.
        status=EventStatus.ALLOCATION_PROCESSING, terms_version="v1", is_active=True,
    )
    team = Team(code="KDHN", name="Kinh doanh Hà Nội", color="#4f46e5")
    db.add_all([event, team])
    db.flush()

    make_user(email="btc@company.vn", role=UserRole.ADMIN, full_name="Ban Tổ Chức")
    make_user(email="nv@company.vn", full_name="Nguyễn Văn A")
    traveller = make_user(
        email="trung@company.vn", full_name="Bùi Quang Trung",
        employee_code="NV007", team_id=team.id,
    )
    quitter = make_user(email="huy@company.vn", full_name="Lê Thị Huỷ", team_id=team.id)

    shift = Shift(event_id=event.id, code="CA1", name="Ca 1 – bay sáng", display_order=1)
    db.add(shift)
    db.flush()

    registration = Registration(
        event_id=event.id, user_id=traveller.id, is_participating=True, shift_id=shift.id,
        status=RegistrationStatus.SUBMITTED, submitted_at=NOW,
    )
    cancelled = Registration(
        event_id=event.id, user_id=quitter.id, is_participating=True,
        status=RegistrationStatus.CANCELLED, submitted_at=NOW,
    )
    db.add_all([registration, cancelled])
    db.flush()

    outbound = Flight(
        event_id=event.id, flight_code="VN1250", airline="Vietnam Airlines",
        direction=FlightDirection.OUTBOUND, shift_id=shift.id,
        departure_airport="HAN", arrival_airport="PQC",
        departure_time=f"{event.start_date}T00:00:00+00:00",
        arrival_time=f"{event.start_date}T02:00:00+00:00", capacity=60,
    )
    db.add(outbound)

    legs = []
    for order, (code, name, direction) in enumerate(
        [
            ("CITY_TO_AIRPORT", "HN/HCM → Sân bay", FlightDirection.OUTBOUND),
            ("AIRPORT_TO_CITY", "Sân bay → HN/HCM", FlightDirection.RETURN),
        ],
        start=1,
    ):
        leg = TripLeg(
            event_id=event.id, code=code, name=name, direction=direction, display_order=order
        )
        db.add(leg)
        legs.append(leg)
    db.flush()

    pickup = PickupPoint(
        event_id=event.id, trip_leg_id=legs[0].id, name="Toà nhà Keangnam", display_order=0
    )
    db.add(pickup)
    db.flush()
    bus = Bus(
        event_id=event.id, trip_leg_id=legs[0].id, bus_code="XE-03", capacity=45,
        pickup_point_id=pickup.id, departure_time=f"{event.start_date}T21:45:00+00:00",
    )
    hotel = Hotel(event_id=event.id, name="Sunset Beach Resort", check_in_at=NOW, check_out_at=NOW)
    layout = GalaLayout(event_id=event.id, name="Gala", grid_width=12, grid_height=8)
    db.add_all([bus, hotel, layout])
    db.flush()

    room = Room(hotel_id=hotel.id, room_number="805", floor="8", room_type="twin", capacity=2)
    table = GalaTable(layout_id=layout.id, table_code="B09", seat_count=10, pos_x=0, pos_y=0)
    table.seats = [GalaSeat(seat_number=number) for number in range(1, 11)]
    db.add_all([room, table])
    db.flush()

    db.add_all(
        [
            FlightAssignment(
                registration_id=registration.id, flight_id=outbound.id,
                direction=FlightDirection.OUTBOUND, seat_number="12A", assigned_at=NOW,
            ),
            BusAssignment(
                registration_id=registration.id, bus_id=bus.id,
                trip_leg_id=legs[0].id, assigned_at=NOW,
            ),
            RoomAssignment(
                registration_id=registration.id, room_id=room.id,
                is_room_captain=True, assigned_at=NOW,
            ),
            GalaSeatAssignment(
                seat_id=table.seats[6].id, team_id=team.id, registration_id=registration.id,
                confirmed_by=traveller.id, confirmed_at=NOW,
            ),
        ]
    )
    db.commit()
    return {
        "traveller": traveller.id, "quitter": quitter.id,
        "flight": outbound.id, "bus": bus.id, "room": room.id,
        "seat": table.seats[6].id, "leg_unassigned": legs[1].id,
    }


def test_search_ignores_diacritics_so_btc_can_type_without_them(
    client: TestClient, auth_headers, world
):
    """Gõ "bui quang trung" phải ra "Bùi Quang Trung". SQLite không có hàm bỏ dấu nên `LIKE` trong SQL
    trả 0 kết quả — thử trên dữ liệu thật, gõ "nguyen" không ra ai trong khi có 7 người tên Nguyễn."""
    admin = auth_headers("btc@company.vn")

    for query in ("bui quang trung", "Bùi Quang", "BUI QUANG", "NV007", "trung@company.vn"):
        found = client.get(f"{URL}/search", headers=admin, params={"q": query}).json()
        assert world["traveller"] in [row["user_id"] for row in found], query

    assert client.get(f"{URL}/search", headers=admin, params={"q": "   "}).json() == []


def test_locate_returns_the_exact_seat_in_every_part_of_the_trip(
    client: TestClient, auth_headers, world
):
    response = client.get(f"{URL}/{world['traveller']}/location", headers=auth_headers("btc@company.vn"))
    assert response.status_code == 200, response.text
    located = response.json()

    assert located["team_name"] == "Kinh doanh Hà Nội"
    assert located["shift"]["code"] == "CA1"
    assert located["flights"]["outbound"]["flight_id"] == world["flight"]
    assert located["flights"]["outbound"]["seat_number"] == "12A"
    assert located["flights"]["return"] is None, "chưa xếp chiều về thì phải nói rõ là chưa"
    assert located["room"]["room_id"] == world["room"]
    assert located["room"]["is_room_captain"] is True
    assert located["gala"]["seat_id"] == world["seat"]
    assert located["gala"]["table_code"] == "B09"


def test_every_leg_is_listed_even_when_no_bus_is_assigned_yet(
    client: TestClient, auth_headers, world
):
    """Chỉ trả chặng đã xếp thì không phân biệt được "kỳ có 2 chặng" với "còn 1 chặng chưa xếp"."""
    located = client.get(
        f"{URL}/{world['traveller']}/location", headers=auth_headers("btc@company.vn")
    ).json()

    legs = {leg["trip_leg_id"]: leg for leg in located["buses"]}
    assert len(legs) == 2, "phải liệt kê đủ mọi chặng của kỳ"
    assert legs[world["leg_unassigned"]]["bus_id"] is None
    assigned = next(leg for leg in located["buses"] if leg["bus_id"] is not None)
    assert assigned["bus_code"] == "XE-03"
    assert assigned["pickup_name"] == "Toà nhà Keangnam"


def test_lookup_works_before_the_event_is_published(client: TestClient, auth_headers, world, db):
    """Khác `/journey/{user_id}`: luật "chỉ xem sau công bố" là để chặn CBNV, không phải chặn BTC —
    họ chính là người đang xếp, và `allocation_processing` là lúc cần dò nhất."""
    event = db.scalar(db.query(Event).filter(Event.code == "TB2026").statement)
    assert event.status == EventStatus.ALLOCATION_PROCESSING

    admin = auth_headers("btc@company.vn")
    located = client.get(f"{URL}/{world['traveller']}/location", headers=admin).json()
    assert located["flights"]["outbound"]["flight_code"] == "VN1250"

    # Cùng người đó, qua /journey: vẫn rỗng vì chưa công bố — hành vi cũ không bị đổi.
    journey = client.get(f"/api/v1/journey/{world['traveller']}", headers=admin).json()
    assert journey["flights"]["outbound"] is None
    assert "flights" in journey["pending"]


def test_cancelled_person_shows_status_instead_of_empty_screen(client: TestClient, auth_headers, world):
    located = client.get(
        f"{URL}/{world['quitter']}/location", headers=auth_headers("btc@company.vn")
    ).json()
    assert located["registration_status"] == "cancelled"
    assert located["flights"]["outbound"] is None
    assert located["room"] is None
    assert [leg["bus_id"] for leg in located["buses"]] == [None, None]


def test_lookup_is_organizer_only_and_unknown_user_is_404(client: TestClient, auth_headers, world):
    employee = auth_headers("nv@company.vn")
    assert client.get(f"{URL}/search", headers=employee, params={"q": "bui"}).status_code == 403
    assert client.get(f"{URL}/{world['traveller']}/location", headers=employee).status_code == 403

    missing = client.get(f"{URL}/99999/location", headers=auth_headers("btc@company.vn"))
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "USER_NOT_FOUND"
