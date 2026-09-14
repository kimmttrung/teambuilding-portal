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
| GET | `/registrations/export` | 🔴 | `.xlsx` sheet "Đăng ký" (trạng thái, ca, cột `Xe: <chặng>` = "Có — điểm đón", huỷ/phạt, đủ giấy tờ bay) + sheet "Chưa đăng ký". Không theo bộ lọc |
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
| GET | `/flights/export` | 🔴 | danh sách hành khách để đặt vé: sheet "Chiều đi", "Chiều về" (chuyến + giờ VN + ngày sinh + số giấy tờ + ghế/mã vé) và "Chưa có chuyến". **Luôn** audit `sensitive: true` |
| POST | `/flights/import` | 🔴 | *(chưa làm)* Excel: mã chuyến, ngày/giờ, điểm đi/đến, capacity |
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
| POST | `/rooms/allocate` | 🔴 | `{dry_run=true, force_reallocate=false}` – xếp phòng tự động cho cả kỳ (docs/05 §7). Trả `summary` (`same_team_rate`, `same_flight_rate`, `rooms_used`, `empty_beds`…), `rooms[].guests[]` (`pinned`, `is_room_captain`, `flight_code`), `unassigned[]`, `flags[]`, `params`. Ghi thật cần `registration_closed`, chạy trong `BEGIN IMMEDIATE`, giữ bản ghi `manual`, dọn bản ghi của người không còn tham gia (`removed_stale`), audit `room.allocated` |
| GET | `/rooms/{id}/occupants` | 🔴 | |
| GET · POST | `/room-assignments` · DELETE `/room-assignments/{id}` | 🔴 | gán/bỏ gán, validate capacity + `gender_policy`; người đã có phòng phải gửi `replace_existing=true` mới chuyển; DELETE đòi `?reason=` |
| GET | `/rooms/export` | 🔴 | sheet "Phân phòng" (cùng cột với `/rooms/import` — tải về, sửa, import lại được; `Trưởng phòng` = `x`), "Phòng trống", "Chưa có phòng" |

## 7. Module 3 – Xe

| Method | Path | Role | Mô tả |
|---|---|---|---|
| GET · POST · PATCH · DELETE | `/buses`, `/buses/{id}` | 🔴 | CRUD, gồm `gather_time`, `pickup_point_id`, `linked_flight_id` |
| POST | `/buses/import` | 🔴 | *(chưa làm — phân xe tự động + xếp tay đã đủ)* |
| POST | `/buses/allocate` | 🔴 | `{event_id, trip_leg_id, dry_run}` – auto phân xe |
| PATCH | `/buses/{id}/leader` | 🔴 | `{leader_user_id}` hoặc `{leader_name, leader_phone}` |
| GET | `/buses/{id}/passengers` | 🔴🔵 | Trưởng xe xem được danh sách xe mình phụ trách |
| GET | `/bus-assignments` | 🔴 | lọc `trip_leg_id` · `bus_id` · `team_id` · `q`; mỗi dòng kèm `employee_code`, `phone`, `pickup_mismatch`, `flight_mismatch` |
| POST | `/bus-assignments` | 🔴 | `{registration_id, bus_id, reason}` — xếp tay người **chưa có xe** ở chặng của xe đó. Chỉ nhận người tham gia có đăng ký cần xe ở chặng này (`BUS_NOT_REQUESTED`); đã có xe thì dùng PATCH (`ALREADY_ASSIGNED_ON_LEG`); xe đầy → `BUS_CAPACITY_EXCEEDED`. Tạo bản ghi `manual`, trả cảnh báo lệch điểm đón/chuyến bay |
| PATCH | `/bus-assignments/{id}` | 🔴 | chuyển người sang xe khác, validate capacity |
| DELETE | `/bus-assignments/{id}?reason=` | 🔴 | bỏ xếp xe, lý do bắt buộc. Người đó vẫn cần xe nên lần phân xe tự động sau sẽ xếp lại |
| GET | `/buses/export` | 🔴 | mỗi chặng một sheet: xe, giờ tập trung/xe chạy (giờ VN), Trưởng xe, tài xế, hành khách + điểm đón + chuyến bay; người cần xe mà chưa có xe ghi `Chưa có xe` |

## 8. Module 4 – Gala Dinner

| Method | Path | Role | Mô tả |
|---|---|---|---|
| GET | `/gala/layout` | 🟢 | một response cho cả màn hình: `layout`, `tables[].seats[]` (trạng thái từng ghế), `draw` (thứ tự + lượt), `my_team` (quota, đã chốt, đang giữ, `is_my_turn`, `is_leader`), `totals`, `server_time`. 404 `GALA_NOT_CONFIGURED` khi chưa có sơ đồ |
| GET | `/gala/draw-orders` | 🟢 | chỉ phần `draw` (mỗi team kèm `leader_name`) |
| GET | `/gala/my-turn` | 🟢 | lượt của team mình cho banner: `is_leader`, `is_my_turn`, `turn_ends_at`, `teams_ahead`, `remaining`… Nhẹ, giao diện hỏi 15 giây/lần |
| GET | `/gala/stream` | 🟢 | **SSE** — xem bên dưới |
| GET | `/gala/team-members` | 🔵🔴 | thành viên tham gia của team kèm ghế. Trưởng nhóm luôn là team mình; BTC truyền `?team_id=` |
| POST | `/gala/seats/hold` | 🔵 | `{seat_ids[]}` (≤30) – giữ ghế tạm, trả `expires_at` (không quá giờ hết lượt) + quota còn lại. Cần kỳ đã công bố |
| DELETE | `/gala/seats/hold` | 🔵 | `?seat_ids=1&seat_ids=2` – nhả; bỏ trống = nhả hết |
| POST | `/gala/seats/confirm` | 🔵 | xác nhận mọi ghế team đang giữ. Đủ quota → tự chuyển lượt (`turn_finished`, `next_team_id`) |
| POST | `/gala/seats/assign-member` | 🔵🔴 | `{seat_id, registration_id}` – xếp thành viên vào ghế **của team**; người đang ngồi chỗ khác thì chuyển; `null` = bỏ gán. BTC xếp được cả người chưa thuộc team |
| POST | `/gala/seats/auto-assign` | 🔵🔴 | `{team_id?, reshuffle=false}` – xếp ngẫu nhiên thành viên vào ghế team đã chốt. Mặc định chỉ xếp người chưa có ghế (không đụng chỗ đã đổi tay); `reshuffle` xáo lại cả team. Trả `{placed, unseated, free_seats}`. BTC bắt buộc `team_id` (`TEAM_REQUIRED`); `NO_TEAM_SEATS` khi team chưa chốt ghế |
| POST · PATCH | `/gala/layout` | 🔴 | tạo (một sơ đồ mỗi kỳ, `turn_seconds`/`hold_seconds` bỏ trống lấy `gala.*` trong event_settings) / sửa; thu nhỏ lưới làm bàn ra ngoài → `TABLE_OUT_OF_GRID` |
| POST · PATCH · DELETE | `/gala/tables`, `/gala/tables/{id}` | 🔴 | ghế tự sinh theo `seat_count`. Chặn trùng mã/ô, bớt ghế đã thuộc team (`SEATS_IN_USE`), khoá hay xoá bàn có ghế đã chốt (`TABLE_HAS_ASSIGNMENTS`) |
| POST | `/gala/draw` | 🔴 | `{seed?}` – xáo thứ tự team có người tham gia, quota = số thành viên tham gia; lưu seed (cùng seed + cùng danh sách team = cùng thứ tự). Bốc lại được tới khi mở chọn |
| POST | `/gala/turn/next` | 🔴 | `{skip}` – lần đầu: mở chọn ghế (cần `information_published`); sau đó: kết thúc lượt hiện tại (`done`/`skipped`), nhả ghế team đang giữ, mở lượt kế; hết team → `finalized` |
| POST | `/gala/finalize` | 🔴 | kết thúc chọn ghế cho mọi team |
| POST | `/gala/reopen` | 🔴 | mở lại khi đã `finalized`: team chưa đủ ghế chọn lại theo đúng thứ tự đã bốc (team đủ ghế giữ nguyên), quota tính lại theo người tham gia hiện tại, team mới có người tham gia xếp cuối. `GALA_NOT_FINALIZED` · `GALA_NOTHING_TO_REOPEN` · `NOT_PUBLISHED`. Audit `gala.selection_reopened` |
| PATCH | `/gala/seats/{id}` | 🔴 | `{team_id?, registration_id?, is_available?, reason}` – ép gán / gỡ / khoá ghế, lý do bắt buộc, audit `gala.seat_updated` |

Mutation của BTC trả luôn `/gala/layout` mới.

**Trạng thái ghế trả về**: `available` · `held_by_me` · `held_by_other` · `taken` · `unavailable`.
Ghế `taken` kèm `team_name` + `team_color` để vẽ; `occupant_name`/`registration_id` **chỉ có với BTC
và chính team sở hữu ghế** — người ngoài team không thấy tên cá nhân. Seed bốc thăm chỉ BTC thấy.

**Chống tranh chấp** (đã implement): giữ, xác nhận, chuyển lượt, ép gán chạy trong `BEGIN IMMEDIATE`,
kiểm tra lượt + quota bên trong khoá; `UNIQUE(seat_id)` ở cả `gala_seat_holds` và
`gala_seat_assignments` là lớp cuối (IntegrityError → 409). Hold hết hạn và lượt hết giờ được dọn
**lazy** mỗi lần đọc sơ đồ và mỗi nhịp SSE — không cần tiến trình nền. Audit: `gala.drawn`,
`gala.selection_opened`, `gala.turn_ended` (`trigger`: `timeout` · `quota_filled` · `admin` · `admin_skip`),
`gala.seats_confirmed`, `gala.member_assigned`, `gala.selection_finalized`, `gala.layout_*`, `gala.table_*`.

**SSE `/gala/stream`**: server hỏi DB mỗi giây, gửi `event: change` + `{"version"}` khi dấu vân tay
sơ đồ đổi, `: ping` mỗi 15 giây, `retry: 3000`. Sự kiện **không chứa dữ liệu ghế** — client tải lại
`/gala/layout`, nơi duy nhất áp quyền xem tên. Header `X-Accel-Buffering: no`. Frontend đọc bằng
`fetch` (EventSource không gửi được `Authorization`), mất kết nối thì tự nối lại sau 3 giây.

**Báo Trưởng nhóm tới lượt**: mỗi khi một lượt bắt đầu — BTC mở chọn / chuyển lượt, team trước chốt đủ
quota, lượt trước hết giờ (dọn lazy), BTC mở lại — hệ thống ghi email `gala_turn_started` (`queued`)
trong cùng transaction chuyển lượt và gửi sau commit (BackgroundTask; nhịp SSE thì gửi ngay trong
luồng phụ). Email có team, lượt, số ghế cần chọn, giờ hết lượt, link `/gala`; gửi lại được từ nhật ký
email khi lượt vẫn còn diễn ra. Team chưa có Trưởng nhóm thì không có ai nhận — bảng thứ tự trên màn
hình BTC cảnh báo. Trên cổng, Trưởng nhóm thấy banner "Đến lượt team bạn" (kèm đồng hồ) hoặc
"Sắp tới lượt" ở mọi trang (`/gala/my-turn`).

**Chặn bắt đầu sự kiện**: `POST /events/{id}/status` sang `event_started` trả `409
GALA_SEATING_INCOMPLETE` khi kỳ có sơ đồ Gala mà các team còn đang chọn, còn team có ghế ít hơn số
người tham gia, hoặc còn người tham gia chưa được xếp vào ghế cụ thể. `details` = `{selection_status,
teams_missing[{team_name, participants, seats}], participants, seated, unseated}`. Dashboard trả cùng số
liệu trong khối `gala` để hộp thoại chuyển trạng thái báo trước.

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
| GET | `/admin/users` | 🔴 | danh sách + phân trang. Lọc `q` · `team_id` · `department_id` · `work_location_id` · `role` · `is_active` · `missing_documents` · `registration` (`none`/`submitted`/`participating`/`not_participating`/`cancelled`, theo kỳ đang chạy). Không trả CCCD/ngày sinh |
| POST | `/admin/users` | 🔴 | tạo tài khoản → `{user, temporary_password}` (mật khẩu tạm chỉ ở response này, `must_change_password=true`). Tạo tài khoản BTC cần ⚫ |
| GET · PATCH | `/admin/users/{id}` | 🔴 | hồ sơ đầy đủ / sửa hồ sơ (không đổi role, trạng thái). Tài khoản BTC chỉ ⚫ sửa được |
| PATCH | `/admin/users/{id}/role` | ⚫ | `{role, reason?}`. Không tự đổi vai trò của mình (`SELF_ROLE_CHANGE`) |
| PATCH | `/admin/users/{id}/status` | 🔴 | `{is_active, reason}` — khoá thì thu hồi mọi refresh token. Không tự khoá mình |
| POST | `/admin/users/{id}/reset-password` | 🔴 | → `{temporary_password, sessions_revoked}`; gỡ khoá đăng nhập, bắt đổi mật khẩu |
| POST | `/admin/users/{id}/unlock` | 🔴 | gỡ khoá tạm sau 5 lần sai mật khẩu |
| GET | `/admin/users/export` | 🔴 | `.xlsx` sheet "CBNV". `?include_sensitive=true` thêm ngày sinh, giấy tờ, địa chỉ, liên hệ khẩn cấp. Không bao giờ có ghi chú sức khoẻ |
| POST | `/admin/users/import` | 🔴 | import Excel danh sách CBNV, `?dry_run=true` mặc định — xem bên dưới |
| GET | `/admin/audit-logs` | 🔴 | filter `event_id` · `entity_type` · `entity_id` · `actor_id` · `action`, phân trang; `before`/`after` trả dạng object |
| GET · POST | `/admin/announcements` | 🔴 | tạo & publish thông báo (tuỳ chọn gửi email) |
| GET · POST · PATCH | `/admin/itinerary` | 🔴 | quản lý lịch trình |
| GET | `/admin/email-logs` | 🔴 | theo dõi email gửi thành công/thất bại, filter `status` · `template` · `q` |
| GET | `/admin/email-logs/stats` | 🔴 | đếm theo trạng thái + theo template, kèm `email_enabled` và `template_labels` (mọi loại thư) |
| POST | `/admin/email-logs/resend` | 🔴 | gửi lại thư lỗi. Body `{ids}` (`null` = mọi thư lỗi, tối đa 500) → `{queued, skipped[{id, reason, message}], email_enabled}`. Dựng lại nội dung từ dữ liệu hiện tại, gửi tới email **hiện tại** của CBNV; bỏ qua thư không còn đúng (`no_longer_relevant`: đăng ký đã đổi trạng thái, đã bổ sung giấy tờ) · `no_recipient` · `not_failed` · `not_found` · `cannot_rebuild`. Cập nhật chính dòng lỗi (`failed → queued`, `retry_count+1`) trong `BEGIN IMMEDIATE` nên bấm hai lần không gửi trùng |
| GET | `/admin/reminders/{kind}` | 🔴 | xem trước người nhận email nhắc. `kind`: `missing_documents` · `not_registered` |
| POST | `/admin/reminders/{kind}` | 🔴 | gửi nhắc. Body `{user_ids?, include_recently_reminded}` → `{queued, skipped[], email_enabled}` |
| POST | `/admin/rag/reindex` | 🔴 | nạp lại vector store sau khi sửa quy định/lịch trình |

**Import / export Excel** (đã implement, bước 21):
- **Đọc**: chỉ `.xlsx` thật (kiểm chữ ký file, không tin đuôi), tối đa `MAX_UPLOAD_MB` và 2000 dòng,
  sheet đầu tiên. Cột nhận theo **tên** (không phân biệt hoa thường/dấu), thứ tự tuỳ ý, cột lạ bỏ qua.
- **Tất cả hoặc không**: còn một dòng lỗi thì không ghi dòng nào. Dry-run trả `errors[{row, code, message}]`
  với số dòng Excel; ghi thật mà file có lỗi → `400 IMPORT_VALIDATION_FAILED`, `details` = cùng báo cáo.
- `/admin/users/import`: bắt buộc `Mã NV`, `Họ tên`, `Email`; tuỳ chọn `Giới tính`, `SĐT`, `Team`,
  `Phòng ban`, `Nơi làm việc` (mã hoặc tên), `Chức danh`, `Ngày vào làm`, `Vai trò`, `Ngày sinh`,
  `Số CCCD/Hộ chiếu`. Khớp theo Mã NV, không có thì Email → `to_create` / `to_update` / `unchanged`.
  **Ô trống giữ nguyên**; SĐT 9 chữ số được thêm số 0 (Excel làm mất). Không cấp quyền BTC
  (`ROLE_NOT_ALLOWED`) và không sửa tài khoản BTC (`ADMIN_ACCOUNT_PROTECTED`). Lần ghi thật trả
  `created_accounts[{employee_code, full_name, email, temporary_password}]` — **không gửi email**, không
  ghi vào audit (`user.imported` chỉ lưu số lượng + `created_ids`). Mật khẩu băm song song ngoài
  transaction, ghi trong `BEGIN IMMEDIATE` và kiểm tra lại.
- **Ghi**: file tải về có `Cache-Control: no-store`, tên `<loại>-<mã kỳ>-<YYYYMMDD-HHMM>.xlsx`. Mọi ô
  chữ ép kiểu chuỗi — họ tên `=HYPERLINK(...)` không thành công thức, SĐT không mất số 0. Mỗi lần tải
  ghi audit `export.downloaded` với `{kind, rows, sensitive}`.

**Email nhắc việc** (đã implement):
- Nhóm người nhận khớp số liệu dashboard: `missing_documents` = đã xác nhận tham gia nhưng thiếu
  CCCD hoặc ngày sinh; `not_registered` = tài khoản còn hoạt động chưa gửi đăng ký (người đã huỷ
  tính là đã phản hồi).
- `not_registered` chỉ gửi khi kỳ đang `registration_open`; `missing_documents` chặn từ
  `event_started`. Trái điều kiện → `409 REMINDER_NOT_ALLOWED`.
- **Chống gửi trùng**: ai đã được nhắc cùng loại, cùng kỳ trong 24 giờ (email không `failed`) thì bị
  bỏ qua với lý do `recently_reminded`, trừ khi `include_recently_reminded=true`. Kiểm tra và ghi
  dòng `email_logs` trạng thái `queued` nằm chung một `BEGIN IMMEDIATE` → hai lần bấm đồng thời
  không gửi hai lần. Gửi SMTP chạy trong BackgroundTask sau khi commit.
- `user_ids` không còn thuộc nhóm (vừa bổ sung giấy tờ, id lạ) → bỏ qua với lý do `not_eligible`.
- Email chỉ nêu **tên** trường còn thiếu, không nêu giá trị hồ sơ. Ghi audit `reminder.sent`.

**`GET /admin/dashboard`** (đã implement) — một request cho cả màn hình `/admin`:

| Khối | Nội dung |
|---|---|
| `event` | trạng thái + `next_statuses[]` (`status`, `label`, `is_forward`, `requires_reason`) — bước tiến xếp trước |
| `registrations` | y hệt `/registrations/stats` |
| `teams[]` | theo team: `members`, `submitted`, `participating`, `not_participating`, `cancelled`, `not_submitted`, `response_rate`, `participation_rate`; người chưa gán team gom thành dòng "Chưa gán team" để tổng khớp |
| `flights[]` | theo chiều: slot từ `capacity_summary` + `unassigned` = người tham gia chưa có chuyến ở chiều đó |
| `buses[]` | theo chặng: `demand` (người tham gia cần xe), `buses`, `capacity`, `assigned`, `unassigned`, `shortfall` |
| `rooms` · `gala` · `emails` | tóm tắt từ service gốc |
| `checklist[]` · `ready_to_publish` | việc trước khi công bố (`key`, `label`, `done`, `required`, `detail`, `link`). **Chỉ nhắc, không chặn** chuyển trạng thái; email lỗi là `required=false` |
| `recent_activity[]` | 12 dòng audit log mới nhất của kỳ, kèm tên người thao tác |

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
