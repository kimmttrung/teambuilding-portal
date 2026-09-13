"""Kiểm thử import phân phòng từ Excel (MVP của docs/05 §7)."""

from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.models import AuditLog, Event, Hotel, Registration, Room, RoomAssignment, User
from app.models.enums import AssignmentMode, EventStatus, Gender, RegistrationStatus, RoomGenderPolicy, UserRole

IMPORT = "/api/v1/rooms/import"
XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture
def setup(db: Session) -> dict:
    event = Event(
        code="TB2026", name="Team Building 2026", start_date="2026-10-15", end_date="2026-10-17",
        status=EventStatus.REGISTRATION_CLOSED, terms_version="v1", is_active=True,
    )
    db.add(event)
    db.flush()
    hotel = Hotel(event_id=event.id, name="Sunset Beach Resort")
    db.add(hotel)
    db.flush()
    male = Room(hotel_id=hotel.id, room_number="801", capacity=2, gender_policy=RoomGenderPolicy.MALE)
    female = Room(hotel_id=hotel.id, room_number="802", capacity=2, gender_policy=RoomGenderPolicy.FEMALE)
    shared = Room(hotel_id=hotel.id, room_number="901", capacity=3, gender_policy=RoomGenderPolicy.ANY)
    db.add_all([male, female, shared])
    db.commit()
    return {"event": event, "hotel": hotel, "male": male, "female": female, "shared": shared}


@pytest.fixture
def admin_headers(make_user, auth_headers, setup):
    make_user(email="btc@company.vn", password="MatKhau123", role=UserRole.ADMIN)
    return auth_headers("btc@company.vn")


@pytest.fixture
def person(db: Session, setup):
    """CBNV NV001, NV002, ... theo thứ tự tạo."""
    counter = {"n": 0}

    def _make(*, gender=Gender.MALE, participating=True) -> Registration:
        counter["n"] += 1
        index = counter["n"]
        user = User(
            email=f"nv{index}@company.vn",
            full_name=f"Người Số {index:02d}",
            employee_code=f"NV{index:03d}",
            password_hash="x",
            role=UserRole.EMPLOYEE,
            gender=gender,
        )
        db.add(user)
        db.flush()
        registration = Registration(
            event_id=setup["event"].id,
            user_id=user.id,
            is_participating=participating,
            status=RegistrationStatus.SUBMITTED,
            submitted_at="2026-09-12T03:00:00+00:00",
        )
        db.add(registration)
        db.commit()
        db.refresh(registration)
        return registration

    return _make


def workbook(rows, headers=("Mã NV", "Số phòng", "Trưởng phòng")) -> bytes:
    book = Workbook()
    sheet = book.active
    sheet.append(list(headers))
    for row in rows:
        sheet.append(list(row))
    buffer = BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def upload(client, headers, content, *, dry_run=True, replace_existing=False):
    return client.post(
        IMPORT,
        headers=headers,
        params={"dry_run": str(dry_run).lower(), "replace_existing": str(replace_existing).lower()},
        files={"file": ("phan-phong.xlsx", content, XLSX_TYPE)},
    )


def errors_by_row(body) -> dict[int, str]:
    return {error["row"]: error["code"] for error in body["errors"]}


# --- Luồng thành công ---


def test_dry_run_reports_valid_rows_without_writing(
    client: TestClient, setup, admin_headers, person, db: Session
):
    person(gender=Gender.MALE)
    person(gender=Gender.MALE)
    person(gender=Gender.FEMALE)
    # Số phòng gõ dạng số trong Excel (801 -> 801.0) vẫn phải khớp phòng "801".
    content = workbook([("NV001", 801, "x"), ("NV002", 801, ""), ("NV003", "802", "")])

    response = upload(client, admin_headers, content)

    assert response.status_code == 200
    body = response.json()
    assert body["dry_run"] is True
    assert body["committed"] is False
    assert body["total_rows"] == 3
    assert body["valid_rows"] == 3
    assert body["error_count"] == 0
    assert body["to_create"] == 3
    assert db.query(RoomAssignment).count() == 0


def test_commit_writes_manual_assignments_and_audit(
    client: TestClient, setup, admin_headers, person, db: Session
):
    person(gender=Gender.MALE)
    person(gender=Gender.MALE)
    content = workbook([("NV001", "801", "x"), ("NV002", "801", "")])

    response = upload(client, admin_headers, content, dry_run=False)

    assert response.status_code == 200
    assert response.json()["committed"] is True
    rows = db.query(RoomAssignment).order_by(RoomAssignment.id).all()
    assert len(rows) == 2
    assert {row.assignment_mode for row in rows} == {AssignmentMode.MANUAL}
    assert [row.is_room_captain for row in rows] == [True, False]
    assert db.query(AuditLog).filter(AuditLog.action == "room.imported").count() == 1


def test_accepts_header_variants_email_and_hotel_column(
    client: TestClient, setup, admin_headers, person
):
    person(gender=Gender.FEMALE)
    content = workbook(
        [("NV1@COMPANY.VN", "802", "sunset beach resort")],
        headers=("  EMAIL ", "phong", "Khach San"),
    )

    body = upload(client, admin_headers, content).json()

    assert body["error_count"] == 0
    assert body["valid_rows"] == 1


# --- Lỗi từng dòng ---


def test_row_errors_are_listed_with_excel_row_numbers(
    client: TestClient, setup, admin_headers, person
):
    person(gender=Gender.MALE)            # NV001
    person(gender=Gender.MALE)            # NV002
    person(gender=Gender.FEMALE)          # NV003
    person(participating=False)           # NV004
    content = workbook(
        [
            ("NV999", "801", ""),   # dòng 2: không có người này
            ("NV003", "801", ""),   # dòng 3: nữ vào phòng nam
            ("NV001", "999", ""),   # dòng 4: không có phòng
            ("NV002", "901", ""),   # dòng 5: hợp lệ
            ("NV002", "901", ""),   # dòng 6: trùng trong file
            ("NV004", "901", ""),   # dòng 7: không tham gia
        ]
    )

    body = upload(client, admin_headers, content).json()

    assert errors_by_row(body) == {
        2: "USER_NOT_FOUND",
        3: "GENDER_POLICY_VIOLATION",
        4: "ROOM_NOT_FOUND",
        6: "DUPLICATE_IN_FILE",
        7: "NOT_PARTICIPATING",
    }
    assert body["valid_rows"] == 1


def test_commit_with_errors_writes_nothing(
    client: TestClient, setup, admin_headers, person, db: Session
):
    """Tất cả hoặc không gì cả: một dòng lỗi thì không dòng nào được ghi."""
    person(gender=Gender.MALE)
    content = workbook([("NV001", "801", ""), ("NV999", "801", "")])

    response = upload(client, admin_headers, content, dry_run=False)

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "IMPORT_VALIDATION_FAILED"
    assert error["details"]["error_count"] == 1
    assert db.query(RoomAssignment).count() == 0


def test_room_over_capacity_counts_all_file_rows(
    client: TestClient, setup, admin_headers, person
):
    for _ in range(3):
        person(gender=Gender.MALE)
    content = workbook([("NV001", "801", ""), ("NV002", "801", ""), ("NV003", "801", "")])

    body = upload(client, admin_headers, content).json()

    assert set(errors_by_row(body).values()) == {"ROOM_OVER_CAPACITY"}
    assert body["error_count"] == 3


def test_existing_assignment_needs_replace_flag(
    client: TestClient, setup, admin_headers, person, db: Session
):
    registration = person(gender=Gender.MALE)
    db.add(
        RoomAssignment(
            registration_id=registration.id,
            room_id=setup["shared"].id,
            assignment_mode=AssignmentMode.MANUAL,
            assigned_at="2026-09-12T04:00:00+00:00",
        )
    )
    db.commit()
    content = workbook([("NV001", "801", "")])

    blocked = upload(client, admin_headers, content).json()
    allowed = upload(client, admin_headers, content, replace_existing=True).json()
    committed = upload(client, admin_headers, content, dry_run=False, replace_existing=True)

    assert errors_by_row(blocked) == {2: "ALREADY_HAS_ROOM"}
    assert allowed["error_count"] == 0
    assert allowed["to_move"] == 1
    assert committed.status_code == 200
    assert db.query(RoomAssignment).filter_by(registration_id=registration.id).one().room_id == setup["male"].id


def test_multiple_captains_in_same_room_rejected(
    client: TestClient, setup, admin_headers, person
):
    person(gender=Gender.MALE)
    person(gender=Gender.MALE)
    content = workbook([("NV001", "801", "x"), ("NV002", "801", "có")])

    body = upload(client, admin_headers, content).json()

    assert errors_by_row(body) == {3: "CAPTAIN_CONFLICT"}


# --- File sai ---


def test_rejects_non_excel_file_and_missing_columns(client: TestClient, setup, admin_headers):
    not_excel = upload(client, admin_headers, b"ho ten,so phong\nA,801")
    no_columns = upload(client, admin_headers, workbook([("A", "ghi chú")], headers=("Họ tên", "Ghi chú")))

    assert not_excel.status_code == 400
    assert not_excel.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"
    assert no_columns.status_code == 400
    assert no_columns.json()["error"]["code"] == "MISSING_COLUMNS"


def test_employee_cannot_import(client: TestClient, setup, make_user, auth_headers):
    make_user(email="nv@company.vn", password="MatKhau123")
    response = upload(client, auth_headers("nv@company.vn"), workbook([("NV001", "801", "")]))
    assert response.status_code == 403
