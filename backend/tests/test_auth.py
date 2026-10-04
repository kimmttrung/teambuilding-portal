"""Kiểm thử xác thực: đăng nhập, token, phân quyền, hồ sơ, avatar."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import (
    MAX_FAILED_LOGINS,
    MAX_FAILED_PER_EMAIL_IP,
    MAX_FAILED_PER_IP,
    TOKEN_TYPE_ACCESS,
    create_token_pair,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.auth import LoginAttempt, RefreshToken
from app.models.enums import UserRole

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPG_BYTES = b"\xff\xd8\xff" + b"\x00" * 64

LOGIN_URL = "/api/v1/auth/login"

# Đủ 6 trường `SELF_PROFILE_REQUIRED_FIELDS`: thiếu một trường là PATCH /auth/me bị từ chối.
COMPLETE_PROFILE = {
    "gender": "male",
    "date_of_birth": "1999-05-20",
    "phone": "0912345678",
    "id_card_type": "cccd",
    "id_card_number": "001099012345",
    "id_card_issue_date": "2021-05-20",
}


def post_login(client: TestClient, email: str, password: str, *, ip: str = "10.0.0.1", **headers):
    """Đăng nhập giả lập từ một IP cụ thể.

    `X-Real-IP` là header nginx đặt từ `$remote_addr`; backend tin nó vì không publish
    cổng ra ngoài, mọi request đều phải qua nginx.
    """
    return client.post(
        LOGIN_URL, json={"email": email, "password": password}, headers={"X-Real-IP": ip, **headers}
    )


# --- Băm mật khẩu ---


def test_password_hash_is_salted_and_verifiable():
    first = hash_password("MatKhau123")
    second = hash_password("MatKhau123")
    assert first != second  # salt khác nhau mỗi lần
    assert verify_password("MatKhau123", first)
    assert not verify_password("MatKhau124", first)


def test_verify_password_handles_missing_hash():
    """Tài khoản chỉ dùng SSO chưa có password_hash — không được làm sập request."""
    assert verify_password("bat-ky", None) is False
    assert verify_password("bat-ky", "hash-hong") is False


def test_password_over_bcrypt_limit_is_rejected():
    with pytest.raises(ValueError):
        hash_password("a" * 73)


# --- Token ---


def test_token_payload_has_no_personal_data():
    pair = create_token_pair(user_id=7, role=UserRole.EMPLOYEE)
    payload = decode_token(pair.access_token, expected_type=TOKEN_TYPE_ACCESS)
    assert payload["sub"] == "7"
    assert payload["role"] == UserRole.EMPLOYEE
    assert not {"email", "full_name", "phone"} & payload.keys()


def test_refresh_token_rejected_as_access_token():
    pair = create_token_pair(user_id=1, role=UserRole.EMPLOYEE)
    from app.core.exceptions import UnauthorizedError

    with pytest.raises(UnauthorizedError):
        decode_token(pair.refresh_token, expected_type=TOKEN_TYPE_ACCESS)


# --- Đăng nhập ---


def test_login_returns_tokens_and_profile(client: TestClient, make_user):
    make_user(email="a@company.vn", password="MatKhau123", full_name="Trần Thị B")

    response = client.post(
        "/api/v1/auth/login", json={"email": "a@company.vn", "password": "MatKhau123"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["full_name"] == "Trần Thị B"
    assert "password_hash" not in body["user"]


def test_login_with_wrong_password_is_rejected(client: TestClient, make_user):
    make_user(email="a@company.vn")
    response = client.post(
        "/api/v1/auth/login", json={"email": "a@company.vn", "password": "SaiRoi999"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_unknown_email_gives_same_message_as_wrong_password(client: TestClient, make_user):
    """Không được để lộ email nào có thật trong hệ thống."""
    make_user(email="a@company.vn")
    wrong_password = client.post(
        "/api/v1/auth/login", json={"email": "a@company.vn", "password": "SaiRoi999"}
    )
    unknown_email = client.post(
        "/api/v1/auth/login", json={"email": "khong-ton-tai@company.vn", "password": "SaiRoi999"}
    )
    assert wrong_password.json()["error"] == unknown_email.json()["error"]


def test_account_locks_after_repeated_failures(client: TestClient, make_user):
    """Lớp khoá theo tài khoản vẫn còn, nhưng phải đổi IP mới chạm tới ngưỡng.

    Đúng ý đồ: khoá tài khoản là đòn nặng (ai biết email người khác là khoá được họ)
    nên ngưỡng của nó cao hơn rate limit theo IP — xem docs/09 §5.
    """
    make_user(email="a@company.vn", password="MatKhau123")

    for index in range(MAX_FAILED_LOGINS):
        response = post_login(client, "a@company.vn", "Sai12345", ip=f"10.0.0.{index}")
        assert response.status_code == 401

    # Đúng mật khẩu, từ một IP sạch, vẫn bị chặn vì tài khoản đang khoá tạm.
    response = post_login(client, "a@company.vn", "MatKhau123", ip="10.0.9.9")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "ACCOUNT_LOCKED"


def test_successful_login_resets_failure_counter(client: TestClient, make_user, db):
    user = make_user(email="a@company.vn", password="MatKhau123")
    client.post("/api/v1/auth/login", json={"email": "a@company.vn", "password": "Sai12345"})
    client.post("/api/v1/auth/login", json={"email": "a@company.vn", "password": "MatKhau123"})

    db.refresh(user)
    assert user.failed_login_count == 0
    assert user.last_login_at is not None


# --- Rate limit theo IP (docs/09 §5) ---


def test_same_email_and_ip_blocked_after_five_failures(client: TestClient, make_user):
    make_user(email="a@company.vn", password="MatKhau123")

    for _ in range(MAX_FAILED_PER_EMAIL_IP):
        assert post_login(client, "a@company.vn", "Sai12345").status_code == 401

    # Kể cả mật khẩu đúng: chặn xảy ra TRƯỚC khi so mật khẩu.
    blocked = post_login(client, "a@company.vn", "MatKhau123")
    assert blocked.status_code == 429
    error = blocked.json()["error"]
    assert error["code"] == "TOO_MANY_ATTEMPTS"
    assert error["details"]["retry_after_seconds"] > 0


def test_ip_block_does_not_affect_the_real_user_elsewhere(client: TestClient, make_user):
    """Khoá theo (email, IP) không được biến thành công cụ khoá tài khoản người khác."""
    make_user(email="a@company.vn", password="MatKhau123")

    for _ in range(MAX_FAILED_PER_EMAIL_IP + 2):
        post_login(client, "a@company.vn", "Sai12345", ip="10.0.0.1")

    assert post_login(client, "a@company.vn", "MatKhau123", ip="10.0.0.2").status_code == 200


def test_one_ip_spraying_many_emails_is_blocked(client: TestClient, make_user):
    """Kiểu tấn công lớp khoá tài khoản không thấy: ít lần sai nhưng rải nhiều email."""
    attempts_per_email = MAX_FAILED_PER_EMAIL_IP - 1  # cố ý ở dưới ngưỡng của từng email
    emails = [f"nv{index}@company.vn" for index in range(MAX_FAILED_PER_IP // attempts_per_email)]
    for email in emails:
        make_user(email=email, password="MatKhau123")

    for email in emails:
        for _ in range(attempts_per_email):
            assert post_login(client, email, "Sai12345", ip="10.0.0.9").status_code == 401

    # Chặn cả email chưa từng bị thử từ IP này — giới hạn là của IP, không của tài khoản.
    blocked = post_login(client, "nguoi-khac@company.vn", "MatKhau123", ip="10.0.0.9")
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "TOO_MANY_ATTEMPTS"

    # Người dùng thật ở IP khác không bị vạ lây.
    assert post_login(client, emails[0], "MatKhau123", ip="10.0.0.8").status_code == 200


def test_forged_forwarded_for_header_does_not_bypass_the_limit(
    client: TestClient, make_user, db
):
    """Kẻ tấn công tự gửi X-Forwarded-For để giả IP mỗi lần — nginx nối IP thật vào cuối."""
    make_user(email="a@company.vn", password="MatKhau123")

    for index in range(MAX_FAILED_PER_EMAIL_IP):
        response = client.post(
            LOGIN_URL,
            json={"email": "a@company.vn", "password": "Sai12345"},
            headers={"X-Forwarded-For": f"9.9.9.{index}, 10.0.0.7"},
        )
        assert response.status_code == 401

    blocked = client.post(
        LOGIN_URL,
        json={"email": "a@company.vn", "password": "MatKhau123"},
        headers={"X-Forwarded-For": "9.9.9.250, 10.0.0.7"},
    )
    assert blocked.status_code == 429
    # Chỉ IP do proxy nối vào mới được ghi; phần client tự bịa bị bỏ qua hoàn toàn.
    assert {row.ip_address for row in db.scalars(select(LoginAttempt))} == {"10.0.0.7"}


def test_real_ip_header_wins_over_forwarded_for(client: TestClient, make_user, db):
    make_user(email="a@company.vn", password="MatKhau123")

    post_login(client, "a@company.vn", "Sai12345", ip="10.0.0.5", **{"X-Forwarded-For": "1.2.3.4"})

    assert db.scalar(select(LoginAttempt.ip_address)) == "10.0.0.5"


def test_successful_login_clears_the_ip_counter(client: TestClient, make_user):
    make_user(email="a@company.vn", password="MatKhau123")

    for _ in range(MAX_FAILED_PER_EMAIL_IP - 1):
        post_login(client, "a@company.vn", "Sai12345")
    assert post_login(client, "a@company.vn", "MatKhau123").status_code == 200

    # Bộ đếm đã về 0: lại sai được đủ ngưỡng mới bị chặn, không phải sai một lần là chặn.
    for _ in range(MAX_FAILED_PER_EMAIL_IP - 1):
        assert post_login(client, "a@company.vn", "Sai12345").status_code == 401


def test_disabled_account_cannot_login(client: TestClient, make_user):
    make_user(email="a@company.vn", password="MatKhau123", is_active=False)
    response = client.post(
        "/api/v1/auth/login", json={"email": "a@company.vn", "password": "MatKhau123"}
    )
    assert response.json()["error"]["code"] == "ACCOUNT_DISABLED"


def test_expired_lock_starts_a_new_failure_cycle(client, make_user, db):
    user = make_user(
        failed_login_count=MAX_FAILED_LOGINS, locked_until="2020-01-01T00:00:00+00:00"
    )
    response = post_login(client, user.email, "WrongPassword123")
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"
    db.refresh(user)
    assert user.failed_login_count == 1
    assert user.locked_until is None


def test_login_rejects_password_over_bcrypt_byte_limit(client, make_user):
    make_user(password="a" * 71 + "1")
    response = post_login(client, "nhanvien@company.vn", "a" * 71 + "1extra")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


# --- /auth/me ---


def test_me_requires_token(client: TestClient):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "NOT_AUTHENTICATED"


def test_me_returns_own_profile(client: TestClient, make_user, auth_headers):
    make_user(email="a@company.vn", password="MatKhau123", employee_code="NV001")
    response = client.get("/api/v1/auth/me", headers=auth_headers("a@company.vn"))
    assert response.status_code == 200
    assert response.json()["employee_code"] == "NV001"


def test_garbage_token_is_rejected(client: TestClient):
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer khong-phai-jwt"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TOKEN_INVALID"


def test_update_profile_persists_and_computes_can_fly(client: TestClient, make_user, auth_headers):
    make_user(email="a@company.vn", password="MatKhau123")
    headers = auth_headers("a@company.vn")

    assert client.get("/api/v1/auth/me", headers=headers).json()["can_fly"] is False

    response = client.patch(
        "/api/v1/auth/me",
        headers=headers,
        json=COMPLETE_PROFILE | {"address": "12 Nguyễn Trãi, Hà Nội", "shirt_size": "L"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["phone"] == "0912345678"
    assert body["can_fly"] is True

    # Hồ sơ đã đủ thì sửa lẻ một trường tuỳ chọn vẫn được.
    response = client.patch("/api/v1/auth/me", headers=headers, json={"display_name": "A IT"})
    assert response.status_code == 200
    assert response.json()["display_name"] == "A IT"


def test_update_profile_requires_travel_documents(client: TestClient, make_user, auth_headers, db):
    """Điền mỗi tên thì không lưu được: thiếu trường bắt buộc là từ chối cả lần lưu."""
    user = make_user(email="a@company.vn", password="MatKhau123")
    headers = auth_headers("a@company.vn")

    response = client.patch(
        "/api/v1/auth/me", headers=headers, json={"display_name": "A IT", "phone": "0912345678"}
    )
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "PROFILE_REQUIRED_FIELDS"
    assert error["details"]["missing_fields"] == [
        "Giới tính", "Ngày sinh", "Loại giấy tờ", "Số CCCD/Hộ chiếu", "Ngày cấp",
    ]
    db.refresh(user)
    assert user.display_name is None and user.phone is None

    # Xoá một trường bắt buộc của hồ sơ đang đủ cũng bị từ chối.
    assert client.patch("/api/v1/auth/me", headers=headers, json=COMPLETE_PROFILE).status_code == 200
    response = client.patch("/api/v1/auth/me", headers=headers, json={"id_card_issue_date": None})
    assert response.status_code == 400
    assert response.json()["error"]["details"]["missing_fields"] == ["Ngày cấp"]


def test_temporary_password_blocks_everything_but_changing_it(
    client: TestClient, make_user, auth_headers
):
    make_user(email="moi@company.vn", password="MatKhauTam1", must_change_password=True)
    headers = auth_headers("moi@company.vn", "MatKhauTam1")

    # Vẫn xem được mình là ai (frontend cần cờ `must_change_password`), còn lại bị chặn.
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200 and me.json()["must_change_password"] is True
    for method, path, payload in (
        ("patch", "/api/v1/auth/me", COMPLETE_PROFILE),
        ("get", "/api/v1/admin/users", None),
    ):
        blocked = client.request(method, path, headers=headers, json=payload)
        assert blocked.status_code == 403, path
        assert blocked.json()["error"]["code"] == "PASSWORD_CHANGE_REQUIRED"

    changed = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": "MatKhauTam1", "new_password": "MatKhauMoi456"},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["user"]["must_change_password"] is False

    new_headers = {"Authorization": f"Bearer {changed.json()['access_token']}"}
    assert client.patch("/api/v1/auth/me", headers=new_headers, json=COMPLETE_PROFILE).status_code == 200


def test_profile_update_rejects_privileged_fields(client: TestClient, make_user, auth_headers):
    """CBNV không được tự nâng quyền cho mình."""
    make_user(email="a@company.vn", password="MatKhau123")
    response = client.patch(
        "/api/v1/auth/me",
        headers=auth_headers("a@company.vn"),
        json={"role": "super_admin"},
    )
    assert response.status_code == 422


def test_invalid_date_format_is_rejected(client: TestClient, make_user, auth_headers):
    make_user(email="a@company.vn", password="MatKhau123")
    response = client.patch(
        "/api/v1/auth/me",
        headers=auth_headers("a@company.vn"),
        json={"date_of_birth": "20/05/1999"},
    )
    assert response.status_code == 422


# --- Refresh & logout ---


def test_refresh_returns_new_tokens(client: TestClient, make_user):
    make_user(email="a@company.vn", password="MatKhau123")
    login = client.post(
        "/api/v1/auth/login", json={"email": "a@company.vn", "password": "MatKhau123"}
    ).json()

    response = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]}
    )
    assert response.status_code == 200
    assert response.json()["access_token"] != login["access_token"]


def test_refresh_token_cannot_be_reused(client: TestClient, make_user):
    """Xoay vòng token: dùng lại token cũ là dấu hiệu bị đánh cắp."""
    make_user(email="a@company.vn", password="MatKhau123")
    login = client.post(
        "/api/v1/auth/login", json={"email": "a@company.vn", "password": "MatKhau123"}
    ).json()

    client.post("/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]})
    replay = client.post("/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]})

    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "SESSION_REVOKED"


def test_logout_revokes_session(client: TestClient, make_user):
    make_user(email="a@company.vn", password="MatKhau123")
    login = client.post(
        "/api/v1/auth/login", json={"email": "a@company.vn", "password": "MatKhau123"}
    ).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}

    client.post("/api/v1/auth/logout", headers=headers, json={"refresh_token": login["refresh_token"]})
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert response.status_code == 401


def test_change_password_invalidates_other_sessions(client: TestClient, make_user):
    make_user(email="a@company.vn", password="MatKhau123")
    login = client.post(
        "/api/v1/auth/login", json={"email": "a@company.vn", "password": "MatKhau123"}
    ).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}

    response = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": "MatKhau123", "new_password": "MatKhauMoi456"},
    )
    assert response.status_code == 200

    # Phiên cũ chết
    assert (
        client.post("/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]})
        .status_code
        == 401
    )
    # Mật khẩu mới dùng được
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "a@company.vn", "password": "MatKhauMoi456"}
        ).status_code
        == 200
    )


def test_change_password_requires_letter_and_digit(client: TestClient, make_user, auth_headers):
    make_user(email="a@company.vn", password="MatKhau123")
    response = client.post(
        "/api/v1/auth/change-password",
        headers=auth_headers("a@company.vn"),
        json={"current_password": "MatKhau123", "new_password": "khongcochuso"},
    )
    assert response.status_code == 422


def test_first_password_change_returns_a_refreshable_session(client, make_user, db):
    make_user(email="first@company.vn", must_change_password=True)
    original = post_login(client, "first@company.vn", "MatKhau123").json()
    other = post_login(client, "first@company.vn", "MatKhau123").json()
    assert original["user"]["must_change_password"] is True
    response = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {original['access_token']}"},
        json={"current_password": "MatKhau123", "new_password": "NewPassword456"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user"]["must_change_password"] is False
    assert "password_hash" not in body["user"]
    for old in (original, other):
        revoked = client.post("/api/v1/auth/refresh", json={"refresh_token": old["refresh_token"]})
        assert revoked.json()["error"]["code"] == "SESSION_REVOKED"
    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert refreshed.status_code == 200
    active = list(db.scalars(select(RefreshToken).where(RefreshToken.revoked_at.is_(None))))
    assert len(active) == 1


@pytest.mark.parametrize("current,new,status,code", [
    ("WrongPassword123", "NewPassword456", 401, "INVALID_CREDENTIALS"),
    ("MatKhau123", "MatKhau123", 409, "PASSWORD_UNCHANGED"),
    ("MatKhau123", "Short1", 422, "VALIDATION_ERROR"),
    ("MatKhau123", "a1" + "á" * 36, 422, "VALIDATION_ERROR"),
])
def test_change_password_errors_do_not_revoke_session(
    client, make_user, current, new, status, code,
):
    make_user(must_change_password=True)
    original = post_login(client, "nhanvien@company.vn", "MatKhau123").json()
    headers = {"Authorization": f"Bearer {original['access_token']}"}
    response = client.post("/api/v1/auth/change-password", headers=headers,
        json={"current_password": current, "new_password": new})
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert client.get("/api/v1/auth/me", headers=headers).json()["must_change_password"] is True
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": original["refresh_token"]}).status_code == 200


@pytest.mark.parametrize("field", ["date_of_birth", "id_card_issue_date"])
def test_profile_rejects_impossible_calendar_dates(client, make_user, auth_headers, field):
    make_user()
    response = client.patch(
        "/api/v1/auth/me", headers=auth_headers(), json={field: "2026-02-30"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_concurrent_refresh_only_issues_one_replacement(client, make_user, engine):
    from sqlalchemy.orm import Session

    from app.core.exceptions import UnauthorizedError
    from app.services.auth_service import refresh_tokens

    make_user()
    token = post_login(client, "nhanvien@company.vn", "MatKhau123").json()["refresh_token"]

    def refresh():
        with Session(engine) as session:
            try:
                refresh_tokens(session, refresh_token=token)
                return "OK"
            except UnauthorizedError as exc:
                return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: refresh(), range(2))) == ["OK", "SESSION_REVOKED"]


# --- Phân quyền ---


def test_require_role_blocks_employee(client: TestClient, make_user, auth_headers):
    from fastapi import Depends

    from app.core.dependencies import require_admin
    from app.main import app

    @app.get("/api/v1/_test/admin-only", dependencies=[Depends(require_admin)])
    def _admin_only():
        return {"ok": True}

    make_user(email="nv@company.vn", password="MatKhau123", role=UserRole.EMPLOYEE)
    make_user(email="btc@company.vn", password="MatKhau123", role=UserRole.ADMIN)

    denied = client.get("/api/v1/_test/admin-only", headers=auth_headers("nv@company.vn"))
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "PERMISSION_DENIED"

    allowed = client.get("/api/v1/_test/admin-only", headers=auth_headers("btc@company.vn"))
    assert allowed.status_code == 200


def test_role_change_takes_effect_without_new_login(client: TestClient, make_user, db):
    """Token cũ mang role cũ, nhưng quyền phải lấy theo database."""
    user = make_user(email="a@company.vn", password="MatKhau123", role=UserRole.EMPLOYEE)
    login = client.post(
        "/api/v1/auth/login", json={"email": "a@company.vn", "password": "MatKhau123"}
    ).json()

    user.role = UserRole.ADMIN
    db.commit()

    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {login['access_token']}"}
    )
    assert response.json()["role"] == UserRole.ADMIN


# --- Avatar ---


def test_upload_avatar_accepts_png(client: TestClient, make_user, auth_headers):
    make_user(email="a@company.vn", password="MatKhau123")
    response = client.post(
        "/api/v1/auth/me/avatar",
        headers=auth_headers("a@company.vn"),
        files={"file": ("anh.png", PNG_BYTES, "image/png")},
    )
    assert response.status_code == 201
    assert response.json()["avatar_url"].startswith("/uploads/avatar_")


def test_upload_avatar_rejects_disguised_file(client: TestClient, make_user, auth_headers):
    """Đổi đuôi file thành .png không qua được: kiểm tra magic bytes, không tin tên file."""
    make_user(email="a@company.vn", password="MatKhau123")
    response = client.post(
        "/api/v1/auth/me/avatar",
        headers=auth_headers("a@company.vn"),
        files={"file": ("virus.png", b"MZ\x90\x00 day la file exe", "image/png")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


def test_upload_avatar_rejects_oversized_file(client: TestClient, make_user, auth_headers):
    make_user(email="a@company.vn", password="MatKhau123")
    huge = JPG_BYTES + b"\x00" * (3 * 1024 * 1024)
    response = client.post(
        "/api/v1/auth/me/avatar",
        headers=auth_headers("a@company.vn"),
        files={"file": ("to.jpg", huge, "image/jpeg")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"
