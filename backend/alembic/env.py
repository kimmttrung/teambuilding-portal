"""Cấu hình Alembic cho dự án.

Hai điểm khác mặc định:
1. URL database lấy từ app.core.config (một nguồn cấu hình duy nhất), không hard-code
   trong alembic.ini.
2. render_as_batch=True — bắt buộc với SQLite, vì SQLite không hỗ trợ ALTER COLUMN /
   DROP CONSTRAINT. Alembic sẽ tạo bảng mới, copy dữ liệu rồi đổi tên.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings

# Import để mọi model được đăng ký vào Base.metadata trước khi autogenerate chạy.
from app.models import Base  # noqa: F401
import app.models  # noqa: F401, E402  (đảm bảo nạp hết module con)

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Sinh câu lệnh SQL ra stdout thay vì chạy trực tiếp."""
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Chạy migration trực tiếp trên database."""
    settings.ensure_directories()
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # bắt buộc với SQLite
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
