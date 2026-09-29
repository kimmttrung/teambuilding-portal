"""Export the actual v2 SQLite DDL for docs/03-data-model.md.

    python scripts/export_schema_v2.py --database /tmp/v2.db --output /docs/03-data-model.md

Run only against a disposable database after `alembic upgrade head`.
"""

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.verify_schema_v2 import verify


def render(database: Path) -> str:
    report = verify(database)
    with sqlite3.connect(database.resolve(strict=True).as_uri() + "?mode=ro", uri=True) as db:
        tables = db.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' AND name != 'alembic_version' ORDER BY name"
        ).fetchall()
        indexes = db.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        views = db.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='view' ORDER BY name"
        ).fetchall()
    lines = [
        "# 03 – Mô hình dữ liệu v2 (SQLite)", "",
        "> DDL chuẩn được xuất từ SQLite sau Alembic revision `c24a29db2026`.",
        "> File lịch sử: [03-legacy-data-model.md](03-legacy-data-model.md).",
        "> Mapping bảng cũ → mới, giới hạn ORM/API và cách seed:",
        "> [16-schema-v2-handoff.md](16-schema-v2-handoff.md).", "",
        "**24 bảng** (không tính `alembic_version`; `schema_archive` là bảng thứ 24).",
        "Thời gian UTC ISO-8601, SQLite bật `foreign_keys=ON`, WAL và `busy_timeout`",
        "theo `backend/app/core/database.py`. JSON lưu dưới dạng TEXT.",
        "`registrations.room_id` hiện chưa có FK cứng: SQLite không thêm được FK cho",
        "bảng cũ qua ALTER TABLE; cần kiểm tra phòng ở service trước khi ghi.",
        "**ORM và service cũ chưa chuyển theo DDL này**; không chạy ứng dụng với DB v2.", "",
        "## 1. Danh sách bảng và DDL", "",
    ]
    for name, sql in tables:
        lines.extend((f"### `{name}`", "", "```sql",
                      "\n".join(line.rstrip() for line in sql.rstrip(";").splitlines()) + ";",
                      "```", ""))
    lines.extend(("## 2. Index tường minh", "", "```sql"))
    lines.extend(sql.rstrip(";") + ";" for _, sql in indexes)
    lines.extend(("```", "", "## 3. Views (không tính trong số bảng)", ""))
    if views:
        lines.extend(("```sql", *(sql.rstrip(";") + ";" for _, sql in views), "```", ""))
    else:
        lines.extend(("Không có VIEW trong revision này.", ""))
    lines.extend(("## 4. Di trú và xác minh", "",
                  f"Revision: `{report['revision']}`. Kiểm tra số bảng, archive và foreign key",
                  "bằng `backend/scripts/verify_schema_v2.py` trên **bản sao** DB cũ.",
                  "Tuyệt đối không dùng `seed_v2.py --reset` trên dữ liệu thật.", ""))
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(render(args.database), encoding="utf-8")


if __name__ == "__main__":
    main()