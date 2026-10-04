"""Kiểm thử API phân bổ chuyến bay và điều chỉnh thủ công (docs/04 §5, docs/05 §5)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    Bus,
    EmailLog,
    Event,
    Flight,
    FlightAssignment,
    Registration,
    RegistrationLeg,
    PickupPoint,
    Shift,
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

ALLOCATE = "/api/v1/flights/allocate"
ASSIGNMENTS = "/api/v1/flight-assignments"


@pytest.fixture
def setup(db: Session) -> dict:
    """Kỳ ĐÃ ĐÓNG đăng ký, 2 ca, 2 chuyến chiều đi (8 + 6 ghế dùng được), 2 team."""
    event = Event(
        code="TB2026",
        name="Team Building 2026",
        start_date="2026-10-15",
        end_date="2026-10-17",
        status=EventStatus.REGISTRATION_CLOSED,
        terms_version="v1",
        is_active=True,
    )
    db.add(event)
    db.flush()

    shift1 = Shift(event_id=event.id, code="CA1", name="Ca 1", display_order=1)
    shift2 = Shift(event_id=event.id, code="CA2", name="Ca 2", display_order=2)
    team1 = Team(code="IT", name="Công nghệ")
    team2 = Team(code="SALE", name="Kinh doanh")
    db.add_all([shift1, shift2, team1, team2])
    db.flush()

    ca1 = Flight(
        event_id=event.id,
        flight_code="VN1234",
        direction=FlightDirection.OUTBOUND,
        shift_id=shift1.id,
        departure_airport="HAN",
        arrival_airport="PQC",
        departure_time="2026-10-15T06:30:00+00:00",
        arrival_time="2026-10-15T08:40:00+00:00",
        capacity=10,
        reserved_slots=2,
    )
    ca2 = Flight(
        event_id=event.id,
        flight_code="VN1250",
        direction=FlightDirection.OUTBOUND,
        shift_id=shift2.id,
        departure_airport="HAN",
        arrival_airport="PQC",
        departure_time="2026-10-15T19:15:00+00:00",
        arrival_time="2026-10-15T21:25:00+00:00",
        capacity=6,
        reserved_slots=0,
    )
    back = Flight(
        event_id=event.id,
        flight_code="VN1235",
        direction=FlightDirection.RETURN,
        shift_id=shift1.id,
        departure_airport="PQC",
        arrival_airport="HAN",
        departure_time="2026-10-17T15:00:00+00:00",
        arrival_time="2026-10-17T17:10:00+00:00",
        capacity=20,
        reserved_slots=0,
    )
    db.add_all([ca1, ca2, back])
    db.commit()

    return {
        "event": event,
        "shift1": shift1,
        "shift2": shift2,
        "team1": team1,
        "team2": team2,
        "ca1": ca1,
        "ca2": ca2,
        "back": back,
    }


@pytest.fixture
def admin_headers(make_user, auth_headers, setup):
    make_user(email="btc@company.vn", password="MatKhau123", role=UserRole.ADMIN)
    return auth_headers("btc@company.vn")


@pytest.fixture
def register(db: Session, setup):
    """Tạo CBNV đã đăng ký tham gia."""
    counter = {"n": 0}

    def _add(
        *,
        team: Team | None = None,
        shift: Shift | None = None,
        locked: bool = False,
        can_fly: bool = True,
        cancelled: bool = False,
    ) -> Registration:
        counter["n"] += 1
        index = counter["n"]
        user = User(
            email=f"nv{index}@company.vn",
            full_name=f"Nguyễn Văn {index:02d}",
            employee_code=f"NV{index:03d}",
            password_hash="x",
            role=UserRole.EMPLOYEE,
            team_id=team.id if team else None,
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
            shift_id=shift.id if shift else None,
            is_shift_locked=locked,
            status=(
                RegistrationStatus.CANCELLED if cancelled else RegistrationStatus.SUBMITTED
            ),
            submitted_at="2026-09-12T03:00:00+00:00",
        )
        db.add(registration)
        db.commit()
        db.refresh(registration)
        return registration

    return _add


def allocate(client, headers, **overrides) -> dict:
    payload = {"direction": "outbound", "dry_run": True}
    payload.update(overrides)
    response = client.post(ALLOCATE, headers=headers, json=payload)
    assert response.status_code == 200, response.text
    return response.json()


# --- Quyền ---


def test_employee_cannot_allocate_or_move(
    client: TestClient, setup, make_user, auth_headers
):
    make_user(email="nv@company.vn", password="MatKhau123")
    headers = auth_headers("nv@company.vn")

    assert client.post(ALLOCATE, headers=headers, json={"direction": "outbound"}).status_code == 403
    assert client.get(ASSIGNMENTS, headers=headers).status_code == 403
    assert client.patch(f"{ASSIGNMENTS}/1", headers=headers,
                        json={"flight_id": setup["ca1"].id, "reason": "Chuyển chuyến"}).status_code == 403
    assert client.post(f"{ASSIGNMENTS}/bulk-move", headers=headers,
                       json={"registration_ids": [1], "flight_id": setup["ca1"].id,
                             "reason": "Chuyển chuyến"}).status_code == 403
    assert client.delete(f"{ASSIGNMENTS}/1?reason=BTC+chuyển+chuyến", headers=headers).status_code == 403


# --- Dry run ---


def test_dry_run_returns_preview_without_writing(
    client: TestClient, setup, admin_headers, register, db: Session
):
    for _ in range(5):
        register(team=setup["team1"], shift=setup["shift1"])

    body = allocate(client, admin_headers)

    assert body["dry_run"] is True
    assert body["committed"] is False
    assert body["summary"]["assigned"] == 5
    assert body["summary"]["unassigned"] == 0
    assert len(body["flights"]) == 2
    assert body["params"]["team_weight"] == 10
    # Quan trọng nhất: preview không được ghi gì vào DB.
    assert db.query(FlightAssignment).count() == 0
    assert db.query(AuditLog).filter(AuditLog.action == "flight.allocated").count() == 0


def test_dry_run_works_even_while_registration_is_open(
    client: TestClient, setup, admin_headers, register, db: Session
):
    """BTC cần xem trước ĐỂ quyết định có đóng đăng ký hay chưa."""
    setup["event"].status = EventStatus.REGISTRATION_OPEN
    db.commit()
    register(team=setup["team1"], shift=setup["shift1"])

    body = allocate(client, admin_headers)
    assert body["summary"]["assigned"] == 1


def test_preview_reports_flags_and_teams_per_flight(
    client: TestClient, setup, admin_headers, register
):
    for _ in range(10):
        register(team=setup["team1"], shift=setup["shift1"])
    register(team=setup["team2"], shift=setup["shift1"], can_fly=False)

    body = allocate(client, admin_headers)
    flag_types = {flag["type"] for flag in body["flags"]}

    assert "MISSING_ID_CARD" in flag_types
    teams_on_flights = {
        team["team_name"] for flight in body["flights"] for team in flight["teams"]
    }
    assert "Công nghệ" in teams_on_flights


# --- Commit ---


def test_commit_writes_assignments_and_audit(
    client: TestClient, setup, admin_headers, register, db: Session
):
    registrations = [register(team=setup["team1"], shift=setup["shift1"]) for _ in range(6)]

    body = allocate(client, admin_headers, dry_run=False)

    assert body["committed"] is True
    assert body["summary"]["assigned"] == 6

    rows = db.query(FlightAssignment).all()
    assert len(rows) == 6
    assert {row.registration_id for row in rows} == {r.id for r in registrations}
    assert {row.assignment_mode for row in rows} == {AssignmentMode.AUTO}
    assert {row.direction for row in rows} == {FlightDirection.OUTBOUND}

    audit = db.query(AuditLog).filter(AuditLog.action == "flight.allocated").one()
    assert '"assigned": 6' in (audit.after_data or "")


def test_commit_blocked_while_registration_open(
    client: TestClient, setup, admin_headers, register, db: Session
):
    setup["event"].status = EventStatus.REGISTRATION_OPEN
    db.commit()
    register(team=setup["team1"], shift=setup["shift1"])

    response = client.post(
        ALLOCATE, headers=admin_headers, json={"direction": "outbound", "dry_run": False}
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "REGISTRATION_STILL_OPEN"
    assert db.query(FlightAssignment).count() == 0


def test_commit_twice_is_idempotent(
    client: TestClient, setup, admin_headers, register, db: Session
):
    """Chạy lại phải cho cùng kết quả, không nhân đôi bản ghi."""
    for _ in range(6):
        register(team=setup["team1"], shift=setup["shift1"])

    first = allocate(client, admin_headers, dry_run=False)
    placement_one = {
        row.registration_id: row.flight_id for row in db.query(FlightAssignment).all()
    }

    second = allocate(client, admin_headers, dry_run=False)
    placement_two = {
        row.registration_id: row.flight_id for row in db.query(FlightAssignment).all()
    }

    assert db.query(FlightAssignment).count() == 6
    assert placement_one == placement_two
    assert first["summary"] == second["summary"]


def test_commit_never_exceeds_capacity(
    client: TestClient, setup, admin_headers, register, db: Session
):
    # 8 + 6 = 14 ghế dùng được, nhưng có 20 người.
    for _ in range(20):
        register(team=setup["team1"], shift=setup["shift1"])

    body = allocate(client, admin_headers, dry_run=False)

    assert body["summary"]["assigned"] == 14
    assert body["summary"]["unassigned"] == 6
    assert len([f for f in body["flags"] if f["type"] == "UNASSIGNED"]) == 6

    per_flight = {}
    for row in db.query(FlightAssignment).all():
        per_flight[row.flight_id] = per_flight.get(row.flight_id, 0) + 1
    assert per_flight[setup["ca1"].id] <= 8
    assert per_flight[setup["ca2"].id] <= 6


def test_commit_keeps_manual_assignment(
    client: TestClient, setup, admin_headers, register, db: Session
):
    """Bản ghi thủ công của BTC không bị auto ghi đè (docs/05 §5)."""
    pinned = register(team=setup["team1"], shift=setup["shift1"])
    others = [register(team=setup["team1"], shift=setup["shift1"]) for _ in range(4)]

    db.add(
        FlightAssignment(
            registration_id=pinned.id,
            flight_id=setup["ca2"].id,  # ca 2, dù người này xin ca 1
            direction=FlightDirection.OUTBOUND,
            assignment_mode=AssignmentMode.MANUAL,
            assigned_at="2026-09-12T04:00:00+00:00",
            seat_number="12A",
            ticket_code="MANUAL01",
            note="BTC đã xác nhận vé",
        )
    )
    db.commit()

    original = db.query(FlightAssignment).filter_by(registration_id=pinned.id).one()
    original_id, original_time = original.id, original.assigned_at

    allocate(client, admin_headers, dry_run=False)

    kept = db.query(FlightAssignment).filter_by(registration_id=pinned.id).one()
    assert kept.flight_id == setup["ca2"].id
    assert kept.assignment_mode == AssignmentMode.MANUAL
    assert (kept.id, kept.assigned_at) == (original_id, original_time)
    assert (kept.seat_number, kept.ticket_code, kept.note) == ("12A", "MANUAL01", "BTC đã xác nhận vé")
    # Những người khác vẫn được xếp bình thường.
    assert db.query(FlightAssignment).count() == len(others) + 1


def test_force_reallocate_overrides_manual(
    client: TestClient, setup, admin_headers, register, db: Session
):
    pinned = register(team=setup["team1"], shift=setup["shift1"])
    for _ in range(4):
        register(team=setup["team1"], shift=setup["shift1"])

    db.add(
        FlightAssignment(
            registration_id=pinned.id,
            flight_id=setup["ca2"].id,
            direction=FlightDirection.OUTBOUND,
            assignment_mode=AssignmentMode.MANUAL,
            assigned_at="2026-09-12T04:00:00+00:00",
        )
    )
    db.commit()

    allocate(client, admin_headers, dry_run=False, force_reallocate=True)

    row = db.query(FlightAssignment).filter_by(registration_id=pinned.id).one()
    assert row.assignment_mode == AssignmentMode.AUTO
    # Cả team về cùng một chuyến đúng ca.
    assert row.flight_id == setup["ca1"].id


def test_commit_cleans_up_assignment_of_cancelled_registration(
    client: TestClient, setup, admin_headers, register, db: Session
):
    """Người huỷ đăng ký sau khi đã được xếp chỗ: ghế phải được trả lại.

    Để lại bản ghi đó thì một ghế bị chiếm bởi người không đi, và mọi phép đếm slot sai.
    """
    gone = register(team=setup["team1"], shift=setup["shift1"], cancelled=True)
    db.add(
        FlightAssignment(
            registration_id=gone.id,
            flight_id=setup["ca1"].id,
            direction=FlightDirection.OUTBOUND,
            assignment_mode=AssignmentMode.MANUAL,
            assigned_at="2026-09-12T04:00:00+00:00",
        )
    )
    db.commit()
    for _ in range(3):
        register(team=setup["team1"], shift=setup["shift1"])

    body = allocate(client, admin_headers, dry_run=False)

    assert body["removed_stale"] == 1
    assert db.query(FlightAssignment).filter_by(registration_id=gone.id).count() == 0
    assert db.query(FlightAssignment).count() == 3


def test_each_direction_is_allocated_independently(
    client: TestClient, setup, admin_headers, register, db: Session
):
    for _ in range(4):
        register(team=setup["team1"], shift=setup["shift1"])

    allocate(client, admin_headers, dry_run=False)
    allocate(client, admin_headers, direction="return", dry_run=False)

    rows = db.query(FlightAssignment).all()
    assert len(rows) == 8  # 4 người x 2 chiều
    assert {row.direction for row in rows} == {
        FlightDirection.OUTBOUND,
        FlightDirection.RETURN,
    }


# --- Danh sách phân bổ ---


def test_list_assignments_with_filters(
    client: TestClient, setup, admin_headers, register, db: Session
):
    for _ in range(4):
        register(team=setup["team1"], shift=setup["shift1"])
    undocumented = register(team=setup["team2"], shift=setup["shift2"], can_fly=False)
    result = allocate(client, admin_headers, dry_run=False)

    # Thiếu giấy tờ thì KHÔNG được xếp chuyến bay — chỉ bị gắn cờ để BTC đi nhắc bổ sung.
    flagged = [flag for flag in result["flags"] if flag["type"] == "MISSING_ID_CARD"]
    assert [flag["registration_id"] for flag in flagged] == [undocumented.id]
    assert db.query(FlightAssignment).filter_by(registration_id=undocumented.id).count() == 0

    body = client.get(ASSIGNMENTS, headers=admin_headers).json()
    assert body["total"] == 4
    assert body["items"][0]["flight_code"] in {"VN1234", "VN1250"}
    assert "id_card_number" not in str(body)

    by_flight = client.get(
        f"{ASSIGNMENTS}?flight_id={setup['ca1'].id}", headers=admin_headers
    ).json()
    assert all(row["flight_id"] == setup["ca1"].id for row in by_flight["items"])

    by_team = client.get(
        f"{ASSIGNMENTS}?team_id={setup['team2'].id}", headers=admin_headers
    ).json()
    assert by_team["total"] == 0

    missing = client.get(f"{ASSIGNMENTS}?missing_documents=true", headers=admin_headers).json()
    assert missing["total"] == 0, "người thiếu giấy tờ không còn nằm trong danh sách đã xếp"

    # Xếp tay cũng theo luật đó.
    manual = client.post(
        f"{ASSIGNMENTS}/bulk-move", headers=admin_headers,
        json={"registration_ids": [undocumented.id], "flight_id": setup["ca1"].id, "reason": "xếp tay thử"},
    )
    assert manual.status_code == 409
    assert manual.json()["error"]["code"] == "FLIGHT_DOCUMENTS_MISSING"


def test_list_filters_by_shift_mismatch(
    client: TestClient, setup, admin_headers, register, db: Session
):
    """9 người xin Ca 1 nhưng chuyến Ca 1 chỉ 8 ghế -> có người phải sang Ca 2."""
    for _ in range(9):
        register(team=setup["team1"], shift=setup["shift1"])
    allocate(client, admin_headers, dry_run=False)

    mismatched = client.get(f"{ASSIGNMENTS}?shift_mismatch=true", headers=admin_headers).json()
    matched = client.get(f"{ASSIGNMENTS}?shift_mismatch=false", headers=admin_headers).json()

    assert mismatched["total"] + matched["total"] == 9
    assert mismatched["total"] >= 1
    assert all(row["shift_mismatch"] is True for row in mismatched["items"])


# --- Chuyển một người ---


def test_move_marks_manual_and_audits(
    client: TestClient, setup, admin_headers, register, db: Session
):
    for _ in range(3):
        register(team=setup["team1"], shift=setup["shift1"])
    allocate(client, admin_headers, dry_run=False)
    assignment = db.query(FlightAssignment).first()

    response = client.patch(
        f"{ASSIGNMENTS}/{assignment.id}",
        headers=admin_headers,
        json={"flight_id": setup["ca2"].id, "reason": "Vợ chồng muốn bay cùng chuyến"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["moved"] == 1
    assert body["assignments"][0]["flight_id"] == setup["ca2"].id
    assert body["assignments"][0]["assignment_mode"] == "manual"
    # Lệch ca là cảnh báo, không chặn.
    assert {w["type"] for w in body["warnings"]} >= {"SHIFT_NOT_SATISFIED"}

    audit = db.query(AuditLog).filter(AuditLog.action == "flight_assignment.moved").one()
    assert audit.reason == "Vợ chồng muốn bay cùng chuyến"
    assert f'"flight_id": {setup["ca2"].id}' in (audit.after_data or "")


def test_move_blocked_when_target_is_full(
    client: TestClient, setup, admin_headers, register, db: Session
):
    """Sức chứa là ràng buộc CỨNG: vượt thì 409, không cảnh báo rồi cho qua."""
    for _ in range(14):  # lấp kín cả 8 + 6 ghế
        register(team=setup["team1"], shift=setup["shift1"])
    allocate(client, admin_headers, dry_run=False)

    on_ca1 = db.query(FlightAssignment).filter_by(flight_id=setup["ca1"].id).first()
    response = client.patch(
        f"{ASSIGNMENTS}/{on_ca1.id}",
        headers=admin_headers,
        json={"flight_id": setup["ca2"].id, "reason": "Thử vượt sức chứa"},
    )

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "FLIGHT_CAPACITY_EXCEEDED"
    assert error["details"]["remaining"] == 0
    # Không được ghi gì khi đã chối.
    db.refresh(on_ca1)
    assert on_ca1.flight_id == setup["ca1"].id


def test_move_requires_reason(client: TestClient, setup, admin_headers, register, db: Session):
    register(team=setup["team1"], shift=setup["shift1"])
    allocate(client, admin_headers, dry_run=False)
    assignment = db.query(FlightAssignment).one()

    no_reason = client.patch(
        f"{ASSIGNMENTS}/{assignment.id}",
        headers=admin_headers,
        json={"flight_id": setup["ca2"].id},
    )
    too_short = client.patch(
        f"{ASSIGNMENTS}/{assignment.id}",
        headers=admin_headers,
        json={"flight_id": setup["ca2"].id, "reason": "x"},
    )

    assert no_reason.status_code == 422
    assert too_short.status_code == 422


def test_move_rejects_flight_of_other_direction(
    client: TestClient, setup, admin_headers, register, db: Session
):
    """Mỗi người một chuyến cho mỗi chiều — chuyển sang chiều khác là dữ liệu sai."""
    register(team=setup["team1"], shift=setup["shift1"])
    allocate(client, admin_headers, dry_run=False)
    assignment = db.query(FlightAssignment).one()

    response = client.patch(
        f"{ASSIGNMENTS}/{assignment.id}",
        headers=admin_headers,
        json={"flight_id": setup["back"].id, "reason": "Chuyển sai chiều"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "DIRECTION_MISMATCH"


def test_move_to_same_flight_is_rejected(
    client: TestClient, setup, admin_headers, register, db: Session
):
    register(team=setup["team1"], shift=setup["shift1"])
    allocate(client, admin_headers, dry_run=False)
    assignment = db.query(FlightAssignment).one()

    response = client.patch(
        f"{ASSIGNMENTS}/{assignment.id}",
        headers=admin_headers,
        json={"flight_id": assignment.flight_id, "reason": "Không đổi gì"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ALREADY_ON_FLIGHT"


def test_moved_person_survives_next_auto_run(
    client: TestClient, setup, admin_headers, register, db: Session
):
    """Chuyển tay xong chạy lại auto: quyết định của con người phải còn nguyên."""
    for _ in range(4):
        register(team=setup["team1"], shift=setup["shift1"])
    allocate(client, admin_headers, dry_run=False)
    assignment = db.query(FlightAssignment).first()

    client.patch(
        f"{ASSIGNMENTS}/{assignment.id}",
        headers=admin_headers,
        json={"flight_id": setup["ca2"].id, "reason": "Đi cùng người nhà"},
    )
    allocate(client, admin_headers, dry_run=False)

    db.refresh(assignment)
    assert assignment.flight_id == setup["ca2"].id
    assert assignment.assignment_mode == AssignmentMode.MANUAL


# --- Chuyển cả nhóm ---


def test_bulk_move_moves_group_and_creates_missing(
    client: TestClient, setup, admin_headers, register, db: Session
):
    assigned = [register(team=setup["team1"], shift=setup["shift1"]) for _ in range(3)]
    allocate(client, admin_headers, dry_run=False)
    # Người đăng ký muộn, chưa có phân bổ.
    late = register(team=setup["team1"], shift=setup["shift1"])

    response = client.post(
        f"{ASSIGNMENTS}/bulk-move",
        headers=admin_headers,
        json={
            "registration_ids": [r.id for r in assigned] + [late.id],
            "flight_id": setup["ca2"].id,
            "reason": "Dồn cả team sang chuyến chiều",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["moved"] == 3
    assert body["created"] == 1
    assert all(row["flight_id"] == setup["ca2"].id for row in body["assignments"])
    assert all(row["assignment_mode"] == "manual" for row in body["assignments"])

    audit = db.query(AuditLog).filter(AuditLog.action == "flight_assignment.bulk_moved").one()
    assert audit.reason == "Dồn cả team sang chuyến chiều"


def test_bulk_move_is_all_or_nothing_when_capacity_short(
    client: TestClient, setup, admin_headers, register, db: Session
):
    """Chuyển được một nửa rồi hết chỗ là trạng thái không ai muốn dọn bằng tay."""
    people = [register(team=setup["team1"], shift=setup["shift1"]) for _ in range(8)]
    allocate(client, admin_headers, dry_run=False)
    before = {
        row.registration_id: row.flight_id for row in db.query(FlightAssignment).all()
    }

    # Chuyến Ca 2 chỉ 6 ghế, chuyển 8 người sang.
    response = client.post(
        f"{ASSIGNMENTS}/bulk-move",
        headers=admin_headers,
        json={
            "registration_ids": [r.id for r in people],
            "flight_id": setup["ca2"].id,
            "reason": "Thử dồn quá tải",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "FLIGHT_CAPACITY_EXCEEDED"
    after = {row.registration_id: row.flight_id for row in db.query(FlightAssignment).all()}
    assert after == before


def test_bulk_move_rejects_registration_from_other_event(
    client: TestClient, setup, admin_headers, register, db: Session
):
    register(team=setup["team1"], shift=setup["shift1"])
    allocate(client, admin_headers, dry_run=False)

    response = client.post(
        f"{ASSIGNMENTS}/bulk-move",
        headers=admin_headers,
        json={
            "registration_ids": [99999],
            "flight_id": setup["ca2"].id,
            "reason": "Đăng ký không tồn tại",
        },
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "REGISTRATION_NOT_FOUND"


def test_bulk_move_warns_about_team_split(
    client: TestClient, setup, admin_headers, register, db: Session
):
    people = [register(team=setup["team1"], shift=setup["shift1"]) for _ in range(6)]
    allocate(client, admin_headers, dry_run=False)

    response = client.post(
        f"{ASSIGNMENTS}/bulk-move",
        headers=admin_headers,
        json={
            "registration_ids": [people[0].id, people[1].id],
            "flight_id": setup["ca2"].id,
            "reason": "Hai người phải bay muộn",
        },
    )

    warnings = {w["type"] for w in response.json()["warnings"]}
    assert "TEAM_SPLIT" in warnings


def test_bulk_move_warns_when_locked_shift_is_broken(
    client: TestClient, setup, admin_headers, register, db: Session
):
    """Khoá ca là cứng với thuật toán, nhưng BTC vẫn được quyền phá — có cảnh báo rõ."""
    locked = register(team=setup["team1"], shift=setup["shift1"], locked=True)
    allocate(client, admin_headers, dry_run=False)

    response = client.post(
        f"{ASSIGNMENTS}/bulk-move",
        headers=admin_headers,
        json={
            "registration_ids": [locked.id],
            "flight_id": setup["ca2"].id,
            "reason": "BTC quyết định đổi ca cho người này",
        },
    )

    assert response.status_code == 200
    assert "SHIFT_LOCKED_VIOLATION" in {w["type"] for w in response.json()["warnings"]}


# --- Bỏ phân bổ ---


def test_delete_assignment_frees_the_seat(
    client: TestClient, setup, admin_headers, register, db: Session
):
    register(team=setup["team1"], shift=setup["shift1"])
    allocate(client, admin_headers, dry_run=False)
    assignment = db.query(FlightAssignment).one()

    response = client.delete(
        f"{ASSIGNMENTS}/{assignment.id}?reason=Nghỉ việc trước chuyến đi",
        headers=admin_headers,
    )

    assert response.status_code == 204
    assert db.query(FlightAssignment).count() == 0
    audit = db.query(AuditLog).filter(AuditLog.action == "flight_assignment.removed").one()
    assert audit.reason == "Nghỉ việc trước chuyến đi"


def test_delete_requires_reason(client: TestClient, setup, admin_headers, register, db: Session):
    register(team=setup["team1"], shift=setup["shift1"])
    allocate(client, admin_headers, dry_run=False)
    assignment = db.query(FlightAssignment).one()

    response = client.delete(f"{ASSIGNMENTS}/{assignment.id}", headers=admin_headers)

    assert response.status_code == 422
    assert db.query(FlightAssignment).count() == 1


def test_delete_rejects_assignment_of_other_event(
    client: TestClient, setup, admin_headers
):
    response = client.delete(f"{ASSIGNMENTS}/99999?reason=Không tồn tại", headers=admin_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ASSIGNMENT_NOT_FOUND"


# --- Bỏ toàn bộ phân bổ (để sửa lại số ghế rồi chạy lại) ---

RESET = "/api/v1/flights/reset-allocation"


def test_reset_clears_auto_rows_but_keeps_manual(
    client: TestClient, setup, admin_headers, register, db: Session
):
    people = [register(team=setup["team1"], shift=setup["shift1"]) for _ in range(6)]
    allocate(client, admin_headers, dry_run=False)
    pinned = db.query(FlightAssignment).filter_by(registration_id=people[0].id).one()
    pinned.assignment_mode = AssignmentMode.MANUAL
    db.commit()

    response = client.post(
        RESET,
        headers=admin_headers,
        json={"direction": "outbound", "reason": "Đặt lại số ghế theo vé thật"},
    )

    assert response.status_code == 200, response.text
    assert response.json() == {"removed": 5, "kept_manual": 1}
    rows = db.query(FlightAssignment).all()
    assert [row.registration_id for row in rows] == [people[0].id]

    audit = db.query(AuditLog).filter(AuditLog.action == "flight_allocation.reset").one()
    assert audit.reason == "Đặt lại số ghế theo vé thật"


def test_reset_with_include_manual_clears_everything(
    client: TestClient, setup, admin_headers, register, db: Session
):
    people = [register(team=setup["team1"], shift=setup["shift1"]) for _ in range(6)]
    allocate(client, admin_headers, dry_run=False)
    db.query(FlightAssignment).filter_by(registration_id=people[0].id).one().assignment_mode = (
        AssignmentMode.MANUAL
    )
    db.commit()

    body = client.post(
        RESET,
        headers=admin_headers,
        json={"direction": "outbound", "reason": "Xếp lại từ đầu", "include_manual": True},
    ).json()

    assert body == {"removed": 6, "kept_manual": 0}
    assert db.query(FlightAssignment).count() == 0


def test_reset_touches_only_the_chosen_direction(
    client: TestClient, setup, admin_headers, register, db: Session
):
    register(team=setup["team1"], shift=setup["shift1"])
    allocate(client, admin_headers, dry_run=False)
    allocate(client, admin_headers, dry_run=False, direction="return")
    assert db.query(FlightAssignment).count() == 2

    client.post(RESET, headers=admin_headers, json={"direction": "outbound", "reason": "Dọn chiều đi"})

    remaining = db.query(FlightAssignment).all()
    assert [row.direction for row in remaining] == [FlightDirection.RETURN]


def test_reset_requires_a_reason(client: TestClient, setup, admin_headers):
    response = client.post(RESET, headers=admin_headers, json={"direction": "outbound"})
    assert response.status_code == 422


def test_employee_cannot_reset(client: TestClient, setup, make_user, auth_headers):
    make_user(email="nv@company.vn", password="MatKhau123")
    headers = auth_headers("nv@company.vn")

    response = client.post(
        RESET, headers=headers, json={"direction": "outbound", "reason": "thử"}
    )

    assert response.status_code == 403


def test_preview_reads_event_json_and_v2_pickup_points(client, setup, admin_headers, register, db):
    from app.services.allocator.loader import load_participants

    registration = register(team=setup["team1"], shift=setup["shift1"])
    leg = TripLeg(event_id=setup["event"].id, code="CITY_TO_AIRPORT", name="Ra sân bay", direction="outbound")
    db.add(leg)
    db.flush()
    point = PickupPoint(event_id=setup["event"].id, trip_leg_id=leg.id, name="Điểm F3")
    db.add(point)
    db.flush()
    db.add(RegistrationLeg(registration_id=registration.id, trip_leg_id=leg.id,
                           needs_bus=True, pickup_point_id=point.id))
    setup["event"].settings = {"allocation.team_weight": 27, "allocation.min_chunk_size": 2}
    db.commit()

    body = allocate(client, admin_headers)
    assert body["params"]["team_weight"] == 27
    assert body["params"]["min_chunk_size"] == 2
    participants = load_participants(db, event_id=setup["event"].id, direction="outbound")
    assert participants[0].pickup_point_id == point.id
    assert db.query(FlightAssignment).count() == 0
    assert db.query(AuditLog).filter_by(action="flight.allocated").count() == 0


def test_commit_rechecks_capacity_after_preview(client, setup, admin_headers, register, db):
    for _ in range(3):
        register(shift=setup["shift1"])
    preview = allocate(client, admin_headers)
    assert preview["summary"]["assigned"] == 3
    setup["ca1"].capacity = 3  # Chỉ còn 1 ghế dùng được, sau khi BTC đã xem trước.
    setup["ca2"].is_active = False
    db.commit()

    body = allocate(client, admin_headers, dry_run=False)
    assert body["committed"] is True
    assert body["summary"]["assigned"] == 1
    assert body["summary"]["unassigned"] == 2
    assert db.query(FlightAssignment).count() == 1


def test_selected_event_allocation_does_not_touch_default_event(client, setup, admin_headers, register, db):
    person = register(shift=setup["shift1"])
    allocate(client, admin_headers, dry_run=False)
    original = db.query(FlightAssignment).filter_by(registration_id=person.id).one()
    original_id, original_flight = original.id, original.flight_id
    other = Event(code="TB2027", name="Kỳ khác", start_date="2027-10-15", end_date="2027-10-17",
                  status=EventStatus.REGISTRATION_CLOSED, settings={"allocation.team_weight": 31})
    db.add(other)
    db.flush()
    flight = Flight(event_id=other.id, flight_code="VN2027", direction="outbound",
                    departure_airport="HAN", arrival_airport="PQC", capacity=5,
                    departure_time="2027-10-15T06:00:00+00:00", arrival_time="2027-10-15T08:00:00+00:00")
    registration = Registration(event_id=other.id, user_id=person.user_id, is_participating=True,
                                status=RegistrationStatus.SUBMITTED)
    db.add_all([flight, registration])
    db.commit()

    body = allocate(client, {**admin_headers, "X-Event-Id": str(other.id)}, dry_run=False)
    assert body["summary"]["total_participants"] == 1
    assert body["params"]["team_weight"] == 31
    db.expire_all()
    original = db.query(FlightAssignment).filter_by(registration_id=person.id).one()
    assert (original.id, original.flight_id) == (original_id, original_flight)
    assert db.query(FlightAssignment).filter_by(registration_id=registration.id).one().flight_id == flight.id


def test_move_rejects_cancelled_registration(client, setup, admin_headers, register, db):
    person = register(cancelled=True)
    assignment = FlightAssignment(registration_id=person.id, flight_id=setup["ca1"].id,
                                  direction="outbound", assignment_mode="auto",
                                  assigned_at="2026-09-12T04:00:00+00:00")
    db.add(assignment)
    db.commit()
    response = client.patch(f"{ASSIGNMENTS}/{assignment.id}", headers=admin_headers,
                            json={"flight_id": setup["ca2"].id, "reason": "Chuyển chuyến"})
    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "REGISTRATION_NOT_FOUND"
    db.expire_all()
    assert db.get(FlightAssignment, assignment.id).flight_id == setup["ca1"].id


def test_missing_flight_shift_is_reported_by_mismatch_filter(client, setup, admin_headers, register, db):
    person = register(shift=setup["shift1"])
    setup["ca1"].shift_id = None
    db.add(FlightAssignment(registration_id=person.id, flight_id=setup["ca1"].id,
                           direction="outbound", assignment_mode="manual",
                           assigned_at="2026-09-12T04:00:00+00:00"))
    db.commit()
    mismatched = client.get(f"{ASSIGNMENTS}?shift_mismatch=true", headers=admin_headers).json()
    matched = client.get(f"{ASSIGNMENTS}?shift_mismatch=false", headers=admin_headers).json()
    assert mismatched["total"] == 1
    assert mismatched["items"][0]["shift_mismatch"] is True
    assert matched["total"] == 0


def test_move_warns_for_v2_bus_assignment(client, setup, admin_headers, register, db):
    from app.services import transport_timing_service

    person = register(shift=setup["shift2"])
    leg = TripLeg(event_id=setup["event"].id, code="CITY_TO_AIRPORT", name="Ra sân bay", direction="outbound")
    db.add(leg)
    db.flush()
    bus = Bus(event_id=setup["event"].id, trip_leg_id=leg.id, bus_code="XE-F3", capacity=10,
              departure_time="2026-10-15T17:00:00+00:00")
    db.add(bus)
    db.flush()
    db.add(RegistrationLeg(registration_id=person.id, trip_leg_id=leg.id, needs_bus=True,
                           bus_id=bus.id, assignment_mode="auto", assigned_at="2026-09-12T04:00:00+00:00"))
    assignment = FlightAssignment(registration_id=person.id, flight_id=setup["ca2"].id,
                                  direction="outbound", assignment_mode="auto",
                                  assigned_at="2026-09-12T04:00:00+00:00")
    db.add(assignment)
    db.commit()
    response = client.patch(f"{ASSIGNMENTS}/{assignment.id}", headers=admin_headers,
                            json={"flight_id": setup["ca1"].id, "reason": "Chuyển sớm"})
    assert response.status_code == 200, response.text
    warning = next(w for w in response.json()["warnings"] if w["type"] == "BUS_TIME_MISMATCH")
    assert warning["details"]["bus_id"] == bus.id
    assert response.json()["assignments"][0]["assignment_mode"] == "manual"
    assert bus.id in transport_timing_service.bus_timing_issues(db, event_id=setup["event"].id)
    mismatches = transport_timing_service.event_mismatches(db, event_id=setup["event"].id)
    assert len(mismatches) == 1
    assert mismatches[0]["registration_id"] == person.id


def test_two_admins_cannot_take_the_same_last_seat(engine, setup, register, make_user, db):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from app.core.exceptions import ConflictError
    from app.services.flight_allocation_service import bulk_move

    actor = make_user(email="btc-concurrent@company.vn", role=UserRole.ADMIN)
    people = [register() for _ in range(2)]
    setup["ca1"].capacity = 3  # 2 ghế giữ + 1 ghế trống.
    db.commit()
    event_id, actor_id, flight_id = setup["event"].id, actor.id, setup["ca1"].id
    registration_ids = [person.id for person in people]
    barrier = Barrier(2)

    def move(registration_id):
        with Session(engine) as session:
            event = session.get(Event, event_id)
            admin = session.get(User, actor_id)
            barrier.wait(timeout=10)
            try:
                bulk_move(session, event=event, registration_ids=[registration_id], flight_id=flight_id,
                          reason="BTC xếp chỗ cuối", actor=admin)
                return "committed"
            except ConflictError as error:
                return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(move, registration_ids))
    assert sorted(outcomes) == ["FLIGHT_CAPACITY_EXCEEDED", "committed"]
    db.expire_all()
    assert db.query(FlightAssignment).filter_by(flight_id=flight_id).count() == 1
    assert db.query(AuditLog).filter_by(action="flight_assignment.bulk_moved").count() == 1


def test_published_preview_with_notify_does_not_write(client, setup, admin_headers, register, db):
    register(shift=setup["shift1"])
    setup["event"].status = EventStatus.INFORMATION_PUBLISHED
    db.commit()
    response = client.post(f"{ALLOCATE}?notify=true", headers=admin_headers,
                           json={"direction": "outbound", "dry_run": True})
    assert response.status_code == 200, response.text
    assert response.json()["committed"] is False
    assert response.json()["summary"]["assigned"] == 1
    assert db.query(FlightAssignment).count() == 0
    assert db.query(EmailLog).count() == 0
    assert db.query(AuditLog).filter_by(action="flight.allocated").count() == 0
    assert db.query(AuditLog).filter_by(action="journey.notified").count() == 0


def test_preview_mapping_matches_commit_and_preserves_manual(client, setup, admin_headers, register, db):
    pinned = register(team=setup['team1'], shift=setup['shift1'])
    register(team=setup['team2'], shift=setup['shift2'])
    manual = FlightAssignment(registration_id=pinned.id, flight_id=setup['ca2'].id,
                              direction=FlightDirection.OUTBOUND, assignment_mode=AssignmentMode.MANUAL,
                              assigned_at='2026-09-12T05:00:00+00:00', note='Giữ cùng gia đình')
    db.add(manual)
    db.commit()
    manual_id = manual.id
    preview = allocate(client, admin_headers, seed=734)
    assert {'registration_id': pinned.id, 'flight_id': setup['ca2'].id, 'pinned': True} in preview['assignments']
    committed = allocate(client, admin_headers, dry_run=False, seed=preview['seed'],
                         expected_assignments=preview['assignments'])
    actual = {a.registration_id: a.flight_id for a in db.query(FlightAssignment).all()}
    assert actual == {a['registration_id']: a['flight_id'] for a in committed['assignments']}
    db.refresh(manual)
    assert manual.id == manual_id
    assert manual.note == 'Giữ cùng gia đình'
    assert manual.assignment_mode == AssignmentMode.MANUAL


def test_preview_stale_rolls_back_all_changes(client, setup, admin_headers, register, db):
    register(team=setup['team1'], shift=setup['shift1'])
    preview = allocate(client, admin_headers)
    register(team=setup['team2'], shift=setup['shift2'])
    response = client.post(ALLOCATE, headers=admin_headers, json={
        'direction': 'outbound', 'dry_run': False, 'seed': preview['seed'],
        'expected_assignments': preview['assignments'],
    })
    assert response.status_code == 409
    assert response.json()['error']['code'] == 'FLIGHT_PREVIEW_STALE'
    assert db.query(FlightAssignment).count() == 0
    assert db.query(AuditLog).filter_by(action='flight.allocated').count() == 0


def test_priority_is_per_run_not_event_setting(client, setup, admin_headers, register, db):
    setup['event'].settings = {'allocation.team_weight': 31, 'allocation.shift_weight': 7}
    db.commit()
    register(team=setup['team1'], shift=setup['shift1'])
    preview = allocate(client, admin_headers, priority='shift', seed=125)
    assert preview['params']['team_weight'] == 7
    assert preview['params']['shift_weight'] == 31
    result = allocate(client, admin_headers, priority='shift', seed=preview['seed'], dry_run=False,
                      expected_assignments=preview['assignments'])
    assert result['assignments'] == preview['assignments']
    db.refresh(setup['event'])
    assert setup['event'].settings == {'allocation.team_weight': 31, 'allocation.shift_weight': 7}
    assert allocate(client, admin_headers)['params']['team_weight'] == 31


def test_allocation_rejects_unknown_priority(client, setup, admin_headers):
    response = client.post(ALLOCATE, headers=admin_headers,
                           json={'direction': 'outbound', 'priority': 'unknown'})
    assert response.status_code == 422


def test_board_participants_pagination_excludes_cancelled_and_private_fields(client, setup, admin_headers, register, db):
    first = register(team=setup['team1'], shift=setup['shift1'], locked=True)
    register(cancelled=True)
    users = [User(email=f'board{i}@company.vn', full_name=f'Board {i}', password_hash='secret',
                  role=UserRole.EMPLOYEE) for i in range(200)]
    db.add_all(users)
    db.flush()
    db.add_all([Registration(event_id=setup['event'].id, user_id=u.id, is_participating=True,
                             status=RegistrationStatus.SUBMITTED) for u in users])
    db.commit()
    page1 = client.get(f'{ASSIGNMENTS}/participants?page_size=200', headers=admin_headers)
    page2 = client.get(f'{ASSIGNMENTS}/participants?page_size=200&page=2', headers=admin_headers)
    assert page1.status_code == page2.status_code == 200
    one, two = page1.json(), page2.json()
    assert one['total'] == two['total'] == 201
    assert len(one['items']) == 200 and len(two['items']) == 1
    assert {r['registration_id'] for r in one['items']}.isdisjoint({r['registration_id'] for r in two['items']})
    row = next(r for r in one['items'] if r['registration_id'] == first.id)
    assert row['shift_locked'] is True
    assert row['requested_shift_id'] == setup['shift1'].id
    assert row['team_name'] == setup['team1'].name
    assert 'id_card_number' not in row and 'password_hash' not in row and 'date_of_birth' not in row
    assert client.get(f'{ASSIGNMENTS}/participants?page_size=201', headers=admin_headers).status_code == 422


def test_board_participants_require_admin_and_selected_event(client, setup, admin_headers, register, db, make_user, auth_headers):
    register(team=setup['team1'])
    other = Event(code='OTHER-BOARD', name='Khác', start_date='2027-01-01', end_date='2027-01-02',
                  status=EventStatus.REGISTRATION_CLOSED)
    db.add(other)
    db.commit()
    result = client.get(f'{ASSIGNMENTS}/participants', headers={**admin_headers, 'X-Event-Id': str(other.id)})
    assert result.status_code == 200
    assert result.json()['total'] == 0
    make_user(email='employee-board@company.vn', password='MatKhau123')
    assert client.get(f'{ASSIGNMENTS}/participants', headers=auth_headers('employee-board@company.vn')).status_code == 403
