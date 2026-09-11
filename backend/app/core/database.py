"""Engine, session và các PRAGMA bắt buộc của SQLite.

Đọc kèm: docs/03-data-model.md §11.
"""

import logging
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)

# check_same_thread=False: FastAPI chạy request trên nhiều thread khác nhau.
# Session vẫn được tạo/đóng theo từng request nên không dùng chung connection.
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=settings.SQL_ECHO and not settings.is_production,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@event.listens_for(Engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
    """Áp PRAGMA cho MỖI connection.

    Đây không phải tối ưu hoá — thiếu `foreign_keys=ON` thì SQLite bỏ qua toàn bộ
    khoá ngoại và dữ liệu sẽ mồ côi trong im lặng.
    """
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")     # SQLite mặc định TẮT
        cursor.execute("PRAGMA journal_mode=WAL")    # cho đọc song song khi đang ghi
        cursor.execute("PRAGMA synchronous=NORMAL")  # đủ an toàn khi đã bật WAL
        cursor.execute("PRAGMA busy_timeout=5000")   # chờ 5s thay vì ném 'database is locked'
        cursor.execute("PRAGMA temp_store=MEMORY")
    finally:
        cursor.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: mở session cho một request, luôn đóng khi xong."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Dùng ngoài request (script, background task): tự commit / rollback."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def immediate_transaction(db: Session) -> Generator[Session, None, None]:
    """Transaction giành write-lock ngay từ đầu (BEGIN IMMEDIATE).

    Dùng cho thao tác có tranh chấp: giữ/xác nhận ghế Gala, đổi chuyến bay.
    Nếu để SQLAlchemy mở transaction đọc rồi mới nâng lên ghi, hai request đồng thời
    có thể cùng đọc "còn chỗ" rồi cùng ghi -> vượt slot.
    """
    db.rollback()  # đảm bảo chưa có transaction đọc nào đang mở
    db.execute(text("BEGIN IMMEDIATE"))
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise


def check_database() -> dict[str, object]:
    """Kiểm tra kết nối + xác nhận PRAGMA thực sự có hiệu lực. Dùng cho /health."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            foreign_keys = conn.execute(text("PRAGMA foreign_keys")).scalar()
            journal_mode = conn.execute(text("PRAGMA journal_mode")).scalar()
        return {
            "connected": True,
            "foreign_keys": bool(foreign_keys),
            "journal_mode": journal_mode,
            "path": str(settings.sqlite_path),
        }
    except Exception as exc:  # pragma: no cover - chỉ chạy khi DB hỏng
        logger.exception("Kiểm tra database thất bại")
        return {"connected": False, "error": str(exc)}
