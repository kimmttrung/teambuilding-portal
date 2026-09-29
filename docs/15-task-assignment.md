# 15 – Chia việc đợt làm lại v2 (29/9 → CN 4/10/2026)

**Mục tiêu:** tối CN 4/10 báo cáo mentor bản v2 chạy đầy đủ: toàn bộ màn hình theo Figma v2, backend chạy
trên schema mới của An, test xanh, đã merge vào `main` và gắn tag `v2.0.0`.

Mỗi người nhận **trọn một nhóm tính năng**: giao diện theo Figma + backend theo schema mới + test. Quy tắc
bắt buộc ở [14-team-rules.md](14-team-rules.md). Mỗi mã (`F0`, `F1`…) là một thẻ Trello, tên nhánh bắt đầu
bằng mã đó (`feature/F3-flight-board`). Thẻ lớn thì tách thành nhiều PR nhỏ, cùng mã.

## 1. Tổng quan

| Người | Vai trò | Nhận | Điểm |
|---|---|---|---|
| **Việt** | Fullstack + test | F3 Chuyến bay · F4 Xe & Trưởng xe · F9 Cấu hình kỳ & master data | 10 |
| **Anh** | Fullstack + test | F2 Đăng ký & huỷ · F6 My Journey & lịch trình · F7 Gala Dinner | 12 |
| **An** | Chủ schema DB + fullstack | F-DB Hoàn tất DB mới · F1 Đăng nhập, hồ sơ & CBNV · F5 Khách sạn & phòng | 9 |
| **PM** | Quản lý, review, merge | F0 Nền tảng UI ✅ · F8 Dashboard & vận hành · F10 Chatbot Tibi | 9 |

"Điểm" là độ nặng tương đối, không phải giờ. PM và An nhận ít hơn vì PM phải review mọi PR, còn An đã làm
xong phần DB.

**Vì sao chia như vậy**
- **F0 là việc chặn người khác** (token, component chung, layout). PM tự làm luôn ngay T3 để cả nhóm không phải chờ (ban đầu giao Việt).
- **Chuyến bay và xe dính nhau** qua kiểm tra giờ xe khớp giờ bay (`transport_timing_service`), nên cùng giao cho Việt.
- **Đăng ký → My Journey → Gala** là trọn hành trình của CBNV, cùng giao cho Anh để giao diện phía CBNV đồng nhất.
- **Phòng nặng về dữ liệu** (import Excel, xếp phòng theo giới/team), hợp với An là người vừa làm schema.
- **Dashboard đọc dữ liệu của mọi module** nên làm cuối. PM đã review toàn bộ code nên làm nhanh nhất.

## 2. Lịch

| Ngày | Việc chính | Mốc |
|---|---|---|
| **T3 29/9** | PM: commit docs/14, docs/15 và chỗ đặt skill design-notion vào `main` → tạo `develop` → review và merge `feature/migrate-db` vào `develop` → lập board Trello → bật branch protection. Cả nhóm đọc docs/14. | `develop` có schema mới |
| **T4 30/9** | **F0 đã xong (PM làm T3)** — merge vào `develop` sáng T4. Mọi người làm **backend + test** trên schema mới, rồi giao diện trên F0. | F0 merged |
| **T5 1/10** | Mọi người làm giao diện trên F0. Mở PR sớm, merge dần. | Mỗi người ≥ 1 PR merged |
| **T6 2/10** | Tiếp tục. PM bắt đầu F8 (lúc này dữ liệu các module đã ổn). | ≥ 70% thẻ ở Review/Done |
| **T7 3/10** | Làm nốt. **20h: chốt code**, sau giờ này chỉ merge `fix/`. | Tất cả thẻ ở Review/Done |
| **CN 4/10** | **Sáng:** cả nhóm chạy [12-test-cases.md](12-test-cases.md) trên `docker compose` từ `develop` (thẻ F11), sửa lỗi. **Chiều:** PM merge `develop` → `main`, tag `v2.0.0`. **Tối:** báo cáo. | Báo cáo |

Thứ tự làm của từng người:
- **Việt:** F3 → F4 → F9
- **Anh:** F2 → F6 → F7
- **An:** F-DB → F1 → F5
- **PM:** F0 ✅ → review liên tục → F10 → F8 (từ T6)

## 3. Chi tiết từng thẻ

Mỗi thẻ đều có sẵn 4 dòng checklist chung, chép vào Trello:

```
- [ ] Giao diện khớp Figma v2 (desktop + mobile nếu là màn CBNV)
- [ ] Backend chạy trên schema mới, trả JSON đúng docs/14 §2
- [ ] Test: thành công + sai quyền + dữ liệu sai/xung đột; test cũ của module xanh
- [ ] Cập nhật docs/04 (và docs/03 nếu đổi schema)
```

Dưới đây là phần riêng của từng thẻ.

---

### F-DB · Hoàn tất DB mới — **An** · 2 điểm · làm đầu tiên
Nhánh đã có: `feature/migrate-db` (33 → ~20 bảng).
- [ ] Sửa theo góp ý review của PM để merge vào `develop` **trong T3 29/9**
- [ ] [03-data-model.md](03-data-model.md) khớp từng bảng mới; bảng cũ bị gộp/xoá ghi rõ đi đâu
- [ ] `alembic upgrade head` chạy từ DB trống **và** từ DB cũ; `alembic check` không lệch
- [ ] `scripts/seed.py --reset` và `--second-event` chạy được
- [ ] `pytest -q` xanh trên schema mới. Service nào gãy vì đổi bảng thì An sửa (hoặc ghi rõ trong PR
      để chủ module sửa trong thẻ của họ)
- [ ] Gửi nhóm một bảng ngắn "bảng cũ → bảng mới" để mọi người biết chỗ đọc dữ liệu

### F0 · Nền tảng UI — **PM** · 3 điểm · ✅ **đã xong (T3 29/9)**
Mọi thẻ giao diện khác phụ thuộc thẻ này. Nhánh `feature/F0-ui-foundation`.
- [x] Chuyển token của skill design-notion (`colors`, `typography`, `rounded`, `spacing`, shadow) vào khối `@theme` của `frontend/src/index.css`, giữ đúng tên token; font Inter thay Be Vietnam Pro; thay class cũ (`slate-*`, `brand-*`, `indigo-*`) sang token mới
- [x] Làm lại theo design-notion các component `frontend/src/components/common/`: `Button`, `Input`, `Select`,
      `Textarea`, `Card`, `Modal`, `Badge`, `Alert`, `Avatar`, `ChoiceCard`, `EmptyState`, `PageHeader`,
      `SearchBox`, `Spinner`, `Stepper`, `ExportButton`, `MarkdownText`
- [x] `components/admin/` dùng chung: `TabNav`, `CrudSection`, `SlotBar`, `FlagList`, `NotifyToggle`
- [x] Khung trang `components/layout/AppLayout.jsx` (sidebar, menu mobile, header), `EventSwitcher`, `EventCreateModal`
- [x] Trang `/` (`pages/public/LandingPage.jsx`) và trang 404
- [x] Giữ nguyên **tên và props** của component chung (đổi thì báo nhóm), để trang cũ không vỡ trong lúc người khác chưa làm lại

**Mọi người cần biết khi làm tiếp trên F0:**
- **Token:** dùng class theo tên token của skill: `bg-canvas-soft`, `bg-surface`, `border-hairline`, `text-ink`,
  `text-ink-muted`, `text-primary`, `bg-primary`, `text-heading-2`, `text-body-sm`, `text-caption`,
  `text-eyebrow`, `rounded-xs…xl`, `shadow-soft`, `shadow-elevated`, `bg-accent-*` (chỉ để trang trí/phân loại).
- **Cầu nối tạm:** trong `index.css`, `slate-*` đã trỏ về xám ấm của Notion, `brand-*` về xanh `primary`,
  `shadow-sm…2xl` về 2 mức bóng của skill. Nhờ vậy màn hình chưa làm lại cũng đã đúng tông. Khi làm lại màn
  hình của mình thì **đổi sang class token**, không viết thêm `slate-*`/`brand-*` mới.
- **Prop mới (không phá code cũ):** `Button shape="pill"` (CTA kiểu Landing), `Card elevated` (thẻ nổi Level 1).
  Kiểu ô nhập dùng chung nằm ở `components/common/fieldStyles.js`.
- **Ô nhập trên điện thoại giữ chữ 16px** (từ `sm` trở lên mới là `body-sm` 15px), vì iOS tự phóng to trang khi
  bấm vào ô chữ nhỏ hơn 16px.
- **Figma chưa được đối chiếu** (Figma MCP hết lượt gọi): F0 dựng theo skill design-notion. Lệch Figma chỗ nào
  thì mở thẻ `fix/F0-…` giao PM.
- Đã chạy: `npm run build` · `lint` · quét `no-undef` · `rules-of-hooks` 0 vi phạm · `check:render` 189 kịch bản OK.

### F1 · Đăng nhập, hồ sơ & quản lý CBNV — **An** · 3 điểm
| FE | BE | Test |
|---|---|---|
| `/login` (`pages/auth/LoginPage.jsx`), `/profile` (`pages/user/ProfilePage.jsx`, `components/profile/`), `/admin/users` (`pages/admin/UsersPage.jsx`, `pages/admin/users/`) | `api/v1/auth.py`, `api/v1/users.py`; `auth_service`, `login_guard`, `user_admin_service`, `user_import_service`, `export_service` (phần CBNV) | `test_auth.py`, `test_admin_users.py`, `test_user_import.py` |
- [ ] Đăng nhập, refresh token xoay vòng, khoá sau nhiều lần sai, chặn dò mật khẩu theo IP vẫn đúng
- [ ] Bắt đổi mật khẩu lần đầu (`ProtectedRoute` đẩy về `/profile`)
- [ ] Import/export CBNV Excel, tải lại file vừa xuất ra `unchanged`

### F2 · Đăng ký & huỷ tham gia — **Anh** · 4 điểm
| FE | BE | Test |
|---|---|---|
| `/register-event` (`pages/user/RegisterEventPage.jsx`, `pages/user/registration/`), `/admin/registrations`, `/admin/cancellations` (`pages/admin/cancellations/`) | `registrations.py`, `cancellations.py`, `team_leaders.py`; `registration_service`, `cancellation_service`, `team_leader_service` | `test_registrations.py`, `test_cancellations.py`, `test_team_leaders.py` |
- [ ] Form 5 bước, lưu nháp, consent bắt cuộn hết quy định, nhu cầu xe theo chặng
- [ ] Huỷ theo giai đoạn (tự huỷ / gửi yêu cầu / BTC duyệt hoặc từ chối), gỡ đủ bay/xe/phòng/ghế Gala, không để "ghế ma"
- [ ] Đăng ký lại, chỉ định Trưởng nhóm (`TeamLeaderDialog`)

### F3 · Chuyến bay — **Việt** · 4 điểm
| FE | BE | Test |
|---|---|---|
| `/admin/flights`, `/admin/flights/board` (`pages/admin/flights/`) | `flights.py`, `flight_assignments.py`; `flight_service`, `flight_allocation_service`, `services/allocator/` | `test_flights.py`, `test_flight_allocation.py`, `test_allocator.py` |
- [ ] Bảng chuyến bay + slot, form thêm/sửa (lỗi trùng mã gắn vào ô Mã chuyến)
- [ ] Phân bổ tự động 2 bước: xem trước (dry-run) → ghi; không ghi đè bản ghi `manual`
- [ ] Board kéo-thả + nút Chuyển cho màn hình cảm ứng; danh sách hành khách mỗi chuyến
- [ ] Sửa giờ bay vẫn bị chặn khi lệch giờ xe (`FLIGHT_BUS_TIME_CONFLICT`)

### F4 · Xe & Trưởng xe — **Việt** · 4 điểm
| FE | BE | Test |
|---|---|---|
| `/admin/buses` (`pages/admin/buses/`); phần Trưởng xe trong My Journey (`pages/user/journey/LedBusCard.jsx`, `pages/user/journey/BusPassengersModal.jsx`) | `buses.py`, `bus_assignments.py`; `bus_service`, `transport_timing_service`, `services/allocator/` (phần xe) | `test_buses.py`, `test_bus_allocator.py`, `test_transport_timing.py` |
- [ ] Tab theo chặng (`?leg=`), thẻ xe, cột "Chưa có xe" theo điểm đón
- [ ] Phân xe tự động, xếp tay/bỏ xếp có lý do, chỉ định Trưởng xe
- [ ] Trưởng xe chỉ xem được hành khách xe mình
- [ ] Phối hợp với Anh: thẻ Trưởng xe nằm trong trang My Journey của F6

### F5 · Khách sạn & phòng — **An** · 4 điểm
| FE | BE | Test |
|---|---|---|
| `/admin/rooms` (`pages/admin/rooms/`) | `hotels.py`, `rooms.py`, `room_assignments.py`; `accommodation_service`, `room_import_service`, `room_allocation_service` | `test_accommodation.py`, `test_room_import.py`, `test_room_allocation.py`, `test_room_allocator.py` |
- [ ] Bảng giường theo giới tính, sơ đồ phòng theo tầng, lọc qua URL
- [ ] Chi tiết phòng: trưởng phòng, chuyển, bỏ xếp, thêm người (chỉ phòng hợp giới tính)
- [ ] Import Excel kiểm tra → ghi (tất cả hoặc không)
- [ ] Xếp phòng tự động: không trộn giới, giữ `manual`

### F6 · My Journey & lịch trình — **Anh** · 3 điểm
| FE | BE | Test |
|---|---|---|
| `/my-journey` (`pages/user/MyJourneyPage.jsx`, `pages/user/journey/`), `/schedule`, `/admin/itinerary` (`pages/admin/itinerary/`) | `journey.py`, `itinerary.py`; `journey_service`, `itinerary_service`, `journey_notice_service`, `itinerary_notice_service`, `change_notice_service` | `test_journey.py`, `test_itinerary.py`, `test_itinerary_notices.py`, `test_journey_notices.py`, `test_change_notices.py` |
- [ ] My Journey **mobile trước**: thẻ bay/xe/phòng/Gala, `.ics`, Google Maps, `tel:`
- [ ] Chưa công bố thì hiện trạng thái chờ + lý do (không lộ dữ liệu phân bổ)
- [ ] Trang lịch trình BTC + tuỳ chọn email báo đổi lịch trình sau công bố

### F7 · Gala Dinner — **Anh** · 5 điểm
| FE | BE | Test |
|---|---|---|
| `/gala` (`pages/gala/`), `/admin/gala` (`pages/admin/gala/`), `components/gala/` (`SeatMap`, `DrawOrderPanel`, `Countdown`, `GalaTurnBanner`…) | `gala.py`; `gala_service`, `gala_stream` | `test_gala.py`, `test_gala_flow.py` |
- [ ] Sơ đồ ghế theo Figma, tự thu vừa khung, dùng được trên điện thoại
- [ ] Bốc thăm, điều khiển lượt, giữ/xác nhận ghế không vượt quota (quota tính lại từ số người đang tham gia, không dùng cột `quota` lưu lúc bốc thăm)
- [ ] Người chưa có team vẫn được BTC xếp ghế
- [ ] SSE vẫn chạy qua nginx (`docker compose`), không chỉ khi chạy dev

### F8 · Dashboard & vận hành — **PM** · 4 điểm · bắt đầu từ T6
| FE | BE | Test |
|---|---|---|
| `/admin` (`pages/admin/DashboardPage.jsx`, `pages/admin/dashboard/`), `/admin/people` (`components/admin/PersonLocator.jsx`), `/admin/announcements`, `/admin/email-logs` (`pages/admin/emails/`), `ReminderDialog` | `admin.py`, `people.py`, `announcements.py`, `emails.py`, `email_jobs.py`, `reminders.py`, `downloads.py`; `dashboard_service`, `people_locator_service`, `announcement_service`, `email_service`, `email_resend_service`, `reminder_service` | `test_dashboard.py`, `test_people_locator.py`, `test_announcements.py`, `test_email_logs.py`, `test_emails.py`, `test_reminders.py`, `test_excel_exports.py` |
- [ ] Dải trạng thái kỳ + "Việc cần làm" + tiến độ bay/xe/phòng + nhật ký
- [ ] Tra cứu một người (tìm có bỏ dấu, tô và cuộn tới đúng chỗ ở các trang F3/F4/F5/F7)
- [ ] Thông báo BTC, nhật ký email + gửi lại thư lỗi, email nhắc

### F9 · Cấu hình kỳ & master data — **Việt** · 2 điểm
| FE | BE | Test |
|---|---|---|
| `/admin/settings` (`pages/admin/settings/`, 6 tab), `/admin/master-data` | `events.py`, `master_data.py`, `policy_documents.py`; `event_service`, `policy_document_service` | `test_events.py`, `test_master_data.py`, `test_policy_documents.py`, `test_multi_event.py` |
- [ ] Sửa kỳ, chuyển trạng thái có xác nhận, đặt kỳ mặc định, nhiều kỳ song song (`X-Event-Id`)
- [ ] Quy định (bắt lên `terms_version`), tài liệu, ca bay, chặng & điểm đón, trọng số phân bổ
- [ ] Master data (phòng ban, địa điểm, team) dùng `CrudSection` của F0

### F10 · Chatbot Tibi — **PM** · 2 điểm
| FE | BE | Test |
|---|---|---|
| `components/chat/` (`ChatWidget`, `ChatPanel`, `ChatBubble`, `ChatMascot`, `ChatHistory`) | `chat.py`; `chat_service`, `rag_index_service`, `app/rag/` | 3 file test RAG theo [11-rag-backend-guide.md](11-rag-backend-guide.md) §10 (còn nợ) |
- [ ] Widget theo Figma, không che nút quan trọng trên mobile
- [ ] Đưa 3 file test RAG vào repo
- [ ] Nếu schema mới đổi bảng công khai (lịch trình, thông báo, tài liệu) thì sửa chỗ nạp kiến thức cho khớp

### F11 · Kiểm thử tích hợp — **cả nhóm** · CN 4/10 sáng
- [ ] `docker compose up -d --build` từ `develop`, `seed.py --reset`
- [ ] Chia [12-test-cases.md](12-test-cases.md) theo vai trò: **Việt** – BTC phần bay/xe/cấu hình ·
      **Anh** – CBNV + Trưởng nhóm · **An** – BTC phần CBNV/phòng · **PM** – dashboard, email, chatbot
- [ ] Lỗi tìm được → thẻ `fix/` giao cho chủ tính năng, PM merge ngay
- [ ] Chạy lại toàn bộ `pytest -q` + `npm run check:render` trên `develop` trước khi merge vào `main`

## 4. Rủi ro và cách xử lý

| Rủi ro | Dấu hiệu | Xử lý |
|---|---|---|
| F0 lệch Figma v2 | So màn hình với frame Figma thấy khác | Mở thẻ `fix/F0-…` giao PM; không tự sửa component chung trong PR tính năng |
| Schema mới làm gãy nhiều service | `pytest` đỏ hàng loạt sau khi merge F-DB | An sửa phần chung trong T3–T4; phần của module nào thì chủ module sửa trong thẻ của mình |
| Hai PR cùng tạo migration | `alembic heads` ra 2 đầu | Người merge sau chạy `alembic merge heads`, An duyệt |
| Figma thiếu màn hình hoặc trạng thái | Không tìm thấy frame | Hỏi PM, không tự vẽ kiểu riêng (docs/14 §6) |
| PR dồn về PM cuối tuần | Cột Review > 4 thẻ | PR nhỏ, merge dần; PM review ít nhất 2 lần/ngày (trưa, tối) |
| Một người quá tải | Thẻ đứng yên > 1 ngày | PM chuyển F9 (Việt) hoặc F6 (Anh) sang người đang rảnh |
