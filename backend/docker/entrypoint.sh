#!/bin/sh
# Khởi động backend trong container.
#   serve (mặc định) : chạy migration rồi uvicorn — không bao giờ quên `alembic upgrade`.
#   lệnh bất kỳ      : chạy thẳng, ví dụ `python scripts/seed.py --reset`.
set -eu

mkdir -p /app/data/sqlite /app/data/uploads /app/data/chromadb /app/data/backups

if [ "${1:-serve}" = "serve" ]; then
  echo "[entrypoint] alembic upgrade head"
  alembic upgrade head

  workers="${UVICORN_WORKERS:-2}"
  echo "[entrypoint] uvicorn, ${workers} worker"
  # --proxy-headers: tin X-Forwarded-* của nginx để audit log ghi đúng IP người dùng.
  # Chỉ nginx gọi được backend (cổng 8000 không publish ra ngoài) nên cho phép mọi IP forward.
  exec uvicorn app.main:app \
    --host 0.0.0.0 --port 8000 \
    --workers "${workers}" \
    --proxy-headers --forwarded-allow-ips "*"
fi

exec "$@"
