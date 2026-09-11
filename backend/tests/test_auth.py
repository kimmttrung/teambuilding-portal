"""Kiểm thử xác thực: đăng nhập, token, phân quyền, hồ sơ, avatar."""

import pytest
from fastapi.testclient import TestClient

from app.core.security import (
    MAX_FAILED_LOGINS,
    TOKEN_TYPE_ACCESS,
    create_token_pair,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.enums import UserRole

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPG_BYTES = b"\xff\xd8\xff" + b"\x00" * 64


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
    make_user(email="a@company.vn", password="MatKhau123")

    for _ in range(MAX_FAILED_LOGINS):
        client.post("/api/v1/auth/login", json={"email": "a@company.vn", "password": "Sai12345"})

    # Đúng mật khẩu vẫn bị chặn vì tài khoản đang khoá tạm.
    response = client.post(
        "/api/v1/auth/login", json={"email": "a@company.vn", "password": "MatKhau123"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "ACCOUNT_LOCKED"


def test_successful_login_resets_failure_counter(client: TestClient, make_user, db):
    user = make_user(email="a@company.vn", password="MatKhau123")
    client.post("/api/v1/auth/login", json={"email": "a@company.vn", "password": "Sai12345"})
    client.post("/api/v1/auth/login", json={"email": "a@company.vn", "password": "MatKhau123"})

    db.refresh(user)
    assert user.failed_login_count == 0
    assert user.last_login_at is not None


def test_disabled_account_cannot_login(client: TestClient, make_user):
    make_user(email="a@company.vn", password="MatKhau123", is_active=False)
    response = client.post(
        "/api/v1/auth/login", json={"email": "a@company.vn", "password": "MatKhau123"}
    )
    assert response.json()["error"]["code"] == "ACCOUNT_DISABLED"


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
        json={
            "phone": "0912345678",
            "address": "12 Nguyễn Trãi, Hà Nội",
            "id_card_number": "001099012345",
            "date_of_birth": "1999-05-20",
            "shirt_size": "L",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["phone"] == "0912345678"
    assert body["can_fly"] is True


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


# --- Phân quyền ---


def test_require_role_blocks_employee(client: TestClient, make_user, auth_headers):
    from app.core.dependencies import require_admin
    from fastapi import Depends

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
