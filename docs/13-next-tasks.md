# 13 – 5 task còn lại (bản giao việc cho phiên làm việc mới)

Nguồn: 8 phát hiện ở [12-test-cases.md](12-test-cases.md) §H. Hai mục đã làm xong (huỷ đăng ký theo giai đoạn,
Trưởng nhóm huỷ + đăng ký lại) nên không còn ở đây.

**Thứ tự người dùng đã chốt:** ~~1~~ → ~~2~~ → **6** → 4 → 3. Làm **từng task một**, xong thì tóm tắt + đưa
tên commit rồi dừng (quy ước ở CLAUDE.md).

**Hai quyết định nghiệp vụ đã chốt, đừng hỏi lại:**
- Task 4: **BTC** cấu hình kỳ và dữ liệu riêng của kỳ; **Quản trị hệ thống** quản lý master data dùng chung.
- Task 6: **không** cần giữ team theo từng năm.

**Còn lại ngoài 5 task này:** bước 24 (README demo + ảnh chụp), đưa 3 file test RAG (docs/11 §10) vào repo,
và mục "Chưa có" còn lại ở docs/12 §H (màn hình team cho Trưởng nhóm, trang tra cứu audit, job xoá CCCD sau 90 ngày).

---

## Task 1 — Chặn dò mật khẩu theo IP (ưu tiên cao, ~½ ngày) — ✅ ĐÃ XONG

**Đã làm đúng thiết kế dưới đây.** Kết quả: bảng `login_attempts` + migration
`73f5d563dcab`; `app/services/login_guard.py` (`check` / `record` / `clear`, lỗi 429
`TOO_MANY_ATTEMPTS` kèm `details.retry_after_seconds`); ngưỡng tài khoản nâng 5 → 10;
`get_client_ip` ưu tiên `X-Real-IP` rồi phần tử cuối của `X-Forwarded-For`;
`nginx.conf` đổi sang `X-Forwarded-For $remote_addr`. BTC gỡ khoá / đặt lại mật khẩu
xoá luôn bộ đếm IP. 8 test mới (`tests/test_auth.py`, `tests/test_admin_users.py`).
Tài liệu đã cập nhật: docs/03 §10 + §13, docs/04 §2, docs/08 §4, docs/09 §5.1–5.2,
docs/12 AUTH-03 + SEC-10 + §H.

---

### Bản giao việc gốc

**Vấn đề.** docs/09 §5 ghi "khoá 15 phút sau 5 lần sai / **IP + email**", nhưng code chỉ đếm theo tài khoản:
- `backend/app/core/security.py` — `MAX_FAILED_LOGINS = 5`, `LOCKOUT_MINUTES = 15`.
- `auth_service.login` kiểm tra `user.locked_until`; `auth_service._register_failed_login` tăng
  `users.failed_login_count` rồi khoá tài khoản.

Hệ quả: (a) kẻ tấn công rải 4 lần sai cho hàng trăm email từ một IP thì không bị chặn; (b) ai biết email của
người khác là khoá được tài khoản người đó (DoS).

**IP hiện không đáng tin.** `app/core/dependencies.get_client_ip` lấy **phần tử đầu** của `X-Forwarded-For`,
mà `frontend/docker/nginx.conf` đặt `X-Forwarded-For $proxy_add_x_forwarded_for` — tức **nối thêm** vào chuỗi
client tự gửi. Client chỉ cần gửi `X-Forwarded-For: 1.2.3.4` là đổi được "IP" của mình; IP trong audit log
cũng không tin được.

**Thiết kế đề xuất.**
1. Bảng mới `login_attempts` (`email` đã lower, `ip_address`, `succeeded`, `attempted_at` có index) + migration.
   Phải là bảng DB chứ không phải biến in-memory: Docker chạy nhiều worker và restart thường xuyên.
2. `app/services/login_guard.py`:
   - `check(db, email, ip)` — chặn trước khi so mật khẩu:
     - (email, IP): ≥ 5 lần sai / 15 phút → 429 `TOO_MANY_ATTEMPTS`;
     - riêng IP: ≥ 20 lần sai / 15 phút (mọi email) → 429 `TOO_MANY_ATTEMPTS`.
   - `record(db, email, ip, succeeded)`; dọn dòng cũ hơn 24 giờ ngay trong lúc ghi (không cần job nền).
   - `clear(db, email)` khi đăng nhập thành công, BTC gỡ khoá, BTC đặt lại mật khẩu.
3. Khoá theo **tài khoản** vẫn giữ (để BTC còn nút "Gỡ khoá đăng nhập") nhưng nâng ngưỡng (đề xuất 10) để một
   IP không khoá nổi tài khoản người khác. Nêu rõ đánh đổi này trong tóm tắt.
4. `get_client_ip`: ưu tiên `X-Real-IP` (nginx đặt từ `$remote_addr`), nếu chỉ có `X-Forwarded-For` thì lấy
   phần tử **cuối** (do proxy của mình thêm vào), cuối cùng mới tới `request.client.host`.
5. `nginx.conf`: đổi thành `proxy_set_header X-Forwarded-For $remote_addr;` để bỏ chuỗi client tự gửi.

**Xong khi:** `POST /auth/login` trả 429 đúng hai ngưỡng trên; khoá theo (email, IP) không ảnh hưởng người dùng
thật ở IP khác; header giả không đổi được IP ghi vào `login_attempts` / audit.

**Test cần thêm** (`tests/test_auth.py`): sai 5 lần cùng IP → 429; cùng email nhưng IP khác vẫn đăng nhập được;
một IP sai 20 lần với nhiều email khác nhau → 429; gửi `X-Forwarded-For` giả không qua mặt được; đăng nhập
thành công xoá bộ đếm. **Sửa test cũ** `test_account_locks_after_repeated_failures` theo ngưỡng mới.

**Tài liệu:** docs/04 §2 (bảng mã lỗi auth), docs/09 §5, docs/12 case AUTH-03 + SEC-10 (đang ghi "Lệch").

---

## Task 2 — Màn hình Trưởng xe xem hành khách (~3 giờ) — ✅ ĐÃ XONG

**Đã làm đúng thiết kế dưới đây.** `journey_service._led_buses` + schema `JourneyLedBus`
(`led_buses` trong `GET /journey/me`, kèm `bus_id` mới trong `buses`); rỗng khi kỳ chưa
`information_published`, nhưng **không** phụ thuộc việc người đó có đăng ký — Trưởng xe có thể
là người ở lại điều phối. Frontend: `api/buses.fetchBusPassengers` + `useBusPassengers`,
`pages/user/journey/LedBusCard.jsx` (khối "Xe bạn phụ trách") và `BusPassengersModal.jsx` chỉ
đọc; thẻ xe mình đi thì nút nằm ngay trên `BusCard` thay vì dựng thẻ thứ hai. 3 test backend
mới + 1 kịch bản `check:render` (140). Tài liệu: docs/04 §9, docs/07 §3.2, docs/12 TL-14 +
BTC-39 + §H.

---

### Bản giao việc gốc

**Vấn đề.** Backend đã có `GET /buses/{bus_id}/passengers` với `bus_service.ensure_can_view_passengers`
(BTC xem mọi xe, Trưởng xe chỉ xe mình), nhưng frontend không có chỗ nào gọi — Trưởng xe không xem được danh
sách hành khách và số điện thoại để điều phối.

**Thiết kế đề xuất.**
1. `journey_service.build_journey` trả thêm `led_buses`: các xe mà `buses.leader_user_id == user.id` trong kỳ
   (kể cả khi người đó không đi xe đó), mỗi xe gồm mã xe, chặng, giờ tập trung, điểm đón, số khách.
2. My Journey: thẻ Xe (và khối mới "Xe bạn phụ trách" nếu không trùng xe mình đi) có nút
   **"Danh sách hành khách"** → modal: tên, SĐT bấm gọi (`tel:`), điểm đón, team. Không hiện CCCD, ngày sinh.
3. `frontend/src/api/buses.js` thêm `fetchBusPassengers(busId)` (hiện chỉ có hàm cho BTC).

**Xong khi:** Trưởng xe mở được danh sách xe mình trên web; gọi API với xe khác vẫn 403.

**Test:** backend — Trưởng xe xem xe mình 200 / xe khác 403 (case TL-14); frontend — thêm kịch bản
`check:render` cho My Journey có `led_buses`.

---

## Task 6 — Nhiều kỳ Team Building song song (~2–3 ngày) — ✅ ĐÃ XONG

**Đã làm:** `get_active_event` đọc `X-Event-Id`, không có thì lấy kỳ mặc định (`is_active`) nên client cũ
chạy nguyên. CBNV trỏ vào kỳ `draft` → 404 (không phải 403: không xác nhận kỳ nháp có thật); BTC vào mọi kỳ.
Header sai định dạng → 400 `EVENT_HEADER_INVALID`, kỳ không có → 404 `EVENT_NOT_FOUND`. Thêm
`GET /events/selectable` dùng **chung một luật** với dependency (`event_service.list_selectable_events`) để
bộ chọn kỳ không bao giờ hiện ra kỳ mà chọn vào lại 404. Dọn 9 chỗ đọc kỳ không qua dependency:
`master_data._active_event` (7 endpoint) bị xoá hẳn, `users.list_users`, `users.export_users` +
`export_service.export_users` nhận kỳ từ router; `/events/active` cũng đi qua dependency để tiêu đề màn
hình không bao giờ lệch với dữ liệu bên dưới. SSE Gala và chatbot vốn đã dùng `ActiveEvent` nên theo sẵn.
Frontend: `eventStore` trong `api/client.js`, header gắn ở interceptor axios **và** `api/sse.js`
(`authHeaders`); `EventSwitcher` ở sidebar + menu mobile, chỉ hiện khi có ≥2 kỳ; đổi kỳ gọi
`queryClient.resetQueries()` trừ danh sách kỳ (không phải `clear()` — clear không báo observer nên màn hình đứng im tới khi F5; cũng không phải `invalidateQueries` — chỉ đánh dấu
cũ thì màn hình còn vẽ dữ liệu kỳ trước); đăng xuất xoá luôn kỳ đã chọn. Seed: `--second-event` nạp thêm
TB2027 – Đà Nẵng với ca/chặng/điểm đón/chuyến bay/khách sạn/Gala/lịch trình/đăng ký riêng, **không**
`is_active`; **`--second-event` chạy được trên DB đã có dữ liệu** (không cần `--reset`), chỉ thêm kỳ phụ và
không đụng kỳ cũ, chạy lại không tạo trùng. BTC có nút **"Thêm kỳ cho mùa sau"** ngay trong bộ chọn kỳ
(`EventCreateModal` → `POST /events`), nên không phải vào DB để mở kỳ mới; bộ chọn vì thế luôn hiện với
BTC kể cả khi mới có một kỳ. 5 test mới (`test_multi_event.py`) + 7 kịch bản `check:render`.

> Còn thiếu so với task 4: sửa/xoá kỳ, đặt kỳ mặc định (`POST /events/{id}/activate`), và nhân bản master
> data (ca, chặng, điểm đón) từ kỳ cũ sang kỳ mới — hiện kỳ mới tạo qua UI trống hoàn toàn, phải dựng tay.

### Bản giao việc gốc

**Đã sẵn sàng:** mọi dữ liệu nghiệp vụ đều gắn `event_id` (đăng ký, ca, chuyến bay, chặng, xe, khách sạn,
sơ đồ Gala, lịch trình, thông báo, phiên chat); ChromaDB đã lọc theo `event_id`.

**Vướng:** hệ thống chỉ biết "kỳ đang active" (`dependencies.get_active_event`) — 109 chỗ trong 16 router dùng
`ActiveEvent`, frontend 13 chỗ.

**Thiết kế đề xuất (đã chốt): chọn kỳ theo từng người qua header `X-Event-Id`.**
1. Sửa **một** chỗ: `get_active_event` → đọc header, không có thì lấy kỳ mặc định. Kèm kiểm tra quyền: CBNV
   chỉ chọn được kỳ đã qua `draft`; BTC chọn kỳ bất kỳ.
2. Thêm API danh sách kỳ cho người dùng thường (hiện `GET /events` chỉ BTC).
3. Soát các chỗ gọi thẳng kỳ active, không qua dependency: `master_data._active_event`, `export_service`,
   `event_service`, luồng SSE Gala, chat.
4. Frontend: bộ chọn kỳ ở sidebar; interceptor gắn header cho mọi request **kể cả SSE Gala và chat**
   (`api/sse.js` dùng `fetch` riêng); nhớ kỳ đã chọn; đổi kỳ thì xoá cache TanStack Query.
5. Seed thêm kỳ "Team Building 2027 – Đà Nẵng" để demo.

**Xong khi:** hai kỳ chạy song song, đổi kỳ thì dashboard, bay, xe, phòng, Gala, chatbot, email nhắc đều đổi
theo; không có dữ liệu nào lẫn giữa hai kỳ.

**Test — phần quan trọng nhất:** dựng 2 kỳ rồi kiểm tra từng module chỉ thấy dữ liệu kỳ được chọn. Sót một chỗ
là lẫn dữ liệu, nên viết test cách ly cho: dashboard, danh sách đăng ký, bay, xe, phòng, Gala, chatbot, email.

**Giới hạn chấp nhận:** CBNV, team, phòng ban là dữ liệu chung, không theo năm — bảng team của kỳ cũ hiển thị
theo team hiện tại (người dùng đã đồng ý).

---

## Task 4 — Màn hình cấu hình kỳ & master data (~2 ngày) — ✅ ĐÃ XONG

**Đã làm:** `/admin/settings` cho BTC với 6 tab qua `?tab=` — **Thông tin kỳ** (sửa tên/điểm đến/ngày,
mốc mở-đóng đăng ký nhập giờ VN đổi sang UTC khi lưu, + nút "Đặt làm kỳ mặc định" có xác nhận vì đổi là
ảnh hưởng mọi CBNV), **Quy định** (`terms_content` + `terms_version`, xem trước markdown, cảnh báo phải
lên phiên bản mới trước khi người dùng bấm Lưu rồi mới ăn `TERMS_VERSION_REQUIRED`), **Tài liệu**
(FAQ/hướng dẫn), **Ca bay**, **Chặng & điểm đón**, **Trọng số & Gala** (10 khoá `event_settings` gom theo
việc: xếp bay / xếp phòng / Gala, kèm cảnh báo chỉ áp cho lần chạy phân bổ sau). `/admin/master-data`:
Phòng ban · Địa điểm · Team. Lịch trình chỉ **đặt liên kết** sang `/admin/itinerary` (opencode đã làm)
thay vì nhúng — tránh hai luồng sửa cùng file.

Sáu loại master data dùng chung một `CrudSection` mô tả bằng cấu hình `fields` thay vì sáu màn hình gần
giống nhau. Mã (`code`) khoá lại khi sửa vì `*Update` của backend không nhận `code` — dữ liệu cũ đang
tham chiếu tới nó.

**API mới:** `/admin/documents` CRUD (`policy_document_service`). Chỉ quản `faq` + `guide`; `terms` và
`itinerary` bị từ chối bằng `DOCUMENT_TYPE_READONLY` vì mỗi thứ đã có nguồn sự thật riêng
(`events.terms_content`, bảng `itinerary_items`) — cho sửa hai nơi là chắc chắn lệch. Sửa tài liệu hạ
`is_indexed` về false để BTC thấy cần nạp lại kiến thức cho Tibi. Tài liệu dùng chung (`event_id` NULL)
chỉ Quản trị hệ thống sửa (`DOCUMENT_SHARED` 403), API trả kèm `can_edit` để frontend khoá nút thay vì
để người dùng bấm rồi ăn 403. 6 test mới + 17 kịch bản `check:render`.

> **Phân quyền: người dùng đổi quyết định giữa chừng** — `/admin/master-data` mở cho **cả BTC**, không
> chuyển sang `require_super_admin` như ghi bên dưới. Nhờ vậy không phải sửa `tests/test_master_data.py`.
> Riêng tài liệu dùng chung vẫn chỉ super admin sửa được.

**Chưa làm:** nhân bản ca/chặng/điểm đón từ kỳ cũ sang kỳ mới (kỳ tạo qua UI vẫn trống, phải khai tay).

---

### Bản giao việc gốc

**Vấn đề.** 27 endpoint đã có nhưng không có màn hình: tạo kỳ, đổi thông tin kỳ, sửa quy định, ca bay, chặng,
điểm đón, team, phòng ban, địa điểm, trọng số thuật toán. Vận hành kỳ thật đang phải dùng Swagger hoặc seed.

**Phân quyền đã chốt:**
- **BTC**: dữ liệu của kỳ — thông tin kỳ, quy định (`terms_content`, `terms_version`), ca bay, chặng, điểm đón,
  cấu hình `event_settings` (trọng số phân bổ, thời gian lượt/giữ ghế Gala).
- **Quản trị hệ thống**: master data dùng chung — phòng ban, địa điểm làm việc, team (kèm Trưởng nhóm).
  → phải đổi các endpoint dùng chung từ `require_admin` sang `require_super_admin` (sẽ làm đỏ test
  `tests/test_master_data.py` hiện dùng tài khoản BTC — cập nhật theo).

**Còn thiếu API:** sửa **lịch trình** (`itinerary_items`) và tài liệu FAQ/hướng dẫn (`policy_documents`) — hiện
chỉ có `GET /events/{id}/terms`. Cần bổ sung nếu muốn BTC tự sửa lịch trình.

**Màn hình đề xuất:** `/admin/settings` nhiều tab cho BTC (Thông tin kỳ · Quy định · Ca bay · Chặng & điểm đón ·
Lịch trình · Trọng số & Gala) và `/admin/master-data` cho Quản trị hệ thống (Phòng ban · Địa điểm · Team).

**Xong khi:** tạo được một kỳ mới và khai đủ dữ liệu cho kỳ đó **không cần Swagger**. Đây cũng là lối vào của
task 6 (tạo kỳ thứ hai), nên làm sau task 6.

**Tài liệu:** docs/12 case SA-07, SA-08, SA-09 (đang "Lệch"), docs/04 §3.

---

## Task 3 — BTC gửi thông báo cho CBNV (~1 ngày)

**Đã sẵn sàng:** bảng `announcements` đủ cột (kỳ, tiêu đề, nội dung markdown, `severity`, `target_type` +
`target_id`, `published_at`, `send_email`, `created_by`); `journey_service._announcements` đã lọc đúng người
nhận (tất cả / team / chuyến bay / xe / cá nhân) và My Journey đã hiển thị, kể cả banner đỏ cho mức khẩn.

**Thiếu:** API và màn hình — panel thông báo hiện chỉ có dữ liệu seed.

**Thiết kế đề xuất.**
1. `app/api/v1/announcements.py` + `announcement_service`: tạo / sửa / đăng / xoá; kiểm tra đối tượng nhận
   thuộc kỳ đang chọn; đăng thì ghi `published_at`, tuỳ chọn gửi email hàng loạt (dùng `email_service.enqueue`
   + BackgroundTask như `reminder_service`); audit `announcement.*`.
2. Trang `/admin/announcements`: danh sách (nháp / đã đăng) + soạn thảo (chọn đối tượng, mức độ, xem trước
   markdown, bật gửi email). Menu BTC đã bỏ mục giữ chỗ ở bước 25 — thêm lại khi có màn hình thật.
3. RAG: chỉ đưa thông báo `target_type = all` **đã đăng** vào knowledge base (thông báo riêng của một team là
   dữ liệu không công khai — ADR-005).

**Xong khi:** BTC soạn và gửi được thông báo đổi giờ bay; đúng nhóm người nhận thấy nó trong My Journey; mẫu
email mới ghi vào nhật ký email.

**Test:** lọc đối tượng nhận; thông báo nháp không hiện với CBNV; gửi email hàng loạt ghi đủ dòng log; CBNV gọi
API tạo thông báo → 403.

**Tài liệu:** docs/12 case EMP-23, BTC-68 (đang "Chưa có"), docs/04 (mục mới), docs/03 §9.
