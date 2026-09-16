"""Kiểm thử Gala Dinner: bốc thăm, lượt chọn, giữ/xác nhận ghế, quyền riêng tư (docs/04 §8, docs/03 §12)."""

import asyncio
import json
import threading

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from app.core.exceptions import AppError
from app.models.audit import AuditLog
from app.models.enums import DrawStatus, EventStatus, RegistrationStatus, UserRole
from app.models.event import Event, EventSetting
from app.models.gala import GalaDrawOrder, GalaLayout, GalaSeat, GalaSeatAssignment, GalaSeatHold, GalaTable
from app.models.org import Team
from app.models.registration import Registration
from app.models.user import User
from app.services import cancellation_service, gala_service, gala_stream

URL = "/api/v1/gala"
NOW = "2026-09-12T04:00:00+00:00"
PAST = "2020-01-01T00:00:00+00:00"


@pytest.fixture
def world(db: Session, make_user) -> dict:
    """Alpha: 2 người đi + 1 người không đi. Beta: 2 người đi. 1 người đi chưa có team. Sơ đồ 2 bàn × 4 ghế."""
    event = Event(
        code="TB2026", name="Team Building 2026", start_date="2026-10-15", end_date="2026-10-17",
        status=EventStatus.INFORMATION_PUBLISHED, terms_version="v1", is_active=True,
    )
    alpha = Team(code="ALPHA", name="Team Alpha", color="#4f46e5")
    beta = Team(code="BETA", name="Team Beta", color="#059669")
    empty = Team(code="EMPTY", name="Team Trống")
    db.add_all([event, alpha, beta, empty])
    db.flush()

    make_user(email="btc@company.vn", role=UserRole.ADMIN, full_name="Ban Tổ Chức")
    users = {
        "la": make_user(email="la@company.vn", role=UserRole.TEAM_LEADER, full_name="Trưởng Alpha", team_id=alpha.id),
        "a2": make_user(email="a2@company.vn", full_name="Thành Viên Alpha", team_id=alpha.id),
        "a3": make_user(email="a3@company.vn", full_name="Không Đi Alpha", team_id=alpha.id),
        "lb": make_user(email="lb@company.vn", role=UserRole.TEAM_LEADER, full_name="Trưởng Beta", team_id=beta.id),
        "b2": make_user(email="b2@company.vn", full_name="Thành Viên Beta", team_id=beta.id),
        "loner": make_user(email="loner@company.vn", full_name="Chưa Có Team"),
    }
    alpha.leader_user_id = users["la"].id
    beta.leader_user_id = users["lb"].id

    registrations = {}
    for key, user in users.items():
        registration = Registration(
            event_id=event.id, user_id=user.id, is_participating=key != "a3",
            status=RegistrationStatus.SUBMITTED, submitted_at=NOW,
        )
        db.add(registration)
        registrations[key] = registration

    layout = GalaLayout(
        event_id=event.id, name="Gala Dinner", venue="Sảnh Pearl", grid_width=12, grid_height=10,
        turn_seconds=300, hold_seconds=120,
    )
    db.add(layout)
    db.flush()
    for index, code in enumerate(("B01", "B02")):
        table = GalaTable(layout_id=layout.id, table_code=code, seat_count=4, pos_x=index * 3, pos_y=0)
        table.seats = [GalaSeat(seat_number=number) for number in range(1, 5)]
        db.add(table)
    db.commit()
    return {
        "event": event.id,
        "layout": layout.id,
        "alpha": alpha.id,
        "beta": beta.id,
        "users": {key: user.id for key, user in users.items()},
        "registrations": {key: registration.id for key, registration in registrations.items()},
    }


@pytest.fixture
def login(world, auth_headers):
    cache: dict[str, dict] = {}

    def _login(key: str) -> dict[str, str]:
        email = "btc@company.vn" if key == "admin" else f"{key}@company.vn"
        if key not in cache:
            cache[key] = auth_headers(email)
        return cache[key]

    return _login


def view(client: TestClient, headers) -> dict:
    response = client.get(f"{URL}/layout", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def seats_of(data: dict, table_code: str) -> list[int]:
    return [seat["id"] for table in data["tables"] if table["table_code"] == table_code for seat in table["seats"]]


def seat(data: dict, seat_id: int) -> dict:
    return next(item for table in data["tables"] for item in table["seats"] if item["id"] == seat_id)


def open_selection(client: TestClient, login, world, seed: int = 7) -> tuple[str, str]:
    """Bốc thăm + mở chọn ghế. Trả (trưởng nhóm tới lượt trước, trưởng nhóm tới lượt sau)."""
    drawn = client.post(f"{URL}/draw", headers=login("admin"), json={"seed": seed})
    assert drawn.status_code == 200, drawn.text
    opened = client.post(f"{URL}/turn/next", headers=login("admin"), json={})
    assert opened.status_code == 200, opened.text
    first = opened.json()["draw"]["active_team_id"]
    return ("la", "lb") if first == world["alpha"] else ("lb", "la")


def error_code(response) -> str:
    return response.json()["error"]["code"]


# --- Xem sơ đồ & bốc thăm ---


def test_layout_is_readable_by_everyone_but_seed_is_organizer_only(client: TestClient, login):
    employee = view(client, login("a2"))
    assert employee["totals"] == {"seats": 8, "available": 8, "held": 0, "taken": 0, "unavailable": 0}
    assert employee["my_team"]["team_name"] == "Team Alpha"
    assert employee["my_team"]["is_leader"] is False
    assert employee["can_manage"] is False

    client.post(f"{URL}/draw", headers=login("admin"), json={"seed": 99})
    assert view(client, login("a2"))["layout"]["draw_seed"] is None
    assert view(client, login("admin"))["layout"]["draw_seed"] == 99


def test_draw_sets_quota_per_participating_members_and_is_reproducible(
    client: TestClient, login, world, db: Session
):
    first = client.post(f"{URL}/draw", headers=login("admin"), json={"seed": 42}).json()["draw"]
    quotas = {order["team_id"]: order["quota"] for order in first["orders"]}
    # Alpha có 3 thành viên nhưng một người không đi; team không có ai tham gia không được bốc.
    assert quotas == {world["alpha"]: 2, world["beta"]: 2}
    assert first["unteamed_participants"] == 1
    assert first["total_seats"] == 8
    assert first["selection_status"] == "drawing"

    again = client.post(f"{URL}/draw", headers=login("admin"), json={"seed": 42}).json()["draw"]
    assert [order["team_id"] for order in again["orders"]] == [order["team_id"] for order in first["orders"]]
    assert db.query(AuditLog).filter(AuditLog.action == "gala.drawn").count() == 2

    assert client.post(f"{URL}/draw", headers=login("la"), json={}).status_code == 403


def test_selection_opens_only_after_publishing(client: TestClient, login, world, db: Session):
    db.execute(update(Event).where(Event.id == world["event"]).values(status=EventStatus.ALLOCATION_PROCESSING))
    db.commit()
    client.post(f"{URL}/draw", headers=login("admin"), json={"seed": 1})

    response = client.post(f"{URL}/turn/next", headers=login("admin"), json={})
    assert response.status_code == 409
    assert error_code(response) == "NOT_PUBLISHED"


# --- Giữ & xác nhận ---


def test_hold_and_confirm_in_turn_then_turn_passes(client: TestClient, login, world, db: Session):
    first, second = open_selection(client, login, world)
    data = view(client, login(first))
    wanted = seats_of(data, "B01")[:2]

    held = client.post(f"{URL}/seats/hold", headers=login(first), json={"seat_ids": wanted})
    assert held.status_code == 200, held.text
    assert held.json()["remaining"] == 0

    # Không tới lượt, hoặc không phải trưởng nhóm: không giữ được.
    other = client.post(f"{URL}/seats/hold", headers=login(second), json={"seat_ids": [seats_of(data, "B02")[0]]})
    assert other.status_code == 409 and error_code(other) == "NOT_YOUR_TURN"
    member = "a2" if first == "la" else "b2"
    assert client.post(f"{URL}/seats/hold", headers=login(member), json={"seat_ids": wanted}).status_code == 403

    # Người cùng team thấy "team mình giữ", team khác thấy "team khác giữ".
    assert seat(view(client, login(member)), wanted[0])["state"] == "held_by_me"
    assert seat(view(client, login(second)), wanted[0])["state"] == "held_by_other"

    confirmed = client.post(f"{URL}/seats/confirm", headers=login(first))
    assert confirmed.status_code == 200, confirmed.text
    body = confirmed.json()
    assert body["confirmed_total"] == 2 and body["turn_finished"] is True

    after = view(client, login(second))
    assert after["draw"]["active_team_id"] == body["next_team_id"]
    assert after["my_team"]["is_my_turn"] is True
    taken = seat(after, wanted[0])
    assert taken["state"] == "taken" and taken["team_name"] in {"Team Alpha", "Team Beta"}
    assert db.query(GalaSeatAssignment).count() == 2
    assert db.query(GalaSeatHold).count() == 0
    assert db.query(AuditLog).filter(AuditLog.action == "gala.seats_confirmed").count() == 1


def test_quota_taken_unavailable_and_unknown_seats_are_rejected(client: TestClient, login, world):
    first, _ = open_selection(client, login, world)
    headers = login(first)
    data = view(client, headers)
    b01, b02 = seats_of(data, "B01"), seats_of(data, "B02")

    client.post(f"{URL}/seats/hold", headers=headers, json={"seat_ids": [b01[0]]})
    client.post(f"{URL}/seats/confirm", headers=headers)  # 1/2, vẫn còn lượt

    over = client.post(f"{URL}/seats/hold", headers=headers, json={"seat_ids": b01[1:3]})
    assert over.status_code == 409 and error_code(over) == "GALA_QUOTA_EXCEEDED"

    taken = client.post(f"{URL}/seats/hold", headers=headers, json={"seat_ids": [b01[0]]})
    assert error_code(taken) == "SEAT_TAKEN"

    locked = client.patch(
        f"{URL}/seats/{b02[0]}", headers=login("admin"), json={"is_available": False, "reason": "Cột che sân khấu"}
    )
    assert locked.status_code == 200, locked.text
    assert seat(locked.json(), b02[0])["state"] == "unavailable"
    assert error_code(client.post(f"{URL}/seats/hold", headers=headers, json={"seat_ids": [b02[0]]})) == "SEAT_UNAVAILABLE"

    unknown = client.post(f"{URL}/seats/hold", headers=headers, json={"seat_ids": [999_999]})
    assert unknown.status_code == 404


def test_release_frees_seats(client: TestClient, login, world):
    first, _ = open_selection(client, login, world)
    headers = login(first)
    wanted = seats_of(view(client, headers), "B02")[:2]
    client.post(f"{URL}/seats/hold", headers=headers, json={"seat_ids": wanted})

    released = client.delete(f"{URL}/seats/hold", headers=headers, params={"seat_ids": [wanted[0]]})
    assert released.json() == {"released": 1}
    data = view(client, headers)
    assert [seat(data, seat_id)["state"] for seat_id in wanted] == ["available", "held_by_me"]


def test_expired_hold_is_cleared_lazily(client: TestClient, login, world, db: Session):
    first, _ = open_selection(client, login, world)
    headers = login(first)
    wanted = seats_of(view(client, headers), "B01")[:1]
    client.post(f"{URL}/seats/hold", headers=headers, json={"seat_ids": wanted})

    db.execute(update(GalaSeatHold).values(expires_at=PAST))
    db.commit()

    assert seat(view(client, headers), wanted[0])["state"] == "available"
    assert db.query(GalaSeatHold).count() == 0
    response = client.post(f"{URL}/seats/confirm", headers=headers)
    assert response.status_code == 409 and error_code(response) == "NO_ACTIVE_HOLDS"


def test_turn_times_out_and_passes_to_next_team(client: TestClient, login, world, db: Session):
    first, second = open_selection(client, login, world)
    headers = login(first)
    client.post(f"{URL}/seats/hold", headers=headers, json={"seat_ids": seats_of(view(client, headers), "B01")[:1]})

    db.execute(update(GalaDrawOrder).where(GalaDrawOrder.status == DrawStatus.ACTIVE).values(turn_ends_at=PAST))
    db.commit()

    data = view(client, login(second))
    assert data["my_team"]["is_my_turn"] is True
    assert [order["status"] for order in data["draw"]["orders"]] == ["done", "active"]
    assert data["totals"]["held"] == 0  # ghế đang giữ của lượt cũ được nhả
    audit = db.query(AuditLog).filter(AuditLog.action == "gala.turn_ended").one()
    assert json.loads(audit.after_data)["trigger"] == "timeout"


def test_admin_skip_then_finalize_locks_everything(client: TestClient, login, world):
    first, second = open_selection(client, login, world)
    admin = login("admin")

    skipped = client.post(f"{URL}/turn/next", headers=admin, json={"skip": True}).json()
    assert [order["status"] for order in skipped["draw"]["orders"]] == ["skipped", "active"]

    finished = client.post(f"{URL}/turn/next", headers=admin, json={}).json()
    assert finished["layout"]["selection_status"] == "finalized"

    seat_id = seats_of(finished, "B01")[0]
    closed = client.post(f"{URL}/seats/hold", headers=login(second), json={"seat_ids": [seat_id]})
    assert error_code(closed) == "GALA_SELECTION_CLOSED"
    assert error_code(client.post(f"{URL}/turn/next", headers=admin, json={})) == "GALA_FINALIZED"
    assert error_code(client.post(f"{URL}/draw", headers=admin, json={})) == "GALA_DRAW_LOCKED"


def test_parallel_holds_cannot_exceed_quota(client: TestClient, login, world, engine):
    """Hai tab của cùng trưởng nhóm giữ 2 ghế khác nhau cùng lúc: quota 2 thì chỉ một tab thành công."""
    first, _ = open_selection(client, login, world)
    data = view(client, login(first))
    batches = [seats_of(data, "B01")[:2], seats_of(data, "B02")[:2]]
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    barrier = threading.Barrier(2)
    outcomes: list[str] = []

    def attempt(seat_ids: list[int]) -> None:
        with factory() as session:
            event = session.get(Event, world["event"])
            user = session.get(User, world["users"][first])
            barrier.wait()
            try:
                gala_service.hold_seats(session, event=event, user=user, seat_ids=seat_ids)
                outcomes.append("ok")
            except AppError as exc:
                outcomes.append(exc.code)

    threads = [threading.Thread(target=attempt, args=(batch,)) for batch in batches]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert sorted(outcomes) == ["GALA_QUOTA_EXCEEDED", "ok"]
    with factory() as session:
        assert session.scalar(select(GalaSeatHold.id).limit(3)) is not None
        assert len(session.scalars(select(GalaSeatHold)).all()) == 2


# --- Gán người & quyền riêng tư ---


def _confirm_two(client: TestClient, login, world) -> tuple[str, list[int]]:
    """Team tới lượt trước xác nhận 2 ghế đầu bàn B01."""
    first, _ = open_selection(client, login, world)
    seat_ids = seats_of(view(client, login(first)), "B01")[:2]
    client.post(f"{URL}/seats/hold", headers=login(first), json={"seat_ids": seat_ids})
    assert client.post(f"{URL}/seats/confirm", headers=login(first)).status_code == 200
    return first, seat_ids


def test_leader_assigns_and_moves_members_names_hidden_from_other_teams(client: TestClient, login, world):
    leader, seat_ids = _confirm_two(client, login, world)
    member, outsider, other_leader = ("a2", "b2", "lb") if leader == "la" else ("b2", "a2", "la")
    registrations = world["registrations"]

    placed = client.post(
        f"{URL}/seats/assign-member", headers=login(leader),
        json={"seat_id": seat_ids[0], "registration_id": registrations[member]},
    )
    assert placed.status_code == 200, placed.text

    moved = client.post(
        f"{URL}/seats/assign-member", headers=login(leader),
        json={"seat_id": seat_ids[1], "registration_id": registrations[member]},
    ).json()
    assert moved["previous_seat_id"] == seat_ids[0]

    wrong_team = client.post(
        f"{URL}/seats/assign-member", headers=login(leader),
        json={"seat_id": seat_ids[0], "registration_id": registrations[outsider]},
    )
    assert wrong_team.status_code == 400 and error_code(wrong_team) == "MEMBER_NOT_IN_TEAM"

    not_mine = client.post(
        f"{URL}/seats/assign-member", headers=login(other_leader),
        json={"seat_id": seat_ids[0], "registration_id": None},
    )
    assert not_mine.status_code == 403

    # Tên người ngồi: team mình và BTC thấy, team khác chỉ thấy tên team.
    assert seat(view(client, login(member)), seat_ids[1])["occupant_name"].startswith("Thành Viên")
    assert seat(view(client, login("admin")), seat_ids[1])["occupant_name"].startswith("Thành Viên")
    hidden = seat(view(client, login(outsider)), seat_ids[1])
    assert hidden["occupant_name"] is None and hidden["registration_id"] is None

    journey = client.get("/api/v1/journey/me", headers=login(member)).json()
    assert journey["gala"]["table_code"] == "B01"
    assert journey["gala"]["seat_number"] == 2


def test_non_participant_and_unconfirmed_seat_cannot_be_assigned(client: TestClient, login, world):
    leader, seat_ids = _confirm_two(client, login, world)
    data = view(client, login(leader))
    free_seat = seats_of(data, "B02")[0]

    unconfirmed = client.post(
        f"{URL}/seats/assign-member", headers=login(leader),
        json={"seat_id": free_seat, "registration_id": world["registrations"][leader]},
    )
    assert unconfirmed.status_code == 409 and error_code(unconfirmed) == "SEAT_NOT_CONFIRMED"

    if leader == "la":
        absent = client.post(
            f"{URL}/seats/assign-member", headers=login(leader),
            json={"seat_id": seat_ids[0], "registration_id": world["registrations"]["a3"]},
        )
        assert absent.status_code == 404


def test_team_members_scope(client: TestClient, login, world):
    leader, _ = _confirm_two(client, login, world)
    members = client.get(f"{URL}/team-members", headers=login(leader)).json()
    assert len(members) == 2 and all(item["seat_id"] is None for item in members)

    assert client.get(f"{URL}/team-members", headers=login("a2")).status_code == 403
    assert error_code(client.get(f"{URL}/team-members", headers=login("admin"))) == "TEAM_REQUIRED"
    assert len(client.get(f"{URL}/team-members", headers=login("admin"), params={"team_id": world["beta"]}).json()) == 2


# --- BTC ---


def test_admin_forces_clears_and_locks_seats_with_reason(client: TestClient, login, world, db: Session):
    admin = login("admin")
    seat_id = seats_of(view(client, admin), "B02")[3]

    missing_reason = client.patch(f"{URL}/seats/{seat_id}", headers=admin, json={"team_id": world["beta"]})
    assert missing_reason.status_code == 422

    forced = client.patch(
        f"{URL}/seats/{seat_id}", headers=admin,
        json={"team_id": world["beta"], "registration_id": world["registrations"]["b2"], "reason": "Ghế gần lối đi cho người đau chân"},
    )
    assert forced.status_code == 200, forced.text
    assert seat(forced.json(), seat_id)["occupant_name"] == "Thành Viên Beta"

    locked = client.patch(f"{URL}/seats/{seat_id}", headers=admin, json={"is_available": False, "reason": "Khoá"})
    assert locked.status_code == 409 and error_code(locked) == "SEAT_TAKEN"

    cleared = client.patch(f"{URL}/seats/{seat_id}", headers=admin, json={"team_id": None, "reason": "Trả lại ghế"})
    assert seat(cleared.json(), seat_id)["state"] == "available"

    audits = db.query(AuditLog).filter(AuditLog.action == "gala.seat_updated").order_by(AuditLog.id).all()
    assert [row.reason for row in audits] == ["Ghế gần lối đi cho người đau chân", "Trả lại ghế"]
    assert client.patch(f"{URL}/seats/{seat_id}", headers=login("la"), json={"team_id": None, "reason": "abc"}).status_code == 403


def test_table_management_protects_confirmed_seats(client: TestClient, login, world):
    admin = login("admin")
    _confirm_two(client, login, world)
    b01 = next(table for table in view(client, admin)["tables"] if table["table_code"] == "B01")

    duplicate = client.post(f"{URL}/tables", headers=admin, json={"table_code": "b01", "seat_count": 6, "pos_x": 6, "pos_y": 0})
    assert error_code(duplicate) == "TABLE_CODE_TAKEN"
    outside = client.post(f"{URL}/tables", headers=admin, json={"table_code": "B03", "seat_count": 6, "pos_x": 12, "pos_y": 0})
    assert error_code(outside) == "TABLE_OUT_OF_GRID"
    stacked = client.post(f"{URL}/tables", headers=admin, json={"table_code": "B03", "seat_count": 6, "pos_x": 0, "pos_y": 0})
    assert error_code(stacked) == "TABLE_POSITION_TAKEN"

    created = client.post(f"{URL}/tables", headers=admin, json={"table_code": "B03", "seat_count": 6, "pos_x": 6, "pos_y": 0, "is_vip": True})
    assert created.status_code == 201
    b03 = next(table for table in created.json()["tables"] if table["table_code"] == "B03")
    assert [item["seat_number"] for item in b03["seats"]] == [1, 2, 3, 4, 5, 6]

    assert error_code(client.patch(f"{URL}/tables/{b01['id']}", headers=admin, json={"seat_count": 1})) == "SEATS_IN_USE"
    assert error_code(client.patch(f"{URL}/tables/{b01['id']}", headers=admin, json={"is_available": False})) == "TABLE_HAS_ASSIGNMENTS"
    assert error_code(client.delete(f"{URL}/tables/{b01['id']}", headers=admin)) == "TABLE_HAS_ASSIGNMENTS"

    grown = client.patch(f"{URL}/tables/{b01['id']}", headers=admin, json={"seat_count": 6}).json()
    assert next(table for table in grown["tables"] if table["id"] == b01["id"])["seat_count"] == 6

    assert error_code(client.patch(f"{URL}/layout", headers=admin, json={"grid_width": 6})) == "TABLE_OUT_OF_GRID"
    assert client.delete(f"{URL}/tables/{b03['id']}", headers=admin).status_code == 200


def test_layout_creation_uses_event_settings(client: TestClient, login, world, db: Session):
    other = Event(
        code="TB2027", name="Team Building 2027", start_date="2027-10-15", end_date="2027-10-17",
        status=EventStatus.DRAFT, terms_version="v1", is_active=False,
    )
    db.add(other)
    db.flush()
    db.execute(update(Event).where(Event.id == world["event"]).values(is_active=False))
    other.is_active = True
    db.add(EventSetting(event_id=other.id, key="gala.hold_seconds", value="90", description=""))
    db.commit()

    admin = login("admin")
    missing = client.get(f"{URL}/layout", headers=admin)
    assert missing.status_code == 404 and error_code(missing) == "GALA_NOT_CONFIGURED"

    created = client.post(f"{URL}/layout", headers=admin, json={"name": "Gala 2027"})
    assert created.status_code == 201, created.text
    assert created.json()["layout"]["hold_seconds"] == 90
    assert created.json()["layout"]["turn_seconds"] == 300
    assert error_code(client.post(f"{URL}/layout", headers=admin, json={"name": "Lần hai"})) == "GALA_LAYOUT_EXISTS"


# --- SSE ---


def test_stream_requires_login(client: TestClient, world):
    assert client.get(f"{URL}/stream").status_code == 401


def test_change_signature_follows_seat_changes(client: TestClient, login, world, db: Session):
    before = gala_service.change_signature(db, event_id=world["event"], jobs=[])
    assert gala_service.change_signature(db, event_id=world["event"], jobs=[]) == before

    first, _ = open_selection(client, login, world)
    opened = gala_service.change_signature(db, event_id=world["event"], jobs=[])
    assert opened != before

    client.post(f"{URL}/seats/hold", headers=login(first), json={"seat_ids": seats_of(view(client, login(first)), "B01")[:1]})
    assert gala_service.change_signature(db, event_id=world["event"], jobs=[]) != opened


def _collect(**kwargs) -> list[str]:
    async def run() -> list[str]:
        return [chunk async for chunk in gala_stream.change_events(**kwargs)]

    return asyncio.run(run())


def test_stream_emits_changes_and_heartbeats():
    versions = iter(["v1", "v1", "v1", "v2"])
    clock = {"now": 0.0, "loops": 0}

    async def poll() -> str:
        return next(versions)

    async def disconnected() -> bool:
        return clock["loops"] >= 4

    async def sleep(_seconds: float) -> None:
        clock["now"] += 10
        clock["loops"] += 1

    chunks = _collect(
        poll=poll, is_disconnected=disconnected, interval=1, heartbeat=15, sleep=sleep, clock=lambda: clock["now"]
    )
    assert chunks == [
        "retry: 3000\n\n",
        'event: change\ndata: {"version": "v1"}\n\n',
        ": ping\n\n",
        'event: change\ndata: {"version": "v2"}\n\n',
    ]


def test_stream_survives_a_failed_poll():
    calls = {"n": 0}

    async def poll() -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("database is locked")
        return "v1"

    async def disconnected() -> bool:
        return calls["n"] >= 2

    async def sleep(_seconds: float) -> None:
        return None

    chunks = _collect(poll=poll, is_disconnected=disconnected, sleep=sleep, clock=lambda: 0.0)
    assert chunks[-1] == 'event: change\ndata: {"version": "v1"}\n\n'


# --- Quota theo người tham gia thật (huỷ / đăng ký lại) ---


def test_quota_follows_cancellation_and_re_registration(client: TestClient, login, world, db: Session):
    """Người huỷ phải làm quota tụt xuống, đăng ký lại phải làm quota tăng trở lại.

    `GalaDrawOrder.quota` là ảnh chụp lúc bốc thăm và không bao giờ tự đổi. Đọc thẳng nó thì team
    có người huỷ bị báo "chưa đủ ghế" vĩnh viễn — ghế đã được trả về sơ đồ nên số ghế không bao giờ
    đuổi kịp con số cũ, và kỳ không chuyển sang `event_started` được nữa.
    """
    first, _second = open_selection(client, login, world)
    alpha_seats = seats_of(view(client, login(first)), "B01")[:2]
    assert client.post(f"{URL}/seats/hold", headers=login(first), json={"seat_ids": alpha_seats}).status_code == 200
    assert client.post(f"{URL}/seats/confirm", headers=login(first)).status_code == 200

    leader_team = world["alpha"] if first == "la" else world["beta"]
    member = "a2" if first == "la" else "b2"

    # Xếp người vào ghế: huỷ mới có ghế để trả về sơ đồ (ghế trống của team thì vẫn là của team).
    for key, seat_id in ((first, alpha_seats[0]), (member, alpha_seats[1])):
        placed = client.post(
            f"{URL}/seats/assign-member", headers=login(first),
            json={"seat_id": seat_id, "registration_id": world["registrations"][key]},
        )
        assert placed.status_code == 200, placed.text

    def order_of(team_id: int) -> dict:
        return next(item for item in view(client, login("admin"))["draw"]["orders"] if item["team_id"] == team_id)

    stored = db.scalar(
        select(GalaDrawOrder).where(
            GalaDrawOrder.layout_id == world["layout"], GalaDrawOrder.team_id == leader_team
        )
    )
    assert stored.quota == 2
    assert order_of(leader_team)["quota"] == 2 and order_of(leader_team)["confirmed"] == 2

    # BTC huỷ thay một thành viên: ghế được trả về sơ đồ, quota phải tụt theo.
    event = db.get(Event, world["event"])
    actor = db.scalar(select(User).where(User.email == "btc@company.vn"))
    cancellation_service.admin_cancel(
        db, event=event, actor=actor, registration_id=world["registrations"][member],
        reason="Có việc gia đình", penalty_applied=False,
    )
    db.commit()

    after = order_of(leader_team)
    db.refresh(stored)
    assert stored.quota == 2, "ảnh chụp lúc bốc thăm giữ nguyên — nó chỉ để tra lại"
    assert after["quota"] == 1, "quota phải theo số người còn tham gia, không phải ảnh chụp lúc bốc thăm"
    assert after["confirmed"] == 1 and after["remaining"] == 0
    db.expire_all()
    gaps = gala_service.seating_gaps(db, event_id=world["event"])
    assert leader_team not in [item["team_id"] for item in gaps["teams_missing"]], (
        "team đã trả ghế của người huỷ về sơ đồ thì không còn thiếu ghế nữa"
    )

    # Đăng ký lại: quota tăng lại và team hiện ra là đang thiếu đúng 1 ghế để BTC xếp bù.
    registration = db.get(Registration, world["registrations"][member])
    registration.status = RegistrationStatus.SUBMITTED
    registration.cancelled_at = None
    db.commit()

    back = order_of(leader_team)
    assert back["quota"] == 2 and back["confirmed"] == 1 and back["remaining"] == 1
    db.expire_all()
    gaps = gala_service.seating_gaps(db, event_id=world["event"])
    mine = next(item for item in gaps["teams_missing"] if item["team_id"] == leader_team)
    assert (mine["seats"], mine["participants"]) == (1, 2), "BTC phải thấy team thiếu đúng 1 ghế để xếp bù"


# --- Người chưa thuộc team nào ---


def test_admin_seats_participant_without_team_on_a_free_seat(client: TestClient, login, world, db: Session):
    """Người không thuộc team nào phải xếp ghế được, không thì kỳ không bao giờ bắt đầu.

    Họ không được bốc thăm nên không team nào chọn ghế hộ. Ghế của họ ghi `team_id = NULL` —
    mượn tạm team khác thì team đó bị đếm dôi ra một ghế và sơ đồ hiện sai chủ ghế.
    """
    admin = login("admin")
    loner = world["registrations"]["loner"]

    unseated = client.get(f"{URL}/unseated", headers=admin)
    assert unseated.status_code == 200, unseated.text
    # Người chưa có team đứng đầu danh sách.
    assert unseated.json()[0]["full_name"] == "Chưa Có Team"
    assert unseated.json()[0]["team_id"] is None and unseated.json()[0]["team_name"] is None
    assert loner in [row["registration_id"] for row in unseated.json()]

    free = seats_of(view(client, admin), "B02")[0]
    placed = client.post(
        f"{URL}/seats/assign-member", headers=admin, json={"seat_id": free, "registration_id": loner}
    )
    assert placed.status_code == 200, placed.text

    taken = seat(view(client, admin), free)
    assert taken["state"] == "taken" and taken["team_id"] is None and taken["team_name"] is None
    assert taken["occupant_name"] == "Chưa Có Team"

    # Đã có ghế thì rời khỏi danh sách, và `unseated` của kỳ giảm theo.
    assert loner not in [row["registration_id"] for row in client.get(f"{URL}/unseated", headers=admin).json()]
    gaps = gala_service.seating_gaps(db, event_id=world["event"])
    assert loner not in db.scalars(
        select(GalaSeatAssignment.registration_id).where(GalaSeatAssignment.registration_id.is_(None))
    )
    assert gaps["unseated"] == gaps["participants"] - gaps["seated"]

    # Gỡ người khỏi ghế: ghế không thuộc team nào thì trả hẳn về sơ đồ, không thành ghế mồ côi.
    removed = client.post(
        f"{URL}/seats/assign-member", headers=admin, json={"seat_id": free, "registration_id": None}
    )
    assert removed.status_code == 200, removed.text
    assert seat(view(client, admin), free)["state"] == "available"


def test_unseated_list_is_organizer_only_and_leader_still_needs_a_confirmed_seat(
    client: TestClient, login, world
):
    assert client.get(f"{URL}/unseated", headers=login("la")).status_code == 403
    assert client.get(f"{URL}/unseated", headers=login("a2")).status_code == 403

    # Trưởng nhóm vẫn không được biến ghế trống thành ghế của team bằng đường gán người.
    open_selection(client, login, world)
    free = seats_of(view(client, login("la")), "B02")[0]
    denied = client.post(
        f"{URL}/seats/assign-member", headers=login("la"),
        json={"seat_id": free, "registration_id": world["registrations"]["a2"]},
    )
    assert denied.status_code == 409 and error_code(denied) == "SEAT_NOT_CONFIRMED"


def test_seat_without_team_hides_occupant_name_from_other_employees(client: TestClient, login, world):
    admin = login("admin")
    free = seats_of(view(client, admin), "B02")[0]
    client.post(
        f"{URL}/seats/assign-member", headers=admin,
        json={"seat_id": free, "registration_id": world["registrations"]["loner"]},
    )
    # `my_team_id` của người chưa có team cũng là None — không được vì thế mà đọc được tên.
    # Nhưng ghế của chính mình thì vẫn phải thấy.
    assert seat(view(client, login("loner")), free)["occupant_name"] == "Chưa Có Team"
    hidden = seat(view(client, login("a2")), free)
    assert hidden["occupant_name"] is None and hidden["registration_id"] is None
