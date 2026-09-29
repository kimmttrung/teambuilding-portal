"""Kiểm kê SQLite cũ và tạo bản sao nhất quán trước khi migrate schema v2.

Chạy khi backend đã dừng, KHÔNG dùng --reset hoặc copy file .db đang có WAL:
    python scripts/preflight_schema_v2.py --source data/sqlite/teambuilding.db \
        --backup data/backups/before-schema-v2.db

Chỉ đọc DB nguồn; --backup sử dụng SQLite backup API. Không xuất dữ liệu cá nhân ra stdout.
Script chỉ làm preflight, không thay thế Alembic migration và không thay đổi schema.
"""

import argparse
import json
import sqlite3
from contextlib import closing
from pathlib import Path

# 35 bảng trước khi gộp; không tính alembic_version hay bảng nội bộ của SQLite.
SOURCE_TABLE_COUNT = 35
SOURCE_REVISION = "5f3a91c7d420"
MERGED_TABLES = (
    "event_settings",
    "registration_bus_needs",
    "consents",
    "room_assignments",
    "gala_draw_orders",
    "gala_seat_holds",
    "gala_seat_assignments",
    "itinerary_items",
    "policy_documents",
    "announcements",
    "chat_sessions",
    "chat_messages",
)
RETAINED_TABLES = (
    "events", "users", "departments", "work_locations", "teams", "shifts",
    "registrations", "registration_cancellations", "flights", "flight_assignments",
    "trip_legs", "pickup_points", "buses", "bus_assignments", "hotels", "rooms",
    "gala_layouts", "gala_tables", "gala_seats", "email_logs", "audit_logs",
    "refresh_tokens", "login_attempts",
)
SOURCE_TABLES = set(MERGED_TABLES) | set(RETAINED_TABLES)
assert len(SOURCE_TABLES) == SOURCE_TABLE_COUNT


def inspect_database(source: Path) -> dict:
    """Kiểm tra lỗi FK, số bảng và số dòng cần lưu; không đọc giá trị nhạy cảm."""
    source = source.resolve(strict=True)
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as connection:
        names = {
            name for (name,) in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%' AND name != 'alembic_version'"
            )
        }
        missing = sorted(SOURCE_TABLES - names)
        unexpected = sorted(names - SOURCE_TABLES)
        version = (
            connection.execute("SELECT version_num FROM alembic_version").fetchall()
            if "alembic_version" in {
                name for (name,) in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            else []
        )
        # Các tên bảng đều là hằng số ở trên; không chèn tên bảng từ CLI/DB vào SQL.
        counts = {
            table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in MERGED_TABLES
            if table in names
        }
        fk_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
        shared_documents = (
            connection.execute(
                "SELECT COUNT(*) FROM policy_documents WHERE event_id IS NULL"
            ).fetchone()[0]
            if "policy_documents" in names
            else None
        )
    return {
        "source": str(source),
        "table_count": len(names),
        "expected_table_count": SOURCE_TABLE_COUNT,
        "revisions": [row[0] for row in version],
        "missing_tables": missing,
        "unexpected_tables": unexpected,
        "rows_to_archive": counts,
        "shared_policy_documents": shared_documents,
        "foreign_key_errors": len(fk_errors),
        "ready": names == SOURCE_TABLES and not fk_errors
        and version == [(SOURCE_REVISION,)],
    }


def backup_database(source: Path, destination: Path) -> None:
    """Sao lưu cả WAL an toàn; từ chối ghi đè backup hoặc trỏ về chính DB nguồn."""
    source = source.resolve(strict=True)
    destination = destination.resolve()
    if source == destination or destination.exists():
        raise ValueError("Đường dẫn backup trùng DB nguồn hoặc file backup đã tồn tại.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as original:
            with closing(sqlite3.connect(destination)) as copy:
                original.backup(copy)
                if copy.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise RuntimeError("Backup không vượt qua PRAGMA integrity_check")
    except Exception:
        destination.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="Đường dẫn DB SQLite hiện tại")
    parser.add_argument("--backup", type=Path, help="File backup MỚI (không ghi đè file cũ)")
    args = parser.parse_args()
    try:
        report = inspect_database(args.source)
        if not report["ready"]:
            print(json.dumps(report, ensure_ascii=True, indent=2))
            print("Database is not the expected 35-table schema; no backup created.")
            return 1
        if args.backup:
            backup_database(args.source, args.backup)
            report["backup"] = str(args.backup.resolve())
        print(json.dumps(report, ensure_ascii=True, indent=2))
        return 0
    except (OSError, sqlite3.Error, RuntimeError, ValueError) as exc:
        parser.exit(1, f"Preflight failed: {str(exc).encode('ascii', 'backslashreplace').decode()}\n")


if __name__ == "__main__":
    raise SystemExit(main())