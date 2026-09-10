# 08 – Môi trường, Docker & vận hành

## 1. Yêu cầu máy

| Công cụ | Bản tối thiểu | Ghi chú |
|---|---|---|
| Docker Desktop | 24+ | máy hiện tại: 28.0.4 ✅ |
| Node.js | 20+ | máy hiện tại: 22.14.0 ✅ |
| Python | **3.13** | máy hiện tại: 3.13.2 ✅ — xem §2 |
| Git | 2.40+ | ✅ |

## 2. Chọn đúng Python trên máy này

Máy có 3 bản Python, và bản đứng đầu PATH lại là bản cũ nhất:

| Đường dẫn | Version | Dùng? |
|---|---|---|
| `C:\mingw64\bin\python.exe` | 3.9.13 | ❌ quá cũ — nhưng `python` trần lại gọi trúng bản này |
| `C:\Users\ADMIN\anaconda3\python.exe` | 3.12.3 | ⚠️ được, nhưng là base env Anaconda — tránh |
| `C:\Users\ADMIN\AppData\Local\Programs\Python\Python313\python.exe` | 3.13.2 | ✅ **bản dùng cho dự án** |

Dự án dùng bản **3.13.2** ở `...\Programs\Python\Python313`. Luôn gọi qua `py` launcher, đừng gọi `python` trần:

```powershell
py -0                             # liệt kê các bản Python đã cài
py -3.13 -m venv backend\.venv    # tạo venv cho dự án
backend\.venv\Scripts\activate
python --version                  # trong venv sẽ là 3.13.2
```

Docker cũng dùng `python:3.13-slim` để local và container **cùng một minor version** —
tránh kiểu "chạy được trên máy tôi".
Nếu chỉ muốn chạy chứ không sửa code: `docker compose -f docker-compose.dev.yml up`, không cần cài gì.

> Nếu lúc `pip install` có thư viện chưa có wheel cho 3.13 (thường là nhóm ML: chromadb, onnxruntime),
> báo tôi biết — phương án dự phòng là hạ cả local lẫn Docker xuống 3.12, không hạ một bên.

## 3. Biến môi trường (`.env`)

```dotenv
# --- App ---
APP_NAME=TeamBuilding Portal
APP_ENV=development                 # development | production
API_PREFIX=/api/v1
TZ=Asia/Ho_Chi_Minh

# --- Database ---
DATABASE_URL=sqlite:///./data/sqlite/teambuilding.db

# --- Auth ---
JWT_SECRET_KEY=doi-chuoi-nay-truoc-khi-deploy
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7

# --- CORS (chỉ dùng khi chạy dev tách cổng) ---
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# --- Email (SMTP) ---
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM_NAME=BTC Team Building
SMTP_FROM_EMAIL=noreply@company.vn
EMAIL_ENABLED=false                 # false = ghi ra log, không gửi thật (dev)

# --- RAG / LLM ---
ANTHROPIC_API_KEY=
LLM_MODEL=claude-opus-5
CHROMA_PERSIST_DIR=./data/chromadb
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
RAG_TOP_K=5
CHAT_RATE_LIMIT_PER_10MIN=20

# --- Upload ---
UPLOAD_DIR=./data/uploads
MAX_UPLOAD_MB=2

# --- Frontend (build time) ---
VITE_API_BASE_URL=/api/v1
```

**`.env` không bao giờ commit.** Chỉ commit `.env.example` với giá trị rỗng/mẫu.

## 4. docker-compose (production-like)

```yaml
services:
  backend:
    build: ./backend
    env_file: .env
    volumes:
      - ./data:/app/data              # SQLite + Chroma + uploads sống ngoài container
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request;urllib.request.urlopen('http://localhost:8000/api/v1/health')"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 40s
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      args:
        VITE_API_BASE_URL: /api/v1
    ports:
      - "3000:80"
    depends_on:
      backend:
        condition: service_healthy
    restart: unless-stopped
```

Backend **không publish cổng ra ngoài** ở production — chỉ nginx của frontend proxy vào.
Ở dev thì `docker-compose.dev.yml` mở `8000:8000` để xem Swagger.

**nginx.conf (frontend)** cần 3 điều:
```nginx
location /api/ { proxy_pass http://backend:8000/api/; proxy_buffering off; }  # off → SSE chạy được
location /     { try_files $uri /index.html; }                                 # SPA fallback
gzip on; gzip_types text/css application/javascript application/json;
```
`proxy_buffering off` là bắt buộc, nếu không stream chat và SSE Gala sẽ bị nghẽn tới khi kết thúc.

## 5. Dockerfile

**Backend** – multi-stage nhẹ:
```dockerfile
FROM python:3.13-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /app/data/sqlite /app/data/chromadb /app/data/uploads
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```
Migration chạy khi khởi động container → không bao giờ quên `alembic upgrade`.

**Frontend** – build rồi serve tĩnh:
```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_API_BASE_URL=/api/v1
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
```

## 6. Lệnh hằng ngày

```bash
docker compose -f docker-compose.dev.yml up --build   # chạy dev, hot reload
docker compose up -d --build                          # chạy bản build
docker compose logs -f backend
docker compose exec backend alembic revision --autogenerate -m "add rooms"
docker compose exec backend alembic upgrade head
docker compose exec backend python scripts/seed.py    # nạp dữ liệu mẫu
docker compose exec backend pytest -q
docker compose down                                   # dữ liệu vẫn còn trong ./data
```

## 7. Sao lưu & khôi phục

SQLite là 1 file, nhưng **không được copy khi đang ghi** (WAL). Dùng lệnh backup của chính SQLite:
```bash
docker compose exec backend python -c "import sqlite3,shutil,datetime; \
  src=sqlite3.connect('data/sqlite/teambuilding.db'); \
  dst=sqlite3.connect(f'data/sqlite/backup_{datetime.date.today()}.db'); \
  src.backup(dst)"
```
Trước mỗi lần chạy Auto Allocation, hệ thống **tự backup** file DB (giữ 10 bản gần nhất) — để BTC lỡ tay còn quay lại được.

## 8. Điểm cần biết trước khi deploy thật

| Việc | Lý do |
|---|---|
| Đổi `JWT_SECRET_KEY` | mặc định trong `.env.example` là công khai |
| Đặt `EMAIL_ENABLED=true` + SMTP thật | dev đang ghi log |
| Bật HTTPS (reverse proxy phía trước) | có CCCD, SĐT — không được chạy HTTP trần |
| Giới hạn `MAX_UPLOAD_MB` + kiểm tra MIME ảnh avatar | tránh upload file lạ |
| Bật cron backup hằng ngày | |
| Kiểm tra `PRAGMA foreign_keys` thực sự ON trong container | xem [03 §11](03-data-model.md) |
