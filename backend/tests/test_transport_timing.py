"""Giờ xe phải khớp giờ chuyến bay (lỗi test tay: sửa giờ bay sớm hơn giờ xe vẫn lưu được).

Kịch bản gốc: chuyến bay 06:00, xe ra sân bay 04:30 chở người bay chuyến đó. BTC dời chuyến
bay về 04:00 → trước đây lưu được và My Journey hiện xe 04:30 cho chuyến 04:00.
"""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.timeutils import VN_TZ, to_iso
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
    TripLeg,
    User,
)
from app.models.enums import AssignmentMode, EventStatus, FlightDirection, Gender, RegistrationStatus, UserRole
from app.services.allocator.bus_types import BusRider, BusSlot
from app.services.allocator.buses import allocate_buses
from app.services.transport_timing_service import (
    AFTER_FLIGHT,
    BEFORE_FLIGHT,
    FlightTimes,
    airport_side,
    conflict_reason,
)

FLIGHTS = "/api/v1/flights"
BUSES = "/api/v1/buses"
ASSIGNMENTS = "/api/v1/bus-assignments"
DAY = "2026-10-15"


def vn_time(day: str, hhmm: str) -> str:
    """Giờ Việt Nam -> ISO UTC, như `scripts/seed.py`."""
    return to_iso(datetime.strptime(f"{day} {hhmm}", "%Y-%m-%d %H:%M").replace(tzinfo=VN_TZ))


@pytest.fixture
def setup(db: Session) -> dict:
    event = Event(
        code="TB2026",
        name="Team Building 2026",
        start_date=DAY,
        end_date="2026-10-17",
        status=EventStatus.REGISTRATION_CLOSED,
        terms_version="v1",
        is_active=True,
    )
    db.add(event)
    db.flush()

    flight = Flight(
        event_id=event.id,
        flight_code="VN1234",
        direction=FlightDirection.OUTBOUND,
        departure_airport="HAN",
        arrival_airport="PQC",
        departure_time=vn_time(DAY, "06:00"),
        arrival_time=vn_time(DAY, "08:10"),
        capacity=60,
    )
    to_airport = TripLeg(
        event_id=event.id, code="CITY_TO_AIRPORT", name="HN → Sân bay",
        direction=FlightDirection.OUTBOUND, is_airport_linked=True, display_order=1,
    )
    from_airport = TripLeg(
        event_id=event.id, code="AIRPORT_TO_HOTEL", name="Sân bay → Khách sạn",
        direction=FlightDirection.OUTBOUND, is_airport_linked=True, display_order=2,
    )
    db.add_all([flight, to_airport, from_airport])
    db.flush()
    point = PickupPoint(event_id=event.id, trip_leg_id=to_airport.id, name="Điểm A")
    db.add(point)
    db.commit()
    return {"event": event, "flight": flight, "to_airport": to_airport, "from_airport": from_airport, "point": point}


@pytest.fixture
def admin_headers(make_user, auth_headers, setup):
    make_user(email="btc@company.vn", password="MatKhau123", role=UserRole.ADMIN)
    return auth_headers("btc@company.vn")


def add_bus(db: Session, setup, *, leg, code="XE-01", at="04:30", flight=None) -> Bus:
    bus = Bus(
        event_id=setup["event"].id,
        trip_leg_id=leg.id,
        bus_code=code,
        capacity=45,
        gather_time=vn_time(DAY, at),
        departure_time=vn_time(DAY, at),
        linked_flight_id=flight.id if flight else None,
    )
    db.add(bus)
    db.commit()
    db.refresh(bus)
    return bus


def add_rider(db: Session, setup, *, flight=None, bus=None, index=1) -> Registration:
    user = User(
        email=f"nv{index}@company.vn", full_name=f"Nguyễn Văn {index:02d}", employee_code=f"NV{index:03d}",
        password_hash="x", role=UserRole.EMPLOYEE, gender=Gender.MALE, phone="0912345678",
    )
    db.add(user)
    db.flush()
    registration = Registration(
        event_id=setup["event"].id, user_id=user.id, is_participating=True,
        status=RegistrationStatus.SUBMITTED, submitted_at="2026-09-12T03:00:00+00:00",
    )
    db.add(registration)
    db.flush()
    db.add(
        RegistrationBusNeed(
            registration_id=registration.id, trip_leg_id=setup["to_airport"].id,
            needs_bus=True, pickup_point_id=setup["point"].id,
        )
    )
    if flight is not None:
        db.add(
            FlightAssignment(
                registration_id=registration.id, flight_id=flight.id, direction=flight.direction,
                assignment_mode=AssignmentMode.AUTO, assigned_at="2026-09-12T04:00:00+00:00",
            )
        )
    if bus is not None:
        db.add(
            BusAssignment(
                registration_id=registration.id, bus_id=bus.id, trip_leg_id=bus.trip_leg_id,
                assignment_mode=AssignmentMode.AUTO, assigned_at="2026-09-12T04:00:00+00:00",
            )
        )
    db.commit()
    db.refresh(registration)
    return registration


# --- Hàm thuần ---


def test_conflict_reason_both_sides():
    flight = FlightTimes(1, "VN1234", vn_time(DAY, "06:00"), vn_time(DAY, "08:10"))

    assert conflict_reason(side=BEFORE_FLIGHT, bus_at=vn_time(DAY, "04:30"), flight=flight) is None
    assert "không kịp" in conflict_reason(side=BEFORE_FLIGHT, bus_at=vn_time(DAY, "06:00"), flight=flight)
    assert conflict_reason(side=AFTER_FLIGHT, bus_at=vn_time(DAY, "08:30"), flight=flight) is None
    assert "trước khi" in conflict_reason(side=AFTER_FLIGHT, bus_at=vn_time(DAY, "08:00"), flight=flight)
    # Không đủ dữ liệu thì không chặn.
    assert conflict_reason(side=None, bus_at=vn_time(DAY, "09:00"), flight=flight) is None
    assert conflict_reason(side=BEFORE_FLIGHT, bus_at=None, flight=flight) is None


def test_airport_side_by_code_then_by_order():
    legs = [
        TripLeg(id=1, code="DI_1", direction="outbound", is_airport_linked=True, display_order=1),
        TripLeg(id=2, code="DI_2", direction="outbound", is_airport_linked=True, display_order=2),
        TripLeg(id=3, code="CITY_TO_AIRPORT", direction="outbound", is_airport_linked=False, display_order=9),
        TripLeg(id=4, code="TOUR", direction="outbound", is_airport_linked=False, display_order=3),
    ]
    assert airport_side(legs[0], legs) == BEFORE_FLIGHT
    assert airport_side(legs[1], legs) == AFTER_FLIGHT
    # Quên bật cờ sân bay nhưng mã chặng nói rõ đi sân bay: vẫn kiểm.
    assert airport_side(legs[2], legs) == BEFORE_FLIGHT
    assert airport_side(legs[3], legs) is None


def test_allocator_skips_bus_that_misses_the_flight():
    rider = BusRider(registration_id=1, full_name="A", team_id=None, team_name="", flight_id=7)
    late = BusSlot(bus_id=1, bus_code="XE-TRE", capacity=10, incompatible_flight_ids=frozenset({7}))
    ok = BusSlot(bus_id=2, bus_code="XE-SOM", capacity=10)

    result = allocate_buses(riders=[rider], buses=[late, ok], trip_leg_id=1, airport_linked=True)

    assert [(seat.registration_id, seat.bus_id) for seat in result.assignments] == [(1, 2)]


# --- Sửa chuyến bay ---


def test_flight_moved_before_bus_is_blocked(client: TestClient, setup, admin_headers, db: Session):
    """Đúng kịch bản báo lỗi: bay 06:00, xe 04:30 → dời chuyến về 04:00 phải bị chặn."""
    bus = add_bus(db, setup, leg=setup["to_airport"], flight=setup["flight"])
    add_rider(db, setup, flight=setup["flight"], bus=bus)

    response = client.patch(
        f"{FLIGHTS}/{setup['flight'].id}",
        headers=admin_headers,
        json={"departure_time": vn_time(DAY, "04:00"), "arrival_time": vn_time(DAY, "06:10")},
    )

    assert response.status_code == 409, response.text
    error = response.json()["error"]
    assert error["code"] == "FLIGHT_BUS_TIME_CONFLICT"
    assert [item["bus_code"] for item in error["details"]["buses"]] == ["XE-01"]
    assert "XE-01" in error["message"]
    db.expire_all()
    assert db.get(Flight, setup["flight"].id).departure_time == vn_time(DAY, "06:00")
    assert db.query(AuditLog).filter_by(action="flight.updated").count() == 0


def test_bus_found_through_passengers_even_without_link(client: TestClient, setup, admin_headers, db: Session):
    bus = add_bus(db, setup, leg=setup["to_airport"])  # BTC quên gắn chuyến cho xe
    add_rider(db, setup, flight=setup["flight"], bus=bus)

    response = client.patch(
        f"{FLIGHTS}/{setup['flight'].id}",
        headers=admin_headers,
        json={"departure_time": vn_time(DAY, "04:00"), "arrival_time": vn_time(DAY, "06:10")},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "FLIGHT_BUS_TIME_CONFLICT"


def test_later_arrival_blocks_pickup_bus(client: TestClient, setup, admin_headers, db: Session):
    add_bus(db, setup, leg=setup["from_airport"], code="XE-05", at="08:30", flight=setup["flight"])

    response = client.patch(
        f"{FLIGHTS}/{setup['flight'].id}",
        headers=admin_headers,
        json={"departure_time": vn_time(DAY, "07:00"), "arrival_time": vn_time(DAY, "09:10")},
    )

    assert response.status_code == 409
    assert response.json()["error"]["details"]["buses"][0]["bus_code"] == "XE-05"


def test_fix_bus_first_then_flight_saves(client: TestClient, setup, admin_headers, db: Session):
    bus = add_bus(db, setup, leg=setup["to_airport"], flight=setup["flight"])
    add_rider(db, setup, flight=setup["flight"], bus=bus)

    moved_bus = client.patch(
        f"{BUSES}/{bus.id}",
        headers=admin_headers,
        json={"gather_time": vn_time(DAY, "02:15"), "departure_time": vn_time(DAY, "02:30")},
    )
    assert moved_bus.status_code == 200, moved_bus.text

    moved_flight = client.patch(
        f"{FLIGHTS}/{setup['flight'].id}",
        headers=admin_headers,
        json={"departure_time": vn_time(DAY, "04:00"), "arrival_time": vn_time(DAY, "06:10")},
    )
    assert moved_flight.status_code == 200, moved_flight.text


def test_other_fields_still_editable_with_mismatched_legacy_data(
    client: TestClient, setup, admin_headers, db: Session
):
    """Dữ liệu lệch có từ trước không được khoá cả chuyến: chỉ kiểm khi đổi giờ bay."""
    add_bus(db, setup, leg=setup["to_airport"], at="07:00", flight=setup["flight"])

    response = client.patch(
        f"{FLIGHTS}/{setup['flight'].id}", headers=admin_headers, json={"capacity": 70}
    )

    assert response.status_code == 200, response.text


# --- Thêm / sửa xe, xếp người ---


def test_bus_create_and_update_reject_late_departure(client: TestClient, setup, admin_headers, db: Session):
    payload = {
        "trip_leg_id": setup["to_airport"].id,
        "bus_code": "XE-09",
        "capacity": 45,
        "gather_time": vn_time(DAY, "06:15"),
        "departure_time": vn_time(DAY, "06:30"),
        "linked_flight_id": setup["flight"].id,
    }
    created = client.post(BUSES, headers=admin_headers, json=payload)
    assert created.status_code == 409
    assert created.json()["error"]["code"] == "BUS_FLIGHT_TIME_CONFLICT"

    bus = add_bus(db, setup, leg=setup["to_airport"])
    add_rider(db, setup, flight=setup["flight"], bus=bus)
    updated = client.patch(
        f"{BUSES}/{bus.id}",
        headers=admin_headers,
        json={"gather_time": vn_time(DAY, "06:00"), "departure_time": vn_time(DAY, "06:05")},
    )
    assert updated.status_code == 409
    assert updated.json()["error"]["code"] == "BUS_FLIGHT_TIME_CONFLICT"


def test_manual_assign_and_move_reject_bus_that_misses_the_flight(
    client: TestClient, setup, admin_headers, db: Session
):
    early = add_bus(db, setup, leg=setup["to_airport"], code="XE-01", at="04:30")
    late = add_bus(db, setup, leg=setup["to_airport"], code="XE-02", at="06:30")

    person = add_rider(db, setup, flight=setup["flight"], index=1)
    assigned = client.post(
        ASSIGNMENTS,
        headers=admin_headers,
        json={"registration_id": person.id, "bus_id": late.id, "reason": "Xếp tay"},
    )
    assert assigned.status_code == 409
    assert assigned.json()["error"]["code"] == "BUS_FLIGHT_TIME_CONFLICT"

    seated = add_rider(db, setup, flight=setup["flight"], bus=early, index=2)
    row = db.query(BusAssignment).filter_by(registration_id=seated.id).one()
    moved = client.patch(
        f"{ASSIGNMENTS}/{row.id}", headers=admin_headers, json={"bus_id": late.id, "reason": "Đổi xe"}
    )
    assert moved.status_code == 409
    assert moved.json()["error"]["code"] == "BUS_FLIGHT_TIME_CONFLICT"


def test_legacy_mismatch_does_not_block_unrelated_time_change(
    client: TestClient, setup, admin_headers, db: Session
):
    """Xe đã lệch từ trước (người bị chuyển chuyến chưa đổi xe) không khoá việc sửa giờ bay."""
    add_bus(db, setup, leg=setup["to_airport"], at="07:00", flight=setup["flight"])

    response = client.patch(
        f"{FLIGHTS}/{setup['flight'].id}",
        headers=admin_headers,
        json={"departure_time": vn_time(DAY, "06:15"), "arrival_time": vn_time(DAY, "08:25")},
    )

    assert response.status_code == 200, response.text


# --- Chuyển chuyến bay ---


def test_moving_flight_warns_when_current_bus_misses_new_flight(
    client: TestClient, setup, admin_headers, db: Session
):
    early = Flight(
        event_id=setup["event"].id, flight_code="VN1200", direction=FlightDirection.OUTBOUND,
        departure_airport="HAN", arrival_airport="PQC",
        departure_time=vn_time(DAY, "04:00"), arrival_time=vn_time(DAY, "06:10"), capacity=60,
    )
    db.add(early)
    db.commit()
    bus = add_bus(db, setup, leg=setup["to_airport"], flight=setup["flight"])
    person = add_rider(db, setup, flight=setup["flight"], bus=bus)
    row = db.query(FlightAssignment).filter_by(registration_id=person.id).one()

    response = client.patch(
        f"/api/v1/flight-assignments/{row.id}",
        headers=admin_headers,
        json={"flight_id": early.id, "reason": "Đổi chuyến sớm"},
    )

    assert response.status_code == 200, response.text
    warnings = [item for item in response.json()["warnings"] if item["type"] == "BUS_TIME_MISMATCH"]
    assert len(warnings) == 1
    assert "XE-01" in warnings[0]["message"]
