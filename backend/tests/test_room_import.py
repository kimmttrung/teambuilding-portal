"""Kiểm thử import phân phòng từ Excel (MVP của docs/05 §7)."""

from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.models import AuditLog, Event, Hotel, Registration, Room, User
from app.models.enums import (
    AssignmentMode,
    EventStatus,
    Gender,
    RegistrationStatus,
    RoomGenderPolicy,
    UserRole,
)

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
    assert db.query(Registration).populate_existing().filter(Registration.room_id.is_not(None)).count() == 0


def test_commit_writes_manual_assignments_and_audit(
    client: TestClient, setup, admin_headers, person, db: Session
):
    person(gender=Gender.MALE)
    person(gender=Gender.MALE)
    content = workbook([("NV001", "801", "x"), ("NV002", "801", "")])

    response = upload(client, admin_headers, content, dry_run=False)

    assert response.status_code == 200
    assert response.json()["committed"] is True
    rows = db.query(Registration).populate_existing().filter(Registration.room_id.is_not(None)).order_by(Registration.id).all()
    assert len(rows) == 2
    assert {row.room_mode for row in rows} == {AssignmentMode.MANUAL}
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
    assert db.query(Registration).populate_existing().filter(Registration.room_id.is_not(None)).count() == 0


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
    registration.room_id = setup["shared"].id
    registration.room_mode = AssignmentMode.MANUAL
    registration.room_assigned_at = "2026-09-12T04:00:00+00:00"
    db.commit()
    content = workbook([("NV001", "801", "")])

    blocked = upload(client, admin_headers, content).json()
    allowed = upload(client, admin_headers, content, replace_existing=True).json()
    committed = upload(client, admin_headers, content, dry_run=False, replace_existing=True)

    assert errors_by_row(blocked) == {2: "ALREADY_HAS_ROOM"}
    assert allowed["error_count"] == 0
    assert allowed["to_move"] == 1
    assert committed.status_code == 200
    assert db.query(Registration).populate_existing().filter_by(id=registration.id).one().room_id == setup["male"].id


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


def test_swap_full_rooms_uses_final_occupancy(client, setup, admin_headers, person, db):
    first, second = person(), person()
    other = Room(hotel_id=setup["hotel"].id, room_number="803", capacity=1, gender_policy="male")
    db.add(other)
    setup["male"].capacity = 1
    first.room_id, second.room_id = setup["male"].id, None
    db.flush()
    second.room_id = other.id
    for reg in (first, second):
        reg.room_mode, reg.room_assigned_at = "manual", "2026-09-12T04:00:00+00:00"
    db.commit()
    content = workbook([("NV001", "803", "x"), ("NV002", "801", "x")])
    preview = upload(client, admin_headers, content, replace_existing=True)
    assert preview.status_code == 200 and preview.json()["error_count"] == 0
    assert preview.json()["to_move"] == 2
    committed = upload(client, admin_headers, content, dry_run=False, replace_existing=True)
    assert committed.status_code == 200, committed.text
    db.refresh(first)
    db.refresh(second)
    assert (first.room_id, second.room_id) == (other.id, setup["male"].id)
    assert first.is_room_captain and second.is_room_captain


def test_commit_revalidates_capacity_changed_after_preview(client, setup, admin_headers, person, db):
    first, second = person(), person()
    content = workbook([("NV001", "801", "x"), ("NV002", "801", "")])
    assert upload(client, admin_headers, content).json()["error_count"] == 0
    setup["male"].capacity = 1
    db.commit()
    response = upload(client, admin_headers, content, dry_run=False)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "IMPORT_VALIDATION_FAILED"
    for reg in (first, second):
        db.refresh(reg)
        assert reg.room_id is None
    assert db.query(AuditLog).filter_by(action="room.imported").count() == 0


def test_import_atomicity_preserves_existing_metadata(client, setup, admin_headers, person, db):
    first, second = person(), person()
    first.room_id = setup["shared"].id
    first.room_mode = "manual"
    first.is_room_captain = True
    first.room_assigned_at = "2026-09-12T04:00:00+00:00"
    first.room_note = "Phân phòng đặc biệt"
    db.commit()
    content = workbook([("NV001", "801", "x"), ("NV002", "missing", "")])
    response = upload(client, admin_headers, content, dry_run=False, replace_existing=True)
    assert response.status_code == 400
    db.refresh(first)
    db.refresh(second)
    assert first.room_id == setup["shared"].id and first.is_room_captain
    assert first.room_note == "Phân phòng đặc biệt"
    assert first.room_assigned_at == "2026-09-12T04:00:00+00:00"
    assert second.room_id is None


def test_export_import_roundtrip_is_unchanged(client, setup, admin_headers, person, db):
    first = person()
    first.room_id = setup["male"].id
    first.room_mode = "manual"
    first.room_assigned_at = "2026-09-12T04:00:00+00:00"
    first.is_room_captain = True
    first.room_note = "Giữ ghi chú"
    db.commit()
    exported = client.get("/api/v1/rooms/export", headers=admin_headers)
    assert exported.status_code == 200, exported.text
    preview = upload(client, admin_headers, exported.content)
    assert preview.status_code == 200, preview.text
    assert preview.json()["unchanged"] == 1
    assert preview.json()["error_count"] == 0
    assert upload(client, admin_headers, exported.content, dry_run=False).status_code == 200
    db.refresh(first)
    assert first.room_note == "Giữ ghi chú" and first.is_room_captain
    assert first.room_assigned_at == "2026-09-12T04:00:00+00:00"


def test_import_replaces_captain_without_modifying_registration(client, setup, admin_headers, person, db):
    first, second = person(), person()
    first.room_id = setup["male"].id
    first.is_room_captain = True
    first.room_mode = "manual"
    db.commit()
    content = workbook([("NV002", "801", "x")])
    response = upload(client, admin_headers, content, dry_run=False)
    assert response.status_code == 200, response.text
    db.refresh(first)
    db.refresh(second)
    assert not first.is_room_captain and second.is_room_captain
    assert first.is_participating and second.is_participating


def test_import_cannot_use_hotel_from_other_event(client, setup, admin_headers, person, db):
    reg = person()
    event = Event(code="OTHER", name="Kỳ khác", start_date="2027-01-01", end_date="2027-01-03",
                  status=EventStatus.REGISTRATION_CLOSED, terms_version="v1")
    db.add(event)
    db.flush()
    db.add(Hotel(event_id=event.id, name="Khách sạn ngoài kỳ"))
    db.commit()
    content = workbook([("NV001", "801", "Khách sạn ngoài kỳ")], headers=("Mã NV", "Số phòng", "Khách sạn"))
    response = upload(client, admin_headers, content, dry_run=False)
    assert response.status_code == 400
    assert response.json()["error"]["details"]["errors"][0]["code"] == "HOTEL_NOT_FOUND"
    db.refresh(reg)
    assert reg.room_id is None


def test_import_rolls_back_all_rows_if_audit_fails(setup, person, db, make_user, monkeypatch):
    from app.services import room_import_service
    first, second = person(), person()
    actor = make_user(email="audit@company.vn", role=UserRole.ADMIN)
    def fail(*args, **kwargs):
        raise RuntimeError("audit unavailable")
    monkeypatch.setattr(room_import_service.audit_service, "log", fail)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        room_import_service.import_room_assignments(
            db, event=setup["event"], actor=actor, dry_run=False,
            content=workbook([("NV001", "801", "x"), ("NV002", "801", "")]),
        )
    for reg in (first, second):
        db.refresh(reg)
        assert reg.room_id is None and not reg.is_room_captain


def test_identifiers_must_refer_to_same_person(client, setup, admin_headers, person, db):
    first, second = person(), person()
    content = workbook([("NV001", "nv2@company.vn", "801")], headers=("Mã NV", "Email", "Số phòng"))
    response = upload(client, admin_headers, content, dry_run=False)
    assert response.status_code == 400
    assert response.json()["error"]["details"]["errors"][0]["code"] == "IDENTIFIER_MISMATCH"
    db.refresh(first)
    db.refresh(second)
    assert first.room_id is None and second.room_id is None


def test_ambiguous_hotel_name_does_not_pick_arbitrarily(client, setup, admin_headers, person, db):
    reg = person()
    db.add(Hotel(event_id=setup["event"].id, name=setup["hotel"].name))
    db.commit()
    content = workbook([("NV001", "801", setup["hotel"].name)], headers=("Mã NV", "Số phòng", "Khách sạn"))
    response = upload(client, admin_headers, content, dry_run=False)
    assert response.status_code == 400
    assert response.json()["error"]["details"]["errors"][0]["code"] == "AMBIGUOUS_HOTEL"
    db.refresh(reg)
    assert reg.room_id is None
