"""Sao lưu database SQLite an toàn ngay cả khi app đang chạy.

Dùng API backup của chính SQLite, KHÔNG copy file: ở chế độ WAL, dữ liệu mới có thể còn nằm trong
file -wal, copy riêng file .db là ra bản thiếu hoặc hỏng.

    py -3.13 scripts/backup_db.py                             # chạy trên máy
    docker compose exec backend python scripts/backup_db.py   # chạy trong container
    docker compose cp backend:/app/data/backups ./backups     # lấy bản sao ra máy

Lưu vào `data/backups/<tên-db>-<YYYYMMDD-HHMMSS>.db` (giờ Việt Nam), giữ `--keep` bản gần nhất.
"""

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.core.timeutils import VN_TZ, utcnow  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Sao lưu database SQLite")
    parser.add_argument("--keep", type=int, default=10, help="Số bản sao giữ lại (mặc định 10)")
    args = parser.parse_args()

    source = settings.sqlite_path
    if not source.exists():
        print(f"Không thấy database: {source}")
        return 1

    backup_dir = source.parent.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = utcnow().astimezone(VN_TZ).strftime("%Y%m%d-%H%M%S")
    target = backup_dir / f"{source.stem}-{stamp}.db"

    src = sqlite3.connect(source)
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()

    kept = sorted(backup_dir.glob(f"{source.stem}-*.db"))
    for old in kept[: max(len(kept) - args.keep, 0)]:
        old.unlink()

    size_kb = target.stat().st_size // 1024
    print(f"Đã sao lưu {source.name} → {target} ({size_kb} KB). Giữ {min(len(kept), args.keep)} bản.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
