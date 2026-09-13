# 04 – Đặc tả API (v1)

Base URL: `/api/v1` · Auth: `Authorization: Bearer <access_token>` · Docs tự sinh: `/docs` (Swagger), `/redoc`.

## 1. Quy ước chung

**Lỗi** — mọi lỗi trả cùng một khuôn:
```json
{ "error": { "code": "FLIGHT_CAPACITY_EXCEEDED",
             "message": "Chuyến VN1234 chỉ còn 2 chỗ, cần 5 chỗ.",
             "details": { "flight_id": 3, "remaining": 2, "requested": 5 } } }
```

| HTTP | Khi nào |
|---|---|
| 400 | Dữ liệu vào sai |
| 401 | Thiếu/hết hạn token |
| 403 | Sai role, hoặc truy cập dữ liệu người khác |
| 404 | Không tồn tại |
| 409 | Xung đột trạng thái: vượt slot, ghế đã bị chiếm, event sai trạng thái |
| 422 | Pydantic validation |
| 429 | Vượt rate limit (chat) |

**Phân trang**: `?page=1&page_size=50` → `{ "items": [...], "total": 340, "page": 1, "page_size": 50 }`
**Lọc/sắp xếp**: `?q=&team_id=&status=&sort=full_name&order=asc`
**Cột `Legend` role**: 🟢 mọi user đã đăng nhập · 🔵 team_leader · 🔴 admin · ⚫ super_admin

---

## 2. Auth & hồ sơ

| Method | Path | Role | Mô tả |
|---|---|---|---|
| POST | `/auth/login` | – | `{email, password}` → `{access_token, refresh_token, user}` |
| POST | `/auth/refresh` | – | đổi refresh token lấy access token mới |
| POST | `/auth/logout` | 🟢 | thu hồi refresh token |
| GET | `/auth/me` | 🟢 | hồ sơ đầy đủ của chính mình |
| PATCH | `/auth/me` | 🟢 | cập nhật `phone`, `address`, `avatar_url`, `dietary_restriction`, `shirt_size`, `emergency_contact_*`, `id_card_*` |
| POST | `/auth/me/avatar` | 🟢 | upload ảnh (multipart, ≤2MB, jpg/png/webp) → trả `avatar_url` |
| POST | `/auth/change-password` | 🟢 | đổi mật khẩu → thu hồi mọi phiên đang mở |
| GET | `/auth/sso/login` · `/auth/sso/callback` | – | stub sẵn, Phase 2 |

**Mã lỗi của nhóm auth** (đã implement):

| Code | HTTP | Khi nào |
|---|---|---|
| `INVALID_CREDENTIALS` | 401 | Sai email **hoặc** sai mật khẩu — cùng một thông điệp, không tiết lộ email nào có thật |
| `ACCOUNT_LOCKED` | 401 | Sai 5 lần liên tiếp → khoá tạm 15 phút |
| `ACCOUNT_DISABLED` | 401 | `is_active = 0` |
| `TOKEN_EXPIRED` · `TOKEN_INVALID` · `TOKEN_WRONG_TYPE` | 401 | Access token hỏng/hết hạn, hoặc dùng refresh token thay access token |
| `SESSION_REVOKED` | 401 | Refresh token đã bị xoay vòng hoặc đã logout — dấu hiệu token bị đánh cắp |
| `SESSION_EXPIRED` · `SESSION_NOT_FOUND` | 401 | Phiên hết hạn hoặc không còn trong DB |
| `PERMISSION_DENIED` | 403 | Sai vai trò, hoặc truy cập dữ liệu người khác |
| `UNSUPPORTED_FILE_TYPE` · `FILE_TOO_LARGE` | 400 | Upload avatar không phải JPG/PNG/WEBP, hoặc quá `MAX_UPLOAD_MB` |

**Refresh token xoay vòng (rotation)**: mỗi lần gọi `/auth/refresh`, token cũ bị thu hồi ngay
và trả về token mới. Dùng lại token cũ → `SESSION_REVOKED`. Frontend phải luôn lưu đè
`refresh_token` mới nhận được.

## 3. Event & master data

| Method | Path | Role | Mô tả |
|---|---|---|---|
| GET | `/events/active` | 🟢 | event đang mở + `status` + `terms_version` + mốc thời gian |
| GET | `/events/{id}/terms` | 🟢 | nội dung quy định & phí phạt (markdown) |
| GET | `/events` | 🔴 | danh sách kỳ |
| POST · PATCH | `/events` · `/events/{id}` | 🔴 | tạo/sửa kỳ |
| POST | `/events/{id}/status` | 🔴 | `{status, reason}` – đổi trạng thái, ghi audit, tuỳ chọn gửi email hàng loạt |
| GET · PUT | `/events/{id}/settings` | 🔴 | trọng số thuật toán, `gala.hold_seconds`, … |
| GET | `/master-data/teams` · `/departments` · `/work-locations` · `/shifts` · `/trip-legs` · `/pickup-points` | 🟢 | dropdown cho form |
| POST · PATCH · DELETE | các path trên | 🔴 | CRUD master data |

## 4. Module 1 – Đăng ký

| Method | Path | Role | Mô tả |
|---|---|---|---|
| GET | `/registrations/me` | 🟢 | đăng ký của mình ở event active (404 nếu chưa có) |
| POST | `/registrations` | 🟢 | tạo đăng ký. Guard: `event.status == registration_open` |
| PATCH | `/registrations/me` | 🟢 | sửa khi còn mở |
| POST | `/registrations/me/cancel` | 🟢 | `{reason}` → `status=cancelled`, tính cờ `penalty_applied` theo mốc `registration_closes_at` |
| GET | `/registrations` | 🔴 | danh sách + filter + phân trang |
| GET | `/registrations/export` | 🔴 | `.xlsx` toàn bộ đăng ký |
| POST | `/registrations/import` | 🔴 | import Excel danh sách CBNV/đăng ký, trả báo cáo dòng lỗi |
| GET | `/registrations/stats` | 🔴 | số liệu dashboard: theo ca, nhu cầu xe từng chặng, thiếu giấy tờ |
| GET | `/registrations/{user_id}` | 🟢🔴 | CBNV chỉ xem được của chính mình |

**Bộ lọc của `GET /registrations`**: `q` (tên/email/mã NV) · `team_id` · `shift_id` · `status`
· `is_participating` · `missing_documents=true` (lọc riêng người thiếu CCCD/ngày sinh — nhóm này
BTC phải nhắc gấp vì không xuất được vé).

**Mã lỗi nhóm đăng ký** (đã implement):

| Code | HTTP | Khi nào |
|---|---|---|
| `REGISTRATION_CLOSED` | 409 | Gửi/sửa khi event không còn ở `registration_open` |
| `ALREADY_REGISTERED` | 409 | Đã đăng ký rồi — dùng PATCH để sửa |
| `TERMS_VERSION_MISMATCH` | 409 | Mở form trước khi BTC sửa quy định; phải đọc lại bản mới |
| `MISSING_PROFILE_FIELDS` | 400 | Thiếu ngày sinh / CCCD / SĐT / giới tính → không xuất được vé |
| `SHIFT_REQUIRED` · `SHIFT_NOT_FOUND` | 400/404 | Không chọn ca, hoặc chọn ca của kỳ khác |
| `TRIP_LEG_NOT_FOUND` · `DUPLICATE_TRIP_LEG` | 404/409 | Chặng không thuộc kỳ, hoặc khai hai lần |
| `ALREADY_CANCELLED` · `EVENT_ALREADY_STARTED` | 409 | Huỷ hai lần, hoặc huỷ khi chương trình đã bắt đầu |

**Ba quy tắc dữ liệu**:
1. Gửi `bus_needs` là **ghi đè toàn bộ** — bỏ tick một chặng thì dòng cũ bị xoá, không chỉ đổi cờ.
2. Chuyển sang "không tham gia" thì hệ thống tự xoá nguyện vọng ca và nhu cầu xe.
3. Huỷ rồi đăng ký lại dùng **cùng một bản ghi** (`UNIQUE(event_id, user_id)`), cờ phí phạt được reset.

**Body POST `/registrations`**
```json
{
  "is_participating": true,
  "shift_id": 2,
  "departure_location_id": 1,
  "bus_needs": [
    { "trip_leg_id": 1, "needs_bus": true,  "pickup_point_id": 3 },
    { "trip_leg_id": 2, "needs_bus": true,  "pickup_point_id": null },
    { "trip_leg_id": 3, "needs_bus": false, "pickup_point_id": null },
    { "trip_leg_id": 4, "needs_bus": true,  "pickup_point_id": 3 }
  ],
  "wish_note": "Mong có hoạt động team building ngoài trời",
  "agreed_terms_version": "v1",
  "profile_patch": { "phone": "0912345678", "id_card_number": "0010xxxxxxx", "shirt_size": "L" }
}
```
Backend: `agreed_terms_version` phải khớp `events.terms_version`, nếu lệch → 409 `TERMS_VERSION_MISMATCH`
(người dùng mở form từ trước khi BTC sửa quy định). `profile_patch` cập nhật `users` trong cùng transaction.

## 5. Module 2 – Chuyến bay

| Method | Path | Role | Mô tả |
|---|---|---|---|
| GET | `/flights` | 🔴 | kèm `assigned_count`, `remaining_slots` (từ `v_flight_load`) |
| POST · PATCH · DELETE | `/flights` · `/flights/{id}` | 🔴 | CRUD |
| POST | `/flights/import` | 🔴 | Excel: mã chuyến, ngày/giờ, điểm đi/đến, capacity |
| POST | `/flights/allocate` | 🔴 | `{event_id, direction, dry_run}` → chạy Auto Allocation |
| GET | `/flights/{id}/passengers` | 🔴 | danh sách hành khách + team |
| GET | `/flight-assignments` | 🔴 | filter theo team/flight/flag |
| PATCH | `/flight-assignments/{id}` | 🔴 | `{flight_id, reason}` – chuyển 1 người |
| POST | `/flight-assignments/bulk-move` | 🔴 | `{registration_ids[], flight_id, reason}` – chuyển cả nhóm |
| DELETE | `/flight-assignments/{id}` | 🔴 | bỏ phân bổ |

**Response `/flights/allocate`**
```json
{
  "dry_run": true,
  "summary": { "total_participants": 320, "assigned": 316, "unassigned": 4,
               "teams_split": 3, "shift_satisfaction_rate": 0.94 },
  "flights": [ { "flight_id": 1, "flight_code": "VN1234", "capacity": 180,
                 "assigned": 178, "remaining": 2,
                 "teams": [ { "team_id": 2, "team_name": "Sales HN", "count": 24 } ] } ],
  "flags": [
    { "type": "TEAM_SPLIT", "severity": "warning", "team_id": 5,
      "message": "Team Marketing bị tách thành 2 chuyến (18 + 6)." },
    { "type": "SHIFT_NOT_SATISFIED", "severity": "warning", "registration_id": 88,
      "message": "Nguyễn Văn A đăng ký Ca 2 nhưng được xếp Ca 1." },
    { "type": "UNASSIGNED", "severity": "error", "registration_id": 91,
      "message": "Hết slot cho chiều đi." }
  ]
}
```
`dry_run=false` trả cùng cấu trúc + `"committed": true` và đã ghi `flight_assignments` + `audit_logs`.

## 6. Khách sạn & phòng

| Method | Path | Role | Mô tả |
|---|---|---|---|
| GET · POST · PATCH · DELETE | `/hotels`, `/hotels/{id}` | 🔴 | CRUD khách sạn |
| GET · POST · PATCH · DELETE | `/rooms`, `/rooms/{id}` | 🔴 | CRUD phòng |
| POST | `/rooms/import` | 🔴 | import Excel phân phòng (MVP). `?dry_run=true&replace_existing=false`. Cột: `Số phòng` + `Mã NV`/`Email`, tuỳ chọn `Khách sạn`, `Trưởng phòng`. Còn lỗi thì **không ghi dòng nào**, trả lỗi kèm số dòng Excel |
| GET | `/rooms/summary` | 🔴 | giường theo `gender_policy` so với người tham gia theo giới tính, kèm `uncovered` |
| GET | `/rooms/{id}/occupants` | 🔴 | |
| GET · POST | `/room-assignments` · DELETE `/room-assignments/{id}` | 🔴 | gán/bỏ gán, validate capacity + `gender_policy`; người đã có phòng phải gửi `replace_existing=true` mới chuyển; DELETE đòi `?reason=` |
| GET | `/rooms/export` | 🔴 | xuất sơ đồ phòng |

## 7. Module 3 – Xe

| Method | Path | Role | Mô tả |
|---|---|---|---|
| GET · POST · PATCH · DELETE | `/buses`, `/buses/{id}` | 🔴 | CRUD, gồm `gather_time`, `pickup_point_id`, `linked_flight_id` |
| POST | `/buses/import` | 🔴 | |
| POST | `/buses/allocate` | 🔴 | `{event_id, trip_leg_id, dry_run}` – auto phân xe |
| PATCH | `/buses/{id}/leader` | 🔴 | `{leader_user_id}` hoặc `{leader_name, leader_phone}` |
| GET | `/buses/{id}/passengers` | 🔴🔵 | Trưởng xe xem được danh sách xe mình phụ trách |
| PATCH | `/bus-assignments/{id}` | 🔴 | chuyển người sang xe khác, validate capacity |
| GET | `/buses/export` | 🔴 | danh sách theo từng xe/chặng |

## 8. Module 4 – Gala Dinner

| Method | Path | Role | Mô tả |
|---|---|---|---|
| GET | `/gala/layout` | 🟢 | sơ đồ đầy đủ: bàn, ghế, trạng thái mỗi ghế |
| POST · PATCH | `/gala/layout` · `/gala/tables` | 🔴 | cấu hình sơ đồ, toạ độ bàn |
| POST | `/gala/draw` | 🔴 | random thứ tự Team → tạo `gala_draw_orders` (ghi seed để tái lập) |
| GET | `/gala/draw-orders` | 🟢 | thứ tự + team đang tới lượt + đồng hồ đếm ngược |
| POST | `/gala/turn/next` | 🔴 | chuyển lượt (thủ công hoặc hết giờ) |
| POST | `/gala/seats/hold` | 🔵 | `{seat_ids[]}` – giữ ghế tạm, trả `expires_at` |
| DELETE | `/gala/seats/hold` | 🔵 | nhả ghế đang giữ |
| POST | `/gala/seats/confirm` | 🔵 | xác nhận toàn bộ ghế đang giữ |
| POST | `/gala/seats/assign-member` | 🔵 | gán CBNV cụ thể vào ghế của team |
| PATCH | `/gala/seats/{id}` | 🔴 | BTC ép gán/khoá ghế |
| GET | `/gala/stream` | 🟢 | **SSE**: đẩy thay đổi trạng thái ghế realtime cho mọi client đang mở sơ đồ |

**Trạng thái ghế trả về**: `available` · `held_by_me` · `held_by_other` · `taken` · `unavailable`.
Ghế `taken` kèm `team_name` + `team_color` để vẽ; **không lộ tên cá nhân** cho người ngoài team.

## 9. Module 5 – My Journey

| Method | Path | Role | Mô tả |
|---|---|---|---|
| GET | `/journey/me` | 🟢 | toàn bộ hành trình trong **1 request** |
| GET | `/journey/me/pdf` | 🟢 | (nice-to-have) xuất PDF mang theo |
| GET | `/journey/{user_id}` | 🔴 | BTC tra cứu hộ CBNV |

```json
{
  "event": { "code": "TB2026", "name": "...", "status": "information_published",
             "destination": "Phú Quốc", "start_date": "2026-10-15" },
  "profile": { "full_name": "...", "employee_code": "...", "avatar_url": "...",
               "team": { "name": "Sales HN", "color": "#2563eb" }, "phone": "..." },
  "flights": {
    "outbound": { "flight_code": "VN1234", "airline": "Vietnam Airlines",
                  "departure_airport": "HAN", "arrival_airport": "PQC",
                  "departure_time": "...", "arrival_time": "...", "seat_number": null },
    "return":   { "...": "..." }
  },
  "buses": [ { "trip_leg": { "code": "CITY_TO_AIRPORT", "name": "HN → Sân bay" },
               "bus_code": "XE-01", "plate_number": "29B-123.45",
               "gather_time": "...", "departure_time": "...",
               "pickup_point": { "name": "Toà nhà Keangnam", "map_url": "..." },
               "leader": { "name": "Trần B", "phone": "0912..." } } ],
  "accommodation": { "hotel_name": "...", "address": "...", "map_url": "...",
                     "room_number": "1204", "room_type": "twin",
                     "roommates": [ { "full_name": "...", "phone": "..." } ] },
  "gala": { "table_code": "B07", "seat_number": 3, "venue": "...", "starts_at": "..." },
  "itinerary": [ { "day_date": "2026-10-15", "start_time": "05:30",
                   "title": "Tập trung tại điểm đón", "location": "..." } ],
  "announcements": [ { "title": "...", "severity": "warning", "published_at": "..." } ],
  "pending": ["accommodation"]
}
```
Trường `pending` liệt kê phần BTC chưa công bố → FE hiện skeleton "Đang chờ BTC công bố" thay vì lỗi.

Kèm `pending_reasons` (`{"accommodation": "not_assigned"}`) để FE nói đúng lý do:
`not_published` (kỳ chưa tới `information_published` — cạm bẫy #6), `not_assigned` (đã công bố
nhưng BTC chưa xếp người này), `not_participating` (không đăng ký hoặc không tham gia).
Xe chỉ tính là chờ khi người đó có đăng ký cần xe mà chưa đủ xe.

Lọc theo người xem:
- `itinerary`: mục `audience = all` + mục theo mã team + mục theo **ca của chuyến bay đã xếp**
  (không dùng ca nguyện vọng; chưa công bố thì chưa hiện mục theo ca).
- `announcements`: đã tới `published_at`, đích là `all` / team của người đó / `user` = chính họ /
  chuyến bay hoặc xe họ được xếp (chỉ khi đã công bố). Mới nhất trước, tối đa 10.
- `accommodation.roommates`: chỉ họ tên, số điện thoại, team, trưởng phòng — không CCCD, không ghi chú sức khoẻ.

`GET /journey/{user_id}` trả cùng cấu trúc cho BTC tra cứu hộ. `/journey/me/pdf` chưa làm.

## 10. Admin dashboard & audit

| Method | Path | Role | Mô tả |
|---|---|---|---|
| GET | `/admin/dashboard` | 🔴 | tổng CBNV, đã/chưa đăng ký, tham gia/không, theo ca, nhu cầu xe theo chặng, tỉ lệ lấp slot bay, tình trạng phân phòng/xe |
| GET | `/admin/users` | 🔴 | quản lý user + filter |
| POST · PATCH | `/admin/users` | ⚫ | tạo user, đổi role, reset mật khẩu |
| POST | `/admin/users/import` | 🔴 | import Excel danh sách CBNV |
| GET | `/admin/audit-logs` | 🔴 | filter theo actor / entity / khoảng thời gian |
| GET · POST | `/admin/announcements` | 🔴 | tạo & publish thông báo (tuỳ chọn gửi email) |
| GET · POST · PATCH | `/admin/itinerary` | 🔴 | quản lý lịch trình |
| GET | `/admin/email-logs` | 🔴 | theo dõi email gửi thành công/thất bại, filter `status` · `template` · `q` |
| GET | `/admin/email-logs/stats` | 🔴 | đếm theo trạng thái + theo template, kèm `email_enabled` |
| POST | `/admin/rag/reindex` | 🔴 | nạp lại vector store sau khi sửa quy định/lịch trình |

## 11. Chatbot RAG

| Method | Path | Role | Mô tả |
|---|---|---|---|
| POST | `/chat` | 🟢 | `{session_id?, message}` → **SSE stream** token + `sources` ở cuối |
| GET | `/chat/sessions` · `/chat/sessions/{id}/messages` | 🟢 | lịch sử của chính mình |
| DELETE | `/chat/sessions/{id}` | 🟢 | |

Rate limit: 20 tin nhắn / user / 10 phút → 429.

## 12. Hệ thống

| Method | Path | Mô tả |
|---|---|---|
| GET | `/health` | `{status, db, vector_store, version}` – dùng cho Docker healthcheck |
| GET | `/version` | git sha + build time |
