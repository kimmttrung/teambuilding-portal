"""Kiểm thử API xếp phòng tự động (docs/04 §6, docs/05 §7)."""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.accommodation import Hotel, Room
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
from app.models.user import User

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
        ]
    )
    regs["cuong"].room_id = rooms["m2"].id
    regs["cuong"].room_mode = AssignmentMode.MANUAL
    regs["cuong"].room_assigned_at = NOW
    regs["nghi"].room_id = rooms["m1"].id
    regs["nghi"].room_mode = AssignmentMode.AUTO
    regs["nghi"].room_assigned_at = NOW
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
        row.id: (row.room_id, row.room_mode, row.is_room_captain)
        for row in db.query(Registration).filter(Registration.room_id.is_not(None)).all()
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


def test_weights_come_from_event_settings(client: TestClient, world, admin, db):
    # F5 kiểm tra đọc cột settings của schema v2; CRUD cấu hình kỳ được kiểm tra ở F9.
    db.get(Event, world["event_id"]).settings = {"rooms.team_weight": 25}
    db.commit()
    assert client.post(URL, headers=admin, json={}).json()["params"]["team_weight"] == 25


ROOM_FIELDS = ("room_id", "room_mode", "is_room_captain", "room_assigned_by", "room_assigned_at", "room_note")


def snapshot_room(reg):
    return tuple(getattr(reg, field) for field in ROOM_FIELDS)


def expected_from_preview(body):
    return [
        {"registration_id": guest["registration_id"], "room_id": room["room_id"],
         "is_room_captain": guest["is_room_captain"], "pinned": guest["pinned"]}
        for room in body["rooms"] for guest in room["guests"]
    ]


def test_manual_metadata_and_other_allocations_are_preserved(client, world, admin, db):
    reg = db.get(Registration, world["regs"]["cuong"])
    reg.is_room_captain = True
    reg.room_note = "Giữ quyết định BTC"
    reg.room_assigned_by = db.query(User).filter_by(role=UserRole.ADMIN).one().id
    db.commit()
    before = snapshot_room(reg)
    response = client.post(URL, headers=admin, json={"dry_run": False})
    assert response.status_code == 200, response.text
    db.refresh(reg)
    assert snapshot_room(reg) == before
    assert db.get(Registration, world["regs"]["nghi"]).is_participating is False
    assert db.query(FlightAssignment).count() == 1
    stale = db.get(Registration, world["regs"]["nghi"])
    assert stale.room_id is None and not stale.is_room_captain
    assert stale.room_assigned_at is None and stale.room_mode is None


def test_apply_exact_preview_and_reject_duplicate_or_stale(client, world, admin, db):
    preview = client.post(URL, headers=admin, json={}).json()
    expected = expected_from_preview(preview)
    before = room_rows(db)
    duplicate = client.post(URL, headers=admin, json={
        "dry_run": False, "expected_assignments": expected + [expected[0]],
    })
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "ROOM_ALLOCATION_PREVIEW_STALE"
    assert room_rows(db) == before
    committed = client.post(URL, headers=admin, json={"dry_run": False, "expected_assignments": expected})
    assert committed.status_code == 200, committed.text
    actual = room_rows(db)
    assert {(reg, values[0], values[2]) for reg, values in actual.items()} == {
        (bed["registration_id"], bed["room_id"], bed["is_room_captain"]) for bed in expected
    }
    fresh_before = room_rows(db)
    changed = client.post(URL, headers=admin, json={"dry_run": False, "expected_assignments": []})
    assert changed.status_code == 409
    assert room_rows(db) == fresh_before


def test_preview_changed_capacity_requires_new_preview(client, world, admin, db):
    expected = expected_from_preview(client.post(URL, headers=admin, json={}).json())
    db.get(Room, world["rooms"]["m1"]).capacity = 1
    db.commit()
    before = room_rows(db)
    response = client.post(URL, headers=admin, json={"dry_run": False, "expected_assignments": expected})
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "ROOM_ALLOCATION_PREVIEW_STALE"
    assert room_rows(db) == before
    assert db.query(AuditLog).filter_by(action="room.allocated").count() == 0


def test_auto_assignment_never_mixes_any_rooms(client, world, admin, db):
    # Cả hai giới dùng phòng any; thuật toán phải dành từng phòng cho một nhóm giới.
    for room in db.query(Room).all():
        room.gender_policy = RoomGenderPolicy.ANY
    db.commit()
    response = client.post(URL, headers=admin, json={"dry_run": False, "force_reallocate": True})
    assert response.status_code == 200, response.text
    for room in response.json()["rooms"]:
        assert len({guest["gender"] for guest in room["guests"]}) <= 1
        assert room["assigned"] <= room["capacity"]


def test_manual_conflict_is_kept_and_flagged(client, world, admin, db):
    db.get(Room, world["rooms"]["m2"]).gender_policy = RoomGenderPolicy.FEMALE
    db.commit()
    response = client.post(URL, headers=admin, json={"dry_run": False})
    assert response.status_code == 200, response.text
    assert any(flag["type"] == "PINNED_ROOM_CONFLICT" for flag in response.json()["flags"])
    assert room_rows(db)[world["regs"]["cuong"]] == (world["rooms"]["m2"], "manual", False)


def test_allocation_leaves_other_event_untouched(client, world, admin, db):
    other = Event(code="OTHER", name="Kỳ khác", start_date="2027-01-01", end_date="2027-01-03",
                  status=EventStatus.REGISTRATION_CLOSED, terms_version="v1")
    db.add(other)
    db.flush()
    hotel = Hotel(event_id=other.id, name="Khách sạn khác")
    db.add(hotel)
    db.flush()
    room = Room(hotel_id=hotel.id, room_number="201", capacity=2)
    db.add(room)
    db.flush()
    reg = Registration(event_id=other.id, user_id=db.get(Registration, world["regs"]["an"]).user_id,
                       is_participating=True, room_id=room.id, room_mode="manual", is_room_captain=True,
                       room_note="Kỳ khác", room_assigned_at=NOW)
    db.add(reg)
    db.commit()
    before = snapshot_room(reg)
    response = client.post(URL, headers=admin, json={"dry_run": False, "force_reallocate": True})
    assert response.status_code == 200, response.text
    db.refresh(reg)
    assert snapshot_room(reg) == before
    assert all(load["hotel_id"] != hotel.id for load in response.json()["rooms"])


def test_no_capacity_clears_only_old_auto_rooms(client, world, admin, db):
    # Phòng nữ bị bỏ khỏi kỳ sau khi chưa ai được xếp: hai người nữ còn unassigned.
    db.delete(db.get(Room, world["rooms"]["f1"]))
    db.commit()
    response = client.post(URL, headers=admin, json={"dry_run": False})
    assert response.status_code == 200, response.text
    assert {guest["registration_id"] for guest in response.json()["unassigned"]} == {
        world["regs"]["dung"], world["regs"]["ha"],
    }
    assert response.json()["summary"]["unassigned"] == 2
    assert room_rows(db)[world["regs"]["cuong"]][1] == "manual"


def test_allocation_rolls_back_stale_cleanup_when_audit_fails(world, db, monkeypatch):
    from app.services import room_allocation_service
    before = room_rows(db)
    def fail(*args, **kwargs):
        raise RuntimeError("audit unavailable")
    monkeypatch.setattr(room_allocation_service.audit_service, "log", fail)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        room_allocation_service.commit(
            db, event=db.get(Event, world["event_id"]),
            actor=db.query(User).filter_by(role=UserRole.ADMIN).one(),
        )
    assert room_rows(db) == before
    assert db.get(Registration, world["regs"]["nghi"]).room_id == world["rooms"]["m1"]
