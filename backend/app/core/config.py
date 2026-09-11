"""Cấu hình ứng dụng, đọc từ biến môi trường / file .env."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> backend/
BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Mọi giá trị cấu hình của backend.

    Thứ tự ưu tiên: biến môi trường thật > backend/.env > .env ở gốc repo.
    """

    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App ---
    APP_NAME: str = "TeamBuilding Portal"
    APP_ENV: str = "development"  # development | production
    APP_VERSION: str = "0.1.0"
    API_PREFIX: str = "/api/v1"
    DEBUG: bool = True
    SQL_ECHO: bool = False  # bật để xem câu SQL sinh ra khi debug
    TZ: str = "Asia/Ho_Chi_Minh"

    # --- Database ---
    DATABASE_URL: str = "sqlite:///./data/sqlite/teambuilding.db"

    # --- Auth (dùng từ bước 4) ---
    JWT_SECRET_KEY: str = "change-me-before-deploy"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --- CORS ---
    CORS_ORIGINS: list[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"]
    )

    # --- Email ---
    EMAIL_ENABLED: bool = False
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_NAME: str = "BTC Team Building"
    SMTP_FROM_EMAIL: str = "noreply@company.vn"
    APP_PUBLIC_URL: str = "http://localhost:3000"

    # --- RAG / LLM ---
    ANTHROPIC_API_KEY: str = ""
    LLM_MODEL: str = "claude-opus-5"
    LLM_MAX_TOKENS: int = 4096
    CHROMA_PERSIST_DIR: str = "./data/chromadb"
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    RAG_TOP_K: int = 5
    RAG_SCORE_THRESHOLD: float = 0.35
    CHAT_RATE_LIMIT_PER_10MIN: int = 20

    # --- Upload ---
    UPLOAD_DIR: str = "./data/uploads"
    MAX_UPLOAD_MB: int = 2

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, value):
        """Cho phép khai báo dạng 'a,b,c' trong .env."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    # --- Tiện ích ---

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"

    @property
    def sqlite_path(self) -> Path:
        """Đường dẫn tuyệt đối tới file SQLite (đường dẫn tương đối tính từ backend/)."""
        raw = self.DATABASE_URL.split("///", 1)[-1]
        path = Path(raw)
        return path if path.is_absolute() else (BACKEND_DIR / path).resolve()

    @property
    def chroma_path(self) -> Path:
        path = Path(self.CHROMA_PERSIST_DIR)
        return path if path.is_absolute() else (BACKEND_DIR / path).resolve()

    @property
    def upload_path(self) -> Path:
        path = Path(self.UPLOAD_DIR)
        return path if path.is_absolute() else (BACKEND_DIR / path).resolve()

    def ensure_directories(self) -> None:
        """Tạo sẵn các thư mục dữ liệu để lần ghi đầu tiên không lỗi."""
        for path in (self.sqlite_path.parent, self.chroma_path, self.upload_path):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Cache lại để không đọc .env nhiều lần; dùng làm FastAPI dependency được."""
    return Settings()


settings = get_settings()
