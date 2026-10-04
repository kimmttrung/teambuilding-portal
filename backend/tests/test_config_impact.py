"""Cảnh báo phân bổ lệch sau khi sửa cấu hình kỳ.

BTC đổi ngày của kỳ hoặc số phút đệm giữa xe và máy bay thì chuyến bay / xe / lịch trình đã nhập có
thể nằm lệch ra ngoài. Không chặn việc sửa, nhưng phải liệt kê đúng thứ đang lệch.
"""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.timeutils import VN_TZ, to_iso
from app.models import Bus, Event, Flight, Shift, TripLeg
from app.models.accommodation import Hotel
from app.models.content import ItineraryItem
from app.models.enums import EventStatus, FlightDirection, UserRole

START = "2026-10-15"
END = "2026-10-17"


def vn_time(day: str, hhmm: str) -> str:
    return to_iso(datetime.strptime(f"{day} {hhmm}", "%Y-%m-%d %H:%M").replace(tzinfo=VN_TZ))


@pytest.fixture
def world(db: Session) -> dict:
    """Kỳ đang phân bổ, mọi thứ khớp nhau: 1 ca, 2 chuyến, 1 xe ra sân bay, lịch trình, khách sạn."""
    event = Event(
        code="TB2026", name="Team Building 2026", start_date=START, end_date=END,
        status=EventStatus.ALLOCATION_PROCESSING, terms_version="v1", is_active=True,
    )
    db.add(event)
    db.flush()

    shift = Shift(event_id=event.id, code="CA1", name="Ca 1", earliest_departure="05:00")
    leg = TripLeg(
        event_id=event.id, code="CITY_TO_AIRPORT", name="HN → Sân bay",
        direction=FlightDirection.OUTBOUND, leg_date=START, is_airport_linked=True,
    )
    db.add_all([shift, leg])
    db.flush()

    outbound = Flight(
        event_id=event.id, flight_code="VN1234", direction=FlightDirection.OUTBOUND,
        shift_id=shift.id, departure_airport="HAN", arrival_airport="PQC",
        departure_time=vn_time(START, "06:00"), arrival_time=vn_time(START, "08:10"), capacity=60,
    )
    back = Flight(
        event_id=event.id, flight_code="VN4321", direction=FlightDirection.RETURN,
        departure_airport="PQC", arrival_airport="HAN",
        departure_time=vn_time(END, "18:00"), arrival_time=vn_time(END, "20:10"), capacity=60,
    )
    db.add_all([outbound, back])
    db.flush()

    # Xe chạy 04:30, chuyến cất cánh 06:00: cách 90 phút, đạt mức đệm mặc định 30 phút.
    bus = Bus(
        event_id=event.id, trip_leg_id=leg.id, bus_code="XE-01", capacity=45,
        gather_time=vn_time(START, "04:15"), departure_time=vn_time(START, "04:30"),
        linked_flight_id=outbound.id,
    )
    db.add_all(
        [
            bus,
            ItineraryItem(event_id=event.id, day_date=START, start_time="09:00", title="Nhận phòng"),
            ItineraryItem(event_id=event.id, day_date=END, start_time="15:00", title="Trả phòng"),
            Hotel(
                event_id=event.id, name="Khách sạn Biển",
                check_in_at=vn_time(START, "14:00"), check_out_at=vn_time(END, "12:00"),
            ),
        ]
    )
    db.commit()
    return {"event": event, "leg": leg, "shift": shift, "outbound": outbound, "bus": bus}


@pytest.fixture
def admin(make_user, auth_headers):
    make_user(email="btc@company.vn", password="MatKhau123", role=UserRole.ADMIN)
    return auth_headers("btc@company.vn")


def impact(client: TestClient, world, headers) -> dict:
    response = client.get(f"/api/v1/events/{world['event'].id}/config-impact", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def kinds(body: dict) -> dict[str, dict]:
    return {item["kind"]: item for item in body["items"]}


def test_nothing_to_review_when_everything_lines_up(client: TestClient, world, admin):
    body = impact(client, world, admin)
    assert body == {"needs_review": False, "items": []}


def test_flight_just_after_midnight_vietnam_time_is_inside_the_event(
    client: TestClient, world, admin, db: Session
):
    """00:30 ngày 15/10 giờ Việt Nam lưu thành 17:30 ngày 14/10 UTC — so chuỗi UTC là báo nhầm."""
    world["shift"].earliest_departure = None
    world["outbound"].departure_time = vn_time(START, "00:30")
    world["outbound"].arrival_time = vn_time(START, "02:40")
    world["bus"].gather_time = vn_time(START, "00:00")
    world["bus"].departure_time = vn_time(START, "00:00")
    db.commit()

    assert "flight_outside_dates" not in kinds(impact(client, world, admin))


def test_shortening_the_event_lists_what_falls_outside(client: TestClient, world, admin):
    saved = client.patch(
        f"/api/v1/events/{world['event'].id}", headers=admin, json={"end_date": "2026-10-16"}
    )
    # Sửa ngày không bị chặn, chỉ cảnh báo sau đó.
    assert saved.status_code == 200, saved.text

    body = impact(client, world, admin)
    found = kinds(body)
    assert body["needs_review"] is True
    assert set(found) == {"flight_outside_dates", "itinerary_outside_dates", "hotel_outside_dates"}

    flights = found["flight_outside_dates"]
    assert flights["count"] == 1 and "VN4321" in flights["details"][0]
    assert flights["link"] == "/admin/flights"
    assert "Trả phòng" in found["itinerary_outside_dates"]["details"][0]
    assert "trả phòng" in found["hotel_outside_dates"]["details"][0]


def test_moving_the_event_lists_buses_and_legs_too(client: TestClient, world, admin):
    client.patch(
        f"/api/v1/events/{world['event'].id}", headers=admin,
        json={"start_date": "2026-10-16", "end_date": "2026-10-18"},
    )
    found = kinds(impact(client, world, admin))
    assert "XE-01" in found["bus_outside_dates"]["details"][0]
    assert found["bus_outside_dates"]["link"] == f"/admin/buses?leg={world['leg'].id}"
    assert found["leg_outside_dates"]["link"] == "/admin/settings?tab=legs"


def test_raising_the_bus_buffer_flags_buses_that_no_longer_fit(client: TestClient, world, admin):
    """Xe cách giờ cất cánh 90 phút: đạt với mức đệm 30, không đạt khi BTC nâng lên 120."""
    saved = client.put(
        f"/api/v1/events/{world['event'].id}/settings", headers=admin,
        json={"values": {"transport.to_airport_buffer_minutes": 120}},
    )
    assert saved.status_code == 200, saved.text

    found = kinds(impact(client, world, admin))
    assert set(found) == {"bus_flight_mismatch"}
    assert "XE-01" in found["bus_flight_mismatch"]["details"][0]
    assert "VN1234" in found["bus_flight_mismatch"]["details"][0]


def test_raising_the_earliest_departure_flags_flights_of_that_shift(
    client: TestClient, world, admin
):
    saved = client.patch(
        f"/api/v1/master-data/shifts/{world['shift'].id}", headers=admin,
        json={"earliest_departure": "07:00"},
    )
    assert saved.status_code == 200, saved.text

    found = kinds(impact(client, world, admin))
    assert set(found) == {"flight_before_shift"}
    assert "VN1234" in found["flight_before_shift"]["details"][0]


def test_only_organisers_can_read_it(client: TestClient, world, make_user, auth_headers):
    make_user(email="nv@company.vn", password="MatKhau123")
    response = client.get(
        f"/api/v1/events/{world['event'].id}/config-impact", headers=auth_headers("nv@company.vn")
    )
    assert response.status_code == 403
