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


def add_bus(db: Session, setup, *, leg, code="XE-01", at="04:30", departs=None, flight=None) -> Bus:
    """`at` = giờ tập trung (xe có mặt), `departs` = giờ xe rời bến; mặc định trùng nhau."""
    bus = Bus(
        event_id=setup["event"].id,
        trip_leg_id=leg.id,
        bus_code=code,
        capacity=45,
        gather_time=vn_time(DAY, at),
        departure_time=vn_time(DAY, departs or at),
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
    # Chiều đón: tới sớm bao nhiêu cũng được, chỉ chặn khi tới muộn hơn mức cho phép.
    assert conflict_reason(side=AFTER_FLIGHT, bus_at=vn_time(DAY, "07:00"), flight=flight) is None
    assert conflict_reason(side=AFTER_FLIGHT, bus_at=vn_time(DAY, "08:10"), flight=flight) is None
    assert "xe tới muộn 20 phút" in conflict_reason(
        side=AFTER_FLIGHT, bus_at=vn_time(DAY, "08:30"), flight=flight
    )

    # Xe ra sân bay: chạy sát giờ bay vẫn là lệch, dù đúng thứ tự.
    gaps = {BEFORE_FLIGHT: 30, AFTER_FLIGHT: 5}
    late = conflict_reason(side=BEFORE_FLIGHT, bus_at=vn_time(DAY, "05:45"), flight=flight, buffers=gaps)
    assert "chỉ cách nhau 15 phút, cần tối thiểu 30 phút" in late
    assert conflict_reason(side=BEFORE_FLIGHT, bus_at=vn_time(DAY, "05:30"), flight=flight, buffers=gaps) is None
    assert conflict_reason(side=AFTER_FLIGHT, bus_at=vn_time(DAY, "08:15"), flight=flight, buffers=gaps) is None
    too_late = conflict_reason(side=AFTER_FLIGHT, bus_at=vn_time(DAY, "08:40"), flight=flight, buffers=gaps)
    assert "xe tới muộn 30 phút, chỉ cho phép muộn 5 phút" in too_late
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


def test_earlier_arrival_makes_the_pickup_bus_late(
    client: TestClient, setup, admin_headers, db: Session
):
    """Dời chuyến về sớm hơn thì xe đón đang đúng giờ bỗng thành tới muộn."""
    add_bus(
        db, setup, leg=setup["from_airport"], code="XE-05", at="08:10", departs="08:45",
        flight=setup["flight"],
    )

    response = client.patch(
        f"{FLIGHTS}/{setup['flight'].id}",
        headers=admin_headers,
        json={"departure_time": vn_time(DAY, "04:00"), "arrival_time": vn_time(DAY, "06:10")},
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


# --- Chặn công bố khi xe còn lệch giờ bay ---


def publish(client: TestClient, setup, headers):
    return client.post(
        f"/api/v1/events/{setup['event'].id}/status",
        headers=headers,
        json={"status": "information_published"},
    )


def test_publish_is_blocked_while_a_rider_bus_misses_the_flight(
    client: TestClient, setup, admin_headers, db: Session
):
    """Lệch giờ tích tụ được (chuyển chuyến chỉ cảnh báo) nên phải rà lại trước khi công bố:
    công bố rồi thì CBNV thấy xe chạy sau giờ cất cánh và không biết tin cái nào."""
    late = add_bus(db, setup, leg=setup["to_airport"], at="06:30")
    add_rider(db, setup, flight=setup["flight"], bus=late)
    setup["event"].status = EventStatus.ALLOCATION_PROCESSING
    db.commit()

    response = publish(client, setup, admin_headers)

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "TRANSPORT_TIME_MISMATCH"
    assert error["details"]["count"] == 1
    assert "Nguyễn Văn 01" in error["message"]
    db.refresh(setup["event"])
    assert setup["event"].status == EventStatus.ALLOCATION_PROCESSING


def test_publish_goes_through_once_the_bus_time_is_fixed(
    client: TestClient, setup, admin_headers, db: Session
):
    late = add_bus(db, setup, leg=setup["to_airport"], at="06:30")
    add_rider(db, setup, flight=setup["flight"], bus=late)
    setup["event"].status = EventStatus.ALLOCATION_PROCESSING
    db.commit()
    assert publish(client, setup, admin_headers).status_code == 409

    late.gather_time = late.departure_time = vn_time(DAY, "04:30")
    db.commit()

    assert publish(client, setup, admin_headers).status_code == 200


def test_bus_without_riders_does_not_block_publishing(
    client: TestClient, setup, admin_headers, db: Session
):
    """Xe rỗng lệch giờ là việc của BTC, không ai nhìn thấy nó trên My Journey."""
    add_bus(db, setup, leg=setup["to_airport"], at="06:30")
    add_rider(db, setup, flight=setup["flight"])
    setup["event"].status = EventStatus.ALLOCATION_PROCESSING
    db.commit()

    assert publish(client, setup, admin_headers).status_code == 200


# --- Khoảng đệm tối thiểu giữa giờ xe và giờ bay ---


def set_buffer(db: Session, setup, *, side_key: str, minutes: int) -> None:
    from app.models import EventSetting

    db.add(EventSetting(event_id=setup["event"].id, key=side_key, value=str(minutes)))
    db.commit()


def test_bus_leaving_one_minute_before_takeoff_is_rejected(
    client: TestClient, setup, admin_headers, db: Session
):
    """Xe chạy 07:00 mà 07:01 cất cánh thì "đúng thứ tự" nhưng không ai kịp làm thủ tục."""
    response = client.post(
        BUSES,
        headers=admin_headers,
        json={
            "trip_leg_id": setup["to_airport"].id,
            "bus_code": "XE-SAT",
            "capacity": 45,
            "departure_time": vn_time(DAY, "05:59"),
            "linked_flight_id": setup["flight"].id,
        },
    )

    assert response.status_code == 409, response.text
    error = response.json()["error"]
    assert error["code"] == "BUS_FLIGHT_TIME_CONFLICT"
    assert "chỉ cách nhau 1 phút, cần tối thiểu 30 phút" in error["message"]


def test_exactly_the_required_gap_is_accepted(client: TestClient, setup, admin_headers):
    """Đúng bằng mức tối thiểu là đạt — không bắt phải hơn."""
    response = client.post(
        BUSES,
        headers=admin_headers,
        json={
            "trip_leg_id": setup["to_airport"].id,
            "bus_code": "XE-VUA",
            "capacity": 45,
            "departure_time": vn_time(DAY, "05:30"),
            "linked_flight_id": setup["flight"].id,
        },
    )

    assert response.status_code == 201, response.text


def test_pickup_bus_may_arrive_as_early_as_it_likes(client: TestClient, setup, admin_headers):
    """Hạ cánh 08:10, xe đón có mặt từ 07:00: xe chờ khách là chuyện thường, không phải lỗi."""
    response = client.post(
        BUSES,
        headers=admin_headers,
        json={
            "trip_leg_id": setup["from_airport"].id,
            "bus_code": "XE-SOM",
            "capacity": 45,
            "gather_time": vn_time(DAY, "07:00"),
            "departure_time": vn_time(DAY, "08:40"),
            "linked_flight_id": setup["flight"].id,
        },
    )

    assert response.status_code == 201, response.text


def test_pickup_bus_arriving_late_is_rejected(client: TestClient, setup, admin_headers):
    """Hạ cánh 08:10 mà 08:40 xe mới tới: khách đứng chờ nửa tiếng ở sân bay."""
    response = client.post(
        BUSES,
        headers=admin_headers,
        json={
            "trip_leg_id": setup["from_airport"].id,
            "bus_code": "XE-MUON",
            "capacity": 45,
            "gather_time": vn_time(DAY, "08:40"),
            "departure_time": vn_time(DAY, "08:50"),
            "linked_flight_id": setup["flight"].id,
        },
    )

    assert response.status_code == 409
    assert "xe tới muộn 30 phút, chỉ cho phép muộn 5 phút" in response.json()["error"]["message"]


def test_pickup_bus_within_tolerance_is_accepted(client: TestClient, setup, admin_headers):
    """Muộn 5 phút vẫn nhận: máy bay lăn bánh vào bãi cũng mất chừng đó."""
    response = client.post(
        BUSES,
        headers=admin_headers,
        json={
            "trip_leg_id": setup["from_airport"].id,
            "bus_code": "XE-VUA-KIP",
            "capacity": 45,
            "gather_time": vn_time(DAY, "08:15"),
            "departure_time": vn_time(DAY, "08:45"),
            "linked_flight_id": setup["flight"].id,
        },
    )

    assert response.status_code == 201, response.text


def test_buffer_is_configurable_per_event(client: TestClient, setup, admin_headers, db: Session):
    """Quãng đường mỗi kỳ mỗi khác: BTC đổi số phút trong cấu hình kỳ, không sửa code."""
    set_buffer(db, setup, side_key="transport.to_airport_buffer_minutes", minutes=90)

    response = client.post(
        BUSES,
        headers=admin_headers,
        json={
            "trip_leg_id": setup["to_airport"].id,
            "bus_code": "XE-XA",
            "capacity": 45,
            "departure_time": vn_time(DAY, "05:00"),  # cách 60 phút: đủ với 30, thiếu với 90
            "linked_flight_id": setup["flight"].id,
        },
    )

    assert response.status_code == 409
    assert "cần tối thiểu 90 phút" in response.json()["error"]["message"]


def test_buffer_zero_keeps_the_plain_order_check(client: TestClient, setup, admin_headers, db):
    set_buffer(db, setup, side_key="transport.to_airport_buffer_minutes", minutes=0)

    ok = client.post(
        BUSES,
        headers=admin_headers,
        json={
            "trip_leg_id": setup["to_airport"].id, "bus_code": "XE-0", "capacity": 45,
            "departure_time": vn_time(DAY, "05:59"), "linked_flight_id": setup["flight"].id,
        },
    )
    assert ok.status_code == 201, ok.text

    # Vẫn chặn xe chạy sau giờ cất cánh.
    late = client.post(
        BUSES,
        headers=admin_headers,
        json={
            "trip_leg_id": setup["to_airport"].id, "bus_code": "XE-TRE", "capacity": 45,
            "departure_time": vn_time(DAY, "06:30"), "linked_flight_id": setup["flight"].id,
        },
    )
    assert late.status_code == 409


def test_publish_is_blocked_by_a_too_tight_transfer(
    client: TestClient, setup, admin_headers, db: Session
):
    """Xe kịp theo thứ tự nhưng sát giờ vẫn phải chặn công bố: CBNV không ra kịp máy bay."""
    tight = add_bus(db, setup, leg=setup["to_airport"], code="XE-SAT", at="05:50")
    add_rider(db, setup, flight=setup["flight"], bus=tight)
    setup["event"].status = EventStatus.ALLOCATION_PROCESSING
    db.commit()

    response = publish(client, setup, admin_headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "TRANSPORT_TIME_MISMATCH"


# --- Cửa sổ chờ của xe đón: rời sân bay không quá sớm, cũng không chờ mãi ---


def create_pickup(client, admin_headers, setup, *, code, gather, departs):
    return client.post(
        BUSES,
        headers=admin_headers,
        json={
            "trip_leg_id": setup["from_airport"].id,
            "bus_code": code,
            "capacity": 45,
            "gather_time": vn_time(DAY, gather),
            "departure_time": vn_time(DAY, departs),
            "linked_flight_id": setup["flight"].id,
        },
    )


def test_pickup_bus_may_not_leave_before_people_get_their_luggage(
    client: TestClient, setup, admin_headers
):
    """Hạ cánh 08:10, xe rời lúc 08:30: khách còn đang lấy hành lý thì xe đã đi."""
    response = create_pickup(client, admin_headers, setup, code="XE-VOI", gather="08:00", departs="08:30")

    assert response.status_code == 409
    assert "cần chờ ít nhất 30 phút" in response.json()["error"]["message"]


def test_pickup_bus_leaving_exactly_at_the_minimum_wait_is_accepted(
    client: TestClient, setup, admin_headers
):
    response = create_pickup(client, admin_headers, setup, code="XE-DU", gather="08:00", departs="08:40")
    assert response.status_code == 201, response.text


def test_pickup_bus_may_wait_up_to_the_limit(client: TestClient, setup, admin_headers):
    ok = create_pickup(client, admin_headers, setup, code="XE-CHO", gather="08:00", departs="08:55")
    assert ok.status_code == 201, ok.text

    too_long = create_pickup(client, admin_headers, setup, code="XE-LI", gather="08:00", departs="09:00")
    assert too_long.status_code == 409
    assert "không chờ quá 45 phút" in too_long.json()["error"]["message"]


def test_wait_window_is_configurable(client: TestClient, setup, admin_headers, db: Session):
    """Bay quốc tế còn nhập cảnh: BTC nới mốc chờ tối thiểu thay vì sửa code."""
    set_buffer(db, setup, side_key="transport.from_airport_min_wait_minutes", minutes=60)

    response = create_pickup(client, admin_headers, setup, code="XE-QT", gather="08:00", departs="08:40")

    assert response.status_code == 409
    assert "cần chờ ít nhất 60 phút" in response.json()["error"]["message"]


def test_wait_limit_can_be_switched_off(client: TestClient, setup, admin_headers, db: Session):
    set_buffer(db, setup, side_key="transport.from_airport_max_wait_minutes", minutes=0)

    response = create_pickup(client, admin_headers, setup, code="XE-KIENNHAN", gather="08:00", departs="10:00")

    assert response.status_code == 201, response.text


def test_one_bus_cannot_serve_two_flights_landing_far_apart(
    client: TestClient, setup, admin_headers, db: Session
):
    """Hai chuyến hạ cánh cách nhau 40 phút: không giờ nào vừa chờ đủ chuyến sau vừa không
    bắt chuyến trước đợi quá lâu — phải tách xe, và thông báo nói đúng điều đó."""
    late_flight = Flight(
        event_id=setup["event"].id, flight_code="VN9999", direction=FlightDirection.OUTBOUND,
        departure_airport="HAN", arrival_airport="PQC",
        departure_time=vn_time(DAY, "06:40"), arrival_time=vn_time(DAY, "08:50"), capacity=60,
    )
    db.add(late_flight)
    db.commit()
    bus = add_bus(
        db, setup, leg=setup["from_airport"], code="XE-CHUNG", at="08:00", departs="08:45",
        flight=setup["flight"],
    )
    rider = add_rider(db, setup, flight=late_flight, bus=None, index=9)
    db.add(
        RegistrationBusNeed(
            registration_id=rider.id, trip_leg_id=setup["from_airport"].id, needs_bus=True
        )
    )
    db.commit()

    response = client.post(
        ASSIGNMENTS,
        headers=admin_headers,
        json={"registration_id": rider.id, "bus_id": bus.id, "reason": "Gom xe cho tiết kiệm"},
    )

    assert response.status_code == 409
    assert "cần chờ ít nhất 30 phút" in response.json()["error"]["message"]


def test_pickup_bus_without_departure_time_is_only_checked_for_presence(
    client: TestClient, setup, admin_headers
):
    """Thiếu giờ rời bến thì không suy đoán — chỉ kiểm xe có mặt kịp hay không."""
    response = client.post(
        BUSES,
        headers=admin_headers,
        json={
            "trip_leg_id": setup["from_airport"].id,
            "bus_code": "XE-THIEUGIO",
            "capacity": 45,
            "gather_time": vn_time(DAY, "08:00"),
            "linked_flight_id": setup["flight"].id,
        },
    )

    assert response.status_code == 201, response.text


def test_pickup_bus_with_only_a_departure_time_is_judged_by_the_wait_window(
    client: TestClient, setup, admin_headers
):
    """Thiếu giờ tập trung thì không đoán là "xe tới muộn": giờ rời bến của xe đón vốn dĩ phải
    muộn hơn giờ hạ cánh. Hai luật chồng nhau sẽ thành không giá trị nào hợp lệ."""
    ok = client.post(
        BUSES,
        headers=admin_headers,
        json={
            "trip_leg_id": setup["from_airport"].id, "bus_code": "XE-CHI-ROI", "capacity": 45,
            "departure_time": vn_time(DAY, "08:45"),  # chờ 35 phút sau khi hạ cánh 08:10
            "linked_flight_id": setup["flight"].id,
        },
    )
    assert ok.status_code == 201, ok.text

    early = client.post(
        BUSES,
        headers=admin_headers,
        json={
            "trip_leg_id": setup["from_airport"].id, "bus_code": "XE-VOI-2", "capacity": 45,
            "departure_time": vn_time(DAY, "08:20"),
            "linked_flight_id": setup["flight"].id,
        },
    )
    assert early.status_code == 409
    assert "cần chờ ít nhất 30 phút" in early.json()["error"]["message"]


# --- Danh sách xe tự tố cáo xe nào lệch ---


def test_bus_list_flags_each_off_schedule_bus(client: TestClient, setup, admin_headers, db: Session):
    """BTC mở màn hình Xe đưa đón phải thấy ngay xe nào hỏng giờ, không phải mở từng xe ra dò."""
    good = add_bus(db, setup, leg=setup["to_airport"], code="XE-OK", at="04:30", flight=setup["flight"])
    bad = add_bus(db, setup, leg=setup["to_airport"], code="XE-SAT", at="05:50", flight=setup["flight"])

    rows = client.get(BUSES, headers=admin_headers).json()

    by_code = {row["bus_code"]: row for row in rows}
    assert by_code["XE-OK"]["timing_issues"] == []
    assert len(by_code["XE-SAT"]["timing_issues"]) == 1
    assert "cần tối thiểu 30 phút" in by_code["XE-SAT"]["timing_issues"][0]
    assert {good.id, bad.id} <= {row["id"] for row in rows}


def test_bus_list_flags_conflicts_coming_from_its_passengers(
    client: TestClient, setup, admin_headers, db: Session
):
    """Xe không gắn chuyến nào vẫn bị tố, nếu người ngồi trên xe bay chuyến lệch giờ."""
    bus = add_bus(db, setup, leg=setup["to_airport"], code="XE-KHONG-GAN", at="05:55")
    add_rider(db, setup, flight=setup["flight"], bus=bus)

    rows = client.get(BUSES, headers=admin_headers, params={"trip_leg_id": setup["to_airport"].id}).json()

    issues = next(row["timing_issues"] for row in rows if row["bus_code"] == "XE-KHONG-GAN")
    assert issues and "VN1234" in issues[0]
