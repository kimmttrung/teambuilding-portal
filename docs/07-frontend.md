# 07 – Frontend (React)

## 1. Stack & lý do

| Thư viện | Dùng để | Vì sao |
|---|---|---|
| React 18 + Vite | nền | build nhanh, HMR tốt |
| React Router 6 | định tuyến | `ProtectedRoute` theo role |
| TanStack Query v5 | server state | cache, refetch, invalidate — thay cho `useEffect + useState` thủ công |
| React Hook Form + Zod | form đăng ký nhiều bước | validate cùng schema với backend, ít re-render |
| TailwindCSS | styling | nhanh, responsive dễ, không cần viết CSS riêng |
| axios | HTTP | interceptor gắn token + auto refresh |
| lucide-react | icon | nhẹ |
| date-fns + date-fns-tz | ngày giờ | format `dd/MM/yyyy`, timezone `Asia/Ho_Chi_Minh` |
| recharts | biểu đồ dashboard | đủ dùng, nhẹ |

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
/team/gala                      Màn hình chọn ghế Gala theo lượt

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
Bố cục thẻ dọc, đọc được bằng một tay ở sân bay:
```
[Ảnh bìa + đếm ngược "Còn 12 ngày"]
[Thẻ Chuyến bay đi]   mã chuyến · giờ · sân bay · nút "Thêm vào lịch" (.ics)
[Thẻ Xe chặng 1]      giờ tập trung nổi bật, điểm đón + link Google Maps, Trưởng xe + nút gọi
[Thẻ Khách sạn]       tên, số phòng, bạn cùng phòng, link chỉ đường
[Thẻ Gala]            bàn B07 – ghế 3, giờ bắt đầu
[Thẻ Xe chặng 3,4 + Chuyến bay về]
[Lịch trình theo ngày – accordion]
[Thông báo mới nhất]
```
Phần chưa công bố hiện skeleton "Đang chờ BTC công bố" (dựa vào mảng `pending` của API), không hiện lỗi.

### 3.3 Bảng phân bổ chuyến bay (`/admin/flights/board`)
- Cột = chuyến bay, thẻ = team (màu theo `teams.color`), hiển thị `x/y slot` với thanh tiến trình.
- Kéo-thả thẻ giữa các cột → gọi `bulk-move`; vượt slot thì cột chuyển đỏ và chặn thả.
- Nút **"Chạy phân bổ tự động"** → mở modal preview (dry run) với bảng flag, phải bấm **"Áp dụng"** mới ghi DB.
- Panel bên phải: danh sách cảnh báo, bấm vào là nhảy tới người/team tương ứng.

### 3.4 Sơ đồ Gala (`/team/gala`, `/admin/gala`)
- SVG lưới bàn tròn; ghế là hình tròn nhỏ quanh bàn.
- Màu: xám = trống · xanh = mình đang giữ · vàng = team khác đang giữ · màu team = đã xác nhận · gạch chéo = không khả dụng.
- Header: thứ tự bốc thăm, team đang tới lượt, đồng hồ đếm ngược, quota còn lại.
- Kết nối `EventSource('/api/v1/gala/stream')` để nhận cập nhật realtime; giữ ghế 120 giây kèm đồng hồ.
- Mobile: pinch-zoom, danh sách bàn dạng list thay cho sơ đồ khi màn hình < 640px.

### 3.5 Widget chat
Nút nổi góc phải dưới → panel chat; stream token bằng `EventSource`/`fetch` reader; chip câu hỏi gợi ý; hiện nguồn trích dẫn.

## 4. Quy ước code

```
src/api/client.js         axios instance: baseURL '/api/v1', interceptor gắn Bearer,
                          401 → thử refresh 1 lần → thất bại thì logout
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
