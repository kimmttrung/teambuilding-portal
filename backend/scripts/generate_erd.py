"""Sinh sơ đồ ERD từ SQLAlchemy metadata.

Chạy: python scripts/generate_erd.py
Xuất:  docs/db-erd.md          (mermaid, GitHub render trực tiếp)
       docs/db-erd.dot         (Graphviz, ai có `dot` thì render ra PNG/SVG)

Sinh từ metadata thật nên sơ đồ không bao giờ lệch với code.
"""

import sys
from collections import defaultdict
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.models import Base  # noqa: E402

DOCS_DIR = BACKEND_DIR.parent / "docs"

# Nhóm bảng theo miền nghiệp vụ để sơ đồ đọc được, thay vì 32 hộp rải rác.
DOMAINS: dict[str, tuple[str, str, list[str]]] = {
    "core": (
        "Nền tảng",
        "#7c3aed",
        ["events", "event_settings", "departments", "work_locations", "teams", "users"],
    ),
    "registration": (
        "Đăng ký",
        "#2563eb",
        ["registrations", "registration_bus_needs", "consents", "shifts"],
    ),
    "flight": ("Chuyến bay", "#0891b2", ["flights", "flight_assignments"]),
    "transport": (
        "Xe & điều phối",
        "#059669",
        ["trip_legs", "pickup_points", "buses", "bus_assignments"],
    ),
    "hotel": ("Khách sạn", "#d97706", ["hotels", "rooms", "room_assignments"]),
    "gala": (
        "Gala Dinner",
        "#db2777",
        [
            "gala_layouts",
            "gala_tables",
            "gala_seats",
            "gala_draw_orders",
            "gala_seat_holds",
            "gala_seat_assignments",
        ],
    ),
    "content": (
        "Nội dung & hệ thống",
        "#64748b",
        [
            "itinerary_items",
            "announcements",
            "policy_documents",
            "email_logs",
            "chat_sessions",
            "chat_messages",
            "audit_logs",
        ],
    ),
}

# Cột phụ trợ, ẩn khỏi sơ đồ cho đỡ rối.
NOISE_COLUMNS = {"created_at", "updated_at"}


def domain_of(table_name: str) -> str:
    for key, (_, _, tables) in DOMAINS.items():
        if table_name in tables:
            return key
    return "content"


def mermaid_type(column) -> str:
    name = type(column.type).__name__.lower()
    if "int" in name:
        return "int"
    if "bool" in name:
        return "bool"
    return "string"


def build_mermaid(tables: list[str], *, show_columns: bool) -> str:
    lines = ["erDiagram"]
    selected = set(tables)

    for table_name in tables:
        table = Base.metadata.tables[table_name]
        if not show_columns:
            lines.append(f"    {table_name} {{ }}")
            continue
        lines.append(f"    {table_name} {{")
        for column in table.columns:
            if column.name in NOISE_COLUMNS:
                continue
            marks = []
            if column.primary_key:
                marks.append("PK")
            elif column.foreign_keys:
                marks.append("FK")
            suffix = f' "{",".join(marks)}"' if marks else ""
            lines.append(f"        {mermaid_type(column)} {column.name}{suffix}")
        lines.append("    }")

    seen: set[tuple[str, str]] = set()
    for table_name in tables:
        table = Base.metadata.tables[table_name]
        for column in table.columns:
            for fk in column.foreign_keys:
                parent = fk.column.table.name
                if parent not in selected or (parent, table_name) in seen:
                    continue
                seen.add((parent, table_name))
                # optional nếu cột cho phép NULL
                cardinality = "||--o{" if column.nullable else "||--|{"
                label = column.name.removesuffix("_id")
                lines.append(f"    {parent} {cardinality} {table_name} : {label}")
    return "\n".join(lines)


def build_dot() -> str:
    lines = [
        "digraph teambuilding {",
        "  rankdir=LR;",
        "  graph [fontname=\"Segoe UI\", splines=ortho, nodesep=0.4];",
        "  node [shape=box, style=\"rounded,filled\", fontname=\"Segoe UI\", fontsize=10];",
        "  edge [color=\"#94a3b8\", arrowsize=0.7];",
    ]
    for index, (key, (label, color, tables)) in enumerate(DOMAINS.items()):
        lines.append(f"  subgraph cluster_{index} {{")
        lines.append(f'    label="{label}"; color="{color}"; fontcolor="{color}";')
        for table_name in tables:
            if table_name in Base.metadata.tables:
                count = len(Base.metadata.tables[table_name].columns)
                lines.append(
                    f'    "{table_name}" [label="{table_name}\\n({count} cột)", '
                    f'fillcolor="{color}20"];'
                )
        lines.append("  }")

    for table in Base.metadata.tables.values():
        for column in table.columns:
            for fk in column.foreign_keys:
                lines.append(f'  "{fk.column.table.name}" -> "{table.name}";')
    lines.append("}")
    return "\n".join(lines)


def count_relations() -> int:
    return sum(
        1
        for table in Base.metadata.tables.values()
        for column in table.columns
        for _ in column.foreign_keys
    )


def main() -> None:
    tables = Base.metadata.tables
    by_domain: dict[str, list[str]] = defaultdict(list)
    for name in sorted(tables):
        by_domain[domain_of(name)].append(name)

    out = [
        "# Sơ đồ quan hệ dữ liệu (ERD)",
        "",
        "> **File này sinh tự động** bằng `python backend/scripts/generate_erd.py`",
        "> từ chính SQLAlchemy metadata — không sửa tay, sửa model rồi chạy lại.",
        "",
        f"**{len(tables)} bảng · {count_relations()} quan hệ khoá ngoại.**",
        "",
        "## Vì sao lại nhiều bảng đến vậy",
        "",
        "Phần lớn không phải bảng dữ liệu lớn, mà là bảng nhỏ phục vụ 3 nguyên tắc:",
        "",
        "| Nguyên tắc | Sinh ra bảng nào | Số bảng |",
        "|---|---|---|",
        "| **Cấu hình được** — không hard-code ca/chặng/team | `shifts`, `trip_legs`, "
        "`pickup_points`, `departments`, `work_locations`, `event_settings` | 6 |",
        "| **Audit được** — mỗi loại phân bổ là bảng riêng có ai/khi nào/vì sao | "
        "`flight_assignments`, `bus_assignments`, `room_assignments`, "
        "`gala_seat_assignments`, `audit_logs` | 5 |",
        "| **Sơ đồ Gala + chống trùng ghế** | `gala_layouts` → `gala_tables` → `gala_seats`, "
        "`gala_draw_orders`, `gala_seat_holds` | 5 |",
        "",
        "Bỏ 3 nguyên tắc đó thì còn khoảng 12 bảng — nhưng mất luôn khả năng chạy kỳ thứ hai, "
        "mất audit log và Gala Dinner sẽ trùng ghế.",
        "",
        "## Xương sống hệ thống",
        "",
        "Chỉ 6 bảng dưới đây là đủ hiểu toàn bộ luồng nghiệp vụ:",
        "",
        "```mermaid",
        build_mermaid(
            [
                "events",
                "users",
                "teams",
                "registrations",
                "flights",
                "flight_assignments",
            ],
            show_columns=True,
        ),
        "```",
        "",
        "`registrations` là trung tâm: một CBNV trong một kỳ. Mọi thứ được phân bổ "
        "(chuyến bay, xe, phòng, ghế Gala) đều trỏ về `registration_id`, không trỏ về "
        "`user_id` — nhờ vậy dữ liệu các kỳ không lẫn vào nhau.",
        "",
    ]

    for key, (label, _, _) in DOMAINS.items():
        domain_tables = by_domain.get(key, [])
        if not domain_tables:
            continue
        out += [
            f"## {label} ({len(domain_tables)} bảng)",
            "",
            "```mermaid",
            build_mermaid(domain_tables, show_columns=True),
            "```",
            "",
        ]

    out += [
        "## Toàn cảnh",
        "",
        "```mermaid",
        build_mermaid(sorted(tables), show_columns=False),
        "```",
        "",
        "## Render ra ảnh PNG/SVG",
        "",
        "File `db-erd.dot` đi kèm dùng được với Graphviz:",
        "",
        "```bash",
        "dot -Tpng docs/db-erd.dot -o docs/db-erd.png",
        "dot -Tsvg docs/db-erd.dot -o docs/db-erd.svg",
        "```",
        "",
        "Chưa có Graphviz: `winget install Graphviz.Graphviz`, "
        "hoặc dán nội dung mermaid ở trên vào https://mermaid.live để tải ảnh.",
        "",
    ]

    (DOCS_DIR / "db-erd.md").write_text("\n".join(out), encoding="utf-8")
    (DOCS_DIR / "db-erd.dot").write_text(build_dot(), encoding="utf-8")
    print(f"Đã sinh docs/db-erd.md và docs/db-erd.dot ({len(tables)} bảng)")


if __name__ == "__main__":
    main()
