"""Gala: mở lại chọn ghế, email báo lượt, chặn bắt đầu sự kiện khi chưa xếp ghế, xếp ngẫu nhiên thành viên."""

# ruff: noqa: F811 -- pytest resolves imported fixtures by their parameter names.

from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.enums import DrawStatus
from app.models.gala import GalaDrawOrder
from app.models.notification import EmailLog
from tests.test_gala import (  # noqa: F401
    PAST,
    URL,
    error_code,
    login,
    open_selection,
    seats_of,
    view,
    world,
)

AUTO = f"{URL}/seats/auto-assign"


def team_of(world, leader: str) -> int:
    return world["alpha"] if leader == "la" else world["beta"]


def confirm(client: TestClient, login, leader: str, table: str, count: int = 2) -> dict:
    seat_ids = seats_of(view(client, login(leader)), table)[:count]
    held = client.post(f"{URL}/seats/hold", headers=login(leader), json={"seat_ids": seat_ids})
    assert held.status_code == 200, held.text
    confirmed = client.post(f"{URL}/seats/confirm", headers=login(leader))
    assert confirmed.status_code == 200, confirmed.text
    return confirmed.json()


def turn_emails(db: Session) -> list[EmailLog]:
    return db.query(EmailLog).filter(EmailLog.template == "gala_turn_started").order_by(EmailLog.id).all()


# --- Thông báo tới lượt ---


def test_leaders_are_emailed_when_their_turn_starts(client: TestClient, login, world, db: Session):
    first, second = open_selection(client, login, world)
    orders = view(client, login("admin"))["draw"]["orders"]
    assert {order["leader_name"] for order in orders} == {"Trưởng Alpha", "Trưởng Beta"}

    # Lượt đầu hết giờ: được dọn lazy khi có người mở sơ đồ → lượt kế bắt đầu → email.
    db.execute(update(GalaDrawOrder).where(GalaDrawOrder.status == DrawStatus.ACTIVE).values(turn_ends_at=PAST))
    db.commit()
    view(client, login("a2"))

    emails = turn_emails(db)
    assert [row.to_email for row in emails] == [f"{first}@company.vn", f"{second}@company.vn"]
    assert "chọn ghế Gala" in emails[0].subject
    assert "Hết lượt lúc" in emails[0].body_preview
    assert emails[1].related_type == "gala_draw_order"


def test_my_turn_banner_data(client: TestClient, login, world):
    before = client.get(f"{URL}/my-turn", headers=login("la")).json()
    assert before["is_leader"] is True
    assert before["selection_status"] == "closed" and before["is_my_turn"] is False

    first, second = open_selection(client, login, world)
    mine = client.get(f"{URL}/my-turn", headers=login(first)).json()
    assert mine["is_my_turn"] is True and mine["turn_ends_at"] and mine["remaining"] == 2

    waiting = client.get(f"{URL}/my-turn", headers=login(second)).json()
    assert waiting["is_my_turn"] is False and waiting["teams_ahead"] == 1
    assert waiting["active_team_name"] in {"Team Alpha", "Team Beta"}

    employee = client.get(f"{URL}/my-turn", headers=login("a2")).json()
    assert employee["is_leader"] is False and employee["is_my_turn"] is False


# Chốt khi còn team thiếu ghế phải kèm xác nhận (F11 B13).
FORCE = {"confirm_incomplete": True}

# --- Mở lại chọn ghế ---


def test_reopen_gives_unseated_teams_another_turn(client: TestClient, login, world, db: Session):
    admin = login("admin")
    first, second = open_selection(client, login, world)
    assert error_code(client.post(f"{URL}/reopen", headers=admin)) == "GALA_NOT_FINALIZED"

    confirm(client, login, first, "B01")  # đủ quota → lượt chuyển cho team sau
    # Còn team chưa đủ ghế: chốt phải là quyết định có chủ ý.
    blocked = client.post(f"{URL}/finalize", headers=admin)
    assert blocked.status_code == 409 and error_code(blocked) == "GALA_FINALIZE_INCOMPLETE"
    assert [team["seats"] for team in blocked.json()["error"]["details"]["teams"]] == [0]
    finished = client.post(f"{URL}/finalize", headers=admin, json=FORCE).json()
    assert finished["layout"]["selection_status"] == "finalized"
    assert client.post(f"{URL}/reopen", headers=login(first)).status_code == 403

    reopened = client.post(f"{URL}/reopen", headers=admin)
    assert reopened.status_code == 200, reopened.text
    body = reopened.json()
    assert body["layout"]["selection_status"] == "open"
    statuses = {order["team_id"]: order["status"] for order in body["draw"]["orders"]}
    assert statuses == {team_of(world, first): "done", team_of(world, second): "active"}
    assert db.query(AuditLog).filter(AuditLog.action == "gala.selection_reopened").count() == 1

    result = confirm(client, login, second, "B02")
    assert result["turn_finished"] is True and result["next_team_id"] is None
    assert view(client, admin)["layout"]["selection_status"] == "finalized"
    assert error_code(client.post(f"{URL}/reopen", headers=admin)) == "GALA_NOTHING_TO_REOPEN"

    # Team sau được báo 2 lần: khi tới lượt lần đầu và khi BTC mở lại.
    assert [row.to_email for row in turn_emails(db)].count(f"{second}@company.vn") == 2


# --- Chặn bắt đầu sự kiện ---


def test_event_cannot_start_until_everyone_has_a_seat(client: TestClient, login, world):
    admin = login("admin")
    status_url = f"/api/v1/events/{world['event']}/status"

    blocked = client.post(status_url, headers=admin, json={"status": "event_started"})
    assert blocked.status_code == 409
    assert error_code(blocked) == "GALA_SEATING_INCOMPLETE"
    assert len(blocked.json()["error"]["details"]["teams_missing"]) == 2

    first, second = open_selection(client, login, world)
    for leader, table in ((first, "B01"), (second, "B02")):
        confirm(client, login, leader, table)
        placed = client.post(AUTO, headers=login(leader), json={})
        assert placed.status_code == 200, placed.text
        assert placed.json()["placed"] == 2

    # Còn một người tham gia chưa thuộc team nào: chưa có ghế thì vẫn chặn.
    still = client.post(status_url, headers=admin, json={"status": "event_started"})
    assert error_code(still) == "GALA_SEATING_INCOMPLETE"
    details = still.json()["error"]["details"]
    assert details["teams_missing"] == [] and details["unseated"] == 1

    free_seat = seats_of(view(client, admin), "B01")[2]
    forced = client.patch(
        f"{URL}/seats/{free_seat}",
        headers=admin,
        json={"team_id": world["alpha"], "registration_id": world["registrations"]["loner"], "reason": "Khách chưa có team"},
    )
    assert forced.status_code == 200, forced.text

    started = client.post(status_url, headers=admin, json={"status": "event_started"})
    assert started.status_code == 200, started.text

    # Bấm nhầm "Đang diễn ra": lùi về "Đã công bố" được ngay, lý do không bắt buộc.
    reverted = client.post(status_url, headers=admin, json={"status": "information_published"})
    assert reverted.status_code == 200, reverted.text
    assert reverted.json()["status"] == "information_published"


# --- Xếp ngẫu nhiên ---


def test_auto_assign_members_then_swap_by_hand(client: TestClient, login, world, db: Session):
    first, second = open_selection(client, login, world)
    team_id = team_of(world, first)
    member = "a2" if first == "la" else "b2"
    leader_registration = world["registrations"][first]
    member_registration = world["registrations"][member]

    assert error_code(client.post(AUTO, headers=login(first), json={})) == "NO_TEAM_SEATS"
    confirm(client, login, first, "B01")

    result = client.post(AUTO, headers=login(first), json={}).json()
    assert result == {"team_id": team_id, "placed": 2, "unseated": 0, "free_seats": 0, "reshuffle": False}
    assert client.post(AUTO, headers=login(first), json={}).json()["placed"] == 0  # không đụng chỗ đã xếp

    reshuffled = client.post(AUTO, headers=login(first), json={"reshuffle": True}).json()
    assert reshuffled["placed"] == 2

    seats = {item["registration_id"]: item["seat_id"] for item in client.get(f"{URL}/team-members", headers=login(first)).json()}
    assert all(seats.values())

    # Đổi chỗ: thành viên sang ghế của trưởng nhóm, trưởng nhóm sang ghế cũ của thành viên.
    moved = client.post(
        f"{URL}/seats/assign-member", headers=login(first),
        json={"seat_id": seats[leader_registration], "registration_id": member_registration},
    ).json()
    assert moved["previous_seat_id"] == seats[member_registration]
    client.post(
        f"{URL}/seats/assign-member", headers=login(first),
        json={"seat_id": seats[member_registration], "registration_id": leader_registration},
    )
    swapped = {item["registration_id"]: item["seat_id"] for item in client.get(f"{URL}/team-members", headers=login(first)).json()}
    assert swapped == {leader_registration: seats[member_registration], member_registration: seats[leader_registration]}

    # Quyền: trưởng nhóm khác, thành viên thường không xếp được; BTC phải chọn team.
    assert client.post(AUTO, headers=login(second), json={"team_id": team_id}).status_code == 403
    assert client.post(AUTO, headers=login(member), json={}).status_code == 403
    assert error_code(client.post(AUTO, headers=login("admin"), json={})) == "TEAM_REQUIRED"
    assert client.post(AUTO, headers=login("admin"), json={"team_id": team_id}).status_code == 200
    assert db.query(AuditLog).filter(AuditLog.action == "gala.members_auto_assigned").count() == 4


def test_reopen_uses_live_quota_without_overwriting_draw_snapshot(client, login, world, db):
    from app.models.registration import Registration

    first, _ = open_selection(client, login, world)
    confirm(client, login, first, "B01")
    assert client.post(f"{URL}/finalize", headers=login("admin"), json=FORCE).status_code == 200
    member = "a2" if first == "la" else "b2"
    db.execute(update(Registration).where(Registration.id == world["registrations"][member])
               .values(is_participating=False))
    db.commit()
    opened = client.post(f"{URL}/reopen", headers=login("admin"))
    assert opened.status_code == 200, opened.text
    order = next(row for row in opened.json()["draw"]["orders"] if row["team_id"] == team_of(world, first))
    assert order["quota"] == 1 and order["status"] == "done"
    stored = db.query(GalaDrawOrder).filter_by(team_id=team_of(world, first)).one()
    assert stored.quota == 2


# --- Tạm dừng/tiếp tục/cộng phút: thời gian ảo, không sleep ---


def _clock(monkeypatch):
    from datetime import timedelta

    from app.core.timeutils import from_iso, to_iso, utcnow_iso
    from app.services import gala_service

    clock = [from_iso(utcnow_iso())]
    monkeypatch.setattr(gala_service, "utcnow_iso", lambda: to_iso(clock[0]))
    monkeypatch.setattr(
        gala_service, "iso_in", lambda **parts: to_iso(clock[0] + timedelta(**parts))
    )
    return clock


def test_pause_survives_sessions_freezes_holds_and_resume_preserves_remaining(
    client, login, world, db, monkeypatch
):
    from datetime import timedelta

    from app.core.timeutils import from_iso
    from app.services.gala_service import change_signature

    clock = _clock(monkeypatch)
    first, second = open_selection(client, login, world)
    first_view = view(client, login(first))
    team_id = first_view["my_team"]["team_id"]
    seat_ids = seats_of(first_view, "B01")[:2]
    held = client.post(f"{URL}/seats/hold", headers=login(first), json={"seat_ids": seat_ids})
    assert held.status_code == 200, held.text
    hold_end = from_iso(held.json()["expires_at"])
    turn_end = from_iso(first_view["my_team"]["turn_ends_at"])
    clock[0] += timedelta(seconds=30)
    before_version = change_signature(db, event_id=world["event"], jobs=[])
    paused = client.post(
        f"{URL}/turn/pause", headers=login("admin"), json={"expected_team_id": team_id}
    )
    assert paused.status_code == 200, paused.text
    assert paused.json()["draw"]["paused_at"]
    assert change_signature(db, event_id=world["event"], jobs=[]) != before_version
    # Nhiều session/request và cả nhịp SSE đều không dọn ghế/lượt đang đóng băng.
    clock[0] += timedelta(seconds=600)
    db.expire_all()
    frozen = view(client, login(first))
    assert frozen["my_team"]["held"] == 2
    assert frozen["draw"]["active_team_id"] == team_id
    assert frozen["totals"]["held"] == 2
    assert client.get(f"{URL}/my-turn", headers=login(first)).json()["paused_at"]
    version = change_signature(db, event_id=world["event"], jobs=[])
    clock[0] += timedelta(seconds=10)
    assert change_signature(db, event_id=world["event"], jobs=[]) == version
    for path, payload in (("hold", {"seat_ids": seat_ids}), ("confirm", {})):
        blocked = client.post(f"{URL}/seats/{path}", headers=login(first), json=payload)
        assert blocked.status_code == 409 and error_code(blocked) == "GALA_TURN_PAUSED"
    resumed = client.post(
        f"{URL}/turn/resume", headers=login("admin"), json={"expected_team_id": team_id}
    )
    assert resumed.status_code == 200, resumed.text
    data = resumed.json()
    assert data["draw"]["paused_at"] is None
    leader_view = view(client, login(first))
    assert from_iso(leader_view["my_team"]["turn_ends_at"]) == turn_end + timedelta(seconds=610)
    assert from_iso(leader_view["my_team"]["hold_expires_at"]) == hold_end + timedelta(seconds=610)
    confirmed = client.post(f"{URL}/seats/confirm", headers=login(first))
    assert confirmed.status_code == 200 and confirmed.json()["turn_finished"]
    assert view(client, login(second))["my_team"]["is_my_turn"]


def test_extend_running_and_paused_turn_changes_only_turn_deadline(
    client, login, world, db, monkeypatch
):
    from datetime import timedelta

    from app.core.timeutils import from_iso
    from app.models.gala import GalaSeat
    from app.services.gala_service import change_signature

    _clock(monkeypatch)
    first, _ = open_selection(client, login, world)
    data = view(client, login(first))
    team_id = data["my_team"]["team_id"]
    ids = seats_of(data, "B01")[:1]
    held = client.post(f"{URL}/seats/hold", headers=login(first), json={"seat_ids": ids}).json()
    deadline = from_iso(data["my_team"]["turn_ends_at"])
    signature = change_signature(db, event_id=world["event"], jobs=[])
    for minutes, pause in ((1, False), (2, True)):
        if pause:
            assert (
                client.post(
                    f"{URL}/turn/pause", headers=login("admin"), json={"expected_team_id": team_id}
                ).status_code
                == 200
            )
        response = client.post(
            f"{URL}/turn/extend",
            headers=login("admin"),
            json={"expected_team_id": team_id, "minutes": minutes},
        )
        assert response.status_code == 200, response.text
        deadline += timedelta(minutes=minutes)
        assert from_iso(response.json()["draw"]["active_turn_ends_at"]) == deadline
        db.expire_all()
        assert db.get(GalaSeat, ids[0]).hold_expires_at == held["expires_at"]
    assert change_signature(db, event_id=world["event"], jobs=[]) != signature
    assert db.query(AuditLog).filter(AuditLog.action == "gala.turn_extend").count() == 2


def test_turn_controls_enforce_role_state_stale_team_and_payload(
    client, login, world, db, monkeypatch
):
    _clock(monkeypatch)
    body = {"expected_team_id": world["alpha"]}
    for action in ("pause", "resume", "extend"):
        denied = client.post(f"{URL}/turn/{action}", headers=login("la"), json=body)
        assert denied.status_code == 403
        closed = client.post(f"{URL}/turn/{action}", headers=login("admin"), json=body)
        assert closed.status_code == 409 and error_code(closed) == "GALA_NO_ACTIVE_TURN"
    first, second = open_selection(client, login, world)
    team_id = view(client, login(first))["my_team"]["team_id"]
    body = {"expected_team_id": team_id}
    wrong = {"expected_team_id": view(client, login(second))["my_team"]["team_id"]}
    changed = client.post(f"{URL}/turn/extend", headers=login("admin"), json=wrong)
    assert changed.status_code == 409 and error_code(changed) == "GALA_TURN_CHANGED"
    resumed = client.post(f"{URL}/turn/resume", headers=login("admin"), json=body)
    assert resumed.status_code == 409 and error_code(resumed) == "GALA_TURN_NOT_PAUSED"
    for minutes in (0, 31, -1, 1.5, True, "1"):
        invalid = client.post(
            f"{URL}/turn/extend", headers=login("admin"), json={**body, "minutes": minutes}
        )
        assert invalid.status_code == 422, invalid.text
    assert client.post(f"{URL}/turn/pause", headers=login("admin"), json=body).status_code == 200
    repeated = client.post(f"{URL}/turn/pause", headers=login("admin"), json=body)
    assert repeated.status_code == 409 and error_code(repeated) == "GALA_TURN_PAUSED"
    # Chuyển lượt từ pause không mang trạng thái đóng băng sang team kế tiếp.
    advanced = client.post(f"{URL}/turn/next", headers=login("admin"), json={"skip": True})
    assert advanced.status_code == 200 and advanced.json()["draw"]["paused_at"] is None
    stale = client.post(f"{URL}/turn/resume", headers=login("admin"), json=body)
    assert stale.status_code == 409 and error_code(stale) == "GALA_TURN_CHANGED"


def test_expired_turn_cannot_be_resurrected_and_finalize_clears_pause(
    client, login, world, monkeypatch
):
    from datetime import timedelta

    clock = _clock(monkeypatch)
    first, _ = open_selection(client, login, world)
    body = {"expected_team_id": view(client, login(first))["my_team"]["team_id"]}
    clock[0] += timedelta(seconds=301)
    for action in ("pause", "extend"):
        response = client.post(f"{URL}/turn/{action}", headers=login("admin"), json=body)
        assert response.status_code == 409 and error_code(response) == "TURN_EXPIRED"
    current = view(client, login("admin"))
    body = {"expected_team_id": current["draw"]["active_team_id"]}
    assert client.post(f"{URL}/turn/pause", headers=login("admin"), json=body).status_code == 200
    finalized = client.post(f"{URL}/finalize", headers=login("admin"), json=FORCE)
    assert finalized.status_code == 200
    assert finalized.json()["draw"]["paused_at"] is None
    assert finalized.json()["layout"]["selection_status"] == "finalized"


def test_pause_migration_preserves_existing_seats_and_blocks_unsafe_downgrade(
    engine, db, world, monkeypatch
):
    from pathlib import Path

    import pytest
    from alembic.config import Config
    from sqlalchemy import text

    from alembic import command
    from app.core.config import settings

    layout_id = world["layout"]
    db.close()
    with engine.begin() as connection:
        before = connection.execute(text("SELECT COUNT(*) FROM gala_seats")).scalar_one()
        connection.execute(text("ALTER TABLE gala_layouts DROP COLUMN turn_paused_at"))
    monkeypatch.setattr(settings, "DATABASE_URL", str(engine.url))
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    command.stamp(config, "7d2a9e41c027")
    command.upgrade(config, "head")
    with engine.begin() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM gala_seats")).scalar_one() == before
        assert (
            connection.execute(
                text("SELECT turn_paused_at FROM gala_layouts WHERE id=:id"), {"id": layout_id}
            ).scalar_one()
            is None
        )
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
        connection.execute(
            text("UPDATE gala_layouts SET turn_paused_at='2026-10-02T00:00:00+00:00' WHERE id=:id"),
            {"id": layout_id},
        )
    with pytest.raises(RuntimeError, match="Tiếp tục"):
        command.downgrade(config, "7d2a9e41c027")
    with engine.begin() as connection:
        connection.execute(text("UPDATE gala_layouts SET turn_paused_at=NULL"))
    command.downgrade(config, "7d2a9e41c027")
    command.upgrade(config, "head")
