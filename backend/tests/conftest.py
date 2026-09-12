"""Fixture dùng chung cho test.

Mỗi test chạy trên một file SQLite riêng trong thư mục tạm, không đụng DB dev.
"""

import os

# Chốt cấu hình TRƯỚC khi import app: `settings` được dựng ngay lúc import module
# config, và nó đọc file .env của máy đang chạy. Không chặn thì cấu hình cá nhân của
# từng người (khoá JWT rỗng, EMAIL_ENABLED=true trỏ Gmail thật) làm test đỏ hoặc
# tệ hơn là gửi email thật. Biến môi trường có ưu tiên cao hơn file .env.
os.environ.update(
    {
        "APP_ENV": "development",
        "JWT_SECRET_KEY": "khoa-chi-dung-cho-test-du-dai-de-vuot-32-byte-0123456789",
        "EMAIL_ENABLED": "false",
        "SMTP_HOST": "",
        "SMTP_USER": "",
        "SMTP_PASSWORD": "",
        # Phải chốt CẢ hai khoá này: ai đó đặt SMTP_STARTTLS=false trong .env để thử
        # Mailpit là test khẳng định "có gọi STARTTLS" sẽ đỏ, dù code không hề sai.
        "SMTP_STARTTLS": "true",
        "SMTP_PORT": "587",
    }
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import get_db
from app.core.security import hash_password
from app.main import app
from app.models import Base, User
from app.models.enums import UserRole


@pytest.fixture
def engine(tmp_path):
    """Engine SQLite tạm, bật PRAGMA giống môi trường thật."""
    test_engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )

    @event.listens_for(test_engine, "connect")
    def _pragma(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(test_engine)
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def db(engine) -> Session:
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with factory() as session:
        yield session


@pytest.fixture
def client(engine, tmp_path, monkeypatch) -> TestClient:
    """TestClient dùng DB tạm và thư mục upload tạm."""
    from app.core.config import settings

    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setattr(type(settings), "upload_path", property(lambda _: upload_dir))

    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def _override_get_db():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    # BackgroundTask (gửi email) chạy sau khi response trả về, lúc đó session của
    # request đã đóng nên nó tự mở session mới qua `database.SessionLocal`. Không thay
    # luôn biến đó thì test sẽ ghi thật vào DB dev — `get_db` override không chặn được.
    monkeypatch.setattr("app.core.database.SessionLocal", factory)

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def make_user(db: Session):
    """Tạo user với mật khẩu đã băm sẵn."""

    def _make(
        email: str = "nhanvien@company.vn",
        password: str = "MatKhau123",
        role: UserRole = UserRole.EMPLOYEE,
        **kwargs,
    ) -> User:
        user = User(
            email=email,
            full_name=kwargs.pop("full_name", "Nguyễn Văn A"),
            password_hash=hash_password(password),
            role=role,
            **kwargs,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return _make


@pytest.fixture
def auth_headers(client: TestClient):
    """Đăng nhập và trả header Authorization."""

    def _login(email: str = "nhanvien@company.vn", password: str = "MatKhau123") -> dict[str, str]:
        response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return _login
