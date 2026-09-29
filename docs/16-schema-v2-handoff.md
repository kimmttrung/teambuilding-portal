# 16 – Schema DB 24 bảng: migration và bàn giao backend

> Revision Alembic `c24a29db2026` chuyển schema xuống 24 bảng và lưu nguyên dòng bị gộp
> vào `schema_archive`. `scripts/seed_v2.py` dùng SQL trực tiếp trên DB mới. **Backend/ORM
> cũ chưa chuyển**: `alembic check` sẽ báo lệch, `seed.py` cũ và API không được chạy trên DB
> 24 bảng. Entry-point giữ backend cũ ở revision `5f3a91c7d420` và chặn `serve`
> nếu volume đã lên v2; chỉ nâng DB thử/bản sao qua `alembic upgrade head` thủ công.

## 1. Danh sách đích (23 bảng nghiệp vụ + 1 bảng archive = 24)

| Nhóm | Bảng giữ lại |
|---|---|
| Kỳ, nhân sự, cấu hình | `events`, `users`, `departments`, `work_locations`, `teams`, `shifts` |
| Đăng ký, vận chuyển | `registrations`, `registration_cancellations`, `flights`, `flight_assignments`, `trip_legs`, `pickup_points`, `buses`, `bus_assignments` |
| Phòng, Gala | `hotels`, `rooms`, `gala_layouts`, `gala_tables`, `gala_seats` |
| Hệ thống | `email_logs`, `audit_logs`, `refresh_tokens`, `login_attempts`, `schema_archive` |

Không có bảng “lưu nháp” riêng trong 35 bảng cũ: nháp đăng ký ở localStorage;
`events.status = 'draft'` là giai đoạn nghiệp vụ; `announcements.published_at IS NULL`
là nháp thông báo. Không được xoá trạng thái `draft` chỉ vì giảm số bảng.

## 2. Ánh xạ 12 bảng cũ bị gộp (không xoá nội dung cũ)

| Bảng cũ | Dữ liệu hoạt động ở bảng mới | Bản gốc để phục hồi |
|---|---|---|
| `event_settings` | `events.settings_json` (key → value/description) | `schema_archive` |
| `registration_bus_needs` | `registrations.bus_needs_json` (mảng theo `trip_leg_id`) | `schema_archive` |
| `consents` | `registrations.consents_json` (mảng *toàn bộ* version/time/IP/UA, không chỉ bản mới nhất) | `schema_archive` |
| `room_assignments` | `registrations.room_id`, `room_assignment_json` (captain, mode, người/giờ gán, note); phải giữ UNIQUE theo registration | `schema_archive` |
| `gala_draw_orders` | `gala_layouts.draw_orders_json` (thứ tự, quota snapshot và trạng thái lượt) | `schema_archive` |
| `gala_seat_holds` | `gala_seats.hold_json` (team, holder, held_at, expires_at) | `schema_archive` |
| `gala_seat_assignments` | `gala_seats.assignment_json` (team nullable, registration nullable, confirmed_by/at); UNIQUE index theo `registration_id` khác NULL | `schema_archive` |
| `itinerary_items` | `events.itinerary_json` (mảng có id, ngày/giờ, audience, trip_leg_id, thứ tự, is_indexed) | `schema_archive` |
| `policy_documents` | `events.documents_json` đối với tài liệu theo kỳ; tài liệu chung `event_id IS NULL` phải có chỗ riêng (vd cấu hình hệ thống trong archive với cơ chế đọc tập trung) | `schema_archive` |
| `announcements` | `events.announcements_json`; **giữ cả bản nháp**, target, thời gian đăng, người tạo | `schema_archive` |
| `chat_sessions` | `users.chat_history_json` (phiên theo event, id, title, created_at) | `schema_archive` |
| `chat_messages` | tin trong từng phiên `users.chat_history_json` (id, role, sources, tokens/latency, timestamp) | `schema_archive` |

**Không gộp** `registration_cancellations` (lịch sử nhiều lần và index `pending`),
`refresh_tokens` (xoay vòng/thu hồi), `login_attempts` (rate limit theo IP),
`audit_logs` (bằng chứng), hay các bảng bay/xe có unique cho từng chiều/chặng.
**Giữ** `hotels` và `rooms`: các phòng thuộc nhiều khách sạn và lookup `room_id`
của nhiều người vẫn cần FK thật; chỉ gộp bản gán vào đăng ký.

## 3. DDL phần thay đổi (các bảng giữ lại theo DDL cũ)

DDL đầy đủ cho **24 bảng sau migration** và index nằm trong `03-data-model.md`.
Các bảng giữ lại bắt nguồn từ `03-legacy-data-model.md` với các cột bổ sung dưới đây;
12 bảng ở §2 trong file lịch sử **không** tồn tại trong schema v2.

```sql
CREATE TABLE schema_archive (
  id INTEGER PRIMARY KEY,
  source_table VARCHAR(64) NOT NULL,
  source_id INTEGER NOT NULL,
  payload TEXT NOT NULL,                -- JSON nguyên dòng nguồn, chỉ truy cập offline
  archived_at VARCHAR(32) NOT NULL,    -- UTC ISO-8601
  CONSTRAINT uq_schema_archive_source UNIQUE(source_table, source_id)
);
ALTER TABLE events ADD COLUMN settings_json TEXT;
ALTER TABLE events ADD COLUMN itinerary_json TEXT;
ALTER TABLE events ADD COLUMN documents_json TEXT;
ALTER TABLE events ADD COLUMN announcements_json TEXT;
ALTER TABLE registrations ADD COLUMN bus_needs_json TEXT;
ALTER TABLE registrations ADD COLUMN consents_json TEXT;
ALTER TABLE registrations ADD COLUMN room_assignment_json TEXT;
ALTER TABLE registrations ADD COLUMN room_id INTEGER;
CREATE INDEX ix_registrations_room_id ON registrations(room_id);
ALTER TABLE gala_layouts ADD COLUMN draw_orders_json TEXT;
ALTER TABLE gala_seats ADD COLUMN hold_json TEXT;
ALTER TABLE gala_seats ADD COLUMN assignment_json TEXT;
ALTER TABLE users ADD COLUMN chat_history_json TEXT;
CREATE UNIQUE INDEX uq_gala_seats_assigned_registration ON gala_seats
  (json_extract(assignment_json, '$.registration_id'))
  WHERE json_extract(assignment_json, '$.registration_id') IS NOT NULL;
```

`registrations.room_id` **chưa có FK cứng**: SQLite không thêm FK vào bảng cũ bằng
`ALTER TABLE` (bảng `registrations` đang được nhiều bảng khác tham chiếu). Không dựa vào
`PRAGMA foreign_key_check` để phát hiện `room_id` không hợp lệ; service phải validate.
JSON mảng/đối tượng giữ đủ các trường nguyên gốc (bao gồm id); `NULL` nghĩa là không
có dòng nguồn. Tài liệu chung `policy_documents.event_id IS NULL` chỉ có trong archive;
RAG hiện **chưa** đọc lại chúng từ schema mới.

## 4. Chạy migration/seed an toàn (DB thử, KHÔNG phải volume production)

```sh
cd backend
# DATABASE_URL trỏ tới bản sao DB cũ, hoặc file DB tạm trống; dùng Python 3.13 có requirements.txt.
alembic upgrade head
python scripts/seed_v2.py --database /path/to/test.db --reset
python scripts/seed_v2.py --database /path/to/test.db --second-event
python scripts/verify_schema_v2.py --database /path/to/test.db
```

**Không** dùng `--reset` trên DB cũ đã migrate: nó sẽ xoá dữ liệu nghiệp vụ;
`seed_v2.py` từ chối `--reset` nếu `schema_archive` có bản ghi. `--second-event`
chỉ tạo TB2027 nếu chưa có, không đụng kỳ cũ. Seed v2 tạo một nhân viên và các
đối tượng liên quan mỗi kỳ (không thay thế bộ mẫu 120 CBNV của seed cũ).
Người dùng mẫu: `superadmin@company.vn` / `btc@company.vn` mật khẩu `Admin12345`;
`demo@company.vn` mật khẩu `Matkhau123`.

## 5. Hợp đồng migration an toàn

1. Sao lưu nhất quán DB nguồn bằng SQLite backup API (không copy file `.db` đang dùng WAL).
   Dùng `backend/scripts/preflight_schema_v2.py --source ... --backup ...` trước khi nâng cấp.
2. Chỉ chạy khi ứng dụng **đã dừng**, kiểm tra `alembic_version` ở revision cũ hợp lệ;
   không sửa các revision đã có. Một revision mới duy nhất nối sau `5f3a91c7d420`.
3. Tạo `schema_archive`: `(source_table, source_id)` UNIQUE, `payload` là JSON nguyên
   dòng, `archived_at` UTC; **không** để bản gốc chứa CCCD/chat trong `audit_logs` hoặc
   ChromaDB. Archive chỉ dành cho khôi phục offline, không trả qua API.
4. Kiểm kê từng bảng, sao nguyên dòng vào archive, verify đếm từng bảng **trước**
   khi drop; chuyển dữ liệu theo `event_id`/`registration_id`/`user_id`, xác minh FK
   và JSON. `policy_documents.event_id IS NULL` chỉ giữ trong archive, không gán
   ngẫu nhiên sang kỳ hiện hành. **SQLite DDL không rollback trọn vẹn khi lỗi:**
   phải tạo backup ngoài DB trước migration, chạy trên bản sao và phục hồi backup
   nếu migration bị ngắt; không tiếp tục với DB đã migrate dở.
5. SQLite không thêm FK cho `registrations.room_id` bằng ALTER TABLE; service phải
   kiểm tra chéo phòng và kỳ trước khi ghi. VIEW không tính là bảng.
6. Trước khi đánh dấu revision head: `PRAGMA foreign_key_check`, đối chiếu số dòng
   archive theo từng bảng, `SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND
   name NOT LIKE 'sqlite_%' AND name <> 'alembic_version'` = **24**.
7. Kiểm tra upgrade trên DB trống và **bản sao** DB cũ; seed `--reset`, `--second-event`,
   `alembic check`, toàn bộ pytest. Không đổi file DB thật để chụp bằng chứng.

## 6. Nơi backend phải đổi cùng PR hoặc bàn giao cho từng chủ module

| Nhóm | Những chỗ phải thay trước khi chạy backend trên DB 24 bảng |
|---|---|
| F2 đăng ký/huỷ | `models/registration.py`, `registration_service`, `cancellation_service`, `services/allocator/buses.py`: đọc/ghi nhu cầu xe và consent JSON; gỡ `room_id`/ghế cùng transaction huỷ. Phải giữ lịch sử đồng ý và `pending` cancellation. |
| F3/F4 bay/xe | Không xoá bảng gán bay/xe; `journey_service`, `export_service`, `transport_timing_service` đọc đúng nhu cầu xe mới. |
| F5 phòng | `models/accommodation.py`, `room_import_service`, `room_allocation_service`, `allocator/rooms.py`, `accommodation_service`: thay `RoomAssignment` bằng trường trên registration; giữ manual, captain, validate capacity/gender và audit. |
| F7 Gala | `models/gala.py`, `gala_service`, `gala_stream`: cập nhật giữ/chốt ghế trên `gala_seats` trong `BEGIN IMMEDIATE`, kiểm tra quota, UNIQUE người/ghế, timeout, bốc thăm. Không đưa thông tin người ngồi ra SSE. |
| F6/F8/F9/F10 | `models/content.py`, `models/chat.py`, `models/event.py`, `event_service`, `itinerary_service`, `announcement_service`, `policy_document_service`, `chat_service`, `rag/knowledge.py`, `rag_index_service`, `dashboard_service`, `email_resend_service`: chuyển truy vấn/CRUD sang JSON; tuyệt đối không index chat/consent hay thông báo riêng vào RAG. Khóa quyền chủ sở hữu session khi đọc/xoá chat. |
| Chung | `models/__init__.py`, `scripts/seed.py` (`--reset`/`--second-event`), test fixtures/`test_models.py` (hiện assert 35 bảng), exports và mọi chỗ import các model bị gộp; không để Alembic autogenerate sinh lại 12 bảng. |

**Chưa nghiệm thu backend:** ORM, `seed.py` cũ và service chưa chuyển; `alembic check`
đỏ đúng vì metadata vẫn có 12 bảng bị drop. `pytest -q` toàn dự án chạy xanh trong
Docker **với fixture ORM 35 bảng cũ**; đây không phải kiểm thử API trên DB v2. Chưa
merge PR/screenshot hay Docker serve trên v2. Chỉ chạy các script v2 trên bản sao DB
bằng container với `--entrypoint sh`, không chạy entrypoint `serve` lên volume đang dùng.