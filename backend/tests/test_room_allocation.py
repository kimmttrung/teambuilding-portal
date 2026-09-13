"""Kiểm thử API xếp phòng tự động (docs/04 §6, docs/05 §7)."""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.accommodation import Hotel, Room, RoomAssignment
from app.models.audit import AuditLog
from app.models.enums import (
    AssignmentMode,
    EventStatus,
    FlightDirection,
    Gender,
    RegistrationStatus,
    RoomGenderPolicy,
    UserRole,
)
from app.models.event import Event
from app.models.flight import Flight, FlightAssignment
from app.models.org import Team
from app.models.registration import Registration

URL = "/api/v1/rooms/allocate"
NOW = "2026-09-13T02:00:00+00:00"


@pytest.fixture
def world(db: Session, make_user) -> dict:
    """Hai phòng nam, một phòng nữ, đều phòng đôi.

    An, Bình (Công nghệ, nam) · Cường (Kinh doanh, nam) đã được BTC xếp tay vào 802 ·
    Dung (Công nghệ, nữ) · Hà (Kinh doanh, nữ) · Nghỉ đã rút khỏi chương trình nhưng còn bản
    ghi phòng cũ ở 801.
    """
    event = Event(
        code="TB2026", name="Team Building 2026", start_date="2026-10-15", end_date="2026-10-17",
        status=EventStatus.REGISTRATION_CLOSED, terms_version="v1", is_active=True,
    )
    it = Team(code="IT", name="Công nghệ")
    sales = Team(code="SALE", name="Kinh doanh")
    db.add_all([event, it, sales])
    db.flush()

    hotel = Hotel(event_id=event.id, name="Sunset Beach Resort")
    db.add(hotel)
    db.flush()
    rooms = {
        "m1": Room(hotel_id=hotel.id, room_number="801", capacity=2, floor="8", gender_policy=RoomGenderPolicy.MALE),
        "m2": Room(hotel_id=hotel.id, room_number="802", capacity=2, floor="8", gender_policy=RoomGenderPolicy.MALE),
        "f1": Room(hotel_id=hotel.id, room_number="803", capacity=2, floor="8", gender_policy=RoomGenderPolicy.FEMALE),
    }
    db.add_all(rooms.values())
    db.flush()

    make_user(email="btc@company.vn", role=UserRole.ADMIN, full_name="Trưởng BTC")

    def join(key, name, gender, team, *, participating=True):
        user = make_user(email=f"{key}@company.vn", full_name=name, gender=gender, team_id=team.id)
        registration = Registration(
            event_id=event.id, user_id=user.id, is_participating=participating,
            status=RegistrationStatus.SUBMITTED, submitted_at=NOW,
        )
        db.add(registration)
        db.flush()
        return registration

    regs = {
        "an": join("an", "An", Gender.MALE, it),
        "binh": join("binh", "Bình", Gender.MALE, it),
        "cuong": join("cuong", "Cường", Gender.MALE, sales),
        "dung": join("dung", "Dung", Gender.FEMALE, it),
        "ha": join("ha", "Hà", Gender.FEMALE, sales),
        "nghi": join("nghi", "Nghỉ", Gender.MALE, sales, participating=False),
    }

    flight = Flight(
        event_id=event.id, flight_code="VN1234", direction=FlightDirection.OUTBOUND,
        departure_airport="HAN", arrival_airport="PQC",
        departure_time="2026-10-15T01:00:00+00:00", arrival_time="2026-10-15T03:00:00+00:00", capacity=60,
    )
    db.add(flight)
    db.flush()
    db.add_all(
        [
            FlightAssignment(
                registration_id=regs["an"].id, flight_id=flight.id, direction=FlightDirection.OUTBOUND,
                assignment_mode=AssignmentMode.AUTO, assigned_at=NOW,
            ),
            RoomAssignment(
                registration_id=regs["cuong"].id, room_id=rooms["m2"].id,
                assignment_mode=AssignmentMode.MANUAL, assigned_at=NOW,
            ),
            RoomAssignment(
                registration_id=regs["nghi"].id, room_id=rooms["m1"].id,
                assignment_mode=AssignmentMode.AUTO, assigned_at=NOW,
            ),
        ]
    )
    db.commit()
    return {
        "event_id": event.id,
        "rooms": {key: item.id for key, item in rooms.items()},
        "regs": {key: item.id for key, item in regs.items()},
    }


@pytest.fixture
def admin(world, auth_headers):
    return auth_headers("btc@company.vn")


def room_rows(db: Session) -> dict[int, tuple[int, str, bool]]:
    db.expire_all()
    return {
        row.registration_id: (row.room_id, row.assignment_mode, row.is_room_captain)
        for row in db.query(RoomAssignment).all()
    }


def test_room_allocation_is_admin_only(client: TestClient, world, auth_headers):
    assert client.post(URL, headers=auth_headers("an@company.vn"), json={}).status_code == 403


def test_dry_run_previews_without_writing(client: TestClient, world, admin, db: Session):
    before = room_rows(db)

    response = client.post(URL, headers=admin, json={"dry_run": True})

    assert response.status_code == 200, response.text
    body = response.json()
    rooms = {load["room_number"]: load for load in body["rooms"]}
    assert body["dry_run"] is True
    assert body["summary"]["assigned"] == 5
    assert {guest["full_name"] for guest in rooms["801"]["guests"]} == {"An", "Bình"}
    assert {guest["full_name"]: guest["flight_code"] for guest in rooms["801"]["guests"]}["An"] == "VN1234"
    assert rooms["802"]["guests"] == [
        {
            "registration_id": world["regs"]["cuong"], "full_name": "Cường", "team_id": rooms["802"]["guests"][0]["team_id"],
            "team_name": "Kinh doanh", "gender": "male", "flight_code": None, "pinned": True, "is_room_captain": False,
        }
    ]
    assert room_rows(db) == before


def test_commit_writes_keeps_manual_removes_stale_and_audits(client: TestClient, world, admin, db: Session):
    response = client.post(URL, headers=admin, json={"dry_run": False})

    assert response.status_code == 200, response.text
    assert response.json()["removed_stale"] == 1
    rooms, regs = world["rooms"], world["regs"]
    assert room_rows(db) == {
        regs["an"]: (rooms["m1"], "auto", True),
        regs["binh"]: (rooms["m1"], "auto", False),
        regs["cuong"]: (rooms["m2"], "manual", False),
        regs["dung"]: (rooms["f1"], "auto", True),
        regs["ha"]: (rooms["f1"], "auto", False),
    }
    audit = db.query(AuditLog).filter_by(action="room.allocated").one()
    assert json.loads(audit.after_data)["removed_stale"] == 1


def test_commit_blocked_while_registration_open(client: TestClient, world, admin, db: Session):
    db.get(Event, world["event_id"]).status = EventStatus.REGISTRATION_OPEN
    db.commit()

    response = client.post(URL, headers=admin, json={"dry_run": False})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "REGISTRATION_STILL_OPEN"
    assert len(room_rows(db)) == 2


def test_force_reallocate_replaces_manual_rows(client: TestClient, world, admin, db: Session):
    response = client.post(URL, headers=admin, json={"dry_run": False, "force_reallocate": True})

    assert response.status_code == 200, response.text
    rows = room_rows(db)
    assert rows[world["regs"]["cuong"]][1] == "auto"
    assert all(mode == "auto" for _room, mode, _captain in rows.values())


def test_weights_come_from_event_settings(client: TestClient, world, admin):
    saved = client.put(
        f"/api/v1/events/{world['event_id']}/settings",
        headers=admin,
        json={"values": {"rooms.team_weight": 25}},
    )

    assert saved.status_code == 200, saved.text
    assert client.post(URL, headers=admin, json={}).json()["params"]["team_weight"] == 25
