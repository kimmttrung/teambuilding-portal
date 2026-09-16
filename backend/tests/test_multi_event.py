"""Nhiều kỳ Team Building chạy song song qua header `X-Event-Id` (docs/13 task 6).

Điểm mấu chốt: `dependencies.get_active_event` là chỗ DUY NHẤT quyết định request đang thao tác trên
kỳ nào. 100 chỗ dùng `ActiveEvent` trong 15 router, `require_event_status`, `require_published_event`,
luồng SSE Gala và chatbot đều đi qua đó, nên test ở đây bảo vệ toàn bộ.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import EventStatus, UserRole
from app.models.event import Event
from app.models.flight import Flight, Shift

URL = "/api/v1"


@pytest.fixture
def two_events(db: Session, make_user) -> dict:
    """Hai kỳ song song, mỗi kỳ một ca và một chuyến bay riêng, cộng một kỳ nháp."""
    current = Event(
        code="TB2026", name="Team Building 2026", destination="Phú Quốc",
        start_date="2026-10-15", end_date="2026-10-17",
        status=EventStatus.REGISTRATION_OPEN, terms_version="v1", is_active=True,
    )
    other = Event(
        code="TB2027", name="Team Building 2027", destination="Đà Nẵng",
        start_date="2027-04-16", end_date="2027-04-18",
        status=EventStatus.REGISTRATION_OPEN, terms_version="v1", is_active=False,
    )
    draft = Event(
        code="TB2028", name="Team Building 2028", destination="Quy Nhơn",
        start_date="2028-05-10", end_date="2028-05-12",
        status=EventStatus.DRAFT, terms_version="v1", is_active=False,
    )
    db.add_all([current, other, draft])
    db.flush()

    make_user(email="btc@company.vn", role=UserRole.ADMIN, full_name="Ban Tổ Chức")
    make_user(email="nv@company.vn", full_name="Nguyễn Văn A")

    for event, code in ((current, "VN1234"), (other, "VN0161")):
        shift = Shift(event_id=event.id, code="CA1", name="Ca 1", display_order=1)
        db.add(shift)
        db.flush()
        db.add(Flight(
            event_id=event.id, flight_code=code, airline="Vietnam Airlines",
            direction="outbound", shift_id=shift.id,
            departure_airport="HAN", arrival_airport="PQC",
            departure_time=f"{event.start_date}T00:00:00+00:00",
            arrival_time=f"{event.start_date}T02:00:00+00:00",
            capacity=60,
        ))
    db.commit()
    return {"current": current.id, "other": other.id, "draft": draft.id}


def headers_for(auth_headers, email: str, event_id: int | None = None) -> dict[str, str]:
    headers = dict(auth_headers(email))
    if event_id is not None:
        headers["X-Event-Id"] = str(event_id)
    return headers


def flight_codes(client: TestClient, headers) -> list[str]:
    response = client.get(f"{URL}/flights", headers=headers)
    assert response.status_code == 200, response.text
    return sorted(item["flight_code"] for item in response.json())


def test_header_picks_the_event_and_no_header_falls_back_to_the_default(
    client: TestClient, auth_headers, two_events
):
    """Không gửi header vẫn ra kỳ mặc định — client cũ và script không đổi gì mà vẫn chạy."""
    admin = headers_for(auth_headers, "btc@company.vn")

    assert client.get(f"{URL}/events/active", headers=admin).json()["code"] == "TB2026"
    assert flight_codes(client, admin) == ["VN1234"]

    switched = headers_for(auth_headers, "btc@company.vn", two_events["other"])
    assert client.get(f"{URL}/events/active", headers=switched).json()["code"] == "TB2027"
    assert flight_codes(client, switched) == ["VN0161"], "dữ liệu hai kỳ không được lẫn vào nhau"


def test_bad_or_unknown_event_header_is_rejected(client: TestClient, auth_headers, two_events):
    admin = headers_for(auth_headers, "btc@company.vn")

    garbage = client.get(f"{URL}/events/active", headers={**admin, "X-Event-Id": "khong-phai-so"})
    assert garbage.status_code == 400
    assert garbage.json()["error"]["code"] == "EVENT_HEADER_INVALID"

    missing = client.get(f"{URL}/events/active", headers={**admin, "X-Event-Id": "99999"})
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "EVENT_NOT_FOUND"

    # Header rỗng = coi như không gửi, không phải lỗi.
    blank = client.get(f"{URL}/events/active", headers={**admin, "X-Event-Id": "   "})
    assert blank.status_code == 200 and blank.json()["code"] == "TB2026"


def test_employees_cannot_reach_a_draft_event_but_organizers_can(
    client: TestClient, auth_headers, two_events
):
    """Kỳ nháp là kế hoạch BTC đang dựng. Trả 404 chứ không 403: không xác nhận nó có tồn tại."""
    employee = headers_for(auth_headers, "nv@company.vn", two_events["draft"])
    blocked = client.get(f"{URL}/events/active", headers=employee)
    assert blocked.status_code == 404
    assert blocked.json()["error"]["code"] == "EVENT_NOT_FOUND"

    admin = headers_for(auth_headers, "btc@company.vn", two_events["draft"])
    assert client.get(f"{URL}/events/active", headers=admin).json()["code"] == "TB2028"


def test_selectable_list_matches_what_each_role_may_actually_open(
    client: TestClient, auth_headers, two_events
):
    """Bộ chọn kỳ và dependency phải cùng một luật, không thì người dùng chọn xong lại ăn 404."""
    admin = client.get(f"{URL}/events/selectable", headers=headers_for(auth_headers, "btc@company.vn"))
    assert sorted(item["code"] for item in admin.json()) == ["TB2026", "TB2027", "TB2028"]

    employee = client.get(f"{URL}/events/selectable", headers=headers_for(auth_headers, "nv@company.vn"))
    codes = sorted(item["code"] for item in employee.json())
    assert codes == ["TB2026", "TB2027"], "CBNV không được thấy kỳ nháp"

    # Mọi kỳ CBNV nhìn thấy đều phải mở được thật.
    for item in employee.json():
        opened = client.get(
            f"{URL}/events/active", headers=headers_for(auth_headers, "nv@company.vn", item["id"])
        )
        assert opened.status_code == 200, item["code"]


def test_event_status_guard_follows_the_selected_event(
    client: TestClient, auth_headers, two_events, db: Session
):
    """`require_event_status` đọc kỳ qua cùng dependency — đóng đăng ký kỳ này không đụng kỳ kia."""
    db.get(Event, two_events["current"]).status = EventStatus.REGISTRATION_CLOSED
    db.commit()

    on_closed = client.post(
        f"{URL}/registrations",
        headers=headers_for(auth_headers, "nv@company.vn", two_events["current"]),
        json={"is_participating": False, "not_participating_reason": "Bận việc gia đình"},
    )
    assert on_closed.status_code == 409
    assert on_closed.json()["error"]["code"] == "REGISTRATION_CLOSED"

    # Kỳ còn lại vẫn mở: cùng một người, cùng một endpoint, chỉ khác header.
    on_open = client.post(
        f"{URL}/registrations",
        headers=headers_for(auth_headers, "nv@company.vn", two_events["other"]),
        json={"is_participating": False, "not_participating_reason": "Bận việc gia đình"},
    )
    assert on_open.status_code in (200, 201), on_open.text
