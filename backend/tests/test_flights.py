"""Kiểm thử Module 2 – quản lý chuyến bay và tình trạng slot."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    Event,
    Flight,
    FlightAssignment,
    Registration,
    Shift,
    Team,
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

BASE = "/api/v1/flights"


@pytest.fixture
def setup(db: Session) -> dict:
    """Kỳ đang mở với 2 ca và 1 chuyến chiều đi sẵn có."""
    event = Event(
        code="TB2026",
        name="Team Building 2026",
        start_date="2026-10-15",
        end_date="2026-10-17",
        status=EventStatus.REGISTRATION_OPEN,
        terms_version="v1",
        is_active=True,
    )
    db.add(event)
    db.flush()

    shift1 = Shift(event_id=event.id, code="CA1", name="Ca 1", display_order=1)
    shift2 = Shift(event_id=event.id, code="CA2", name="Ca 2", display_order=2)
    team = Team(code="IT", name="Công nghệ")
    db.add_all([shift1, shift2, team])
    db.flush()

    flight = Flight(
        event_id=event.id,
        flight_code="VN1234",
        airline="Vietnam Airlines",
        direction=FlightDirection.OUTBOUND,
        shift_id=shift1.id,
        departure_airport="HAN",
        arrival_airport="PQC",
        departure_time="2026-10-15T06:30:00+00:00",
        arrival_time="2026-10-15T08:40:00+00:00",
        capacity=60,
        reserved_slots=2,
    )
    db.add(flight)
    db.commit()

    return {"event": event, "shift1": shift1, "shift2": shift2, "team": team, "flight": flight}


@pytest.fixture
def admin_headers(make_user, auth_headers, setup):
    make_user(email="btc@company.vn", password="MatKhau123", role=UserRole.ADMIN)
    return auth_headers("btc@company.vn")


@pytest.fixture
def add_passenger(db: Session, setup):
    """Tạo một CBNV đã đăng ký và xếp vào chuyến bay."""
    counter = {"n": 0}

    def _add(flight: Flight, *, can_fly: bool = True, mode=AssignmentMode.AUTO) -> FlightAssignment:
        counter["n"] += 1
        index = counter["n"]
        user = User(
            email=f"nv{index}@company.vn",
            full_name=f"Nguyễn Văn {index}",
            employee_code=f"NV{index:03d}",
            password_hash="x",
            role=UserRole.EMPLOYEE,
            team_id=setup["team"].id,
            phone="0912345678",
            gender=Gender.MALE,
            date_of_birth="1995-01-01",
            id_card_number="001095012345" if can_fly else None,
        )
        db.add(user)
        db.flush()

        registration = Registration(
            event_id=setup["event"].id,
            user_id=user.id,
            is_participating=True,
            shift_id=setup["shift1"].id,
            status=RegistrationStatus.SUBMITTED,
            submitted_at="2026-09-12T03:00:00+00:00",
        )
        db.add(registration)
        db.flush()

        assignment = FlightAssignment(
            registration_id=registration.id,
            flight_id=flight.id,
            direction=flight.direction,
            assignment_mode=mode,
            assigned_at="2026-09-12T04:00:00+00:00",
        )
        db.add(assignment)
        db.commit()
        return assignment

    return _add


def payload(setup, **overrides) -> dict:
    data = {
        "flight_code": "VN1250",
        "airline": "Vietnam Airlines",
        "direction": "outbound",
        "shift_id": setup["shift2"].id,
        "departure_airport": "HAN",
        "arrival_airport": "PQC",
        "departure_time": "2026-10-15T19:15:00+00:00",
        "arrival_time": "2026-10-15T21:25:00+00:00",
        "capacity": 52,
        "reserved_slots": 2,
    }
    data.update(overrides)
    return data


# --- Quyền ---


def test_employee_cannot_touch_flights(client: TestClient, setup, make_user, auth_headers):
    make_user(email="nv@company.vn", password="MatKhau123")
    headers = auth_headers("nv@company.vn")

    assert client.get(BASE, headers=headers).status_code == 403
    assert client.post(BASE, headers=headers, json=payload(setup)).status_code == 403


# --- Tạo ---


def test_create_flight_returns_slot_numbers(
    client: TestClient, setup, admin_headers, db: Session
):
    response = client.post(BASE, headers=admin_headers, json=payload(setup))

    assert response.status_code == 201
    body = response.json()
    assert body["flight_code"] == "VN1250"
    assert body["shift_code"] == "CA2"
    # 52 ghế, giữ 2 -> dùng được 50, chưa xếp ai.
    assert body["usable_capacity"] == 50
    assert body["assigned_count"] == 0
    assert body["remaining_slots"] == 50
    assert body["load_ratio"] == 0.0

    assert db.query(Flight).count() == 2
    audit = db.query(AuditLog).filter(AuditLog.action == "flight.created").one()
    assert audit.entity_id == body["id"]


def test_create_rejects_duplicate_flight(client: TestClient, setup, admin_headers):
    same_as_existing = payload(
        setup,
        flight_code="VN1234",
        departure_time="2026-10-15T06:30:00+00:00",
        arrival_time="2026-10-15T08:40:00+00:00",
    )
    response = client.post(BASE, headers=admin_headers, json=same_as_existing)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "FLIGHT_CODE_DUPLICATED"


def test_create_rejects_same_code_at_another_time(
    client: TestClient, setup, admin_headers, db: Session
):
    """Lỗi test tay: VN1234 chiều đi đã có, thêm VN1234 chiều đi giờ khác vẫn lọt."""
    response = client.post(
        BASE,
        headers=admin_headers,
        json=payload(
            setup,
            flight_code="VN1234",
            departure_time="2026-10-15T10:00:00+00:00",
            arrival_time="2026-10-15T12:00:00+00:00",
            capacity=10,
            reserved_slots=0,
        ),
    )

    assert response.status_code == 409, response.text
    error = response.json()["error"]
    assert error["code"] == "FLIGHT_CODE_DUPLICATED"
    assert "VN1234" in error["message"] and "chiều đi" in error["message"]
    assert db.query(Flight).count() == 1


def test_same_code_allowed_on_other_direction_and_other_event(
    client: TestClient, setup, admin_headers, db: Session
):
    """Cùng mã nhưng khác chiều là chuyện thật (chuyến khứ hồi dùng chung số hiệu)."""
    response = client.post(
        BASE,
        headers=admin_headers,
        json=payload(
            setup,
            flight_code="VN1234",
            direction="return",
            departure_airport="PQC",
            arrival_airport="HAN",
            departure_time="2026-10-17T15:00:00+00:00",
            arrival_time="2026-10-17T17:10:00+00:00",
        ),
    )

    assert response.status_code == 201, response.text
    assert db.query(Flight).count() == 2


def test_update_rejects_code_taken_by_another_flight(
    client: TestClient, setup, admin_headers, db: Session
):
    created = client.post(BASE, headers=admin_headers, json=payload(setup))
    other_id = created.json()["id"]

    taken = client.patch(
        f"{BASE}/{other_id}", headers=admin_headers, json={"flight_code": "VN1234"}
    )
    assert taken.status_code == 409
    assert taken.json()["error"]["code"] == "FLIGHT_CODE_DUPLICATED"
    db.expire_all()
    assert db.get(Flight, other_id).flight_code == "VN1250"

    # Lưu lại chính mã của mình thì không phải là trùng.
    same = client.patch(
        f"{BASE}/{other_id}", headers=admin_headers, json={"flight_code": "VN1250", "capacity": 60}
    )
    assert same.status_code == 200, same.text


def test_create_rejects_arrival_before_departure(client: TestClient, setup, admin_headers):
    response = client.post(
        BASE,
        headers=admin_headers,
        json=payload(setup, arrival_time="2026-10-15T18:00:00+00:00"),
    )

    assert response.status_code == 422
    assert "sau giờ khởi hành" in response.text


def test_create_rejects_same_airports_and_bad_codes(client: TestClient, setup, admin_headers):
    same = client.post(BASE, headers=admin_headers, json=payload(setup, arrival_airport="HAN"))
    assert same.status_code == 422

    lowercase = client.post(
        BASE, headers=admin_headers, json=payload(setup, departure_airport="han")
    )
    assert lowercase.status_code == 422


def test_create_rejects_reserved_over_capacity(client: TestClient, setup, admin_headers):
    response = client.post(
        BASE, headers=admin_headers, json=payload(setup, capacity=10, reserved_slots=11)
    )
    assert response.status_code == 422


def test_create_rejects_shift_of_another_event(
    client: TestClient, setup, admin_headers, db: Session
):
    other = Event(
        code="TB2025",
        name="Kỳ cũ",
        start_date="2025-10-15",
        end_date="2025-10-17",
        status=EventStatus.COMPLETED,
        terms_version="v1",
    )
    db.add(other)
    db.flush()
    foreign_shift = Shift(event_id=other.id, code="CA9", name="Ca của kỳ khác")
    db.add(foreign_shift)
    db.commit()

    response = client.post(
        BASE, headers=admin_headers, json=payload(setup, shift_id=foreign_shift.id)
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SHIFT_NOT_FOUND"


def test_create_rejects_bad_time_format(client: TestClient, setup, admin_headers):
    response = client.post(
        BASE, headers=admin_headers, json=payload(setup, departure_time="15/10/2026 19:15")
    )
    assert response.status_code == 422
    assert "ISO-8601" in response.text


# --- Danh sách & lọc ---


def test_list_shows_assigned_count_and_filters(
    client: TestClient, setup, admin_headers, add_passenger, db: Session
):
    add_passenger(setup["flight"])
    add_passenger(setup["flight"])
    client.post(BASE, headers=admin_headers, json=payload(setup, direction="return",
                                                          departure_airport="PQC",
                                                          arrival_airport="HAN"))

    rows = client.get(BASE, headers=admin_headers).json()
    assert len(rows) == 2

    outbound = next(row for row in rows if row["flight_code"] == "VN1234")
    assert outbound["assigned_count"] == 2
    assert outbound["remaining_slots"] == 56  # 60 - 2 giữ lại - 2 đã xếp
    assert 0 < outbound["load_ratio"] < 1

    by_direction = client.get(f"{BASE}?direction=return", headers=admin_headers).json()
    assert [row["direction"] for row in by_direction] == ["return"]

    by_shift = client.get(
        f"{BASE}?shift_id={setup['shift1'].id}", headers=admin_headers
    ).json()
    assert [row["flight_code"] for row in by_shift] == ["VN1234"]

    by_search = client.get(f"{BASE}?q=vn1234", headers=admin_headers).json()
    assert [row["flight_code"] for row in by_search] == ["VN1234"]


def test_list_counts_stay_right_with_many_flights(
    client: TestClient, setup, admin_headers, add_passenger, db: Session
):
    """Subquery đếm gộp phải không nhân chéo khi có nhiều chuyến và nhiều hành khách."""
    second = client.post(BASE, headers=admin_headers, json=payload(setup)).json()
    flight_two = db.get(Flight, second["id"])

    add_passenger(setup["flight"])
    add_passenger(flight_two)
    add_passenger(flight_two)

    rows = {row["flight_code"]: row for row in client.get(BASE, headers=admin_headers).json()}
    assert rows["VN1234"]["assigned_count"] == 1
    assert rows["VN1250"]["assigned_count"] == 2


# --- Sửa ---


def test_update_changes_fields_and_audits(
    client: TestClient, setup, admin_headers, db: Session
):
    flight_id = setup["flight"].id
    response = client.patch(
        f"{BASE}/{flight_id}",
        headers=admin_headers,
        json={"capacity": 70, "airline": "Bamboo Airways", "shift_id": setup["shift2"].id},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["capacity"] == 70
    assert body["usable_capacity"] == 68
    assert body["shift_code"] == "CA2"

    audit = db.query(AuditLog).filter(AuditLog.action == "flight.updated").one()
    assert "capacity" in (audit.after_data or "")


def test_update_cannot_drop_capacity_below_assigned(
    client: TestClient, setup, admin_headers, add_passenger
):
    for _ in range(3):
        add_passenger(setup["flight"])

    response = client.patch(
        f"{BASE}/{setup['flight'].id}", headers=admin_headers, json={"capacity": 4, "reserved_slots": 2}
    )

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "CAPACITY_BELOW_ASSIGNED"
    assert error["details"]["assigned_count"] == 3


def test_update_allows_capacity_exactly_at_assigned(
    client: TestClient, setup, admin_headers, add_passenger
):
    """Ranh giới: ghế dùng được == số đã xếp thì vẫn hợp lệ, chỉ là hết chỗ."""
    for _ in range(3):
        add_passenger(setup["flight"])

    response = client.patch(
        f"{BASE}/{setup['flight'].id}",
        headers=admin_headers,
        json={"capacity": 3, "reserved_slots": 0},
    )

    assert response.status_code == 200
    assert response.json()["remaining_slots"] == 0
    assert response.json()["load_ratio"] == 1.0


def test_update_cannot_deactivate_flight_with_passengers(
    client: TestClient, setup, admin_headers, add_passenger
):
    add_passenger(setup["flight"])

    response = client.patch(
        f"{BASE}/{setup['flight'].id}", headers=admin_headers, json={"is_active": False}
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "FLIGHT_HAS_PASSENGERS"


def test_update_rejects_arrival_before_departure_against_stored_value(
    client: TestClient, setup, admin_headers
):
    """Chỉ đổi giờ đến: phải so với giờ đi đang lưu trong DB, không bỏ qua vì thiếu trường."""
    response = client.patch(
        f"{BASE}/{setup['flight'].id}",
        headers=admin_headers,
        json={"arrival_time": "2026-10-15T05:00:00+00:00"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_FLIGHT_TIME"


def test_update_rejects_route_becoming_circular(client: TestClient, setup, admin_headers):
    response = client.patch(
        f"{BASE}/{setup['flight'].id}", headers=admin_headers, json={"arrival_airport": "HAN"}
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_FLIGHT_ROUTE"


# --- Xoá ---


def test_delete_flight_without_passengers(client: TestClient, setup, admin_headers, db: Session):
    response = client.delete(f"{BASE}/{setup['flight'].id}", headers=admin_headers)

    assert response.status_code == 204
    assert db.query(Flight).count() == 0
    assert db.query(AuditLog).filter(AuditLog.action == "flight.deleted").count() == 1


def test_delete_blocked_while_passengers_remain(
    client: TestClient, setup, admin_headers, add_passenger, db: Session
):
    """Cascade của ORM sẽ xoá luôn phân bổ — chặn ở đây để không mất dữ liệu âm thầm."""
    add_passenger(setup["flight"])

    response = client.delete(f"{BASE}/{setup['flight'].id}", headers=admin_headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "FLIGHT_HAS_PASSENGERS"
    assert db.query(Flight).count() == 1
    assert db.query(FlightAssignment).count() == 1


def test_get_and_delete_reject_flight_of_another_event(
    client: TestClient, setup, admin_headers, db: Session
):
    other = Event(
        code="TB2025",
        name="Kỳ cũ",
        start_date="2025-10-15",
        end_date="2025-10-17",
        status=EventStatus.COMPLETED,
        terms_version="v1",
    )
    db.add(other)
    db.flush()
    foreign = Flight(
        event_id=other.id,
        flight_code="VN9999",
        direction=FlightDirection.OUTBOUND,
        departure_airport="HAN",
        arrival_airport="PQC",
        departure_time="2025-10-15T06:30:00+00:00",
        arrival_time="2025-10-15T08:40:00+00:00",
        capacity=10,
    )
    db.add(foreign)
    db.commit()

    assert client.get(f"{BASE}/{foreign.id}", headers=admin_headers).status_code == 404
    assert client.delete(f"{BASE}/{foreign.id}", headers=admin_headers).status_code == 404


# --- Hành khách ---


def test_passenger_list_has_team_and_no_documents(
    client: TestClient, setup, admin_headers, add_passenger
):
    add_passenger(setup["flight"], can_fly=True)
    add_passenger(setup["flight"], can_fly=False)

    response = client.get(f"{BASE}/{setup['flight'].id}/passengers", headers=admin_headers)

    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 2
    assert rows[0]["team_name"] == "Công nghệ"
    assert rows[0]["requested_shift_code"] == "CA1"
    assert {row["has_flight_documents"] for row in rows} == {True, False}
    # Danh sách này in ra giấy: không được có giấy tờ cá nhân.
    assert "id_card_number" not in response.text
    assert "001095012345" not in response.text


# --- Tổng quan slot ---


def test_summary_reports_shortfall_and_shift_demand(
    client: TestClient, setup, admin_headers, add_passenger, db: Session
):
    for _ in range(4):
        add_passenger(setup["flight"])

    response = client.get(f"{BASE}/summary", headers=admin_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["participants"] == 4

    outbound = next(d for d in body["directions"] if d["direction"] == "outbound")
    assert outbound["flights"] == 1
    assert outbound["usable_capacity"] == 58
    assert outbound["assigned"] == 4
    assert outbound["remaining"] == 54
    assert outbound["shortfall"] == 0

    ca1 = next(s for s in outbound["by_shift"] if s["shift_code"] == "CA1")
    assert ca1["requested"] == 4
    assert ca1["assigned"] == 4

    # Chiều về chưa có chuyến nào -> thiếu đúng bằng số người tham gia.
    inbound = next(d for d in body["directions"] if d["direction"] == "return")
    assert inbound["flights"] == 0
    assert inbound["shortfall"] == 4


def test_summary_counts_shortfall_when_capacity_too_small(
    client: TestClient, setup, admin_headers, add_passenger, db: Session
):
    setup["flight"].capacity = 3
    setup["flight"].reserved_slots = 1
    db.commit()
    for _ in range(5):
        add_passenger(setup["flight"])

    outbound = next(
        d
        for d in client.get(f"{BASE}/summary", headers=admin_headers).json()["directions"]
        if d["direction"] == "outbound"
    )

    # 5 người tham gia, chỉ 2 ghế dùng được -> thiếu 3.
    assert outbound["usable_capacity"] == 2
    assert outbound["shortfall"] == 3


def test_summary_flags_oversubscribed_shift_even_when_total_fits(
    client: TestClient, setup, admin_headers, add_passenger, db: Session
):
    """Ca 2 đông hơn số ghế của ca 2, dù tổng ghế cả chiều vẫn đủ.

    Đây là tình huống có thật trong dữ liệu mẫu (61 nguyện vọng Ca 2 / 50 ghế): tổng
    không thiếu nên `shortfall` theo chiều bằng 0, phải nhìn xuống từng ca mới thấy.
    """
    # Chuyến của Ca 2 chỉ 2 ghế dùng được.
    second = client.post(
        BASE, headers=admin_headers, json=payload(setup, capacity=3, reserved_slots=1)
    ).json()
    assert second["usable_capacity"] == 2

    # 3 người đăng ký nguyện vọng Ca 2.
    for _ in range(3):
        assignment = add_passenger(setup["flight"])
        registration = db.get(Registration, assignment.registration_id)
        registration.shift_id = setup["shift2"].id
    db.commit()

    outbound = next(
        d
        for d in client.get(f"{BASE}/summary", headers=admin_headers).json()["directions"]
        if d["direction"] == "outbound"
    )

    assert outbound["shortfall"] == 0  # 58 + 2 ghế dùng được cho 3 người: tổng vẫn đủ
    ca2 = next(s for s in outbound["by_shift"] if s["shift_code"] == "CA2")
    assert ca2["requested"] == 3
    assert ca2["usable_capacity"] == 2
    assert ca2["shortfall"] == 1

    ca1 = next(s for s in outbound["by_shift"] if s["shift_code"] == "CA1")
    assert ca1["requested"] == 0
    assert ca1["shortfall"] == 0


def test_summary_ignores_inactive_flights(
    client: TestClient, setup, admin_headers, db: Session
):
    """Chuyến đã tắt không được tính vào slot khả dụng, nếu không BTC tưởng còn chỗ."""
    setup["flight"].is_active = False
    db.commit()

    outbound = next(
        d
        for d in client.get(f"{BASE}/summary", headers=admin_headers).json()["directions"]
        if d["direction"] == "outbound"
    )

    assert outbound["flights"] == 0
    assert outbound["usable_capacity"] == 0
