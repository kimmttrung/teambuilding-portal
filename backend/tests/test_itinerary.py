"""Kiểm thử BTC quản lý lịch trình: thêm/sửa/xoá/sắp xếp + chặn dữ liệu sai tay."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Event, Shift, Team
from app.models.audit import AuditLog
from app.models.content import ItineraryItem
from app.models.enums import EventStatus, FlightDirection, UserRole
from app.models.transportation import TripLeg

BASE = "/api/v1/itinerary"


@pytest.fixture
def event(db: Session) -> Event:
    row = Event(
        code="TB2026",
        name="Team Building 2026",
        start_date="2026-10-15",
        end_date="2026-10-17",
        status=EventStatus.REGISTRATION_OPEN,
        is_active=True,
    )
    db.add(row)
    db.flush()
    db.add_all(
        [
            Shift(event_id=row.id, code="CA1", name="Ca 1 – bay sáng", display_order=1),
            Shift(event_id=row.id, code="CA2", name="Ca 2 – bay chiều", display_order=2),
            Team(code="IT-HN", name="Công nghệ Hà Nội"),
        ]
    )
    db.add_all(
        [
            ItineraryItem(
                event_id=row.id,
                day_date="2026-10-15",
                start_time="04:30",
                end_time="05:00",
                title="Tập trung tại điểm đón",
                location="Theo xe đã phân công",
                audience="CA1",
                display_order=0,
            ),
            ItineraryItem(
                event_id=row.id,
                day_date="2026-10-15",
                start_time="06:30",
                end_time="08:40",
                title="Chuyến bay HAN – PQC",
                location="Sân bay Nội Bài",
                audience="CA1",
                display_order=1,
            ),
        ]
    )
    db.commit()
    db.refresh(row)
    return row


@pytest.fixture
def admin_headers(make_user, auth_headers):
    make_user(email="btc@company.vn", password="Admin12345", role=UserRole.ADMIN)
    return auth_headers("btc@company.vn", "Admin12345")


@pytest.fixture
def employee_headers(make_user, auth_headers):
    make_user(email="nv@company.vn", password="MatKhau123")
    return auth_headers("nv@company.vn")


def _payload(**overrides):
    body = {
        "day_date": "2026-10-16",
        "start_time": "18:30",
        "end_time": "22:00",
        "title": "Gala Dinner & Vinh danh",
        "location": "Sảnh Pearl",
        "audience": "all",
    }
    body.update(overrides)
    return body


# --- Đọc ---


def test_admin_lists_items_in_display_order(client: TestClient, event, admin_headers):
    response = client.get(BASE, headers=admin_headers)

    assert response.status_code == 200
    rows = response.json()
    assert [row["title"] for row in rows] == ["Tập trung tại điểm đón", "Chuyến bay HAN – PQC"]
    assert rows[0]["audience"] == "CA1"


def test_employee_cannot_read_raw_itinerary(client: TestClient, event, employee_headers):
    """Bản thô gồm cả mốc riêng ca khác — CBNV chỉ đọc bản lọc qua /journey/me."""
    assert client.get(BASE, headers=employee_headers).status_code == 403
    assert (
        client.post(BASE, headers=employee_headers, json=_payload()).status_code == 403
    )


# --- Thêm ---


def test_create_item_appends_to_end_of_day(client: TestClient, event, admin_headers, db):
    response = client.post(BASE, headers=admin_headers, json=_payload())

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["display_order"] == 0  # ngày 16/10 chưa có mốc nào
    assert (
        db.query(AuditLog)
        .filter(AuditLog.action == "itinerary.created", AuditLog.entity_id == body["id"])
        .count()
        == 1
    )


def test_create_item_marks_knowledge_stale(client: TestClient, event, admin_headers, db):
    body = client.post(BASE, headers=admin_headers, json=_payload()).json()

    assert db.get(ItineraryItem, body["id"]).is_indexed is False


def test_create_rejects_day_outside_event(client: TestClient, event, admin_headers):
    response = client.post(
        BASE, headers=admin_headers, json=_payload(day_date="2026-11-15")
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "ITINERARY_DAY_OUT_OF_RANGE"


def test_create_rejects_end_before_start(client: TestClient, event, admin_headers):
    response = client.post(
        BASE, headers=admin_headers, json=_payload(start_time="22:00", end_time="18:30")
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "ITINERARY_TIME_INVALID"


def test_create_rejects_unknown_audience(client: TestClient, event, admin_headers):
    """Gõ "Ca1" thay vì "CA1" là mốc biến mất với mọi người — chặn ngay lúc nhập."""
    response = client.post(BASE, headers=admin_headers, json=_payload(audience="Ca1"))

    assert response.status_code == 400
    body = response.json()["error"]
    assert body["code"] == "ITINERARY_AUDIENCE_UNKNOWN"
    assert "CA1" in body["message"]


def test_create_accepts_shift_and_team_audience(client: TestClient, event, admin_headers):
    for audience in ("CA1", "CA2", "IT-HN"):
        response = client.post(
            BASE, headers=admin_headers, json=_payload(audience=audience)
        )
        assert response.status_code == 201, audience


# --- Sửa / xoá ---


def test_update_item_and_marks_knowledge_stale(
    client: TestClient, event, admin_headers, db
):
    item = db.query(ItineraryItem).first()
    item.is_indexed = True
    db.commit()

    response = client.patch(
        f"{BASE}/{item.id}", headers=admin_headers, json={"title": "Tập trung (giờ mới)"}
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Tập trung (giờ mới)"
    db.expire_all()
    assert db.get(ItineraryItem, item.id).is_indexed is False
    assert (
        db.query(AuditLog).filter(AuditLog.action == "itinerary.updated").count() == 1
    )


def test_update_rejects_bad_audience(client: TestClient, event, admin_headers, db):
    item = db.query(ItineraryItem).first()

    response = client.patch(
        f"{BASE}/{item.id}", headers=admin_headers, json={"audience": "TEAM-MA"}
    )

    assert response.status_code == 400


def test_update_item_of_other_event_returns_404(
    client: TestClient, event, admin_headers, db
):
    other = Event(
        code="TB2027",
        name="Kỳ khác",
        start_date="2027-10-15",
        end_date="2027-10-17",
        status=EventStatus.DRAFT,
    )
    db.add(other)
    db.flush()
    foreign = ItineraryItem(
        event_id=other.id, day_date="2027-10-15", title="Mốc kỳ khác", audience="all"
    )
    db.add(foreign)
    db.commit()

    assert (
        client.patch(f"{BASE}/{foreign.id}", headers=admin_headers, json={"title": "X"}).status_code
        == 404
    )
    assert client.delete(f"{BASE}/{foreign.id}", headers=admin_headers).status_code == 404


def test_delete_item(client: TestClient, event, admin_headers, db):
    item_id = db.query(ItineraryItem).first().id

    response = client.delete(f"{BASE}/{item_id}", headers=admin_headers)

    assert response.status_code == 204
    db.expire_all()
    assert db.get(ItineraryItem, item_id) is None
    assert (
        db.query(AuditLog).filter(AuditLog.action == "itinerary.deleted").count() == 1
    )


# --- Sắp xếp ---


def test_reorder_day(client: TestClient, event, admin_headers, db):
    rows = (
        db.query(ItineraryItem)
        .filter(ItineraryItem.day_date == "2026-10-15")
        .order_by(ItineraryItem.display_order)
        .all()
    )
    flipped = [rows[1].id, rows[0].id]

    response = client.post(
        f"{BASE}/reorder",
        headers=admin_headers,
        json={"day_date": "2026-10-15", "ordered_ids": flipped},
    )

    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == flipped
    assert client.get(BASE, headers=admin_headers).json()[0]["id"] == flipped[0]
    assert (
        db.query(AuditLog).filter(AuditLog.action == "itinerary.reordered").count() == 1
    )


def test_reorder_rejects_partial_list(client: TestClient, event, admin_headers, db):
    only_one = [db.query(ItineraryItem).first().id]

    response = client.post(
        f"{BASE}/reorder",
        headers=admin_headers,
        json={"day_date": "2026-10-15", "ordered_ids": only_one},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "ITINERARY_REORDER_MISMATCH"


# --- Gắn mốc với chặng xe ---


def add_leg(db: Session, event: Event, *, code="CITY_TO_AIRPORT", name="HN → Sân bay") -> TripLeg:
    leg = TripLeg(
        event_id=event.id, code=code, name=name, direction=FlightDirection.OUTBOUND,
        leg_date="2026-10-15", is_airport_linked=True, display_order=1,
    )
    db.add(leg)
    db.commit()
    db.refresh(leg)
    return leg


def test_item_can_be_tied_to_a_bus_leg(client: TestClient, event, admin_headers, db: Session):
    leg = add_leg(db, event)

    created = client.post(
        BASE,
        headers=admin_headers,
        json={
            "day_date": "2026-10-15", "start_time": "04:30", "title": "Tập trung theo xe",
            "audience": "all", "trip_leg_id": leg.id,
        },
    )

    assert created.status_code == 201, created.text
    body = created.json()
    assert body["trip_leg_id"] == leg.id
    assert body["trip_leg_name"] == "HN → Sân bay"


def test_item_rejects_a_leg_from_another_event(client: TestClient, event, admin_headers, db: Session):
    """Gắn nhầm chặng của kỳ khác thì mốc biến mất với mọi người và không ai hiểu vì sao."""
    other = Event(
        code="TB2027", name="Team Building 2027", start_date="2027-04-16", end_date="2027-04-18",
        status=EventStatus.DRAFT, is_active=False,
    )
    db.add(other)
    db.flush()
    stranger = TripLeg(
        event_id=other.id, code="CITY_TO_AIRPORT", name="Chặng kỳ khác",
        direction=FlightDirection.OUTBOUND, display_order=1,
    )
    db.add(stranger)
    db.commit()

    response = client.post(
        BASE,
        headers=admin_headers,
        json={"day_date": "2026-10-15", "title": "Tập trung", "trip_leg_id": stranger.id},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "ITINERARY_TRIP_LEG_UNKNOWN"


def test_item_can_be_unlinked_from_its_leg(client: TestClient, event, admin_headers, db: Session):
    leg = add_leg(db, event)
    item = db.query(ItineraryItem).filter_by(title="Tập trung tại điểm đón").one()
    item.trip_leg_id = leg.id
    db.commit()

    updated = client.patch(f"{BASE}/{item.id}", headers=admin_headers, json={"trip_leg_id": None})

    assert updated.status_code == 200, updated.text
    assert updated.json()["trip_leg_id"] is None
