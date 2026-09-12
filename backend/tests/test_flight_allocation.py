"""Kiểm thử API phân bổ chuyến bay và điều chỉnh thủ công (docs/04 §5, docs/05 §5)."""

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
        )
    )
    db.commit()

    allocate(client, admin_headers, dry_run=False)

    kept = db.query(FlightAssignment).filter_by(registration_id=pinned.id).one()
    assert kept.flight_id == setup["ca2"].id
    assert kept.assignment_mode == AssignmentMode.MANUAL
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
    register(team=setup["team2"], shift=setup["shift2"], can_fly=False)
    allocate(client, admin_headers, dry_run=False)

    body = client.get(ASSIGNMENTS, headers=admin_headers).json()
    assert body["total"] == 5
    assert body["items"][0]["flight_code"] in {"VN1234", "VN1250"}
    assert "id_card_number" not in str(body)

    by_flight = client.get(
        f"{ASSIGNMENTS}?flight_id={setup['ca1'].id}", headers=admin_headers
    ).json()
    assert all(row["flight_id"] == setup["ca1"].id for row in by_flight["items"])

    by_team = client.get(
        f"{ASSIGNMENTS}?team_id={setup['team2'].id}", headers=admin_headers
    ).json()
    assert by_team["total"] == 1

    missing = client.get(f"{ASSIGNMENTS}?missing_documents=true", headers=admin_headers).json()
    assert missing["total"] == 1
    assert missing["items"][0]["has_flight_documents"] is False


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
