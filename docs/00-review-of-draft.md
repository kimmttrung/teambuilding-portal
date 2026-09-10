# 00 – Đánh giá bản draft (Gemini) & Danh sách bổ sung

> Mục đích: chỉ ra bản thiết kế nháp **đã ổn ở đâu**, **thiếu gì**, và **quyết định thay thế**.
> Mọi quyết định trong file này đã được phản ánh vào [02-architecture.md](02-architecture.md) và [03-data-model.md](03-data-model.md).

## 1. Phần đã ổn (giữ lại)

| Hạng mục | Đánh giá |
|---|---|
| Stack FastAPI + SQLite + React/Vite + Docker | Phù hợp yêu cầu mentor, đủ nhanh cho deadline 14/09/2026 |
| Chia `models / schemas / api / services / rag` | Chuẩn layered architecture, giữ nguyên |
| Tách `services/allocator.py` khỏi API layer | Đúng — thuật toán phân bổ phải test được độc lập |
| RAG dùng ChromaDB + LangChain, có `tools.py` tra cứu DB | Đúng hướng (RAG + Text-to-data tool) |
| Volume mount `data/sqlite`, `data/chromadb` | Đúng, bắt buộc để không mất dữ liệu khi rebuild container |
| Frontend chia `pages/user` và `pages/admin` | Đúng theo phân quyền |

## 2. Các lỗi thiết kế cần sửa (BLOCKER)

### 2.1. `users` quá mỏng — thiếu gần hết trường nghiệp vụ
Draft chỉ có `id, email, name, sso, role`. BRD mục 4.2 + yêu cầu của bạn đòi thêm:

`employee_code`, `phone`, `avatar_url`, `address`, `work_location_id` (HN/HCM/…), `team_id`,
`department`, `job_title`, `gender`, `date_of_birth`, `emergency_contact_name/phone`,
`dietary_restriction`, `shirt_size`, `id_card_number` (bắt buộc để xuất vé máy bay),
`date_of_issue/place` (một số hãng yêu cầu), `password_hash`, `sso_subject`,
`is_active`, `last_login_at`, `created_at`, `updated_at`.

> Ghi chú nghiệp vụ: **không có CMND/CCCD + ngày sinh + giới tính thì BTC không xuất được vé máy bay và không phân phòng theo giới được.** Đây là trường bắt buộc, draft bỏ sót.

### 2.2. Không có khái niệm `events` (kỳ Team Building)
BRD mục 13 ghi rõ *"không hard-code … Admin phải cấu hình theo từng kỳ Team Building"*.
Draft không có bảng `events` ⇒ chạy kỳ thứ 2 là phải xoá DB.
**Sửa:** mọi bảng nghiệp vụ (registration, flight, bus, room, gala, itinerary, announcement) đều mang `event_id` (FK).

### 2.3. `registrations` bị nhồi khoá ngoại (denormalized sai)
Draft: `bus_stage_1..4`, `bus_id_1..4`, `flight_id`, `room_id`, `gala_seat_id` nằm chung một bảng.

Vấn đề:
- Vi phạm 1NF — cột lặp `_1..4`, không thể thêm chặng thứ 5 mà không sửa schema (trái yêu cầu *Configurable*).
- Không có chỗ lưu **ai gán, gán lúc nào, tự động hay thủ công, lý do** ⇒ không đáp ứng được Audit Log (BRD 5.6).
- Một CBNV có **2 chuyến bay** (chiều đi + chiều về), draft chỉ có 1 cột `flight_id`.

**Sửa:** tách thành các bảng gán riêng: `flight_assignments`, `bus_assignments`, `room_assignments`, `gala_seat_assignments` — mỗi bảng có `assigned_by`, `assigned_at`, `assignment_mode` (`auto|manual`), `note`.

### 2.4. Ca 1 / Ca 2 và 4 chặng xe bị hard-code
Draft để `shift` là cột enum trên `flights` và `bus_stage_1..4`.
**Sửa:** `shifts` và `trip_legs` là **master data có bản ghi**, cấu hình theo từng event.

### 2.5. Gala Dinner không có cơ chế chống tranh chấp ghế
Draft chỉ có `gala_seat_id`. BRD 8.5 yêu cầu Seat Locking + Confirmed.
**Sửa:** thêm `gala_seat_holds` (giữ chỗ có `expires_at`), `gala_draw_orders` (thứ tự bốc thăm random của Team), và `UNIQUE(seat_id)` trên bảng assignment + transaction `BEGIN IMMEDIATE` của SQLite.

### 2.6. Thiếu hoàn toàn 7 nhóm bảng
`hotels` (tách khỏi `rooms`), `itineraries` (lịch trình – BRD mục 9), `announcements` (thông báo BTC),
`email_logs` (BRD mục 11 – cần biết mail nào đã gửi/fail), `master data` (`locations`, `pickup_points`, `departments`),
`consents` (BRD 4.3 – lưu **phiên bản quy định** CBNV đã đồng ý + timestamp, có giá trị khi tranh chấp phí phạt),
`chat_sessions` / `chat_messages` (lịch sử chatbot RAG).

### 2.7. SQLite: 3 cạm bẫy draft không nhắc
1. **SQLite mặc định TẮT foreign key enforcement.** Không bật `PRAGMA foreign_keys=ON` mỗi connection thì toàn bộ sơ đồ FK trong draft chỉ là trang trí.
2. **Chỉ 1 writer tại một thời điểm.** Gala Dinner là kịch bản nhiều người bấm cùng lúc ⇒ bắt buộc WAL + `busy_timeout` + transaction ngắn.
3. Không có công cụ migration ⇒ **thêm Alembic** ngay từ đầu.

### 2.8. RAG có nguy cơ rò rỉ dữ liệu cá nhân
Draft cho agent "tra cứu DB SQLite" nhưng không nói scope. Nếu để LLM tự sinh SQL, CBNV A có thể hỏi *"số điện thoại của chị B là gì"* và bot trả lời.
**Sửa:** cấm text-to-SQL tự do. Chỉ expose **tool có tham số cố định**, và `user_id` được **inject từ JWT ở server**, không bao giờ lấy từ câu hỏi của người dùng. Xem [06-rag-chatbot.md](06-rag-chatbot.md) §5.

### 2.9. Thiếu 4 role
BRD mục 2 có **4 nhóm**: CBNV, BTC/Admin, Team Leader, Super Admin. Draft chỉ có `role` chung chung, và `pages/` không có màn hình nào cho Team Leader.

### 2.10. Thiếu quy trình huỷ đăng ký
BRD 4.3 nhắc *"phí phạt khi huỷ không đúng quy định"* nhưng không module nào xử lý. **Sửa:** `registrations.status` có `cancelled`, cộng `cancelled_at`, `cancel_reason`, `penalty_applied`.

## 3. Bổ sung mức kỹ thuật

| Thiếu | Bổ sung |
|---|---|
| Migration | Alembic |
| Data seed | `scripts/seed.py` — tạo 1 event mẫu, ~120 CBNV, 8 team, 4 chuyến bay, 10 xe |
| State/cache FE | TanStack Query (React Query) — draft chỉ có axios trần |
| Form validation | React Hook Form + Zod |
| Rate limit / bảo vệ chat | slowapi hoặc middleware đếm request theo user |
| Health check | `GET /api/v1/health` + `healthcheck` trong docker-compose |
| Serve FE | Nginx trong container frontend (draft chỉ có `Dockerfile` chung chung) |
| Test | pytest + httpx AsyncClient, tối thiểu phủ `allocator.py` |
| i18n | Toàn bộ UI tiếng Việt, format ngày `dd/MM/yyyy`, timezone `Asia/Ho_Chi_Minh` |
| Export | openpyxl / pandas ra `.xlsx` theo template BTC |
| Timezone | Lưu UTC trong DB, render theo `Asia/Ho_Chi_Minh` ở FE |

## 4. Câu hỏi nghiệp vụ chưa chốt (ảnh hưởng code)

Trong lúc chờ BTC trả lời (BRD mục 16), **hệ thống chọn mặc định sau và đưa vào bảng `event_settings` để đổi được bằng cấu hình**:

| # | Câu hỏi | Mặc định đã chọn để làm MVP |
|---|---|---|
| 1 | Team cùng chuyến vs đúng ca cá nhân | **Team cùng chuyến ưu tiên cao hơn** (trọng số cấu hình được) |
| 2 | Ca là nguyện vọng hay ưu tiên cứng | Nguyện vọng; có cờ `is_priority_locked` cho trường hợp đặc biệt |
| 3 | Team lớn không đủ slot | Tách theo **khối lớn nhất có thể**, tối đa 2 mảnh, flag cho BTC |
| 4 | Bắt buộc cùng chuyến? | "Cố gắng tối đa" (soft constraint) |
| 5 | Phân phòng | MVP: **BTC import Excel**; auto allocation ở Phase 2 |
| 6 | Quy tắc phòng | Cùng giới **bắt buộc**, cùng team ưu tiên |
| 7 | Gala | Random thứ tự Team → Team tự chọn bàn/ghế theo lượt |
| 8 | Ai thao tác Gala | Role `team_leader` |
| 9 | Hạn sửa đăng ký | Đến khi event chuyển `registration_closed` |
| 10 | Nguồn dữ liệu CBNV | MVP: **import Excel + login nội bộ**, có sẵn interface để cắm SSO sau |
