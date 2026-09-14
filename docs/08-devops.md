# 08 – Môi trường, Docker & vận hành

## 1. Yêu cầu máy

| Công cụ | Bản tối thiểu | Ghi chú |
|---|---|---|
| Docker Desktop | 24+ | máy hiện tại: 28.0.4 ✅ — chỉ cần Docker nếu chạy bằng container |
| Node.js | 20.19+ / 22.12+ | máy hiện tại: 22.14.0 ✅ (Vite 8 đòi bản này) |
| Python | **3.13** | máy hiện tại: 3.13.2 ✅ — xem §2 |
| Git | 2.40+ | ✅ |

## 2. Chọn đúng Python trên máy này

Máy có 3 bản Python, và bản đứng đầu PATH lại là bản cũ nhất:

| Đường dẫn | Version | Dùng? |
|---|---|---|
| `C:\mingw64\bin\python.exe` | 3.9.13 | ❌ quá cũ — nhưng `python` trần lại gọi trúng bản này |
| `C:\Users\ADMIN\anaconda3\python.exe` | 3.12.3 | ⚠️ được, nhưng là base env Anaconda — tránh |
| `C:\Users\ADMIN\AppData\Local\Programs\Python\Python313\python.exe` | 3.13.2 | ✅ **bản dùng cho dự án** |

Luôn gọi qua `py` launcher, đừng gọi `python` trần:

```powershell
py -0                             # liệt kê các bản Python đã cài
py -3.13 -m venv backend\.venv    # tạo venv cho dự án
backend\.venv\Scripts\activate
python --version                  # trong venv sẽ là 3.13.2
```

Docker dùng `python:3.13-slim` để local và container **cùng một minor version**.

## 3. Biến môi trường (`.env`)

Mẫu đầy đủ ở `.env.example` (gốc repo). Copy thành `.env` rồi điền:

| Nhóm | Biến | Ghi chú |
|---|---|---|
| App | `APP_ENV` | `development` hiện Swagger `/docs`; `production` ẩn Swagger và **bắt buộc** `JWT_SECRET_KEY` riêng ≥ 32 byte |
| DB | `DATABASE_URL` | chạy trên máy: `sqlite:///./data/sqlite/teambuilding.db`. **Trong Docker bị compose ghi đè** (xem §4) |
| Auth | `JWT_SECRET_KEY` | để trống là backend không khởi động. Sinh: `py -3.13 -c "import secrets; print(secrets.token_urlsafe(48))"` |
| Email | `EMAIL_ENABLED`, `SMTP_*` | `EMAIL_ENABLED=false` chỉ ghi log. Gmail: bật 2FA + App Password, `SMTP_FROM_EMAIL` trùng `SMTP_USER` |
| Email | `APP_PUBLIC_URL` | link trong email, ví dụ `http://localhost:3000` khi chạy Docker |
| Upload | `MAX_UPLOAD_MB` | trần file avatar / Excel |
| RAG | `ANTHROPIC_API_KEY`, `LLM_MODEL=claude-opus-5` | dùng từ bước 19 |

Thử SMTP mà không cần Gmail: `py -3.13 scripts/dev_smtp_server.py` (nghe `127.0.0.1:1025`), đặt
`SMTP_HOST=127.0.0.1 SMTP_PORT=1025 SMTP_STARTTLS=false`. Thư lưu ở `backend/data/dev_mail/`.
Backend chạy **trong Docker** thì SMTP giả trên máy là `SMTP_HOST=host.docker.internal`.

**`.env` không bao giờ commit.** Chỉ commit `.env.example`.

## 4. Docker Compose

```
trình duyệt ──:3000──▶ frontend (nginx)  ──/api/, /uploads/──▶ backend (uvicorn, 2 worker) ──▶ volume tb_data
                        └ file tĩnh React, SPA fallback                                          └ sqlite/, uploads/, backups/
```

| File | Dùng khi | Ghi chú |
|---|---|---|
| `docker-compose.yml` | chạy bản build (demo, máy chủ) | chỉ publish cổng `3000` (đổi bằng `TB_HTTP_PORT`); backend không mở cổng ra ngoài |
| `docker-compose.dev.yml` | dev trong container | mount source, hot reload: frontend `:5173`, Swagger `:8000/docs` |

Những quyết định quan trọng:

- **Dữ liệu nằm trong named volume `tb_data`, không bind mount `backend/data`.** SQLite chế độ WAL cần
  khoá file và shared memory; bind mount từ ổ Windows vào container không đảm bảo hai thứ đó → có thể
  hỏng DB, nhất là khi uvicorn trên máy cũng mở cùng file. Hệ quả: DB trong Docker **tách biệt** với DB
  trên máy — seed lại trong container (§6), hoặc chép file vào (§7).
- `DATABASE_URL`, `UPLOAD_DIR`, `CHROMA_PERSIST_DIR` được compose đặt thành đường dẫn tuyệt đối trong
  `/app/data`, đè giá trị của máy dev trong `.env`. Muốn dùng file DB khác trong volume: đặt
  `TB_DATABASE_URL=sqlite:////app/data/sqlite/teambuilding_v2.db` trước `docker compose up`.
- **Migration chạy khi container khởi động** (`docker/entrypoint.sh`) → không bao giờ quên `alembic upgrade`.
- Healthcheck backend đọc `status` trong `/api/v1/health` (endpoint luôn trả HTTP 200 — DB lỗi hoặc
  `foreign_keys` tắt là `degraded`). Frontend chỉ khởi động khi backend `healthy`.
- `extra_hosts: host.docker.internal:host-gateway` để backend gọi dịch vụ trên máy host (SMTP giả).

**nginx** (`frontend/docker/nginx.conf`):

| Cấu hình | Lý do |
|---|---|
| `/api/`: `proxy_buffering off`, `proxy_cache off`, `proxy_read_timeout 1h` | **bắt buộc** cho SSE sơ đồ Gala — thiếu là sự kiện bị giữ tới khi luồng đóng (CLAUDE.md cạm bẫy #2). Đã đo: sự kiện `change` tới trình duyệt ~0,5 giây sau thao tác |
| `gzip_types` không có `text/event-stream` | nén gom byte lại chờ đủ khối → SSE đứng |
| `resolver 127.0.0.11` + `set $backend_upstream` | phân giải tên `backend` mỗi lần request: backend khởi động lại đổi IP thì nginx không trỏ địa chỉ cũ |
| `location /` → `try_files $uri /index.html`, `expires -1` | SPA fallback; `index.html` không cache để bản mới có hiệu lực ngay |
| `/assets/` → `expires max`, `try_files $uri =404` | file có hash trong tên; file thiếu trả 404 thật, không trả index |
| `add_header` chỉ ở cấp `server` | `add_header` trong `location` xoá mất header bảo mật kế thừa |
| `X-Forwarded-For` + uvicorn `--proxy-headers` | audit log ghi IP người dùng (qua Docker Desktop sẽ thấy IP gateway `172.x`, trên máy chủ Linux là IP thật) |

## 5. Image

**Backend** (`backend/Dockerfile`, ~215 MB): `python:3.13-slim`, cài `requirements.txt` trước khi copy code
(sửa code không cài lại thư viện), chạy bằng user `app` (uid 1000). Thư mục `data` thuộc `app` sẵn trong
image nên volume tạo lần đầu kế thừa đúng quyền. `ENTRYPOINT docker/entrypoint.sh`:
`serve` (mặc định) = migration + `uvicorn --workers ${UVICORN_WORKERS:-2}`; lệnh khác thì chạy thẳng.
Image có sẵn `tests/` nên `pytest` chạy được trong container.

**Frontend** (`frontend/Dockerfile`, ~49 MB): `node:22-alpine` chạy `npm ci` + `npm run build`, rồi copy
`dist/` sang `nginx:1.27-alpine`. `package-lock.json` đã có binary Linux musl của rolldown / lightningcss /
oxide nên build trên Alpine không cần cài thêm.

`.gitattributes` ép `*.sh` giữ LF — CRLF làm `entrypoint.sh` lỗi `/bin/sh^M: not found`. Dockerfile cũng
`sed` bỏ `\r` cho chắc.

## 6. Lệnh hằng ngày

### Docker — bản build

```bash
docker compose up -d --build                       # build + chạy nền, http://localhost:3000
docker compose ps                                  # cả hai service phải (healthy)
docker compose exec backend python scripts/seed.py --reset --registration-rate 0.7   # dữ liệu demo
docker compose logs -f backend
docker compose exec backend pytest -q -p no:cacheprovider   # chạy test ngay trong image
docker compose down                                # dừng — dữ liệu còn trong volume tb_data
docker compose down -v                             # dừng VÀ xoá volume = mất dữ liệu
TB_HTTP_PORT=8080 docker compose up -d             # đổi cổng (PowerShell: $env:TB_HTTP_PORT=8080)
```

Sửa code xong: `docker compose up -d --build` — chỉ layer thay đổi được build lại, dữ liệu giữ nguyên.

### Docker — dev (hot reload)

```bash
docker compose -f docker-compose.dev.yml up --build     # frontend :5173, Swagger :8000/docs
docker compose -f docker-compose.dev.yml exec backend python scripts/seed.py --reset
```
Bind mount từ Windows không phát sự kiện đổi file vào container nên compose bật polling
(`WATCHFILES_FORCE_POLLING`, `VITE_USE_POLLING`). `node_modules` bản Linux nằm trong volume riêng, chỉ
`npm ci` lại khi `package-lock.json` đổi.

### Chạy thẳng trên máy (không Docker)

```powershell
cd backend
.venv\Scripts\activate                  # lần đầu: py -3.13 -m venv .venv; pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
```powershell
cd frontend
npm run dev                             # :5173, proxy /api sang 127.0.0.1:8000 (đổi bằng VITE_PROXY_TARGET)
```
Kiểm tra: http://127.0.0.1:8000/api/v1/health phải có `"status":"ok"` và `"foreign_keys":true`.

## 7. Sao lưu & khôi phục

SQLite là 1 file, nhưng **không được copy khi đang ghi** (WAL: dữ liệu mới còn trong file `-wal`). Dùng
`scripts/backup_db.py` — gọi API backup của SQLite, lưu `data/backups/<tên>-<YYYYMMDD-HHMMSS>.db`, giữ 10 bản:

```bash
docker compose exec backend python scripts/backup_db.py
docker compose cp backend:/app/data/backups ./backups      # lấy bản sao ra máy
# chạy trên máy: cd backend && py -3.13 scripts/backup_db.py
```

**Đưa một file DB có sẵn vào Docker** (ví dụ DB đang dùng trên máy):
```bash
cd backend && py -3.13 scripts/backup_db.py                 # tạo bản sao nhất quán trước
docker compose stop backend
docker compose cp data/backups/<file>.db backend:/app/data/sqlite/teambuilding.db
docker compose start backend
```

### Database demo riêng trên máy (giữ nguyên DB đang dùng)

Chạy nhiều bản song song chỉ bằng cách đổi `DATABASE_URL`. Tạo bản demo sạch (kỳ đang mở đăng ký, ~70%
CBNV đã gửi đăng ký, chưa xếp chuyến bay/xe/phòng/ghế, chưa bốc thăm Gala):

```powershell
cd backend
$env:DATABASE_URL = "sqlite:///./data/sqlite/teambuilding_v2.db"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe scripts\seed.py --reset --registration-rate 0.7
Remove-Item Env:DATABASE_URL
```

`--reset` chỉ xoá dữ liệu của file đang trỏ tới (v2). **Chuyển app sang bản demo**: sửa `DATABASE_URL`
trong `.env` thành `sqlite:///./data/sqlite/teambuilding_v2.db` rồi tắt và chạy lại uvicorn. Quay về: đổi
lại `teambuilding.db`. Ảnh avatar (`data/uploads`) dùng chung.

## 8. Điểm cần biết trước khi deploy thật

| Việc | Lý do |
|---|---|
| `APP_ENV=production` + `JWT_SECRET_KEY` riêng ≥ 32 byte | production từ chối khởi động với khoá mặc định; Swagger bị ẩn |
| Bật HTTPS ở reverse proxy phía trước (hoặc thêm cert vào nginx) | có CCCD, SĐT — không chạy HTTP trần. Nhớ giữ `proxy_buffering off` cho `/api/` ở proxy ngoài |
| `EMAIL_ENABLED=true` + SMTP thật, `APP_PUBLIC_URL` = domain thật | dev chỉ ghi log; link trong email trỏ về `APP_PUBLIC_URL` |
| Lịch backup hằng ngày: `docker compose exec -T backend python scripts/backup_db.py` (cron / Task Scheduler) rồi chép `backups/` ra ngoài máy | volume nằm cùng máy với app |
| Máy chủ Linux mà muốn bind mount thư mục data thay volume | thư mục phải thuộc uid 1000 (`chown -R 1000:1000`), nếu không backend không ghi được |
| Kiểm tra `/api/v1/health` → `foreign_keys: true` sau mỗi lần deploy | xem [03 §11](03-data-model.md) |
