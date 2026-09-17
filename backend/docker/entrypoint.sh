#!/bin/sh
# Khởi động backend trong container.
#   serve (mặc định) : migration → seed dữ liệu mẫu nếu DB còn trống → uvicorn.
#   lệnh bất kỳ      : chạy thẳng, ví dụ `python scripts/seed.py --reset`.
set -eu

mkdir -p /app/data/sqlite /app/data/uploads /app/data/chromadb /app/data/backups

if [ "${1:-serve}" = "serve" ]; then
  echo "[entrypoint] alembic upgrade head"
  alembic upgrade head

  # Seed MỘT lần, chỉ khi DB chưa có kỳ nào. Người clone dự án chạy một lệnh là có dữ liệu để test;
  # còn khởi động lại container thì KHÔNG nạp lại — nạp lại là xoá sạch những gì tester đang làm dở.
  # Muốn làm lại từ đầu: `docker compose down -v` (xoá volume) rồi `up` lại.
  if [ "${SEED_ON_START:-1}" = "1" ]; then
    has_data="$(python -c "
from sqlalchemy import func, select
from app.core.database import session_scope
from app.models.event import Event
with session_scope() as db:
    print(1 if db.scalar(select(func.count(Event.id))) else 0)
")"
    if [ "$has_data" = "0" ]; then
      # Tách chuỗi SEED_ARGS thành nhiều tham số là cố ý, nên không bọc trong ngoặc kép.
      # shellcheck disable=SC2086
      echo "[entrypoint] DB trống → nạp dữ liệu mẫu: seed.py ${SEED_ARGS:-}"
      python scripts/seed.py ${SEED_ARGS:-}
    else
      echo "[entrypoint] DB đã có dữ liệu → bỏ qua seed"
    fi
  fi

  # Mặc định 1: ChromaDB nhúng của chatbot không dùng chung được giữa nhiều tiến trình.
  workers="${UVICORN_WORKERS:-1}"
  echo "[entrypoint] uvicorn, ${workers} worker"
  # --proxy-headers: tin X-Forwarded-* của nginx để audit log ghi đúng IP người dùng.
  # Chỉ nginx gọi được backend (cổng 8000 không publish ra ngoài) nên cho phép mọi IP forward.
  exec uvicorn app.main:app \
    --host 0.0.0.0 --port 8000 \
    --workers "${workers}" \
    --proxy-headers --forwarded-allow-ips "*"
fi

exec "$@"
