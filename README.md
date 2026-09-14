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

React 19 · Vite 8 · TailwindCSS 4 · TanStack Query — FastAPI · SQLAlchemy 2.0 · Python 3.13 —
SQLite (WAL) · Alembic — ChromaDB · Claude API — Docker Compose

## Chạy nhanh

```bash
git clone <repo-url> && cd teambuilding-portal
cp .env.example .env          # BẮT BUỘC điền JWT_SECRET_KEY (sinh: python -c "import secrets; print(secrets.token_urlsafe(48))")
docker compose up -d --build  # lần đầu vài phút; đợi `docker compose ps` báo cả hai (healthy)
docker compose exec backend python scripts/seed.py --reset --registration-rate 0.7
```

| Địa chỉ | |
|---|---|
| http://localhost:3000 | Ứng dụng (nginx → FastAPI) |
| http://localhost:5173 · http://localhost:8000/docs | Chế độ dev: `docker compose -f docker-compose.dev.yml up --build` |

Dữ liệu nằm trong Docker volume `tb_data` — `docker compose down` vẫn giữ, `down -v` mới xoá.
`--registration-rate 0.7` để ~30% CBNV chưa đăng ký (demo đăng ký + email nhắc); bỏ đi thì mọi người đã đăng ký.
Chạy không Docker: `cd backend && .venv\Scripts\activate && python scripts/seed.py --reset`.

Seed tạo 1 kỳ Team Building (Phú Quốc, 15–17/10/2026) với 120 CBNV / 8 team,
99 đăng ký tham gia, 4 chuyến bay, 10 xe, 50 phòng, sơ đồ Gala 12 bàn và lịch trình 3 ngày.

**Tài khoản demo** (mọi CBNV dùng chung mật khẩu `Matkhau123`):

| Email | Mật khẩu | Vai trò |
|---|---|---|
| `superadmin@company.vn` | `Admin12345` | super_admin |
| `btc@company.vn` | `Admin12345` | admin (BTC) |
| `trungb001@company.vn` | `Matkhau123` | team_leader |
| `bachd002@company.vn` | `Matkhau123` | employee |

Danh sách đầy đủ in ra ở cuối lệnh `seed.py`.

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
