"""Kiểm tra khung ứng dụng: health check, PRAGMA SQLite, khuôn dạng lỗi."""

from sqlalchemy import text

from app.core.database import engine


def test_health_returns_ok(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"]["connected"] is True


def test_sqlite_foreign_keys_are_enabled():
    """FK bị tắt là lỗi âm thầm nguy hiểm nhất của SQLite — phải có test canh."""
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_sqlite_uses_wal_journal_mode():
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA journal_mode")).scalar().lower() == "wal"


def test_unknown_route_returns_standard_error_shape(client):
    response = client.get("/api/v1/khong-ton-tai")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "NOT_FOUND"
    assert "message" in body["error"]
