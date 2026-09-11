"""Xem nhanh cấu trúc và dữ liệu trong database.

    python scripts/show_db.py                 # danh sách bảng + số dòng
    python scripts/show_db.py users           # các cột của bảng users + 5 dòng mẫu
    python scripts/show_db.py users --rows 20 # xem 20 dòng
    python scripts/show_db.py --sql "SELECT ..."  # chạy câu SQL tự viết

Xem cột nào nhạy cảm thì đọc docs/09-security.md §4 trước khi chia sẻ ảnh chụp.
"""

import argparse
import sqlite3
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings  # noqa: E402

# Cột chứa dữ liệu cá nhân — che bớt khi in ra màn hình để tránh lộ lúc chụp màn hình.
SENSITIVE_COLUMNS = {
    "password_hash",
    "id_card_number",
    "token_hash",
    "health_note",
}
MAX_CELL_WIDTH = 28


def connect() -> sqlite3.Connection:
    path = settings.sqlite_path
    if not path.exists():
        print(f"Chưa có database tại {path}")
        print("Chạy trước:  alembic upgrade head  &&  python scripts/seed.py --reset")
        raise SystemExit(1)
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def list_tables(connection: sqlite3.Connection) -> None:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()

    print(f"\nDatabase: {settings.sqlite_path}")
    print(f"{len(rows)} bảng\n")
    print(f"  {'BẢNG':<28}{'SỐ DÒNG':>9}   {'SỐ CỘT':>7}")
    print("  " + "-" * 46)
    for row in rows:
        name = row["name"]
        count = connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        columns = len(connection.execute(f'PRAGMA table_info("{name}")').fetchall())
        marker = " " if count else "·"  # · = bảng rỗng
        print(f"{marker} {name:<28}{count:>9}   {columns:>7}")
    print("\nXem chi tiết một bảng:  python scripts/show_db.py <tên bảng>")


def describe_table(connection: sqlite3.Connection, table: str, rows_limit: int) -> None:
    columns = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
    if not columns:
        print(f"Không có bảng tên '{table}'.")
        raise SystemExit(1)

    print(f"\n=== CẤU TRÚC: {table} ===\n")
    print(f"  {'CỘT':<26}{'KIỂU':<12}{'NULL?':<8}{'MẶC ĐỊNH':<20}KHOÁ")
    print("  " + "-" * 78)

    foreign_keys = {
        fk["from"]: f'{fk["table"]}.{fk["to"]}'
        for fk in connection.execute(f'PRAGMA foreign_key_list("{table}")').fetchall()
    }
    for column in columns:
        name = column["name"]
        key = "PK" if column["pk"] else (f'→ {foreign_keys[name]}' if name in foreign_keys else "")
        nullable = "NOT NULL" if column["notnull"] else "NULL"
        default = str(column["dflt_value"] or "")[:18]
        print(f"  {name:<26}{column['type']:<12}{nullable:<8}{default:<20}{key}")

    indexes = connection.execute(f'PRAGMA index_list("{table}")').fetchall()
    if indexes:
        print("\n  INDEX / UNIQUE")
        for index in indexes:
            index_columns = ", ".join(
                item["name"]
                for item in connection.execute(f'PRAGMA index_info("{index["name"]}")')
            )
            kind = "UNIQUE" if index["unique"] else "index "
            print(f"    {kind}  {index_columns}")

    total = connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    print(f"\n=== DỮ LIỆU: {min(rows_limit, total)}/{total} dòng ===\n")
    if total:
        _print_rows(
            connection.execute(f'SELECT * FROM "{table}" LIMIT {rows_limit}').fetchall()
        )


def run_sql(connection: sqlite3.Connection, sql: str) -> None:
    try:
        rows = connection.execute(sql).fetchall()
    except sqlite3.Error as error:
        print(f"Lỗi SQL: {error}")
        raise SystemExit(1) from error
    print(f"\n{len(rows)} dòng\n")
    _print_rows(rows)


def _print_rows(rows: list[sqlite3.Row]) -> None:
    if not rows:
        return
    headers = rows[0].keys()
    widths = {
        header: min(
            MAX_CELL_WIDTH,
            max(len(header), *(len(_cell(row, header)) for row in rows)),
        )
        for header in headers
    }
    print("  " + "  ".join(header[: widths[header]].ljust(widths[header]) for header in headers))
    print("  " + "  ".join("-" * widths[header] for header in headers))
    for row in rows:
        print(
            "  "
            + "  ".join(_cell(row, header)[: widths[header]].ljust(widths[header]) for header in headers)
        )


def _cell(row: sqlite3.Row, header: str) -> str:
    if header in SENSITIVE_COLUMNS:
        return "***" if row[header] else ""
    value = row[header]
    return "" if value is None else str(value).replace("\n", " ")


def main() -> int:
    parser = argparse.ArgumentParser(description="Xem cấu trúc và dữ liệu database")
    parser.add_argument("table", nargs="?", help="Tên bảng cần xem chi tiết")
    parser.add_argument("--rows", type=int, default=5, help="Số dòng mẫu (mặc định 5)")
    parser.add_argument("--sql", help="Chạy câu SQL tuỳ ý (chỉ đọc)")
    args = parser.parse_args()

    connection = connect()
    try:
        if args.sql:
            run_sql(connection, args.sql)
        elif args.table:
            describe_table(connection, args.table, args.rows)
        else:
            list_tables(connection)
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
