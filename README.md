# Team Building Portal

Hệ thống quản lý Team Building tập trung: CBNV đăng ký một lần, xem toàn bộ hành trình
(chuyến bay → xe → khách sạn → Gala Dinner → lịch trình) ở một màn hình;
BTC quản lý dữ liệu tập trung, phân bổ tự động và điều chỉnh ngoại lệ.

> Trạng thái: **đang phát triển** — xem [docs/10-roadmap.md](docs/10-roadmap.md).

## Tính năng

| Module | Nội dung |
|---|---|
| 1. Đăng ký | Form nhiều bước, xác nhận quy định, chọn ca, đăng ký nhu cầu xe, email xác nhận |
| 2. Chuyến bay | Quản lý chuyến & slot, **phân bổ tự động** theo team/ca, điều chỉnh thủ công, audit log |
| 3. Xe | Cấu hình xe theo 4 chặng, phân xe tự động, chỉ định Trưởng xe |
| 4. Gala Dinner | Sơ đồ chọn ghế trực quan, bốc thăm thứ tự team, chống tranh chấp ghế |
| 5. My Journey | Dashboard hành trình cá nhân, mobile-first |
| + | Chatbot RAG trả lời về lịch trình, quy định và hành trình của chính người hỏi |

## Công nghệ

React 18 · Vite · TailwindCSS · TanStack Query — FastAPI · SQLAlchemy 2.0 · Python 3.11 —
SQLite (WAL) · Alembic — ChromaDB · Claude API — Docker Compose

## Chạy nhanh

```bash
git clone <repo-url> && cd teambuilding-portal
cp .env.example .env          # điền ANTHROPIC_API_KEY nếu muốn dùng chatbot
docker compose up --build
```

| Địa chỉ | |
|---|---|
| http://localhost:3000 | Ứng dụng |
| http://localhost:8000/docs | API docs (chỉ ở chế độ dev) |

Nạp dữ liệu mẫu:
```bash
docker compose exec backend python scripts/seed.py
```

Tài khoản demo (sau khi seed): xem đầu ra của `seed.py`.

## Phát triển

```bash
docker compose -f docker-compose.dev.yml up --build   # hot reload cả FE lẫn BE
docker compose exec backend pytest -q                 # chạy test
```

Chi tiết môi trường, biến `.env`, backup: [docs/08-devops.md](docs/08-devops.md).

## Tài liệu

Toàn bộ thiết kế nằm trong [docs/](docs/) — bắt đầu từ [docs/README.md](docs/README.md).
Hướng dẫn cho AI coding agent: [CLAUDE.md](CLAUDE.md).

## Giấy phép

Nội bộ — không phân phối ra ngoài.
