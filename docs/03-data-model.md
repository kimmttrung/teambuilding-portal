# 03 – Mô hình dữ liệu (SQLite)

> DDL dưới đây là **nguồn chuẩn**. SQLAlchemy models và Alembic migration phải khớp file này.
> Quy ước: `id INTEGER PRIMARY KEY AUTOINCREMENT`; thời gian lưu **UTC ISO-8601** (`TEXT`);
> mọi bảng nghiệp vụ đều có `created_at`, `updated_at`.

## 1. Sơ đồ quan hệ tổng quan

```
                                ┌────────────┐
                                │   events   │  (1 kỳ Team Building)
                                └─────┬──────┘
        ┌──────────────┬──────────────┼──────────────┬───────────────┐
        ▼              ▼              ▼              ▼               ▼
  registrations    flights        trip_legs        hotels      gala_layouts
        │              │              │              │               │
        │              │              ▼              ▼               ▼
        │              │           buses           rooms        gala_tables
        │              │              │              │               │
        │              │              │              │               ▼
        │              │              │              │          gala_seats
        │              │              │              │           │       │
        ▼              ▼              ▼              ▼           ▼       ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  BẢNG GÁN (mỗi bảng có assigned_by / assigned_at / mode auto|manual)      │
  │  flight_assignments · bus_assignments · room_assignments                  │
  │  gala_seat_assignments · gala_seat_holds                                  │
  └──────────────────────────────────────────────────────────────────────────┘
        ▲
        │
   ┌────┴────┐        ┌────────────┐        ┌───────────────┐
   │  users  ├───────►│   teams    │        │  audit_logs   │
   └─────────┘        └────────────┘        └───────────────┘
```

## 2. Master data & cấu hình

```sql
CREATE TABLE events (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  code                TEXT    NOT NULL UNIQUE,          -- 'TB2026'
  name                TEXT    NOT NULL,                 -- 'Team Building 2026 – Phú Quốc'
  destination         TEXT,
  start_date          TEXT    NOT NULL,                 -- 'YYYY-MM-DD'
  end_date            TEXT    NOT NULL,
  status              TEXT    NOT NULL DEFAULT 'draft',
      -- draft | registration_open | registration_closed | allocation_processing
      -- | information_published | event_started | completed
  registration_opens_at   TEXT,
  registration_closes_at  TEXT,
  terms_version       TEXT    NOT NULL DEFAULT 'v1',    -- version quy định đang áp dụng
  terms_content       TEXT,                             -- markdown nội dung quy định + phí phạt
  banner_url          TEXT,
  is_active           INTEGER NOT NULL DEFAULT 1,       -- chỉ 1 event active tại một thời điểm
  created_at          TEXT    NOT NULL,
  updated_at          TEXT    NOT NULL
);

-- Cấu hình mềm theo event (trọng số thuật toán, thời gian giữ ghế Gala, ...)
CREATE TABLE event_settings (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id  INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  key       TEXT    NOT NULL,        -- 'allocation.team_weight', 'gala.hold_seconds'
  value     TEXT    NOT NULL,        -- JSON string
  UNIQUE(event_id, key)
);

CREATE TABLE departments (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  code    TEXT NOT NULL UNIQUE,
  name    TEXT NOT NULL
);

CREATE TABLE work_locations (              -- HN / HCM / DN ...
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  code    TEXT NOT NULL UNIQUE,
  name    TEXT NOT NULL,
  city    TEXT
);

CREATE TABLE teams (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  code           TEXT    NOT NULL UNIQUE,
  name           TEXT    NOT NULL,
  department_id  INTEGER REFERENCES departments(id),
  leader_user_id INTEGER,                        -- Team Leader thao tác Gala
      -- CỐ Ý không có FOREIGN KEY: users.team_id đã trỏ về teams.id, thêm FK ở đây
      -- tạo vòng lặp mà SQLite không ALTER TABLE thêm constraint được.
      -- Ràng buộc "leader phải là user có thật" kiểm tra ở service layer.
  color          TEXT,                            -- màu hiển thị trên sơ đồ Gala
  is_active      INTEGER NOT NULL DEFAULT 1,
  created_at     TEXT NOT NULL,
  updated_at     TEXT NOT NULL
);

CREATE TABLE shifts (                      -- Ca 1 / Ca 2 — KHÔNG hard-code
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id     INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  code         TEXT    NOT NULL,           -- 'CA1' | 'CA2'
  name         TEXT    NOT NULL,           -- 'Ca 1 – bay sáng'
  description  TEXT,                       -- 'Ca 2 bay sau giờ giao dịch, dự kiến sau 17h00'
  earliest_departure TEXT,                 -- 'HH:MM'
  display_order INTEGER NOT NULL DEFAULT 0,
  UNIQUE(event_id, code)
);
```

## 3. Người dùng — **bản đầy đủ** (điểm draft cũ thiếu nhiều nhất)

```sql
CREATE TABLE users (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,

  -- Định danh & đăng nhập
  employee_code       TEXT    UNIQUE,              -- mã nhân viên
  email               TEXT    NOT NULL UNIQUE,     -- email công ty
  password_hash       TEXT,                        -- NULL nếu chỉ login SSO
  sso_subject         TEXT    UNIQUE,              -- 'oid' từ Azure AD, để trống ở MVP
  role                TEXT    NOT NULL DEFAULT 'employee',
                      -- employee | team_leader | admin | super_admin

  -- Hồ sơ cá nhân
  full_name           TEXT    NOT NULL,
  display_name        TEXT,
  avatar_url          TEXT,                        -- ảnh đại diện (upload hoặc URL)
  phone               TEXT,
  personal_email      TEXT,
  gender              TEXT,                        -- male | female | other  (dùng phân phòng)
  date_of_birth       TEXT,                        -- 'YYYY-MM-DD' (bắt buộc để xuất vé)
  address             TEXT,                        -- địa chỉ liên hệ

  -- Thông tin công việc
  team_id             INTEGER REFERENCES teams(id),
  department_id       INTEGER REFERENCES departments(id),
  work_location_id    INTEGER REFERENCES work_locations(id),
  job_title           TEXT,
  join_date           TEXT,

  -- Thông tin phục vụ vé máy bay (bắt buộc với CBNV tham gia)
  id_card_number      TEXT,                        -- CCCD/CMND hoặc số hộ chiếu
  id_card_type        TEXT,                        -- cccd | passport
  id_card_issue_date  TEXT,
  id_card_issue_place TEXT,

  -- Thông tin phục vụ hậu cần
  shirt_size          TEXT,                        -- S | M | L | XL | XXL
  dietary_restriction TEXT,                        -- 'ăn chay', 'dị ứng hải sản', ...
  health_note         TEXT,
  emergency_contact_name  TEXT,
  emergency_contact_phone TEXT,

  -- Trạng thái
  is_active           INTEGER NOT NULL DEFAULT 1,
  must_change_password INTEGER NOT NULL DEFAULT 0,
  last_login_at       TEXT,
  created_at          TEXT NOT NULL,
  updated_at          TEXT NOT NULL
);

CREATE INDEX idx_users_team    ON users(team_id);
CREATE INDEX idx_users_role    ON users(role);
CREATE INDEX idx_users_active  ON users(is_active);
```

> **Ghi chú riêng tư:** `id_card_number`, `date_of_birth`, `address`, `health_note` là dữ liệu nhạy cảm —
> chỉ `admin`/`super_admin` đọc được; API trả về cho CBNV **chỉ dữ liệu của chính họ**;
> **tuyệt đối không đưa các trường này vào vector store của RAG** (xem [06](06-rag-chatbot.md) §5).

## 4. Đăng ký

```sql
CREATE TABLE registrations (
  id                   INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id             INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  user_id              INTEGER NOT NULL REFERENCES users(id),

  is_participating     INTEGER NOT NULL,            -- 1 = Có, 0 = Không
  not_participating_reason TEXT,

  shift_id             INTEGER REFERENCES shifts(id),   -- nguyện vọng ca
  is_shift_locked      INTEGER NOT NULL DEFAULT 0,      -- BTC ép cứng ca cho case đặc biệt
  departure_location_id INTEGER REFERENCES work_locations(id),  -- HN/HCM

  wish_note            TEXT,                        -- 'mong muốn / đề xuất'
  companion_count      INTEGER NOT NULL DEFAULT 0,  -- người thân đi cùng (nếu BTC cho phép)

  status               TEXT NOT NULL DEFAULT 'submitted',
                       -- draft | submitted | cancelled
  submitted_at         TEXT,
  cancelled_at         TEXT,
  cancel_reason        TEXT,
  penalty_applied      INTEGER NOT NULL DEFAULT 0,  -- huỷ sai quy định → đánh dấu phí phạt

  created_at           TEXT NOT NULL,
  updated_at           TEXT NOT NULL,
  UNIQUE(event_id, user_id)
);
CREATE INDEX idx_reg_event_status ON registrations(event_id, status);
CREATE INDEX idx_reg_shift        ON registrations(shift_id);

-- Nhu cầu xe: 1 dòng / chặng  (thay cho bus_stage_1..4 của draft cũ)
CREATE TABLE registration_bus_needs (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  registration_id INTEGER NOT NULL REFERENCES registrations(id) ON DELETE CASCADE,
  trip_leg_id     INTEGER NOT NULL REFERENCES trip_legs(id),
  needs_bus       INTEGER NOT NULL DEFAULT 0,
  pickup_point_id INTEGER REFERENCES pickup_points(id),
  note            TEXT,
  UNIQUE(registration_id, trip_leg_id)
);

-- Bằng chứng CBNV đã đồng ý quy định (BRD 4.3 – liên quan phí phạt)
CREATE TABLE consents (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id         INTEGER NOT NULL REFERENCES users(id),
  event_id        INTEGER NOT NULL REFERENCES events(id),
  terms_version   TEXT    NOT NULL,
  agreed_at       TEXT    NOT NULL,
  ip_address      TEXT,
  user_agent      TEXT,
  UNIQUE(user_id, event_id, terms_version)
);

-- Mỗi lần huỷ đăng ký: CBNV tự huỷ / CBNV xin huỷ chờ BTC duyệt / BTC huỷ thay (docs/04 §4.3).
-- Bảng riêng để giữ đủ lịch sử (xin → bị từ chối → xin lại), không chỉ lần huỷ cuối.
CREATE TABLE registration_cancellations (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id        INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  registration_id INTEGER NOT NULL REFERENCES registrations(id) ON DELETE CASCADE,
  user_id         INTEGER NOT NULL REFERENCES users(id),
  mode            TEXT    NOT NULL,          -- self | request | admin
  status          TEXT    NOT NULL,          -- pending | approved | rejected | withdrawn
  reason          TEXT    NOT NULL,
  event_status    TEXT    NOT NULL,          -- trạng thái kỳ lúc gửi (giai đoạn huỷ)
  after_deadline  INTEGER NOT NULL DEFAULT 0,
  requested_at    TEXT    NOT NULL,
  decided_by      INTEGER REFERENCES users(id),
  decided_at      TEXT,
  decision_note   TEXT,
  penalty_applied INTEGER NOT NULL DEFAULT 0, -- quyết định phí phạt (tự huỷ: theo hạn đăng ký)
  penalty_note    TEXT,
  released_items  TEXT,                       -- JSON: vé bay / xe / phòng / ghế Gala / vai trò đã gỡ
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);
-- Mỗi đăng ký tối đa MỘT yêu cầu đang chờ (hai lần bấm đồng thời không tạo hai yêu cầu).
CREATE UNIQUE INDEX uq_registration_cancellations_pending
  ON registration_cancellations(registration_id) WHERE status = 'pending';
```

**Huỷ luôn gỡ chỗ trong cùng transaction**: khi đăng ký chuyển `cancelled` (tự huỷ, BTC duyệt, BTC huỷ
thay), mọi `flight_assignments`, `bus_assignments`, `room_assignments`, `gala_seat_assignments` của nó bị
xoá, `buses.leader_user_id` trỏ tới người đó được gỡ, và `teams.leader_user_id` trỏ tới người đó cũng bị
gỡ (Trưởng nhóm huỷ xong không còn đổi được ghế Gala của team — BTC gán trưởng nhóm mới ở Master data).
Để lại thì thành "ghế ma": phép đếm slot bay, giường, ghế Gala tính cả người không đi.

## 5. Chuyến bay

```sql
CREATE TABLE flights (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id          INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  flight_code       TEXT    NOT NULL,               -- 'VN1234'
  airline           TEXT,
  direction         TEXT    NOT NULL,               -- outbound | return
  shift_id          INTEGER REFERENCES shifts(id),
  departure_airport TEXT    NOT NULL,               -- 'HAN'
  arrival_airport   TEXT    NOT NULL,               -- 'PQC'
  departure_time    TEXT    NOT NULL,               -- ISO datetime
  arrival_time      TEXT    NOT NULL,
  capacity          INTEGER NOT NULL,               -- tổng slot BTC mua
  reserved_slots    INTEGER NOT NULL DEFAULT 0,     -- slot giữ lại cho khách VIP/dự phòng
  note              TEXT,
  is_active         INTEGER NOT NULL DEFAULT 1,
  created_at        TEXT NOT NULL,
  updated_at        TEXT NOT NULL,
  UNIQUE(event_id, flight_code, direction, departure_time),
  CHECK (direction IN ('outbound','return')),
  CHECK (capacity >= 0 AND reserved_slots >= 0)
);
CREATE INDEX idx_flights_event_dir ON flights(event_id, direction);
-- Mã chuyến duy nhất theo (kỳ, chiều). UNIQUE ở trên còn kèm departure_time nên vẫn lọt
-- hai VN1234 chiều đi khác giờ; index này mới là ràng buộc thật (migration 8a1d4e77b2c9).
-- UNIQUE cũ giữ nguyên vì gỡ nó trên SQLite phải dựng lại bảng, mất các CHECK ở trên.
CREATE UNIQUE INDEX uq_flights_event_code_direction ON flights(event_id, flight_code, direction);

CREATE TABLE flight_assignments (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  registration_id INTEGER NOT NULL REFERENCES registrations(id) ON DELETE CASCADE,
  flight_id       INTEGER NOT NULL REFERENCES flights(id),
  direction       TEXT    NOT NULL,                 -- denormalize để UNIQUE bên dưới
  seat_number     TEXT,                             -- nếu hãng cấp số ghế
  ticket_code     TEXT,
  assignment_mode TEXT    NOT NULL DEFAULT 'auto',  -- auto | manual
  assigned_by     INTEGER REFERENCES users(id),
  assigned_at     TEXT    NOT NULL,
  note            TEXT,
  UNIQUE(registration_id, direction)                -- 1 người / 1 chiều / 1 chuyến
);
CREATE INDEX idx_fa_flight ON flight_assignments(flight_id);
```

**Chỗ trống thực tế của một chuyến** = `capacity - reserved_slots - COUNT(flight_assignments)`.
Không lưu cột `allocated_count` để tránh lệch dữ liệu; nếu cần tốc độ thì dùng VIEW.

```sql
CREATE VIEW v_flight_load AS
SELECT f.id AS flight_id, f.event_id, f.flight_code, f.direction, f.capacity, f.reserved_slots,
       COUNT(fa.id) AS assigned_count,
       f.capacity - f.reserved_slots - COUNT(fa.id) AS remaining_slots
FROM flights f LEFT JOIN flight_assignments fa ON fa.flight_id = f.id
GROUP BY f.id;
```

## 6. Khách sạn & phòng

```sql
CREATE TABLE hotels (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id   INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  name       TEXT    NOT NULL,
  address    TEXT,
  phone      TEXT,
  check_in_at  TEXT,
  check_out_at TEXT,
  map_url    TEXT,
  note       TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE rooms (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  hotel_id     INTEGER NOT NULL REFERENCES hotels(id) ON DELETE CASCADE,
  room_number  TEXT    NOT NULL,
  room_type    TEXT,                                -- twin | double | triple
  capacity     INTEGER NOT NULL,
  floor        TEXT,
  gender_policy TEXT NOT NULL DEFAULT 'any',        -- any | male | female
  note         TEXT,
  UNIQUE(hotel_id, room_number),
  CHECK (capacity > 0)
);

CREATE TABLE room_assignments (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  registration_id INTEGER NOT NULL REFERENCES registrations(id) ON DELETE CASCADE,
  room_id         INTEGER NOT NULL REFERENCES rooms(id),
  is_room_captain INTEGER NOT NULL DEFAULT 0,
  assignment_mode TEXT NOT NULL DEFAULT 'manual',   -- MVP: import Excel
  assigned_by     INTEGER REFERENCES users(id),
  assigned_at     TEXT NOT NULL,
  note            TEXT,
  UNIQUE(registration_id)
);
CREATE INDEX idx_ra_room ON room_assignments(room_id);
```

## 7. Xe & điều phối

```sql
CREATE TABLE trip_legs (                   -- 4 chặng — cấu hình được, không hard-code
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id      INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  code          TEXT    NOT NULL,          -- CITY_TO_AIRPORT | AIRPORT_TO_HOTEL
                                           -- HOTEL_TO_AIRPORT | AIRPORT_TO_CITY
  name          TEXT    NOT NULL,          -- 'HN/HCM → Sân bay'
  direction     TEXT    NOT NULL,          -- outbound | return
  leg_date      TEXT,
  display_order INTEGER NOT NULL DEFAULT 0,
  UNIQUE(event_id, code)
);

CREATE TABLE pickup_points (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id     INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  trip_leg_id  INTEGER REFERENCES trip_legs(id),
  name         TEXT NOT NULL,              -- 'Toà nhà Keangnam'
  address      TEXT,
  map_url      TEXT,
  work_location_id INTEGER REFERENCES work_locations(id)
);

CREATE TABLE buses (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id          INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  trip_leg_id       INTEGER NOT NULL REFERENCES trip_legs(id),
  bus_code          TEXT    NOT NULL,      -- 'XE-01'
  plate_number      TEXT,
  capacity          INTEGER NOT NULL,
  pickup_point_id   INTEGER REFERENCES pickup_points(id),
  dropoff_point     TEXT,
  gather_time       TEXT,                  -- giờ tập trung (ISO)
  departure_time    TEXT,                  -- giờ khởi hành (ISO)
  leader_user_id    INTEGER REFERENCES users(id),   -- Trưởng xe (là CBNV)
  leader_name       TEXT,                  -- fallback nếu Trưởng xe là người ngoài
  leader_phone      TEXT,
  driver_name       TEXT,
  driver_phone      TEXT,
  linked_flight_id  INTEGER REFERENCES flights(id), -- xe phục vụ chuyến bay nào
  note              TEXT,
  created_at        TEXT NOT NULL,
  updated_at        TEXT NOT NULL,
  UNIQUE(event_id, trip_leg_id, bus_code),
  CHECK (capacity > 0)
);
CREATE INDEX idx_buses_leg ON buses(trip_leg_id);

CREATE TABLE bus_assignments (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  registration_id INTEGER NOT NULL REFERENCES registrations(id) ON DELETE CASCADE,
  bus_id          INTEGER NOT NULL REFERENCES buses(id),
  trip_leg_id     INTEGER NOT NULL REFERENCES trip_legs(id),
  assignment_mode TEXT NOT NULL DEFAULT 'auto',
  assigned_by     INTEGER REFERENCES users(id),
  assigned_at     TEXT NOT NULL,
  note            TEXT,
  UNIQUE(registration_id, trip_leg_id)     -- 1 người / 1 chặng / 1 xe
);
CREATE INDEX idx_ba_bus ON bus_assignments(bus_id);
```

## 8. Gala Dinner

```sql
CREATE TABLE gala_layouts (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id    INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  name        TEXT NOT NULL,
  venue       TEXT,
  starts_at   TEXT,
  stage_position TEXT NOT NULL DEFAULT 'top',   -- top | bottom | left | right
  grid_width  INTEGER NOT NULL DEFAULT 12,      -- lưới toạ độ để vẽ sơ đồ
  grid_height INTEGER NOT NULL DEFAULT 10,
  selection_status TEXT NOT NULL DEFAULT 'closed', -- closed | drawing | open | finalized
  turn_seconds INTEGER NOT NULL DEFAULT 300,    -- thời gian mỗi lượt Team
  hold_seconds INTEGER NOT NULL DEFAULT 120,    -- thời gian giữ ghế tạm
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);

CREATE TABLE gala_tables (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  layout_id   INTEGER NOT NULL REFERENCES gala_layouts(id) ON DELETE CASCADE,
  table_code  TEXT NOT NULL,                    -- 'B01'
  table_name  TEXT,
  seat_count  INTEGER NOT NULL,
  pos_x       INTEGER NOT NULL,                 -- toạ độ trên lưới
  pos_y       INTEGER NOT NULL,
  is_vip      INTEGER NOT NULL DEFAULT 0,
  is_available INTEGER NOT NULL DEFAULT 1,      -- bàn không khả dụng (BTC khoá)
  UNIQUE(layout_id, table_code)
);

CREATE TABLE gala_seats (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  table_id     INTEGER NOT NULL REFERENCES gala_tables(id) ON DELETE CASCADE,
  seat_number  INTEGER NOT NULL,                -- 1..seat_count
  is_available INTEGER NOT NULL DEFAULT 1,
  UNIQUE(table_id, seat_number)
);

-- Thứ tự bốc thăm chọn chỗ của các Team
CREATE TABLE gala_draw_orders (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  layout_id    INTEGER NOT NULL REFERENCES gala_layouts(id) ON DELETE CASCADE,
  team_id      INTEGER NOT NULL REFERENCES teams(id),
  draw_position INTEGER NOT NULL,               -- 1, 2, 3...
  quota        INTEGER NOT NULL,                -- số ghế tối đa Team được chọn
  turn_started_at TEXT,
  turn_ends_at    TEXT,
  status       TEXT NOT NULL DEFAULT 'waiting', -- waiting | active | done | skipped
  UNIQUE(layout_id, team_id),
  UNIQUE(layout_id, draw_position)
);

-- Giữ ghế tạm thời (chống 2 team xác nhận cùng 1 ghế)
CREATE TABLE gala_seat_holds (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  seat_id    INTEGER NOT NULL REFERENCES gala_seats(id) ON DELETE CASCADE,
  team_id    INTEGER NOT NULL REFERENCES teams(id),
  held_by    INTEGER NOT NULL REFERENCES users(id),
  held_at    TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  UNIQUE(seat_id)                                -- 1 ghế chỉ 1 hold tại một thời điểm
);

CREATE TABLE gala_seat_assignments (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  seat_id         INTEGER NOT NULL REFERENCES gala_seats(id),
  team_id         INTEGER REFERENCES teams(id),           -- NULL = BTC xếp cho người chưa có team
  registration_id INTEGER REFERENCES registrations(id),  -- NULL = ghế của team, chưa gán người
  confirmed_by    INTEGER NOT NULL REFERENCES users(id),
  confirmed_at    TEXT NOT NULL,
  UNIQUE(seat_id),                               -- KHOÁ CHỐNG TRÙNG GHẾ
  UNIQUE(registration_id)
);
```

`team_id` NULL là ghế BTC xếp thẳng cho người **không thuộc team nào** (tài khoản BTC, người mới chưa
gán team). Họ không được bốc thăm nên không team nào chọn ghế hộ; không có ô này thì họ vĩnh viễn nằm
trong `unseated` và kỳ không chuyển sang `event_started` được. Ghế đó vẽ màu trung tính trên sơ đồ, không
tính vào quota team nào, và khi gỡ người ra thì bản ghi bị xoá hẳn (trả ghế về sơ đồ) thay vì thành ghế
không chủ. Tên người ngồi các ghế này chỉ BTC và chính người đó đọc được.

`GalaDrawOrder.quota` chỉ là **ảnh chụp lúc bốc thăm**. Mọi phép so "team đủ ghế chưa" tính lại từ số
người đang tham gia, để người huỷ đăng ký làm quota tụt và người đăng ký lại làm quota tăng trở lại.

## 9. Nội dung & thông báo

```sql
CREATE TABLE itinerary_items (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id     INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  day_date     TEXT NOT NULL,                   -- 'YYYY-MM-DD'
  start_time   TEXT,                            -- 'HH:MM'
  end_time     TEXT,
  title        TEXT NOT NULL,
  description  TEXT,
  location     TEXT,
  audience     TEXT NOT NULL DEFAULT 'all',     -- all | shift_code | team_code
  display_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE announcements (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id     INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  title        TEXT NOT NULL,
  content      TEXT NOT NULL,                   -- markdown
  severity     TEXT NOT NULL DEFAULT 'info',    -- info | warning | urgent
  target_type  TEXT NOT NULL DEFAULT 'all',     -- all | team | flight | bus | user
  target_id    INTEGER,                        -- null với all; flight/bus phải thuộc kỳ
  published_at TEXT,                            -- null = nháp, chỉ BTC thấy
  send_email   INTEGER NOT NULL DEFAULT 0,      -- có xếp email ở lần đăng cuối không
  created_by   INTEGER REFERENCES users(id),
  created_at   TEXT NOT NULL
);

CREATE TABLE policy_documents (                  -- nguồn cho RAG + trang quy định
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id    INTEGER REFERENCES events(id) ON DELETE CASCADE,
  doc_type    TEXT NOT NULL,                    -- terms | faq | guide | itinerary
  title       TEXT NOT NULL,
  content     TEXT NOT NULL,                    -- markdown
  version     TEXT NOT NULL DEFAULT 'v1',
  is_indexed  INTEGER NOT NULL DEFAULT 0,       -- đã nạp vào vector store chưa
  updated_at  TEXT NOT NULL
);
```

## 10. Hệ thống: email, chat, audit

```sql
CREATE TABLE email_logs (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  -- Thư thuộc kỳ nào: nhật ký email và ô Email trên Tổng quan lọc theo kỳ đang chọn.
  -- NULL = dòng cũ hoặc thư không gắn kỳ. Không CASCADE: xoá kỳ vẫn giữ bằng chứng đã gửi.
  event_id     INTEGER REFERENCES events(id),
  user_id      INTEGER REFERENCES users(id),
  to_email     TEXT NOT NULL,
  template     TEXT NOT NULL,                   -- registration_confirmed | info_published | change_notice
  subject      TEXT NOT NULL,
  status       TEXT NOT NULL DEFAULT 'queued',  -- queued | sent | failed
  error_message TEXT,
  related_type TEXT,                            -- 'registration' | 'flight_assignment' ...
  related_id   INTEGER,
  sent_at      TEXT,
  created_at   TEXT NOT NULL
);

CREATE TABLE chat_sessions (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id    INTEGER NOT NULL REFERENCES users(id),
  event_id   INTEGER REFERENCES events(id),
  title      TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE chat_messages (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id  INTEGER NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
  role        TEXT NOT NULL,                    -- user | assistant
  content     TEXT NOT NULL,
  sources     TEXT,                             -- JSON: tài liệu đã trích dẫn
  tokens_used INTEGER,
  latency_ms  INTEGER,
  created_at  TEXT NOT NULL
);

-- Nền cho rate limit đăng nhập theo IP (09-security.md §5). Ghi cả lần sai lẫn lần đúng,
-- kể cả với email không tồn tại — nếu chỉ đếm email có thật thì dò danh sách email là miễn phí.
-- Dòng cũ hơn 24 giờ bị xoá ngay trong lúc ghi (login_guard._purge_old), không cần job nền.
CREATE TABLE login_attempts (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  email        TEXT NOT NULL,                   -- đã lower + strip, KHÔNG có FK sang users
  ip_address   TEXT NOT NULL,                   -- 'unknown' nếu không xác định được
  succeeded    INTEGER NOT NULL DEFAULT 0,
  attempted_at TEXT NOT NULL
);
CREATE INDEX ix_login_attempts_email_ip_time ON login_attempts(email, ip_address, attempted_at);
CREATE INDEX ix_login_attempts_ip_time       ON login_attempts(ip_address, attempted_at);

CREATE TABLE audit_logs (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id    INTEGER REFERENCES events(id),
  actor_id    INTEGER REFERENCES users(id),
  action      TEXT NOT NULL,                    -- flight.reassign | bus.assign | event.publish ...
  entity_type TEXT NOT NULL,
  entity_id   INTEGER,
  before_data TEXT,                             -- JSON
  after_data  TEXT,                             -- JSON
  reason      TEXT,
  ip_address  TEXT,
  created_at  TEXT NOT NULL
);
CREATE INDEX idx_audit_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX idx_audit_actor  ON audit_logs(actor_id, created_at);
```

## 11. PRAGMA bắt buộc (SQLite)

Áp dụng **mỗi connection** — nếu thiếu, toàn bộ FOREIGN KEY ở trên không được thực thi:

```python
@event.listens_for(Engine, "connect")
def _sqlite_pragmas(dbapi_conn, _):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")     # SQLite mặc định TẮT
    cur.execute("PRAGMA journal_mode=WAL")    # cho phép đọc song song khi đang ghi
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.execute("PRAGMA busy_timeout=5000")   # chờ 5s thay vì ném 'database is locked'
    cur.close()
```

Với thao tác có tranh chấp (giữ/xác nhận ghế Gala, đổi chuyến bay): mở transaction bằng
`BEGIN IMMEDIATE` để giành write-lock ngay, tránh deadlock upgrade từ read → write.

## 12. Bất biến dữ liệu (invariants) cần test

1. `COUNT(flight_assignments per flight) <= capacity - reserved_slots`
2. `COUNT(bus_assignments per bus) <= buses.capacity`
3. `COUNT(room_assignments per room) <= rooms.capacity`
4. Trong 1 phòng, nếu `rooms.gender_policy != 'any'` thì mọi người trong phòng cùng giới đó.
5. Một `registration` có tối đa 1 `flight_assignment` mỗi `direction`.
6. Một `registration` có tối đa 1 `bus_assignment` mỗi `trip_leg`.
7. Một `gala_seat` có tối đa 1 assignment (DB constraint) và tối đa 1 hold còn hạn.
8. Số ghế Gala một team giữ + đã xác nhận `<= gala_draw_orders.quota`.
9. Chỉ có tối đa 1 `events` với `is_active = 1`.
10. `registration` có `is_participating = 0` thì không được có bất kỳ assignment nào.


## 13. Sai khác giữa tài liệu và schema đã implement

Schema đã được hiện thực hoá bằng SQLAlchemy (`backend/app/models/`) và migration
`alembic/versions/*_initial_schema.py`. **35 bảng.** `alembic check` không báo lệch.

Ba bảng thêm sau bản đầu, mỗi bảng một migration riêng: `refresh_tokens` (phiên đăng nhập,
thu hồi được), `registration_cancellations` (huỷ tham gia theo giai đoạn),
`login_attempts` (rate limit đăng nhập theo IP — DDL ở §10).

Các trường phát sinh trong lúc implement, đã có trong code nhưng chưa nêu ở DDL phía trên:

| Bảng | Trường thêm | Lý do |
|---|---|---|
| `trip_legs` | `is_airport_linked` | Phân biệt chặng gắn sân bay (xe phải khớp giờ chuyến bay) với chặng nội thành — thuật toán phân xe cần cờ này |
| `gala_layouts` | `draw_seed` | Lưu seed của lần bốc thăm để tái lập kết quả khi BTC cần đối chiếu |
| `email_logs` | `body_preview`, `retry_count` | Trả lời được câu "tôi không nhận được mail": xem nội dung đã gửi và số lần thử lại |
| `itinerary_items` | `is_indexed` | Đánh dấu mục lịch trình đã nạp vào vector store chưa |
| `work_locations` | `airport_code` | HN→HAN, HCM→SGN — suy ra sân bay đi mà không cần bảng ánh xạ riêng |
| `departments`, `work_locations` | `display_order`, `is_active` | Thứ tự dropdown và ẩn mục đã ngừng dùng |

Quy ước đã áp dụng khi implement:
- Kiểu `BOOLEAN` của SQLAlchemy lưu thành `INTEGER 0/1` trong SQLite (không sinh CHECK thừa).
- Mọi `CHECK` enum sinh từ `app/models/enums.py` bằng `sql_in()` — sửa enum trong Python
  là migration tự bắt được, không lệch giữa code và DB.
- Mọi constraint đều được đặt tên theo `NAMING_CONVENTION` trong `models/base.py`;
  bắt buộc, vì Alembic batch mode trên SQLite cần tên để drop/tạo lại.
