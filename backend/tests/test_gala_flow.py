"""Gala: mở lại chọn ghế, email báo lượt, chặn bắt đầu sự kiện khi chưa xếp ghế, xếp ngẫu nhiên thành viên."""

from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.enums import DrawStatus
from app.models.gala import GalaDrawOrder
from app.models.notification import EmailLog
from tests.test_gala import PAST, URL, error_code, login, open_selection, seats_of, view, world  # noqa: F401

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


# --- Mở lại chọn ghế ---


def test_reopen_gives_unseated_teams_another_turn(client: TestClient, login, world, db: Session):
    admin = login("admin")
    first, second = open_selection(client, login, world)
    assert error_code(client.post(f"{URL}/reopen", headers=admin)) == "GALA_NOT_FINALIZED"

    confirm(client, login, first, "B01")  # đủ quota → lượt chuyển cho team sau
    finished = client.post(f"{URL}/finalize", headers=admin).json()
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

    # Bấm nhầm "Đang diễn ra": lùi về "Đã công bố" được, nhưng phải nêu lý do.
    back = {"status": "information_published"}
    assert error_code(client.post(status_url, headers=admin, json=back)) == "REASON_REQUIRED"
    reverted = client.post(status_url, headers=admin, json={**back, "reason": "Bấm nhầm, cần xếp lại ghế"})
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
