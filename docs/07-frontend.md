# 07 – Frontend (React)

## 1. Stack & lý do

| Thư viện | Dùng để | Vì sao |
|---|---|---|
| React 19 + Vite 8 | nền | build nhanh, HMR tốt |
| React Router 7 | định tuyến | `ProtectedRoute` theo role |
| TanStack Query v5 | server state | cache, refetch, invalidate — thay cho `useEffect + useState` thủ công |
| React Hook Form + Zod | form đăng ký nhiều bước | validate cùng schema với backend, ít re-render |
| TailwindCSS 4 | styling | cấu hình bằng CSS (`@theme` trong `index.css`), **không có `tailwind.config.js`** |
| axios | HTTP | interceptor gắn token + auto refresh |
| lucide-react | icon | nhẹ |
| date-fns + date-fns-tz | ngày giờ | format `dd/MM/yyyy`, timezone `Asia/Ho_Chi_Minh` |
| recharts | biểu đồ dashboard | **chưa cài** — dashboard hiện chỉ cần thanh tỉ lệ, làm bằng CSS kèm số (đọc được không cần màu); thêm khi cần biểu đồ theo thời gian |

Không dùng Redux — TanStack Query + Context đã đủ cho quy mô này.

## 2. Bản đồ route

```
/login                          công khai
/                               → redirect theo role

# CBNV
/register-event                 Form đăng ký nhiều bước
/my-journey                     Dashboard hành trình cá nhân   ★ màn hình chủ đạo
/profile                        Hồ sơ: avatar, SĐT, địa chỉ, CCCD, size áo, liên hệ khẩn cấp
/schedule                       Lịch trình chương trình
/announcements                  Thông báo từ BTC

# Team Leader
/team                           Danh sách thành viên + trạng thái đăng ký
/gala                           Sơ đồ Gala cho mọi người; Trưởng nhóm chọn ghế theo lượt + xếp thành viên

# Admin (BTC)
/admin                          Dashboard thống kê
/admin/users                    CBNV: tìm/lọc/sửa/import/export
/admin/registrations            Danh sách đăng ký + export
/admin/flights                  Chuyến bay + nút Auto Allocation + preview
/admin/flights/board            Bảng kéo-thả điều chỉnh thủ công
/admin/buses                    Xe theo từng chặng + gán Trưởng xe
/admin/rooms                    Khách sạn/phòng + import
/admin/gala                     Cấu hình sơ đồ + bốc thăm + điều khiển lượt
/admin/itinerary                Lịch trình
/admin/announcements            Thông báo
/admin/audit-logs               Nhật ký thay đổi
/admin/settings                 Cấu hình kỳ + trạng thái chương trình
```

`ProtectedRoute` nhận `roles={['admin','super_admin']}`; sai role → trang 403, chưa login → `/login?next=`.

### 2.1 Chọn kỳ Team Building

Kỳ đang xem **không nằm trong URL** mà đi theo header `X-Event-Id` (docs/04 §3.1), nên không route nào
phải đổi. `eventStore` trong `api/client.js` giữ lựa chọn ở `localStorage`; header được gắn ở hai chỗ và
chỉ hai chỗ: interceptor axios, và `authHeaders` trong `api/sse.js` cho SSE của Gala và chatbot (hai luồng
đó đi bằng `fetch`, không qua axios). Sót một chỗ là màn hình đó lặng lẽ hiện dữ liệu kỳ khác.

`EventSwitcher` (thanh bên + menu mobile): CBNV chỉ thấy khi thực sự có ≥2 kỳ; **BTC luôn thấy**, kể cả
khi mới có một kỳ, vì đây cũng là chỗ mở kỳ cho mùa sau (`EventCreateModal` → `POST /events`). Kỳ mới
luôn là bản `draft` và không thành kỳ mặc định — CBNV chưa nhìn thấy gì cho tới khi BTC dựng xong chuyến
bay / khách sạn / sơ đồ Gala rồi chuyển sang "Mở đăng ký". Tạo xong tự chuyển sang kỳ vừa tạo. Đổi kỳ gọi
`queryClient.clear()` chứ không `invalidateQueries`: khoá cache không mang `event_id`, chỉ đánh dấu cũ thì
màn hình vẫn vẽ dữ liệu kỳ trước cho tới khi request mới về — đủ lâu để BTC bấm nhầm. Đăng xuất
(`tokenStore.clear()`) xoá luôn kỳ đã chọn, để người đăng nhập sau trên cùng máy không thừa hưởng.

## 3. Màn hình quan trọng

### 3.1 Form đăng ký (`/register-event`) – 5 bước
```
Bước 1  Xác nhận thông tin cá nhân   (auto-fill; cho sửa SĐT, địa chỉ, avatar, CCCD, size áo,
                                      ăn kiêng, liên hệ khẩn cấp — các trường bắt buộc để xuất vé
                                      được đánh dấu đỏ và chặn submit nếu thiếu)
Bước 2  Xác nhận tham gia            (Có/Không; chọn "Không" → nhảy thẳng bước 5)
Bước 3  Chọn ca                      (Ca 1 / Ca 2 + banner "Đây là nguyện vọng, BTC phân bổ
                                      theo nguồn lực chung, không cam kết 100%")
Bước 4  Nhu cầu xe                   (4 chặng, mỗi chặng Có/Không + chọn điểm đón)
Bước 5  Mong muốn + đồng ý quy định   (đọc quy định & phí phạt trong modal cuộn hết mới bật checkbox)
```
- Lưu nháp vào `localStorage` mỗi bước để không mất khi F5.
- Thanh tiến trình + cho phép quay lại bước trước.
- Sau submit: trang thành công + tóm tắt + "đã gửi email xác nhận tới {email}".

### 3.2 My Journey (`/my-journey`) – mobile-first
Một trục thời gian duy nhất, gom theo ngày (`JourneyTimeline`), đọc được bằng một tay ở sân bay:
```
[Ảnh bìa + đếm ngược "Còn 12 ngày"]
[Banner "Tiếp theo": mốc gần nhất — vd "04:30 — Tập trung tại điểm đón, Keangnam"]
[Ngày 1 – Thứ 5, 15/10]   mỗi mốc: giờ to + icon loại + tiêu đề + địa điểm
  04:30 🚌 Tập trung tại điểm đón
        └─ hộp vé: Xe XE-01 · Có mặt 04:30, xe chạy 04:45 · điểm đón + Maps · Trưởng xe + nút Gọi
  06:30 ✈ Chuyến bay HAN – PQC
        └─ hộp vé: VN1234 · HAN 06:30 → PQC 08:40 · Ghế 12A · Thêm vào lịch
  09:30 🏨 Nhận phòng khách sạn
        └─ hộp vé: Sunset Beach Resort · Phòng 802 · bạn cùng phòng + nút gọi
[Ngày 2 …] [Ngày 3 …]
[Thông báo mới nhất]
```
- Lịch trình chung là xương sống (gom ngày, sắp giờ); vé cá nhân (giờ thật từ phân bổ)
  gộp vào mốc cùng ngày khớp tiêu đề/giờ, vé không khớp mốc nào thành mốc riêng — không
  mất thông tin, không hiện 2 nơi. Giờ bay/xe luôn lấy từ phân bổ, không lấy giờ chữ
  trong lịch trình.
- Mốc đã qua mờ + ✓, mốc đang diễn ra có badge "Đang diễn ra", mốc đầu chưa qua hiện
  ở banner "Tiếp theo".
- Phần chưa công bố hiện skeleton "Đang chờ BTC công bố" (dựa vào mảng `pending` của API), không hiện lỗi.

**Trưởng xe** (từ `led_buses` của `GET /journey/me`, rỗng với hầu hết mọi người):
- Mốc xe mình phụ trách có **viền vàng + nền vàng nhạt + huy hiệu "Bạn là Trưởng xe"**,
  kèm dòng hướng dẫn trên đầu timeline; xe vừa đi vừa phụ trách gộp nút
  **"Danh sách hành khách"** vào hộp vé của mốc đó, không dựng mốc thứ hai.
- Xe phụ trách mà không tự đi thành mốc riêng cùng ngày ("… — xe bạn phụ trách"),
  cùng style viền vàng, đủ giờ, điểm đón và nút danh sách.
- Nút mở `BusPassengersModal` (bản của CBNV, khác bản BTC): **chỉ đọc** — tên, team, điểm đón, chuyến
  bay, số điện thoại bấm gọi. Không CCCD, không ngày sinh; chuyển xe / bỏ xếp vẫn là việc của BTC.
  Dữ liệu lấy riêng qua `GET /buses/{bus_id}/passengers` khi mở modal, không nhét sẵn vào My Journey.

### 3.3 Bảng phân bổ chuyến bay (`/admin/flights/board`)
- Cột = chuyến bay, thẻ = team (màu theo `teams.color`), hiển thị `x/y slot` với thanh tiến trình.
- Kéo-thả thẻ giữa các cột → gọi `bulk-move`; vượt slot thì cột chuyển đỏ và chặn thả.
- Nút **"Chạy phân bổ tự động"** → mở modal preview (dry run) với bảng flag, phải bấm **"Áp dụng"** mới ghi DB.
- Panel bên phải: danh sách cảnh báo, bấm vào là nhảy tới người/team tương ứng.

### 3.4 Sơ đồ Gala (`/gala`, `/admin/gala`)
- SVG lưới bàn tròn; ghế là hình tròn nhỏ quanh bàn.
- Màu: xám = trống · xanh = mình đang giữ · vàng = team khác đang giữ · màu team = đã xác nhận · gạch chéo = không khả dụng.
- Header: thứ tự bốc thăm, team đang tới lượt, đồng hồ đếm ngược, quota còn lại.
- Đọc `/api/v1/gala/stream` bằng `fetch` + Bearer token (không dùng `EventSource` vì không gửi được header) để nhận cập nhật realtime; giữ ghế 120 giây kèm đồng hồ, đồng hồ bù lệch giờ máy bằng `server_time`.
- Đã implement bằng lưới `div` định vị tuyệt đối thay cho SVG: mỗi ghế là `<button>` có `aria-label` đủ bàn/ghế/trạng thái; màn hình < 640px hiện danh sách thẻ theo bàn.
- Trưởng nhóm thấy banner "Đến lượt team bạn chọn ghế" (đồng hồ + nút "Chọn ghế ngay") hoặc "Sắp tới lượt" ở đầu mọi trang (`GalaTurnBanner` trong `AppLayout`, hỏi `/gala/my-turn` 15 giây/lần); đồng thời nhận email.
- Chốt ghế xong: nút "Xếp ngẫu nhiên" xếp người chưa có ghế, "Xáo lại tất cả" (có xác nhận); đổi chỗ từng người bằng ô chọn ghế cạnh tên.
- BTC: khi đã kết thúc mà còn team thiếu ghế, khung điều hành liệt kê team thiếu + nút "Mở lại chọn ghế".
  Số ghế thiếu tính theo **người đang tham gia**, không theo quota lúc bốc thăm — người huỷ làm số đó tụt,
  người đăng ký lại làm nó tăng trở lại.
- BTC: ô "Chưa có ghế" (`admin/gala/UnseatedCard`) liệt kê mọi người tham gia chưa được xếp chỗ, người
  **chưa thuộc team nào** đứng đầu — họ không được bốc thăm nên không team nào chọn ghế hộ. Mỗi dòng có ô
  chọn ghế (ghế trống hẳn, hoặc ghế đã thuộc team mà chưa có ai ngồi); chọn xong ghế nhận team của người đó,
  hoặc thành ghế "Không thuộc team" (vẽ màu trung tính) nếu họ chưa có team. Dọn hết ô này thì kỳ mới chuyển
  sang "Đang diễn ra" được.
- Mobile: pinch-zoom, danh sách bàn dạng list thay cho sơ đồ khi màn hình < 640px.

### 3.5 Widget chat "Tibi" (đã implement)
- `components/chat/ChatWidget` gắn trong `AppLayout`: nút nổi góc phải dưới (trên mobile nằm trên thanh điều hướng), linh vật SVG `ChatMascot` (mood `happy`/`thinking`), lời mời "Hỏi Tibi…" hiện tới lần mở đầu tiên.
- `ChatPanel`: desktop là khung 400px, mobile toàn màn hình; Esc đóng. Lời chào + câu hỏi gợi ý (`CHAT_SUGGESTIONS`) + dòng bảo mật chỉ sang Hành trình.
- Stream: `api/chat.streamChat` gọi `POST /chat` bằng `fetch` + Bearer, đọc SSE qua `api/sse.readSseStream` (dùng chung với sơ đồ Gala); 401 → refresh token một lần rồi gửi lại. Nút dừng (`AbortController`), thử lại tin lỗi.
- Tin trợ lý render bằng `MarkdownText` (không chèn HTML thô), nguồn trích dẫn là chip dưới câu trả lời.
- Lịch sử: `useChatSessions` / `useChatMessages`; phiên gần nhất nhớ trong `localStorage` theo user.
- Báo trạng thái từ `/chat/status`: chế độ thử (chưa có `GEMINI_API_KEY`), chưa nạp tài liệu, chưa có kỳ, máy chủ chưa bật.
- Dashboard BTC: phần "Trợ lý Tibi" trong thẻ `SystemCard` (Email & trợ lý Tibi) — số đoạn đã nạp, lần nạp gần nhất, cảnh báo "đã công bố nhưng chưa nạp lại", nút nạp lại.

### 3.6 Dashboard BTC (bước 25 – tối ưu theo góp ý mentor)
Trả lời 3 câu theo thứ tự đọc, một request `/admin/dashboard`:
1. **Đang ở bước nào** — dải đầu: tên kỳ, ngày, "còn N ngày", `LifecycleStepper` 7 bước, `StatusControl` (nút chuyển trạng thái nằm ngay đây).
2. **Còn việc gì** — `ActionCenter` "Việc cần làm": gộp checklist trước công bố, nhắc email, cảnh báo giấy tờ, email lỗi. Lọc theo giai đoạn (đang mở đăng ký chưa đẩy việc phân bổ lên), đã công bố mà còn thiếu → mức Khẩn; việc đã xong thu gọn.
3. **Xếp tới đâu** — 4 chỉ số, `AllocationProgress` (nguyện vọng ca chỉ hiện trước công bố), `TeamTable` (team còn người chưa phản hồi lên đầu, bấm tên → danh sách CBNV của team).

Cột phụ: `SystemCard` (email + Tibi), `ActivityFeed` 5 dòng + "Xem thêm". Trên điện thoại "Việc cần làm" đứng ngay sau 4 chỉ số.
Đã bỏ: thẻ "Nhu cầu xe theo chặng" (trùng khối xe trong tiến độ, hiện mã chặng thô), badge trạng thái lặp, thẻ nhắc email có nút mờ khi 0 người.

## 4. Quy ước code

```
src/api/client.js         axios instance: baseURL '/api/v1', interceptor gắn Bearer,
                          401 → refresh MỘT lần cho mọi request đang chờ (single-flight),
                          thất bại thì xoá token và về trang đăng nhập
src/api/<domain>.js       hàm gọi API thuần, không chứa logic UI
src/hooks/use<Domain>.js  useQuery/useMutation bọc quanh api/, export key cache
src/components/common/    Button, Input, Select, Modal, Badge, Toast, EmptyState, Skeleton
src/utils/format.js       formatDate, formatTime, formatDateTime (Asia/Ho_Chi_Minh)
src/utils/schemas.js      Zod schema dùng chung cho form
```

- Query key: `['journey','me']`, `['flights', eventId]`, `['registrations', filters]`.
- Sau mutation thành công → `invalidateQueries` đúng key, không tự set state thủ công.
- Mọi text hiển thị là tiếng Việt, gom vào `src/utils/constants.js` (nhãn trạng thái, tên chặng…).
- Lỗi API: interceptor đọc `error.error.message` từ backend và bắn Toast.

## 5. Responsive
| Breakpoint | Hành vi |
|---|---|
| `< 640px` | Điều hướng bằng bottom tab bar; bảng admin chuyển sang danh sách thẻ |
| `640–1024px` | 2 cột |
| `> 1024px` | Sidebar cố định cho admin, bảng đầy đủ |

## 6. Accessibility & chi tiết dễ bỏ sót
- Sơ đồ ghế Gala phải có phương án chọn bằng bàn phím + danh sách text (không chỉ SVG click).
- Trạng thái ghế không được chỉ phân biệt bằng màu — thêm icon/nhãn.
- Số điện thoại Trưởng xe là `<a href="tel:">` để bấm gọi trên mobile.
- Mọi thời gian hiển thị kèm thứ trong tuần (`Thứ 5, 15/10/2026 05:30`) để tránh nhầm ngày.
