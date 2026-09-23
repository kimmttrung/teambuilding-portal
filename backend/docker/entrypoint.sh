#!/bin/sh
# Khởi động backend trong container.
#   serve (mặc định) : migration → seed dữ liệu mẫu nếu DB còn trống → uvicorn.
#   lệnh bất kỳ      : chạy thẳng, ví dụ `python scripts/seed.py --reset`.
set -eu

mkdir -p /app/data/sqlite /app/data/uploads /app/data/chromadb /app/data/backups

if [ "${1:-serve}" = "serve" ]; then
  echo "[entrypoint] alembic upgrade head"
  alembic upgrade head

  # SEED_RESET=1: nạp lại dữ liệu mẫu SẠCH, xoá hết dữ liệu đang có. Dùng khi tester pull code mới
  # về mà DB cũ còn dữ liệu sinh ra từ bản seed trước (ví dụ giờ xe đón chưa theo luật giờ xe/giờ bay
  # hiện tại, nên kỳ không công bố được). Giữ được volume nên không phải tải lại mô hình embedding
  # ~250 MB như `down -v`.
  #
  # Đây là cờ DÙNG MỘT LẦN, truyền ngay trên dòng lệnh:
  #   SEED_RESET=1 docker compose up -d
  # Để nó nằm lại trong .env thì mỗi lần container khởi động lại là mất sạch dữ liệu tester đang làm.
  if [ "${SEED_RESET:-0}" = "1" ]; then
    echo "[entrypoint] SEED_RESET=1 → XOÁ dữ liệu hiện có và nạp lại bộ mẫu: seed.py --reset ${SEED_ARGS:-}"
    # shellcheck disable=SC2086
    python scripts/seed.py --reset ${SEED_ARGS:-}
    echo "[entrypoint] ĐÃ nạp lại dữ liệu sạch. Bỏ SEED_RESET khỏi lệnh/.env, nếu không lần khởi động sau lại xoá tiếp."

  # Seed MỘT lần, chỉ khi DB chưa có kỳ nào. Người clone dự án chạy một lệnh là có dữ liệu để test;
  # còn khởi động lại container thì KHÔNG nạp lại — nạp lại là xoá sạch những gì tester đang làm dở.
  # Muốn làm lại từ đầu: `docker compose down -v` (xoá volume) rồi `up` lại.
  elif [ "${SEED_ON_START:-1}" = "1" ]; then
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
