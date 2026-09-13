"""Kiểm thử import danh sách CBNV từ Excel (bước 21)."""

import json
from datetime import datetime
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.enums import UserRole
from app.models.org import Department, Team, WorkLocation
from app.models.user import User

URL = "/api/v1/admin/users/import"
XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
HEADERS = ("Mã NV", "Họ tên", "Email", "Giới tính", "SĐT", "Team", "Chức danh", "Ngày vào làm")


@pytest.fixture
def world(db: Session, make_user) -> dict:
    it = Team(code="IT", name="Công nghệ")
    department = Department(code="CN", name="Khối Công nghệ")
    location = WorkLocation(code="HN", name="Hà Nội")
    db.add_all([it, department, location])
    db.flush()
    make_user(email="btc@company.vn", role=UserRole.ADMIN, full_name="Ban Tổ Chức", employee_code="BTC001")
    an = make_user(
        email="an@company.vn", full_name="An Nguyễn", employee_code="NV001", team_id=it.id,
        phone="0912000001", job_title="Lập trình viên",
    )
    make_user(email="binh@company.vn", full_name="Bình Trần", employee_code="NV002")
    return {"it": it.id, "an": an.id}


@pytest.fixture
def admin(world, auth_headers):
    return auth_headers("btc@company.vn")


def workbook(rows, headers=HEADERS) -> bytes:
    book = Workbook()
    sheet = book.active
    sheet.append(list(headers))
    for row in rows:
        sheet.append(list(row))
    buffer = BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def upload(client, headers, content, *, dry_run=True):
    return client.post(
        URL,
        headers=headers,
        params={"dry_run": str(dry_run).lower()},
        files={"file": ("cbnv.xlsx", content, XLSX_TYPE)},
    )


def errors_by_row(body) -> dict[int, set[str]]:
    result: dict[int, set[str]] = {}
    for error in body["errors"]:
        result.setdefault(error["row"], set()).add(error["code"])
    return result


# Dòng 2: cập nhật chức danh của NV001, ô SĐT trống phải giữ số cũ.
# Dòng 3: người mới — SĐT bị Excel lưu thành số (mất số 0), ngày vào làm là ô ngày.
ROWS = [
    ("NV001", "An Nguyễn", "an@company.vn", "", "", "IT", "Trưởng nhóm kỹ thuật", ""),
    ("NV010", "Chi Lê", "Chi@Company.vn", "Nữ", 912345678, "Công nghệ", "Kiểm thử", datetime(2021, 3, 1)),
]


def test_dry_run_counts_without_writing(client: TestClient, admin, db: Session):
    response = upload(client, admin, workbook(ROWS))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["dry_run"] is True and body["committed"] is False
    assert (body["total_rows"], body["valid_rows"], body["error_count"]) == (2, 2, 0)
    assert (body["to_create"], body["to_update"], body["unchanged"]) == (1, 1, 0)
    assert body["created_accounts"] == []
    assert db.query(User).filter(User.employee_code == "NV010").count() == 0


def test_commit_creates_accounts_once_and_keeps_blank_cells(
    client: TestClient, admin, world, db: Session
):
    response = upload(client, admin, workbook(ROWS), dry_run=False)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["committed"] is True
    [account] = body["created_accounts"]
    assert account["employee_code"] == "NV010"
    assert account["email"] == "chi@company.vn"

    db.expire_all()
    created = db.query(User).filter(User.employee_code == "NV010").one()
    assert created.phone == "0912345678"
    assert created.join_date == "2021-03-01"
    assert created.gender == "female"
    assert created.team_id == world["it"]
    assert created.role == UserRole.EMPLOYEE
    assert created.must_change_password is True

    an = db.get(User, world["an"])
    assert an.job_title == "Trưởng nhóm kỹ thuật"
    assert an.phone == "0912000001"

    # Mật khẩu tạm đăng nhập được, nhưng không nằm trong nhật ký.
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "chi@company.vn", "password": account["temporary_password"]},
    )
    assert login.status_code == 200
    audit = db.query(AuditLog).filter(AuditLog.action == "user.imported").one()
    assert account["temporary_password"] not in (audit.after_data or "")
    assert json.loads(audit.after_data)["created_ids"] == [created.id]

    # Import lại đúng file đó: không còn gì để làm.
    again = upload(client, admin, workbook(ROWS)).json()
    assert (again["to_create"], again["to_update"], again["unchanged"]) == (0, 0, 2)


def test_errors_carry_excel_row_numbers_and_block_commit(client: TestClient, admin, db: Session):
    rows = [
        ("NV020", "Thiếu Email", "", "", "", "", "", ""),  # 2
        ("NV021", "Sai Giới Tính", "a21@company.vn", "Nam giới", "", "", "", ""),  # 3
        ("NV022", "Sai Team", "a22@company.vn", "", "", "Không có team này", "", ""),  # 4
        ("NV022", "Trùng Mã", "a23@company.vn", "", "", "", "", ""),  # 5
        ("NV030", "Chiếm Email", "binh@company.vn", "", "", "", "", ""),  # 6
        ("NV031", "Ngày Sai", "a31@company.vn", "", "", "", "", "31/02/2021"),  # 7
        ("NV032", "Người Tốt", "a32@company.vn", "", "", "", "", ""),  # 8
    ]
    content = workbook(rows)

    body = upload(client, admin, content).json()
    assert errors_by_row(body) == {
        2: {"MISSING_EMAIL"},
        3: {"INVALID_GENDER"},
        4: {"TEAM_NOT_FOUND"},
        5: {"DUPLICATE_IN_FILE"},
        6: {"EMAIL_TAKEN"},
        7: {"INVALID_DATE"},
    }
    assert body["valid_rows"] == 1

    response = upload(client, admin, content, dry_run=False)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "IMPORT_VALIDATION_FAILED"
    assert db.query(User).filter(User.employee_code == "NV032").count() == 0


def test_import_never_grants_or_edits_organizer_accounts(client: TestClient, admin):
    headers = ("Mã NV", "Họ tên", "Email", "Vai trò")
    rows = [
        ("NV002", "Bình Trần", "binh@company.vn", "Ban tổ chức"),  # 2: cấp quyền BTC
        ("BTC001", "Tên Mới", "btc@company.vn", ""),  # 3: sửa tài khoản BTC
        ("BTC001", "Ban Tổ Chức", "btc@company.vn", "admin"),  # 4: trùng mã -> lỗi trùng
        ("NV040", "Trưởng Nhóm", "tn@company.vn", "Trưởng nhóm"),  # 5: hợp lệ
    ]
    body = upload(client, admin, workbook(rows, headers)).json()

    assert errors_by_row(body) == {
        2: {"ROLE_NOT_ALLOWED"},
        3: {"ADMIN_ACCOUNT_PROTECTED"},
        4: {"DUPLICATE_IN_FILE"},
    }


def test_unchanged_organizer_row_is_allowed(client: TestClient, admin):
    headers = ("Mã NV", "Họ tên", "Email", "Vai trò")
    body = upload(
        client, admin, workbook([("BTC001", "Ban Tổ Chức", "btc@company.vn", "Ban tổ chức")], headers)
    ).json()
    assert body["error_count"] == 0
    assert body["unchanged"] == 1


def test_rejects_bad_files(client: TestClient, admin):
    missing = upload(client, admin, workbook([("NV050", "Chỉ Tên")], ("Mã NV", "Họ tên")))
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "MISSING_COLUMNS"
    assert missing.json()["error"]["details"]["missing"] == ["Email"]

    fake = upload(client, admin, b"ma_nv,ho_ten,email\nNV1,A,a@b.vn")
    assert fake.status_code == 400
    assert fake.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


def test_employee_cannot_import(client: TestClient, world, auth_headers):
    headers = auth_headers("an@company.vn")
    assert upload(client, headers, workbook(ROWS)).status_code == 403
