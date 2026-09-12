# 02 – Kiến trúc hệ thống

## 1. Tech stack (chốt)

| Tầng | Công nghệ | Ghi chú |
|---|---|---|
| Frontend | React 19 + Vite 8 + TailwindCSS 4 + React Router 7 | TanStack Query v5, React Hook Form + Zod, lucide-react, date-fns |
| Backend | Python **3.13** + FastAPI + SQLAlchemy 2.0 + Pydantic v2 | local dùng 3.13.2, Docker dùng `python:3.13-slim` — cùng một minor version |
| DB | SQLite (WAL) + Alembic | 1 file `data/sqlite/teambuilding.db` |
| Vector store | ChromaDB (persistent, local) | `data/chromadb/` |
| LLM | Claude `claude-opus-5` qua Anthropic API | cấu hình `ANTHROPIC_API_KEY`; có chế độ mock khi thiếu key |
| Embedding | `sentence-transformers/all-MiniLM-L6-v2` (local, offline) | tránh phụ thuộc API cho bước index |
| Auth | JWT (access + refresh), bcrypt | interface `AuthProvider` để cắm SSO sau |
| Đóng gói | Docker + docker-compose (nginx + uvicorn) | |

## 2. Sơ đồ triển khai

```
                       ┌──────────────────────────────────┐
   Browser  ──────────►│ frontend (nginx:alpine)      :80 │
   (CBNV / BTC)        │  React SPA build tĩnh            │
                       │  /api/* → proxy_pass ────────────┼──┐
                       └──────────────────────────────────┘  │
                                                             ▼
                       ┌─────────────────────────────────────────────┐
                       │ backend (python:3.13-slim, uvicorn)   :8000 │
                       │                                             │
                       │  api/v1  ─► services  ─► models (SQLAlchemy)│
                       │     │           ├─ allocator (flight/bus)   │
                       │     │           ├─ email_service (SMTP)     │
                       │     │           └─ excel_service            │
                       │     └────────► rag/engine ──► ChromaDB      │
                       │                     └──────► Anthropic API  │
                       └─────────────────────────────────────────────┘
                              │                          │
                              ▼                          ▼
                    data/sqlite/teambuilding.db    data/chromadb/
                       (docker volume)               (docker volume)
```

## 3. Kiến trúc backend – 4 tầng

```
api/v1/*.py      HTTP: routing, phân quyền, validate I/O bằng Pydantic. KHÔNG chứa logic nghiệp vụ.
services/*.py    Logic nghiệp vụ thuần: nhận Session + tham số, trả object. Test được không cần HTTP.
models/*.py      SQLAlchemy ORM: quan hệ, constraint, index.
core/*.py        config, database, security, dependencies.
```

Quy tắc phụ thuộc: `api → services → models`. **Không đi ngược.** `services` không được import từ `api`.

## 4. Cấu trúc thư mục

```
teambuilding-portal/
├── docker-compose.yml
├── docker-compose.dev.yml          # hot-reload cho dev
├── CLAUDE.md
├── README.md
├── .env.example
├── docs/                           # tài liệu (file này)
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/versions/
│   ├── app/
│   │   ├── main.py                 # FastAPI app, CORS, lifespan, exception handler
│   │   ├── core/
│   │   │   ├── config.py           # Pydantic Settings
│   │   │   ├── database.py         # engine + PRAGMA (foreign_keys, WAL, busy_timeout)
│   │   │   ├── security.py         # JWT, bcrypt, AuthProvider interface
│   │   │   ├── dependencies.py     # get_db, get_current_user, require_role, require_event_status
│   │   │   └── exceptions.py       # AppError + handler chuẩn hoá lỗi
│   │   ├── models/
│   │   │   ├── base.py             # Base, TimestampMixin
│   │   │   ├── event.py            # Event, EventSetting
│   │   │   ├── user.py             # User, Role
│   │   │   ├── org.py              # Team, Department, WorkLocation
│   │   │   ├── registration.py     # Registration, RegistrationBusNeed, Consent
│   │   │   ├── flight.py           # Shift, Flight, FlightAssignment
│   │   │   ├── accommodation.py    # Hotel, Room, RoomAssignment
│   │   │   ├── transportation.py   # TripLeg, PickupPoint, Bus, BusAssignment
│   │   │   ├── gala.py             # GalaLayout, GalaTable, GalaSeat, SeatHold, SeatAssignment, DrawOrder
│   │   │   ├── content.py          # ItineraryItem, Announcement, PolicyDocument
│   │   │   ├── notification.py     # EmailLog
│   │   │   ├── chat.py             # ChatSession, ChatMessage
│   │   │   └── audit.py            # AuditLog
│   │   ├── schemas/                # Pydantic I/O, 1 file / domain
│   │   ├── api/v1/                 # auth, users, events, registrations, flights, buses,
│   │   │                           # rooms, gala, journey, admin, chat, master_data
│   │   ├── services/
│   │   │   ├── allocator/
│   │   │   │   ├── flight_allocator.py
│   │   │   │   ├── bus_allocator.py
│   │   │   │   └── result.py       # AllocationResult, AllocationFlag
│   │   │   ├── journey_service.py  # gom toàn bộ hành trình 1 user
│   │   │   ├── email_service.py
│   │   │   ├── excel_service.py
│   │   │   └── audit_service.py
│   │   └── rag/
│   │       ├── engine.py           # pipeline: retrieve → tool → LLM
│   │       ├── vector_store.py     # ChromaDB wrapper
│   │       ├── indexer.py          # nạp docs + dữ liệu công khai vào vector store
│   │       ├── tools.py            # tool tra cứu, scope theo user_id từ JWT
│   │       └── knowledge/          # .md nguồn: lịch trình, quy định, FAQ
│   ├── scripts/seed.py
│   ├── tests/
│   └── data/                       # KHÔNG commit: sqlite/ chromadb/ uploads/
│
├── frontend/
│   ├── Dockerfile
│   ├── nginx.conf
│   └── src/
│       ├── api/                    # axios client + module theo domain
│       ├── routes/                 # AppRoutes, ProtectedRoute (check role)
│       ├── components/{common,layout,gala,allocation,chat,journey}
│       ├── pages/{auth,user,leader,admin}
│       ├── hooks/                  # useAuth, useJourney, useChatStream
│       ├── context/                # AuthContext, ToastContext
│       └── utils/                  # format ngày/giờ, constants, zod schemas
```

`backend/data/` là nơi duy nhất chứa dữ liệu chạy (SQLite, ChromaDB, ảnh upload).
Docker mount `./backend/data:/app/data` nên đường dẫn local và trong container trùng nhau.

## 5. Luồng nghiệp vụ chính

### 5.1 Đăng ký
```
CBNV login → GET /events/active → POST /registrations
  → guard: event.status == registration_open
  → ghi registrations + registration_bus_needs (n bản ghi, 1 / chặng) + consents (terms_version)
  → BackgroundTask: gửi email xác nhận → ghi email_logs
```

### 5.2 Auto Flight Allocation
```
POST /flights/allocate  { event_id, direction, dry_run: true }
  → allocator gom theo team → xếp greedy có trọng số → trả preview + flags
  → Admin xem preview (đã xếp / slot còn lại / team bị tách)
  → POST lại dry_run=false → ghi flight_assignments + audit_logs
```

### 5.3 Manual Adjustment
```
PATCH /flight-assignments/{id} { flight_id, reason }
  → transaction IMMEDIATE, đếm lại slot
  → vượt slot → 409; tách team → 200 kèm warning
  → ghi audit_logs (before/after dạng JSON)
```

### 5.4 Gala seat selection (chống tranh chấp)
```
POST /gala/seats/hold     BEGIN IMMEDIATE; seat chưa assigned & chưa bị hold còn hạn
                          → insert gala_seat_holds(expires_at = now + 120s); COMMIT
POST /gala/seats/confirm  BEGIN IMMEDIATE; verify hold còn hạn & đúng team
                          → insert gala_seat_assignments (UNIQUE seat_id); xoá hold; COMMIT
Hold hết hạn được dọn lazy mỗi lần đọc layout.
```

### 5.5 Chatbot RAG
```
POST /chat  { session_id, message }  (SSE stream)
  → retrieve top-k từ ChromaDB (lịch trình, quy định, FAQ – dữ liệu CÔNG KHAI)
  → nếu câu hỏi thuộc nhóm cá nhân → gọi tool get_my_journey(user_id từ JWT)
  → LLM tổng hợp → stream về FE → lưu chat_messages
```

## 6. Quyết định kiến trúc (ADR tóm tắt)

| # | Quyết định | Lý do |
|---|---|---|
| ADR-001 | SQLite + WAL thay vì Postgres | Yêu cầu mentor; quy mô ≤1000 user; 1 file dễ demo/backup |
| ADR-002 | Bảng gán riêng thay vì cột FK trên `registrations` | Cần audit, cần 2 chiều bay, cần n chặng xe |
| ADR-003 | Greedy + trọng số thay vì ILP | Đủ tốt, chạy <1s, giải thích được cho BTC; ILP để Phase 2 |
| ADR-004 | RAG dùng tool tham số cố định, không text-to-SQL | Chặn rò rỉ dữ liệu cá nhân |
| ADR-005 | Nginx serve build tĩnh + proxy `/api` | Một origin duy nhất, không phải cấu hình CORS production |
| ADR-006 | Alembic ngay từ commit đầu | Đổi schema giữa chừng mà không mất dữ liệu demo |

Chi tiết: thư mục [adr/](adr/).
