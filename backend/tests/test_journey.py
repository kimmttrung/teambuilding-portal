"""Kiểm thử My Journey (docs/04 §9, CLAUDE.md cạm bẫy #6)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.accommodation import Hotel, Room, RoomAssignment
from app.models.content import Announcement, ItineraryItem
from app.models.enums import (
    AnnouncementSeverity,
    AnnouncementTarget,
    AssignmentMode,
    EventStatus,
    FlightDirection,
    Gender,
    RegistrationStatus,
    RoomGenderPolicy,
    UserRole,
)
from app.models.event import Event
from app.models.flight import Flight, FlightAssignment, Shift
from app.models.gala import GalaLayout, GalaSeat, GalaSeatAssignment, GalaTable
from app.models.org import Team
from app.models.registration import Registration, RegistrationBusNeed
from app.models.transportation import Bus, BusAssignment, PickupPoint, TripLeg

URL = "/api/v1/journey/me"
NOW = "2026-09-12T04:00:00+00:00"


@pytest.fixture
def world(db: Session, make_user) -> dict:
    """Một CBNV đã được xếp đủ: 2 chuyến bay, 1 xe, 1 phòng có bạn cùng phòng, 1 ghế Gala."""
    event = Event(
        code="TB2026",
        name="Team Building 2026",
        destination="Phú Quốc",
        start_date="2026-10-15",
        end_date="2026-10-17",
        status=EventStatus.INFORMATION_PUBLISHED,
        terms_version="v1",
        is_active=True,
    )
    team = Team(code="IT-HN", name="Công nghệ Hà Nội", color="#7c3aed")
    other_team = Team(code="SALES-HN", name="Kinh doanh Hà Nội")
    db.add_all([event, team, other_team])
    db.flush()

    ca1 = Shift(event_id=event.id, code="CA1", name="Ca 1", display_order=1)
    ca2 = Shift(event_id=event.id, code="CA2", name="Ca 2", display_order=2)
    db.add_all([ca1, ca2])
    db.flush()

    outbound = Flight(
        event_id=event.id, flight_code="VN1234", airline="Vietnam Airlines",
        direction=FlightDirection.OUTBOUND, shift_id=ca1.id,
        departure_airport="HAN", arrival_airport="PQC",
        departure_time="2026-10-15T06:30:00+00:00", arrival_time="2026-10-15T08:40:00+00:00",
        capacity=60,
    )
    back = Flight(
        event_id=event.id, flight_code="VN1235", airline="Vietnam Airlines",
        direction=FlightDirection.RETURN, shift_id=ca1.id,
        departure_airport="PQC", arrival_airport="HAN",
        departure_time="2026-10-17T15:00:00+00:00", arrival_time="2026-10-17T17:10:00+00:00",
        capacity=60,
    )
    city = TripLeg(
        event_id=event.id, code="CITY_TO_AIRPORT", name="HN → Sân bay",
        direction=FlightDirection.OUTBOUND, leg_date="2026-10-15", is_airport_linked=True,
        display_order=1,
    )
    db.add_all([outbound, back, city])
    db.flush()

    pickup = PickupPoint(
        event_id=event.id, trip_leg_id=city.id, name="Toà nhà Keangnam",
        address="Phạm Hùng, Hà Nội", map_url="https://maps.google.com/?q=Keangnam",
    )
    db.add(pickup)
    db.flush()

    traveller = make_user(
        email="nv@company.vn", full_name="Nguyễn Văn Đi", phone="0911000111",
        team_id=team.id, gender=Gender.MALE, date_of_birth="1995-01-01",
        id_card_number="001095012345", health_note="Dị ứng hải sản",
    )
    roommate = make_user(
        email="roommate@company.vn", full_name="Trần Văn Cùng", phone="0922000222",
        team_id=team.id, gender=Gender.MALE, id_card_number="001095099999",
        health_note="Hen suyễn",
    )
    leader = make_user(
        email="leader@company.vn", full_name="Lê Trưởng Xe", phone="0933000333",
        role=UserRole.TEAM_LEADER,
    )
    admin = make_user(email="btc@company.vn", role=UserRole.ADMIN)

    registration = Registration(
        event_id=event.id, user_id=traveller.id, is_participating=True, shift_id=ca1.id,
        status=RegistrationStatus.SUBMITTED, submitted_at=NOW,
    )
    mate_registration = Registration(
        event_id=event.id, user_id=roommate.id, is_participating=True,
        status=RegistrationStatus.SUBMITTED, submitted_at=NOW,
    )
    db.add_all([registration, mate_registration])
    db.flush()

    db.add(
        RegistrationBusNeed(
            registration_id=registration.id, trip_leg_id=city.id, needs_bus=True,
            pickup_point_id=pickup.id,
        )
    )
    db.add_all(
        [
            FlightAssignment(
                registration_id=registration.id, flight_id=outbound.id,
                direction=FlightDirection.OUTBOUND, assignment_mode=AssignmentMode.AUTO,
                assigned_at=NOW,
            ),
            FlightAssignment(
                registration_id=registration.id, flight_id=back.id,
                direction=FlightDirection.RETURN, assignment_mode=AssignmentMode.AUTO,
                assigned_at=NOW,
            ),
        ]
    )

    bus = Bus(
        event_id=event.id, trip_leg_id=city.id, bus_code="XE-01", plate_number="29B-123.45",
        capacity=45, pickup_point_id=pickup.id,
        gather_time="2026-10-15T04:30:00+00:00", departure_time="2026-10-15T04:45:00+00:00",
        leader_user_id=leader.id, leader_name=leader.full_name, leader_phone=leader.phone,
        linked_flight_id=outbound.id,
    )
    hotel = Hotel(
        event_id=event.id, name="Sunset Beach Resort", address="Trần Hưng Đạo, Phú Quốc",
        map_url="https://maps.google.com/?q=Sunset",
    )
    db.add_all([bus, hotel])
    db.flush()
    db.add(
        BusAssignment(
            registration_id=registration.id, bus_id=bus.id, trip_leg_id=city.id,
            assignment_mode=AssignmentMode.AUTO, assigned_at=NOW,
        )
    )

    room = Room(
        hotel_id=hotel.id, room_number="1204", room_type="twin", capacity=2, floor="12",
        gender_policy=RoomGenderPolicy.MALE,
    )
    layout = GalaLayout(
        event_id=event.id, name="Gala Dinner", venue="Sảnh Pearl",
        starts_at="2026-10-16T12:30:00+00:00",
    )
    db.add_all([room, layout])
    db.flush()
    db.add_all(
        [
            RoomAssignment(
                registration_id=registration.id, room_id=room.id, is_room_captain=True,
                assignment_mode=AssignmentMode.MANUAL, assigned_at=NOW,
            ),
            RoomAssignment(
                registration_id=mate_registration.id, room_id=room.id,
                assignment_mode=AssignmentMode.MANUAL, assigned_at=NOW,
            ),
        ]
    )

    table = GalaTable(
        layout_id=layout.id, table_code="B07", table_name="Bàn Công nghệ", seat_count=10,
        pos_x=1, pos_y=1,
    )
    db.add(table)
    db.flush()
    seat = GalaSeat(table_id=table.id, seat_number=3)
    db.add(seat)
    db.flush()
    db.add(
        GalaSeatAssignment(
            seat_id=seat.id, team_id=team.id, registration_id=registration.id,
            confirmed_by=admin.id, confirmed_at=NOW,
        )
    )

    db.add_all(
        [
            ItineraryItem(event_id=event.id, day_date="2026-10-15", start_time="04:30",
                          title="Tập trung tại điểm đón", audience="all", display_order=0),
            ItineraryItem(event_id=event.id, day_date="2026-10-15", start_time="06:30",
                          title="Bay ca 1", audience="CA1", display_order=1),
            ItineraryItem(event_id=event.id, day_date="2026-10-15", start_time="19:15",
                          title="Bay ca 2", audience="CA2", display_order=2),
            ItineraryItem(event_id=event.id, day_date="2026-10-16", start_time="09:00",
                          title="Workshop team Công nghệ", audience="IT-HN", display_order=0),
            ItineraryItem(event_id=event.id, day_date="2026-10-16", start_time="09:00",
                          title="Workshop team Kinh doanh", audience="SALES-HN", display_order=1),
        ]
    )

    def announcement(title, target, target_id=None, published_at="2026-09-10T00:00:00+00:00",
                     severity=AnnouncementSeverity.INFO):
        return Announcement(
            event_id=event.id, title=title, content=f"Nội dung: {title}", severity=severity,
            target_type=target, target_id=target_id, published_at=published_at, created_at=NOW,
        )

    db.add_all(
        [
            announcement("Chào mừng", AnnouncementTarget.ALL),
            announcement("Tin cho team Công nghệ", AnnouncementTarget.TEAM, team.id,
                         "2026-09-12T00:00:00+00:00", AnnouncementSeverity.WARNING),
            announcement("Tin riêng cho bạn", AnnouncementTarget.USER, traveller.id,
                         "2026-09-11T00:00:00+00:00", AnnouncementSeverity.URGENT),
            announcement("Tin cho team Kinh doanh", AnnouncementTarget.TEAM, other_team.id,
                         "2026-09-12T00:00:00+00:00"),
            announcement("Hẹn giờ tương lai", AnnouncementTarget.ALL, None, "2099-01-01T00:00:00+00:00"),
            announcement("Bản nháp", AnnouncementTarget.ALL, None, None),
            announcement("Tin cho chuyến VN1234", AnnouncementTarget.FLIGHT, outbound.id,
                         "2026-09-12T06:00:00+00:00"),
        ]
    )
    db.commit()

    return {
        "event": event,
        "team": team,
        "traveller": traveller,
        "roommate": roommate,
        "registration": registration,
        "city": city,
    }


# --- Quyền ---


def test_requires_login(client: TestClient, world):
    assert client.get(URL).status_code == 401


def test_me_ignores_user_id_in_query(client: TestClient, world, auth_headers):
    """Người dùng lấy từ JWT: thêm ?user_id= không đổi được người được xem."""
    response = client.get(
        f"{URL}?user_id={world['roommate'].id}", headers=auth_headers("nv@company.vn")
    )
    assert response.json()["profile"]["full_name"] == "Nguyễn Văn Đi"


def test_admin_can_look_up_employee_journey(client: TestClient, world, auth_headers):
    admin = auth_headers("btc@company.vn")

    ok = client.get(f"/api/v1/journey/{world['traveller'].id}", headers=admin)
    missing = client.get("/api/v1/journey/99999", headers=admin)
    employee = client.get(
        f"/api/v1/journey/{world['roommate'].id}", headers=auth_headers("nv@company.vn")
    )

    assert ok.status_code == 200
    assert ok.json()["profile"]["full_name"] == "Nguyễn Văn Đi"
    assert missing.status_code == 404
    assert employee.status_code == 403


# --- Đã công bố ---


def test_full_journey_when_published(client: TestClient, world, auth_headers):
    body = client.get(URL, headers=auth_headers("nv@company.vn")).json()

    assert body["event"]["is_published"] is True
    assert body["profile"]["team"]["color"] == "#7c3aed"
    assert body["flights"]["outbound"]["flight_code"] == "VN1234"
    assert body["flights"]["return"]["flight_code"] == "VN1235"

    bus = body["buses"][0]
    assert bus["bus_code"] == "XE-01"
    assert bus["trip_leg"]["code"] == "CITY_TO_AIRPORT"
    assert bus["pickup_point"]["map_url"].startswith("https://")
    assert bus["leader"] == {"name": "Lê Trưởng Xe", "phone": "0933000333"}
    assert bus["linked_flight_code"] == "VN1234"

    stay = body["accommodation"]
    assert stay["room_number"] == "1204"
    assert stay["is_room_captain"] is True
    assert [mate["full_name"] for mate in stay["roommates"]] == ["Trần Văn Cùng"]

    assert body["gala"]["table_code"] == "B07"
    assert body["gala"]["seat_number"] == 3
    assert body["pending"] == []
    assert body["pending_reasons"] == {}


def test_roommates_expose_only_contact_details(client: TestClient, world, auth_headers):
    response = client.get(URL, headers=auth_headers("nv@company.vn"))
    mate = response.json()["accommodation"]["roommates"][0]

    assert set(mate) == {"full_name", "phone", "team_name", "is_room_captain"}
    for secret in ("001095099999", "Hen suyễn", "roommate@company.vn", "001095012345", "Dị ứng hải sản"):
        assert secret not in response.text


# --- Chưa công bố / không tham gia ---


def test_allocation_hidden_before_publish(client: TestClient, world, auth_headers, db: Session):
    world["event"].status = EventStatus.ALLOCATION_PROCESSING
    db.commit()

    response = client.get(URL, headers=auth_headers("nv@company.vn"))
    body = response.json()

    assert body["event"]["is_published"] is False
    assert body["flights"] == {"outbound": None, "return": None}
    assert body["buses"] == []
    assert body["accommodation"] is None
    assert body["gala"] is None
    assert set(body["pending"]) == {"flights", "buses", "accommodation", "gala"}
    assert set(body["pending_reasons"].values()) == {"not_published"}
    # Thông tin chung vẫn hiện, nhưng không lộ phân bổ qua bất kỳ đường nào.
    assert body["itinerary"]
    assert body["announcements"]
    assert "VN1234" not in response.text
    assert "1204" not in response.text


def test_not_participating_gets_reason(client: TestClient, world, auth_headers, db: Session):
    world["registration"].is_participating = False
    db.commit()

    body = client.get(URL, headers=auth_headers("nv@company.vn")).json()

    assert body["registration"]["is_participating"] is False
    assert body["flights"]["outbound"] is None
    assert set(body["pending_reasons"].values()) == {"not_participating"}


def test_user_without_registration(client: TestClient, world, make_user, auth_headers):
    make_user(email="chuadangky@company.vn")

    body = client.get(URL, headers=auth_headers("chuadangky@company.vn")).json()

    assert body["registration"] is None
    assert set(body["pending_reasons"].values()) == {"not_participating"}


# --- Xếp chưa đủ ---


def test_partial_assignments_are_marked_not_assigned(
    client: TestClient, world, auth_headers, db: Session
):
    registration_id = world["registration"].id
    db.query(FlightAssignment).filter_by(
        registration_id=registration_id, direction=FlightDirection.RETURN
    ).delete()
    db.query(BusAssignment).filter_by(registration_id=registration_id).delete()
    db.query(RoomAssignment).filter_by(registration_id=registration_id).delete()
    db.query(GalaSeatAssignment).filter_by(registration_id=registration_id).delete()
    db.commit()

    body = client.get(URL, headers=auth_headers("nv@company.vn")).json()

    assert body["flights"]["outbound"]["flight_code"] == "VN1234"
    assert body["flights"]["return"] is None
    assert body["pending_reasons"] == {
        "flights": "not_assigned",
        "buses": "not_assigned",
        "accommodation": "not_assigned",
        "gala": "not_assigned",
    }


def test_no_bus_need_means_buses_are_not_pending(
    client: TestClient, world, auth_headers, db: Session
):
    """Tự đi thì không có gì để chờ — đừng hiện ô "đang chờ xe" mãi."""
    registration_id = world["registration"].id
    db.query(BusAssignment).filter_by(registration_id=registration_id).delete()
    db.query(RegistrationBusNeed).filter_by(registration_id=registration_id).update({"needs_bus": False})
    db.commit()

    body = client.get(URL, headers=auth_headers("nv@company.vn")).json()

    assert body["buses"] == []
    assert "buses" not in body["pending"]


# --- Lịch trình & thông báo ---


def test_itinerary_follows_team_and_assigned_shift(
    client: TestClient, world, auth_headers, db: Session
):
    headers = auth_headers("nv@company.vn")
    published = {item["title"] for item in client.get(URL, headers=headers).json()["itinerary"]}

    world["event"].status = EventStatus.ALLOCATION_PROCESSING
    db.commit()
    before = {item["title"] for item in client.get(URL, headers=headers).json()["itinerary"]}

    assert published == {"Tập trung tại điểm đón", "Bay ca 1", "Workshop team Công nghệ"}
    # Trước công bố: người này XIN Ca 1 nhưng chưa chắc được xếp Ca 1 — chưa hiện mục theo ca.
    assert before == {"Tập trung tại điểm đón", "Workshop team Công nghệ"}


def test_announcements_follow_targets_and_schedule(client: TestClient, world, auth_headers):
    body = client.get(URL, headers=auth_headers("nv@company.vn")).json()

    assert [item["title"] for item in body["announcements"]] == [
        "Tin cho chuyến VN1234",
        "Tin cho team Công nghệ",
        "Tin riêng cho bạn",
        "Chào mừng",
    ]
