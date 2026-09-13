"""Kiểm thử khách sạn, phòng và phân phòng (docs/04 §6, docs/05 §7)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import AuditLog, Event, Hotel, Registration, Room, RoomAssignment, Team, User
from app.models.enums import (
    AssignmentMode,
    EventStatus,
    Gender,
    RegistrationStatus,
    RoomGenderPolicy,
    UserRole,
)

HOTELS = "/api/v1/hotels"
ROOMS = "/api/v1/rooms"
ASSIGN = "/api/v1/room-assignments"


@pytest.fixture
def setup(db: Session) -> dict:
    """1 khách sạn: phòng nam 2 chỗ, phòng nữ 2 chỗ, phòng không giới hạn 3 chỗ."""
    event = Event(
        code="TB2026",
        name="Team Building 2026",
        start_date="2026-10-15",
        end_date="2026-10-17",
        status=EventStatus.REGISTRATION_CLOSED,
        terms_version="v1",
        is_active=True,
    )
    team = Team(code="IT", name="Công nghệ")
    db.add_all([event, team])
    db.flush()

    hotel = Hotel(
        event_id=event.id,
        name="Sunset Beach Resort",
        check_in_at="2026-10-15T07:00:00+00:00",
        check_out_at="2026-10-17T05:00:00+00:00",
    )
    db.add(hotel)
    db.flush()

    male = Room(hotel_id=hotel.id, room_number="801", room_type="twin", capacity=2, floor="8",
                gender_policy=RoomGenderPolicy.MALE)
    female = Room(hotel_id=hotel.id, room_number="802", room_type="twin", capacity=2, floor="8",
                  gender_policy=RoomGenderPolicy.FEMALE)
    shared = Room(hotel_id=hotel.id, room_number="901", room_type="triple", capacity=3, floor="9",
                  gender_policy=RoomGenderPolicy.ANY)
    db.add_all([male, female, shared])
    db.commit()
    return {"event": event, "team": team, "hotel": hotel, "male": male, "female": female, "shared": shared}


@pytest.fixture
def admin_headers(make_user, auth_headers, setup):
    make_user(email="btc@company.vn", password="MatKhau123", role=UserRole.ADMIN)
    return auth_headers("btc@company.vn")


@pytest.fixture
def person(db: Session, setup):
    counter = {"n": 0}

    def _make(
        *,
        gender=Gender.MALE,
        participating=True,
        status=RegistrationStatus.SUBMITTED,
        team=None,
        health_note=None,
        dietary=None,
    ) -> Registration:
        counter["n"] += 1
        index = counter["n"]
        user = User(
            email=f"nv{index}@company.vn",
            full_name=f"Người Số {index:02d}",
            employee_code=f"NV{index:03d}",
            password_hash="x",
            role=UserRole.EMPLOYEE,
            gender=gender,
            team_id=team.id if team else None,
            phone="0912345678",
            date_of_birth="1995-01-01",
            id_card_number="001095012345",
            health_note=health_note,
            dietary_restriction=dietary,
        )
        db.add(user)
        db.flush()
        registration = Registration(
            event_id=setup["event"].id,
            user_id=user.id,
            is_participating=participating,
            status=status,
            submitted_at="2026-09-12T03:00:00+00:00",
        )
        db.add(registration)
        db.commit()
        db.refresh(registration)
        return registration

    return _make


def assign(client, headers, registration, room, **extra):
    return client.post(
        ASSIGN,
        headers=headers,
        json={"registration_id": registration.id, "room_id": room.id, **extra},
    )


# --- Quyền ---


def test_employee_cannot_manage_accommodation(client: TestClient, setup, make_user, auth_headers):
    make_user(email="nv@company.vn", password="MatKhau123")
    headers = auth_headers("nv@company.vn")

    assert client.get(HOTELS, headers=headers).status_code == 403
    assert client.get(ROOMS, headers=headers).status_code == 403
    assert client.get(f"{ROOMS}/summary", headers=headers).status_code == 403
    assert client.get(ASSIGN, headers=headers).status_code == 403


# --- Khách sạn ---


def test_create_hotel_and_reject_checkout_before_checkin(
    client: TestClient, setup, admin_headers, db: Session
):
    created = client.post(
        HOTELS,
        headers=admin_headers,
        json={
            "name": "Vinpearl Phú Quốc",
            "check_in_at": "2026-10-15T07:00:00+00:00",
            "check_out_at": "2026-10-17T05:00:00+00:00",
        },
    )
    wrong = client.post(
        HOTELS,
        headers=admin_headers,
        json={
            "name": "Sai giờ",
            "check_in_at": "2026-10-17T07:00:00+00:00",
            "check_out_at": "2026-10-15T05:00:00+00:00",
        },
    )

    assert created.status_code == 201
    assert db.query(AuditLog).filter(AuditLog.action == "hotel.created").count() == 1
    assert wrong.status_code == 422


def test_hotel_list_shows_room_bed_and_assigned_counts(
    client: TestClient, setup, admin_headers, person
):
    assign(client, admin_headers, person(gender=Gender.MALE), setup["male"])

    hotel = client.get(HOTELS, headers=admin_headers).json()[0]

    assert hotel["room_count"] == 3
    assert hotel["bed_count"] == 7
    assert hotel["assigned_count"] == 1


# --- Phòng ---


def test_create_room_rejects_duplicate_and_foreign_hotel(
    client: TestClient, setup, admin_headers, db: Session
):
    duplicate = client.post(
        ROOMS,
        headers=admin_headers,
        json={"hotel_id": setup["hotel"].id, "room_number": "801", "capacity": 2},
    )

    other_event = Event(
        code="TB2025", name="Kỳ cũ", start_date="2025-10-15", end_date="2025-10-17",
        status=EventStatus.COMPLETED, terms_version="v1",
    )
    db.add(other_event)
    db.flush()
    foreign = Hotel(event_id=other_event.id, name="Khách sạn kỳ cũ")
    db.add(foreign)
    db.commit()

    foreign_room = client.post(
        ROOMS, headers=admin_headers, json={"hotel_id": foreign.id, "room_number": "101", "capacity": 2}
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "ROOM_NUMBER_DUPLICATED"
    assert foreign_room.status_code == 404
    assert foreign_room.json()["error"]["code"] == "HOTEL_NOT_FOUND"


# --- Xếp phòng: giới tính ---


def test_assign_respects_gender_policy(
    client: TestClient, setup, admin_headers, person, db: Session
):
    ok = assign(client, admin_headers, person(gender=Gender.MALE), setup["male"])
    wrong_gender = assign(client, admin_headers, person(gender=Gender.FEMALE), setup["male"])
    no_gender = assign(client, admin_headers, person(gender=None), setup["female"])
    other_in_shared = assign(client, admin_headers, person(gender=Gender.OTHER), setup["shared"])

    assert ok.status_code == 200
    assert ok.json()["assignment"]["assignment_mode"] == "manual"
    assert ok.json()["assignment"]["room_number"] == "801"
    assert db.query(AuditLog).filter(AuditLog.action == "room_assignment.created").count() == 2

    assert wrong_gender.status_code == 400
    assert wrong_gender.json()["error"]["code"] == "GENDER_POLICY_VIOLATION"
    assert no_gender.status_code == 400
    assert no_gender.json()["error"]["code"] == "MISSING_GENDER"
    assert other_in_shared.status_code == 200


def test_assign_blocked_when_room_full(client: TestClient, setup, admin_headers, person):
    for _ in range(2):
        assert assign(client, admin_headers, person(gender=Gender.MALE), setup["male"]).status_code == 200

    third = assign(client, admin_headers, person(gender=Gender.MALE), setup["male"])

    assert third.status_code == 409
    assert third.json()["error"]["code"] == "ROOM_FULL"


def test_existing_room_requires_replace_flag_to_move(
    client: TestClient, setup, admin_headers, person, db: Session
):
    registration = person(gender=Gender.MALE)
    assign(client, admin_headers, registration, setup["male"])

    blocked = assign(client, admin_headers, registration, setup["shared"])
    moved = assign(
        client, admin_headers, registration, setup["shared"], replace_existing=True, reason="Đổi phòng theo nguyện vọng"
    )

    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "ALREADY_HAS_ROOM"
    assert moved.status_code == 200
    assert moved.json()["moved_from_room_id"] == setup["male"].id
    assert db.query(RoomAssignment).filter_by(registration_id=registration.id).one().room_id == setup["shared"].id
    audit = db.query(AuditLog).filter(AuditLog.action == "room_assignment.moved").one()
    assert audit.reason == "Đổi phòng theo nguyện vọng"


def test_only_one_captain_per_room(client: TestClient, setup, admin_headers, person, db: Session):
    first = person(gender=Gender.MALE)
    second = person(gender=Gender.MALE)
    assign(client, admin_headers, first, setup["male"], is_room_captain=True)
    assign(client, admin_headers, second, setup["male"], is_room_captain=True)

    captains = db.query(RoomAssignment).filter_by(room_id=setup["male"].id, is_room_captain=True).all()
    assert [row.registration_id for row in captains] == [second.id]


def test_non_participating_registration_cannot_get_room(
    client: TestClient, setup, admin_headers, person
):
    response = assign(client, admin_headers, person(participating=False), setup["shared"])

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "REGISTRATION_NOT_FOUND"


# --- Bảo vệ khi sửa / xoá ---


def test_room_and_hotel_update_delete_guards(client: TestClient, setup, admin_headers, person):
    for _ in range(2):
        assign(client, admin_headers, person(gender=Gender.MALE), setup["male"])
    url = f"{ROOMS}/{setup['male'].id}"

    shrink = client.patch(url, headers=admin_headers, json={"capacity": 1})
    to_female = client.patch(url, headers=admin_headers, json={"gender_policy": "female"})
    to_any = client.patch(url, headers=admin_headers, json={"gender_policy": "any"})
    delete_room = client.delete(url, headers=admin_headers)
    delete_hotel = client.delete(f"{HOTELS}/{setup['hotel'].id}", headers=admin_headers)

    assert shrink.status_code == 409
    assert shrink.json()["error"]["code"] == "CAPACITY_BELOW_OCCUPIED"
    assert to_female.status_code == 409
    assert to_female.json()["error"]["code"] == "GENDER_POLICY_CONFLICT"
    assert to_any.status_code == 200
    assert to_any.json()["gender_policy"] == "any"
    assert delete_room.status_code == 409
    assert delete_room.json()["error"]["code"] == "ROOM_HAS_OCCUPANTS"
    assert delete_hotel.status_code == 409
    assert delete_hotel.json()["error"]["code"] == "HOTEL_HAS_OCCUPANTS"


def test_remove_assignment_requires_reason_and_frees_bed(
    client: TestClient, setup, admin_headers, person, db: Session
):
    row_id = assign(client, admin_headers, person(gender=Gender.MALE), setup["male"]).json()["assignment"]["id"]

    no_reason = client.delete(f"{ASSIGN}/{row_id}", headers=admin_headers)
    removed = client.delete(f"{ASSIGN}/{row_id}?reason=Không đi nữa", headers=admin_headers)

    assert no_reason.status_code == 422
    assert removed.status_code == 204
    assert db.query(RoomAssignment).count() == 0
    room = client.get(f"{ROOMS}/{setup['male'].id}", headers=admin_headers).json()
    assert room["occupied"] == 0
    assert room["remaining"] == 2


# --- Người ở phòng ---


def test_occupants_flag_health_note_without_content(
    client: TestClient, setup, admin_headers, person
):
    registration = person(
        gender=Gender.FEMALE, team=setup["team"], health_note="Hen suyễn, cần phòng tầng thấp", dietary="Ăn chay"
    )
    assign(client, admin_headers, registration, setup["female"], is_room_captain=True)

    response = client.get(f"{ROOMS}/{setup['female'].id}/occupants", headers=admin_headers)

    assert response.status_code == 200
    row = response.json()[0]
    assert row["team_name"] == "Công nghệ"
    assert row["is_room_captain"] is True
    assert row["dietary_restriction"] == "Ăn chay"
    assert row["has_health_note"] is True
    assert "Hen suyễn" not in response.text
    assert "001095012345" not in response.text


# --- Tổng quan giường ---


def test_summary_reports_gender_shortfall_after_shared_rooms(
    client: TestClient, setup, admin_headers, person
):
    """5 nam cho 2 giường nam (thiếu 3), 1 người giới tính khác chỉ ở được phòng 'any'.
    Phòng 'any' 3 giường bù được 3 chỗ -> vẫn còn 1 người không có giường hợp lệ."""
    for _ in range(5):
        person(gender=Gender.MALE)
    person(gender=Gender.FEMALE)
    person(gender=Gender.OTHER)

    body = client.get(f"{ROOMS}/summary", headers=admin_headers).json()
    policies = {load["gender_policy"]: load for load in body["by_policy"]}

    assert body["participants"] == 7
    assert body["total_beds"] == 7
    assert policies["male"]["beds"] == 2
    assert policies["male"]["shortfall"] == 3
    assert policies["female"]["shortfall"] == 0
    assert policies["any"]["participants"] == 1
    assert body["uncovered"] == 1
    assert body["unassigned"] == 7


def test_list_assignments_filters(client: TestClient, setup, admin_headers, person):
    assign(client, admin_headers, person(gender=Gender.MALE, team=setup["team"]), setup["male"])
    assign(client, admin_headers, person(gender=Gender.OTHER), setup["shared"])

    everything = client.get(ASSIGN, headers=admin_headers).json()
    by_room = client.get(f"{ASSIGN}?room_id={setup['shared'].id}", headers=admin_headers).json()
    by_team = client.get(f"{ASSIGN}?team_id={setup['team'].id}", headers=admin_headers).json()

    assert everything["total"] == 2
    assert by_room["total"] == 1
    assert by_room["items"][0]["hotel_name"] == "Sunset Beach Resort"
    assert by_team["total"] == 1
    assert by_team["items"][0]["room_number"] == "801"
