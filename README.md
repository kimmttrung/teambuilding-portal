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

Chỉ cần Docker Desktop. **Không cần tạo `.env`, không cần chạy seed.**

```bash
git clone <repo-url> && cd teambuilding-portal
docker compose up -d --build
```

Lần đầu mất vài phút (build + nạp dữ liệu mẫu). Xong khi `docker compose ps` báo cả ba dịch vụ `(healthy)`;
muốn xem tiến trình thì `docker compose logs -f backend`.

| Địa chỉ | |
|---|---|
| http://localhost:3000 | Ứng dụng (nginx → FastAPI) |
| http://localhost:8025 | **Hộp thư Mailpit** — mọi email hệ thống gửi (xác nhận đăng ký, nhắc việc, thông báo, huỷ…) đều hiện ở đây, không gửi ra ngoài |

Lần chạy đầu, backend tự migration rồi nạp dữ liệu mẫu **một lần**. Dữ liệu sinh bằng random có seed cố định,
nên **ai clone về cũng có cùng một bộ dữ liệu** — báo cáo kiểm thử so được với nhau.

- 2 kỳ Team Building: **TB2026 – Phú Quốc** (kỳ mặc định) và **TB2027 – Đà Nẵng** (chuyển kỳ ở thanh bên).
- Kỳ TB2026: 120 CBNV / 8 team, 87 đã đăng ký (72 tham gia), **~30% chưa đăng ký** để thử luồng đăng ký và
  email nhắc; 4 chuyến bay, 10 xe, 50 phòng, sơ đồ Gala 12 bàn, lịch trình 3 ngày. Kỳ đang **Mở đăng ký, chưa
  phân bổ gì** — tester tự chạy phân bổ bay / xe / phòng để kiểm tra.

**Làm lại từ đầu với dữ liệu sạch** (xoá hết thứ đã thao tác):

```bash
docker compose down -v && docker compose up -d --build
```

`docker compose down` (không `-v`) và khởi động lại **giữ nguyên** dữ liệu.

**Pull code mới về mà đã có dữ liệu cũ** — nạp lại bộ mẫu sạch, giữ nguyên volume (không phải tải
lại mô hình embedding ~250 MB, không mất hộp thư Mailpit):

```bash
docker compose up -d --build            # code mới + migration tự chạy
SEED_RESET=1 docker compose up -d       # rồi nạp lại dữ liệu mẫu sạch (XOÁ dữ liệu đang có)
```

`SEED_RESET` là cờ dùng **một lần** — truyền ngay trên dòng lệnh, đừng để trong `.env`, nếu không mỗi
lần container khởi động lại là mất sạch dữ liệu đang thao tác. Cách tương đương không cần khởi động lại:
`docker compose exec backend python scripts/seed.py --reset --registration-rate 0.7 --second-event`.

Vì sao cần: dữ liệu sinh từ bản seed cũ có thể không còn hợp các luật mới (ví dụ giờ xe đón chưa theo
luật giờ xe ↔ giờ bay), khiến kỳ không chuyển sang "Đã công bố" được.

**Tuỳ chọn** — tạo `.env` ở gốc repo nếu cần:

| Biến | Dùng khi |
|---|---|
| `GEMINI_API_KEY` | Bật chatbot Tibi thật. Để trống thì Tibi chạy "chế độ thử" (câu trả lời mẫu) |
| `TB_HTTP_PORT` · `TB_MAIL_PORT` | Cổng 3000 / 8025 đang bị chiếm (ví dụ đã chạy Mailpit riêng) |
| `SEED_ARGS` | Đổi bộ dữ liệu mẫu, ví dụ `SEED_ARGS=` để mọi CBNV đều đã đăng ký |

Chế độ dev có hot reload: `docker compose -f docker-compose.dev.yml up --build` (http://localhost:5173 ·
Swagger http://localhost:8000/docs). Chạy không Docker: `cd backend && .venv\Scripts\activate && python scripts/seed.py --reset`.

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
