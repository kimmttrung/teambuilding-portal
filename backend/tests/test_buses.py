"""Kiểm thử API xe, Trưởng xe, phân xe và điều chỉnh (docs/04 §7, docs/05 §6)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    Bus,
    BusAssignment,
    Event,
    Flight,
    FlightAssignment,
    PickupPoint,
    Registration,
    RegistrationBusNeed,
    Team,
    TripLeg,
    User,
)
from app.models.enums import (
    AssignmentMode,
    EventStatus,
    FlightDirection,
    Gender,
    RegistrationStatus,
    UserRole,
)

BUSES = "/api/v1/buses"
ASSIGNMENTS = "/api/v1/bus-assignments"


@pytest.fixture
def setup(db: Session) -> dict:
    """Kỳ đã đóng đăng ký: 2 chuyến chiều đi, 1 chiều về, 3 chặng, 3 điểm đón."""
    event = Event(
        code="TB2026",
        name="Team Building 2026",
        start_date="2026-10-15",
        end_date="2026-10-17",
        status=EventStatus.REGISTRATION_CLOSED,
        terms_version="v1",
        is_active=True,
    )
    team1 = Team(code="IT", name="Công nghệ")
    team2 = Team(code="SALE", name="Kinh doanh")
    db.add_all([event, team1, team2])
    db.flush()

    def flight(code, direction, departure):
        return Flight(
            event_id=event.id,
            flight_code=code,
            direction=direction,
            departure_airport="HAN" if direction == FlightDirection.OUTBOUND else "PQC",
            arrival_airport="PQC" if direction == FlightDirection.OUTBOUND else "HAN",
            departure_time=departure,
            arrival_time=departure.replace("T0", "T1"),
            capacity=60,
        )

    out1 = flight("VN1234", FlightDirection.OUTBOUND, "2026-10-15T06:30:00+00:00")
    out2 = flight("VN1250", FlightDirection.OUTBOUND, "2026-10-15T08:15:00+00:00")
    back = flight("VN1235", FlightDirection.RETURN, "2026-10-17T05:00:00+00:00")

    city = TripLeg(
        event_id=event.id,
        code="CITY_TO_AIRPORT",
        name="HN → Sân bay",
        direction=FlightDirection.OUTBOUND,
        is_airport_linked=False,
        display_order=1,
    )
    airport = TripLeg(
        event_id=event.id,
        code="AIRPORT_TO_HOTEL",
        name="Sân bay → Khách sạn",
        direction=FlightDirection.OUTBOUND,
        is_airport_linked=True,
        display_order=2,
    )
    db.add_all([out1, out2, back, city, airport])
    db.flush()

    point_a = PickupPoint(event_id=event.id, trip_leg_id=city.id, name="Toà nhà Keangnam")
    point_b = PickupPoint(event_id=event.id, trip_leg_id=city.id, name="Trụ sở Hoàn Kiếm")
    point_airport = PickupPoint(event_id=event.id, trip_leg_id=airport.id, name="Cổng ga đến")
    db.add_all([point_a, point_b, point_airport])
    db.commit()

    return {
        "event": event,
        "team1": team1,
        "team2": team2,
        "out1": out1,
        "out2": out2,
        "back": back,
        "city": city,
        "airport": airport,
        "point_a": point_a,
        "point_b": point_b,
        "point_airport": point_airport,
    }


@pytest.fixture
def admin_headers(make_user, auth_headers, setup):
    make_user(email="btc@company.vn", password="MatKhau123", role=UserRole.ADMIN)
    return auth_headers("btc@company.vn")


@pytest.fixture
def rider(db: Session, setup):
    """CBNV tham gia, có nhu cầu xe ở các chặng cho trước và (tuỳ chọn) chuyến bay."""
    counter = {"n": 0}

    def _make(*, team=None, needs=None, flight=None, participating=True) -> Registration:
        counter["n"] += 1
        index = counter["n"]
        user = User(
            email=f"nv{index}@company.vn",
            full_name=f"Nguyễn Văn {index:02d}",
            employee_code=f"NV{index:03d}",
            password_hash="x",
            role=UserRole.EMPLOYEE,
            team_id=team.id if team else None,
            phone=f"09123456{index:02d}",
            gender=Gender.MALE,
            date_of_birth="1995-01-01",
            id_card_number="001095012345",
        )
        db.add(user)
        db.flush()

        registration = Registration(
            event_id=setup["event"].id,
            user_id=user.id,
            is_participating=participating,
            status=RegistrationStatus.SUBMITTED,
            submitted_at="2026-09-12T03:00:00+00:00",
        )
        db.add(registration)
        db.flush()

        for leg, point in (needs or {}).items():
            db.add(
                RegistrationBusNeed(
                    registration_id=registration.id,
                    trip_leg_id=leg.id,
                    needs_bus=True,
                    pickup_point_id=point.id if point else None,
                )
            )
        if flight is not None:
            db.add(
                FlightAssignment(
                    registration_id=registration.id,
                    flight_id=flight.id,
                    direction=flight.direction,
                    assignment_mode=AssignmentMode.AUTO,
                    assigned_at="2026-09-12T04:00:00+00:00",
                )
            )
        db.commit()
        db.refresh(registration)
        return registration

    return _make


def add_bus(db: Session, setup, *, leg, code="XE-01", capacity=45, pickup=None, flight=None, leader=None) -> Bus:
    bus = Bus(
        event_id=setup["event"].id,
        trip_leg_id=leg.id,
        bus_code=code,
        capacity=capacity,
        pickup_point_id=pickup.id if pickup else None,
        linked_flight_id=flight.id if flight else None,
        leader_user_id=leader.id if leader else None,
    )
    db.add(bus)
    db.commit()
    db.refresh(bus)
    return bus


def seat(db: Session, registration, bus, *, mode=AssignmentMode.AUTO) -> BusAssignment:
    row = BusAssignment(
        registration_id=registration.id,
        bus_id=bus.id,
        trip_leg_id=bus.trip_leg_id,
        assignment_mode=mode,
        assigned_at="2026-09-12T04:00:00+00:00",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def bus_payload(setup, **overrides) -> dict:
    data = {
        "trip_leg_id": setup["city"].id,
        "bus_code": "XE-01",
        "plate_number": "29B-123.45",
        "capacity": 45,
        "pickup_point_id": setup["point_a"].id,
        "gather_time": "2026-10-15T04:30:00+00:00",
        "departure_time": "2026-10-15T04:45:00+00:00",
        "linked_flight_id": setup["out1"].id,
    }
    data.update(overrides)
    return data


# --- Quyền ---


def test_employee_cannot_manage_buses(client: TestClient, setup, make_user, auth_headers):
    make_user(email="nv@company.vn", password="MatKhau123")
    headers = auth_headers("nv@company.vn")

    assert client.get(BUSES, headers=headers).status_code == 403
    assert client.post(BUSES, headers=headers, json=bus_payload(setup)).status_code == 403
    assert (
        client.post(f"{BUSES}/allocate", headers=headers, json={"trip_leg_id": setup["city"].id}).status_code
        == 403
    )
    assert client.get(ASSIGNMENTS, headers=headers).status_code == 403


# --- CRUD ---


def test_create_bus_returns_names_and_audit(client: TestClient, setup, admin_headers, db: Session):
    response = client.post(BUSES, headers=admin_headers, json=bus_payload(setup))

    assert response.status_code == 201
    body = response.json()
    assert body["trip_leg_code"] == "CITY_TO_AIRPORT"
    assert body["pickup_point_name"] == "Toà nhà Keangnam"
    assert body["linked_flight_code"] == "VN1234"
    assert body["remaining_seats"] == 45
    assert body["airport_linked"] is False
    assert db.query(AuditLog).filter(AuditLog.action == "bus.created").count() == 1


def test_create_rejects_pickup_point_of_another_leg(client: TestClient, setup, admin_headers):
    response = client.post(
        BUSES, headers=admin_headers, json=bus_payload(setup, pickup_point_id=setup["point_airport"].id)
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "PICKUP_POINT_LEG_MISMATCH"


def test_create_rejects_flight_of_wrong_direction(client: TestClient, setup, admin_headers):
    """Xe chặng chiều đi không thể phục vụ chuyến bay chiều về."""
    response = client.post(
        BUSES, headers=admin_headers, json=bus_payload(setup, linked_flight_id=setup["back"].id)
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "FLIGHT_DIRECTION_MISMATCH"


def test_create_rejects_duplicate_code_on_same_leg(client: TestClient, setup, admin_headers):
    assert client.post(BUSES, headers=admin_headers, json=bus_payload(setup)).status_code == 201
    response = client.post(BUSES, headers=admin_headers, json=bus_payload(setup))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "BUS_CODE_DUPLICATED"


def test_create_rejects_departure_before_gather(client: TestClient, setup, admin_headers):
    response = client.post(
        BUSES,
        headers=admin_headers,
        json=bus_payload(setup, departure_time="2026-10-15T04:00:00+00:00"),
    )
    assert response.status_code == 422


def test_capacity_floor_and_delete_guard(
    client: TestClient, setup, admin_headers, rider, db: Session
):
    bus = add_bus(db, setup, leg=setup["city"], pickup=setup["point_a"])
    for _ in range(3):
        seat(db, rider(needs={setup["city"]: setup["point_a"]}), bus)

    lowered = client.patch(f"{BUSES}/{bus.id}", headers=admin_headers, json={"capacity": 2})
    assert lowered.status_code == 409
    assert lowered.json()["error"]["code"] == "CAPACITY_BELOW_ASSIGNED"

    deleted = client.delete(f"{BUSES}/{bus.id}", headers=admin_headers)
    assert deleted.status_code == 409
    assert deleted.json()["error"]["code"] == "BUS_HAS_PASSENGERS"

    empty = add_bus(db, setup, leg=setup["city"], code="XE-09")
    assert client.delete(f"{BUSES}/{empty.id}", headers=admin_headers).status_code == 204


# --- Trưởng xe ---


def test_leader_from_user_copies_contact(
    client: TestClient, setup, admin_headers, make_user, db: Session
):
    leader = make_user(
        email="tn@company.vn", role=UserRole.TEAM_LEADER, full_name="Trần Trưởng Xe", phone="0988111222"
    )
    bus = add_bus(db, setup, leg=setup["city"])

    response = client.patch(
        f"{BUSES}/{bus.id}/leader", headers=admin_headers, json={"leader_user_id": leader.id}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["leader_user_id"] == leader.id
    assert body["leader_name"] == "Trần Trưởng Xe"
    assert body["leader_phone"] == "0988111222"
    assert db.query(AuditLog).filter(AuditLog.action == "bus.leader_changed").count() == 1


def test_outsider_leader_needs_name_and_phone(client: TestClient, setup, admin_headers, db: Session):
    bus = add_bus(db, setup, leg=setup["city"])

    only_name = client.patch(
        f"{BUSES}/{bus.id}/leader", headers=admin_headers, json={"leader_name": "Hướng dẫn viên"}
    )
    both = client.patch(
        f"{BUSES}/{bus.id}/leader",
        headers=admin_headers,
        json={"leader_name": "Hướng dẫn viên", "leader_phone": "0909000111"},
    )

    assert only_name.status_code == 422
    assert both.status_code == 200
    assert both.json()["leader_user_id"] is None


def test_unknown_leader_user_is_rejected(client: TestClient, setup, admin_headers, db: Session):
    bus = add_bus(db, setup, leg=setup["city"])
    response = client.patch(
        f"{BUSES}/{bus.id}/leader", headers=admin_headers, json={"leader_user_id": 99999}
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "USER_NOT_FOUND"


def test_passengers_visible_to_admin_and_own_leader_only(
    client: TestClient, setup, admin_headers, make_user, auth_headers, rider, db: Session
):
    own_leader = make_user(email="leader1@company.vn", role=UserRole.TEAM_LEADER)
    other_leader = make_user(email="leader2@company.vn", role=UserRole.TEAM_LEADER)
    make_user(email="nv@company.vn")
    bus = add_bus(db, setup, leg=setup["city"], pickup=setup["point_a"], leader=own_leader)
    seat(db, rider(team=setup["team1"], needs={setup["city"]: setup["point_a"]}, flight=setup["out1"]), bus)

    url = f"{BUSES}/{bus.id}/passengers"
    as_admin = client.get(url, headers=admin_headers)
    as_own = client.get(url, headers=auth_headers("leader1@company.vn"))
    as_other = client.get(url, headers=auth_headers("leader2@company.vn"))
    as_employee = client.get(url, headers=auth_headers("nv@company.vn"))

    assert as_admin.status_code == 200
    assert as_own.status_code == 200
    assert as_other.status_code == 403
    assert as_employee.status_code == 403

    row = as_own.json()[0]
    assert row["phone"].startswith("09")
    assert row["pickup_point_name"] == "Toà nhà Keangnam"
    assert row["flight_code"] == "VN1234"
    assert row["team_name"] == "Công nghệ"
    # Trưởng xe cần số điện thoại để điểm danh, không cần giấy tờ tuỳ thân.
    assert "001095012345" not in as_own.text


# --- Phân xe tự động ---


def test_allocate_dry_run_does_not_write(
    client: TestClient, setup, admin_headers, rider, db: Session
):
    add_bus(db, setup, leg=setup["city"], pickup=setup["point_a"], flight=setup["out1"])
    for _ in range(5):
        rider(team=setup["team1"], needs={setup["city"]: setup["point_a"]}, flight=setup["out1"])

    response = client.post(
        f"{BUSES}/allocate", headers=admin_headers, json={"trip_leg_id": setup["city"].id}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["dry_run"] is True
    assert body["committed"] is False
    assert body["trip_leg_code"] == "CITY_TO_AIRPORT"
    assert body["summary"]["assigned"] == 5
    assert db.query(BusAssignment).count() == 0
    assert db.query(AuditLog).filter(AuditLog.action == "bus.allocated").count() == 0


def test_allocate_commit_writes_and_audits(
    client: TestClient, setup, admin_headers, rider, db: Session
):
    add_bus(db, setup, leg=setup["city"], pickup=setup["point_a"], flight=setup["out1"])
    for _ in range(5):
        rider(team=setup["team1"], needs={setup["city"]: setup["point_a"]}, flight=setup["out1"])

    response = client.post(
        f"{BUSES}/allocate",
        headers=admin_headers,
        json={"trip_leg_id": setup["city"].id, "dry_run": False},
    )

    assert response.status_code == 200
    assert response.json()["committed"] is True
    rows = db.query(BusAssignment).all()
    assert len(rows) == 5
    assert {row.assignment_mode for row in rows} == {AssignmentMode.AUTO}
    assert db.query(AuditLog).filter(AuditLog.action == "bus.allocated").count() == 1


def test_allocate_commit_blocked_while_registration_open(
    client: TestClient, setup, admin_headers, rider, db: Session
):
    setup["event"].status = EventStatus.REGISTRATION_OPEN
    db.commit()
    add_bus(db, setup, leg=setup["city"], pickup=setup["point_a"])
    rider(needs={setup["city"]: setup["point_a"]})

    response = client.post(
        f"{BUSES}/allocate",
        headers=admin_headers,
        json={"trip_leg_id": setup["city"].id, "dry_run": False},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "REGISTRATION_STILL_OPEN"
    assert db.query(BusAssignment).count() == 0


def test_airport_leg_needs_flight_assignment_first(
    client: TestClient, setup, admin_headers, rider, db: Session
):
    add_bus(db, setup, leg=setup["airport"], flight=setup["out1"])
    for _ in range(2):
        rider(team=setup["team1"], needs={setup["airport"]: None}, flight=setup["out1"])
    for _ in range(2):
        rider(team=setup["team1"], needs={setup["airport"]: None})  # chưa có chuyến bay

    body = client.post(
        f"{BUSES}/allocate", headers=admin_headers, json={"trip_leg_id": setup["airport"].id}
    ).json()

    assert body["airport_linked"] is True
    assert body["summary"]["assigned"] == 2
    missing = [flag for flag in body["flags"] if flag["type"] == "MISSING_FLIGHT_ASSIGNMENT"]
    assert len(missing) == 2


def test_commit_keeps_manual_and_removes_stale(
    client: TestClient, setup, admin_headers, rider, db: Session
):
    bus1 = add_bus(db, setup, leg=setup["city"], code="XE-01", pickup=setup["point_a"])
    bus2 = add_bus(db, setup, leg=setup["city"], code="XE-02", pickup=setup["point_a"])

    kept = rider(team=setup["team1"], needs={setup["city"]: setup["point_a"]})
    seat(db, kept, bus2, mode=AssignmentMode.MANUAL)

    # Từng được xếp nhưng giờ không còn nhu cầu xe ở chặng này.
    gone = rider(team=setup["team1"], needs={})
    seat(db, gone, bus1)

    for _ in range(3):
        rider(team=setup["team1"], needs={setup["city"]: setup["point_a"]})

    body = client.post(
        f"{BUSES}/allocate",
        headers=admin_headers,
        json={"trip_leg_id": setup["city"].id, "dry_run": False},
    ).json()

    assert body["removed_stale"] == 1
    manual = db.query(BusAssignment).filter_by(registration_id=kept.id).one()
    assert manual.bus_id == bus2.id
    assert manual.assignment_mode == AssignmentMode.MANUAL
    assert db.query(BusAssignment).filter_by(registration_id=gone.id).count() == 0
    assert db.query(BusAssignment).count() == 4


# --- Điều chỉnh thủ công ---


def test_move_marks_manual_warns_pickup_and_audits(
    client: TestClient, setup, admin_headers, rider, db: Session
):
    bus_a = add_bus(db, setup, leg=setup["city"], code="XE-01", pickup=setup["point_a"])
    bus_b = add_bus(db, setup, leg=setup["city"], code="XE-02", pickup=setup["point_b"])
    row = seat(db, rider(needs={setup["city"]: setup["point_a"]}), bus_a)

    response = client.patch(
        f"{ASSIGNMENTS}/{row.id}",
        headers=admin_headers,
        json={"bus_id": bus_b.id, "reason": "Nhà gần Hoàn Kiếm hơn"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["assignment"]["bus_code"] == "XE-02"
    assert body["assignment"]["assignment_mode"] == "manual"
    assert body["assignment"]["pickup_mismatch"] is True
    assert "PICKUP_MISMATCH" in {warning["type"] for warning in body["warnings"]}

    audit = db.query(AuditLog).filter(AuditLog.action == "bus_assignment.moved").one()
    assert audit.reason == "Nhà gần Hoàn Kiếm hơn"


def test_move_blocked_when_bus_is_full(
    client: TestClient, setup, admin_headers, rider, db: Session
):
    bus_a = add_bus(db, setup, leg=setup["city"], code="XE-01")
    bus_b = add_bus(db, setup, leg=setup["city"], code="XE-02", capacity=1)
    seat(db, rider(needs={setup["city"]: None}), bus_b)
    row = seat(db, rider(needs={setup["city"]: None}), bus_a)

    response = client.patch(
        f"{ASSIGNMENTS}/{row.id}",
        headers=admin_headers,
        json={"bus_id": bus_b.id, "reason": "Thử vượt sức chứa"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "BUS_CAPACITY_EXCEEDED"
    db.refresh(row)
    assert row.bus_id == bus_a.id


def test_move_rejects_bus_of_another_leg(
    client: TestClient, setup, admin_headers, rider, db: Session
):
    city_bus = add_bus(db, setup, leg=setup["city"])
    airport_bus = add_bus(db, setup, leg=setup["airport"], code="XE-05")
    row = seat(db, rider(needs={setup["city"]: None}), city_bus)

    response = client.patch(
        f"{ASSIGNMENTS}/{row.id}",
        headers=admin_headers,
        json={"bus_id": airport_bus.id, "reason": "Sai chặng"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "TRIP_LEG_MISMATCH"


def test_move_requires_reason(client: TestClient, setup, admin_headers, rider, db: Session):
    bus_a = add_bus(db, setup, leg=setup["city"], code="XE-01")
    bus_b = add_bus(db, setup, leg=setup["city"], code="XE-02")
    row = seat(db, rider(needs={setup["city"]: None}), bus_a)

    response = client.patch(f"{ASSIGNMENTS}/{row.id}", headers=admin_headers, json={"bus_id": bus_b.id})
    assert response.status_code == 422


def test_list_assignments_filters(client: TestClient, setup, admin_headers, rider, db: Session):
    city_bus = add_bus(db, setup, leg=setup["city"], pickup=setup["point_a"], flight=setup["out1"])
    airport_bus = add_bus(db, setup, leg=setup["airport"], code="XE-05", flight=setup["out1"])

    person = rider(
        team=setup["team1"],
        needs={setup["city"]: setup["point_a"], setup["airport"]: None},
        flight=setup["out1"],
    )
    seat(db, person, city_bus)
    seat(db, person, airport_bus)
    seat(db, rider(team=setup["team2"], needs={setup["city"]: setup["point_a"]}), city_bus)

    everything = client.get(ASSIGNMENTS, headers=admin_headers).json()
    by_leg = client.get(f"{ASSIGNMENTS}?trip_leg_id={setup['airport'].id}", headers=admin_headers).json()
    by_team = client.get(f"{ASSIGNMENTS}?team_id={setup['team2'].id}", headers=admin_headers).json()

    assert everything["total"] == 3
    assert by_leg["total"] == 1
    assert by_leg["items"][0]["bus_code"] == "XE-05"
    assert by_leg["items"][0]["flight_code"] == "VN1234"
    assert by_team["total"] == 1

    city_row = next(item for item in everything["items"] if item["bus_code"] == "XE-01" and item["team_name"] == "Công nghệ")
    assert city_row["pickup_point_name"] == "Toà nhà Keangnam"
    assert city_row["pickup_mismatch"] is False
    assert city_row["flight_mismatch"] is False


# --- Xếp tay người chưa có xe / bỏ xếp ---


def test_assign_rider_creates_manual_warns_and_audits(
    client: TestClient, setup, admin_headers, rider, db: Session
):
    person = rider(team=setup["team1"], needs={setup["city"]: setup["point_b"]})
    bus = add_bus(db, setup, leg=setup["city"], pickup=setup["point_a"])

    response = client.post(
        ASSIGNMENTS,
        headers=admin_headers,
        json={"registration_id": person.id, "bus_id": bus.id, "reason": "Xếp bổ sung"},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["assignment"]["assignment_mode"] == "manual"
    assert body["assignment"]["employee_code"].startswith("NV")
    assert body["assignment"]["phone"].startswith("09")
    # Xe đón Keangnam nhưng người này chọn Hoàn Kiếm: vẫn xếp được, nhưng phải cảnh báo.
    assert [warning["type"] for warning in body["warnings"]] == ["PICKUP_MISMATCH"]
    log = db.query(AuditLog).filter_by(action="bus_assignment.created").one()
    assert log.reason == "Xếp bổ sung"


def test_assign_rider_guards(client: TestClient, setup, admin_headers, rider, db: Session):
    needs_city = rider(needs={setup["city"]: setup["point_a"]})
    other_leg_only = rider(needs={setup["airport"]: None})
    latecomer = rider(needs={setup["city"]: setup["point_a"]})
    bus = add_bus(db, setup, leg=setup["city"], capacity=1)

    def assign(registration_id):
        return client.post(
            ASSIGNMENTS,
            headers=admin_headers,
            json={"registration_id": registration_id, "bus_id": bus.id, "reason": "Xếp tay"},
        )

    assert assign(other_leg_only.id).json()["error"]["code"] == "BUS_NOT_REQUESTED"
    assert assign(needs_city.id).status_code == 201
    assert assign(needs_city.id).json()["error"]["code"] == "ALREADY_ASSIGNED_ON_LEG"
    assert assign(latecomer.id).json()["error"]["code"] == "BUS_CAPACITY_EXCEEDED"
    assert assign(99999).status_code == 404
    assert (
        client.post(
            ASSIGNMENTS,
            headers=admin_headers,
            json={"registration_id": latecomer.id, "bus_id": bus.id, "reason": ""},
        ).status_code
        == 422
    )


def test_remove_assignment_requires_reason_and_audits(
    client: TestClient, setup, admin_headers, rider, db: Session
):
    person = rider(needs={setup["city"]: None})
    bus = add_bus(db, setup, leg=setup["city"])
    row = seat(db, person, bus)
    url = f"{ASSIGNMENTS}/{row.id}"

    assert client.delete(url, headers=admin_headers).status_code == 422

    response = client.delete(url, headers=admin_headers, params={"reason": "Tự đi xe riêng"})

    assert response.status_code == 204
    db.expire_all()
    assert db.query(BusAssignment).count() == 0
    log = db.query(AuditLog).filter_by(action="bus_assignment.removed").one()
    assert log.reason == "Tự đi xe riêng"
    assert client.delete(url, headers=admin_headers, params={"reason": "Lần hai"}).status_code == 404


def test_employee_cannot_assign_or_remove(
    client: TestClient, setup, rider, db: Session, make_user, auth_headers
):
    make_user(email="nhanvien@company.vn")
    headers = auth_headers("nhanvien@company.vn")
    person = rider(needs={setup["city"]: None})
    bus = add_bus(db, setup, leg=setup["city"])
    row = seat(db, person, bus)

    assert (
        client.post(
            ASSIGNMENTS,
            headers=headers,
            json={"registration_id": person.id, "bus_id": bus.id, "reason": "Tự xếp"},
        ).status_code
        == 403
    )
    assert client.delete(f"{ASSIGNMENTS}/{row.id}", headers=headers, params={"reason": "xoá"}).status_code == 403
