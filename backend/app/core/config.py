"""Cấu hình ứng dụng, đọc từ biến môi trường / file .env."""

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

logger = logging.getLogger(__name__)

# backend/app/core/config.py -> backend/
BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent

MIN_JWT_SECRET_BYTES = 32
DEV_JWT_SECRET = "dev-only-khong-dung-cho-production-doi-truoc-khi-deploy"


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

    # --- Auth ---
    # HS256 yêu cầu khoá >= 32 byte (RFC 7518). Giá trị này chỉ dùng khi dev;
    # `_reject_default_secret_in_production` chặn nó ở môi trường production.
    JWT_SECRET_KEY: str = DEV_JWT_SECRET
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --- CORS ---
    # `NoDecode` là bắt buộc, không phải cho đẹp: với field kiểu phức tạp (list/dict),
    # pydantic-settings chạy json.loads NGAY khi đọc từ .env, TRƯỚC mọi validator.
    # Không có nó thì `CORS_ORIGINS=a,b` trong .env làm app chết lúc khởi động với
    # SettingsError, và `_split_origins` bên dưới không bao giờ được gọi.
    CORS_ORIGINS: Annotated[list[str], NoDecode] = Field(
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
    # Tắt khi dùng SMTP local để thử (Mailpit, MailHog) hoặc relay nội bộ cổng 25 —
    # những server đó không nói STARTTLS và sẽ ném lỗi ngay ở bước bắt tay.
    # Cổng 465 luôn dùng TLS ngay từ đầu, cờ này không ảnh hưởng.
    SMTP_STARTTLS: bool = True
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

    @model_validator(mode="after")
    def _reject_default_secret_in_production(self) -> "Settings":
        """Khoá JWT yếu ở production nghĩa là ai cũng ký được token admin."""
        # Chặn khoá rỗng ở MỌI môi trường. Một dòng `JWT_SECRET_KEY=` không có giá trị
        # trong .env sẽ đè lên default của code, và lỗi chỉ hiện ra lúc ai đó đăng nhập:
        # PyJWT ném "HMAC key must not be empty" -> login trả 500 không rõ nguyên nhân.
        # Thà chết ngay lúc khởi động với thông điệp nói rõ phải làm gì.
        if not self.JWT_SECRET_KEY.strip():
            raise ValueError(
                "JWT_SECRET_KEY đang rỗng (kiểm tra dòng JWT_SECRET_KEY= trong .env). "
                "Sinh khoá mới: "
                'py -3.13 -c "import secrets; print(secrets.token_urlsafe(48))"'
            )

        # Bật email mà bỏ trống cấu hình thì thư đi ra với người gửi rỗng
        # ("BTC Team Building <>"): SMTP local vẫn nhận nên tưởng là chạy được, còn
        # Gmail chối hoặc đẩy vào spam. Dòng `SMTP_FROM_EMAIL=` trống trong .env đè
        # lên default của code, nên chỉ có cách chặn ở đây.
        if self.EMAIL_ENABLED:
            missing = [
                name
                for name in ("SMTP_HOST", "SMTP_FROM_EMAIL")
                if not getattr(self, name).strip()
            ]
            if missing:
                raise ValueError(
                    f"EMAIL_ENABLED=true nhưng {' và '.join(missing)} đang rỗng trong .env. "
                    "Điền giá trị, hoặc đặt EMAIL_ENABLED=false để chỉ ghi log."
                )

        if not self.is_production:
            if len(self.JWT_SECRET_KEY.encode()) < MIN_JWT_SECRET_BYTES:
                logger.warning(
                    "JWT_SECRET_KEY ngắn hơn %d byte — chạy dev thì được, deploy thì phải đổi.",
                    MIN_JWT_SECRET_BYTES,
                )
            return self
        if self.JWT_SECRET_KEY == DEV_JWT_SECRET:
            raise ValueError(
                "JWT_SECRET_KEY vẫn là giá trị mặc định. Sinh khoá mới: "
                'python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        if len(self.JWT_SECRET_KEY.encode()) < MIN_JWT_SECRET_BYTES:
            raise ValueError(
                f"JWT_SECRET_KEY phải dài ít nhất {MIN_JWT_SECRET_BYTES} byte (HS256, RFC 7518)."
            )
        return self

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, value):
        """Nhận cả hai cách viết trong .env: 'a,b,c' và '["a","b"]'.

        Dạng danh sách phẩy là cách người ta viết .env theo bản năng (và là dạng ở
        .env.example); dạng JSON là dạng pydantic-settings vốn hiểu. Đỡ cả hai để
        không ai phải nhớ đúng một kiểu duy nhất.
        """
        if not isinstance(value, str):
            return value

        text = value.strip()
        if text.startswith("["):
            try:
                return json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"CORS_ORIGINS không phải JSON hợp lệ: {exc}") from exc
        return [origin.strip() for origin in text.split(",") if origin.strip()]

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
