"""Kiểm thử đọc cấu hình từ .env.

Bài học đã trả giá: `CORS_ORIGINS` là `list[str]`, và pydantic-settings chạy json.loads
cho field kiểu phức tạp NGAY khi đọc .env — trước mọi validator. Thiếu `NoDecode` thì
dòng `CORS_ORIGINS=a,b` trong .env làm backend chết lúc khởi động, và bug đó chỉ lộ ra
khi có file .env thật (repo trước đó chỉ có .env.example).
"""

import pytest

from app.core.config import DEV_JWT_SECRET, Settings


def settings_from_env(monkeypatch, **env) -> Settings:
    """Dựng Settings từ biến môi trường, bỏ qua mọi file .env của máy đang chạy."""
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return Settings(_env_file=None)


def test_cors_origins_accepts_comma_separated(monkeypatch):
    settings = settings_from_env(
        monkeypatch, CORS_ORIGINS="http://localhost:5173,http://localhost:3000"
    )
    assert settings.CORS_ORIGINS == ["http://localhost:5173", "http://localhost:3000"]


def test_cors_origins_accepts_json_list(monkeypatch):
    settings = settings_from_env(monkeypatch, CORS_ORIGINS='["http://a","http://b"]')
    assert settings.CORS_ORIGINS == ["http://a", "http://b"]


def test_cors_origins_trims_spaces_and_empty_entries(monkeypatch):
    settings = settings_from_env(monkeypatch, CORS_ORIGINS=" http://a , , http://b ,")
    assert settings.CORS_ORIGINS == ["http://a", "http://b"]


def test_cors_origins_rejects_broken_json(monkeypatch):
    with pytest.raises(ValueError, match="JSON"):
        settings_from_env(monkeypatch, CORS_ORIGINS='["http://a", ')


def test_email_flags_read_from_env(monkeypatch):
    settings = settings_from_env(
        monkeypatch,
        EMAIL_ENABLED="true",
        SMTP_HOST="smtp.gmail.com",
        SMTP_PORT="465",
        SMTP_STARTTLS="false",
    )
    assert settings.EMAIL_ENABLED is True
    assert settings.SMTP_PORT == 465
    assert settings.SMTP_STARTTLS is False


def test_enabled_email_requires_host_and_sender(monkeypatch):
    """Bật email mà bỏ trống SMTP_FROM_EMAIL thì thư đi ra với người gửi rỗng —
    SMTP local vẫn nhận nên lỗi trôi qua, còn Gmail chối."""
    with pytest.raises(ValueError, match="SMTP_FROM_EMAIL"):
        settings_from_env(
            monkeypatch, EMAIL_ENABLED="true", SMTP_HOST="127.0.0.1", SMTP_FROM_EMAIL=""
        )

    with pytest.raises(ValueError, match="SMTP_HOST"):
        settings_from_env(
            monkeypatch, EMAIL_ENABLED="true", SMTP_HOST="", SMTP_FROM_EMAIL="a@b.vn"
        )


def test_disabled_email_allows_empty_smtp_config(monkeypatch):
    """Chế độ dev chỉ ghi log thì không cần khai SMTP gì cả."""
    settings = settings_from_env(
        monkeypatch, EMAIL_ENABLED="false", SMTP_HOST="", SMTP_FROM_EMAIL=""
    )
    assert settings.EMAIL_ENABLED is False


def test_empty_jwt_secret_is_rejected_in_any_environment(monkeypatch):
    """Dòng `JWT_SECRET_KEY=` bỏ trống trong .env từng làm mọi lần login trả 500."""
    with pytest.raises(ValueError, match="rỗng"):
        settings_from_env(monkeypatch, APP_ENV="development", JWT_SECRET_KEY="")


def test_short_jwt_secret_only_warns_in_development(monkeypatch):
    settings = settings_from_env(monkeypatch, APP_ENV="development", JWT_SECRET_KEY="ngan")
    assert settings.JWT_SECRET_KEY == "ngan"


def test_production_rejects_default_jwt_secret(monkeypatch):
    with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
        settings_from_env(monkeypatch, APP_ENV="production", JWT_SECRET_KEY=DEV_JWT_SECRET)


def test_production_rejects_short_jwt_secret(monkeypatch):
    with pytest.raises(ValueError, match="32 byte"):
        settings_from_env(monkeypatch, APP_ENV="production", JWT_SECRET_KEY="qua-ngan")
