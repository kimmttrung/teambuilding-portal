# 01 – Yêu cầu & Phạm vi

## 1. Mục tiêu
Một cổng duy nhất (One-stop Portal) cho kỳ Team Building: CBNV đăng ký và tra cứu toàn bộ hành trình;
BTC quản lý dữ liệu tập trung, phân bổ tự động chuyến bay/xe, điều chỉnh ngoại lệ và công bố thông tin.

**Single Source of Truth**: đổi chuyến bay của một CBNV ⇒ mọi màn hình liên quan (xe, My Journey, export) phản ánh ngay.

## 2. Vai trò & quyền

| Role | Quyền |
|---|---|
| `employee` (CBNV) | Đăng ký, sửa đăng ký khi event còn mở, xem **chỉ dữ liệu của mình**, hỏi chatbot |
| `team_leader` | Quyền của CBNV + xem danh sách Team mình + thao tác chọn ghế Gala cho Team |
| `admin` (BTC) | Quản lý toàn bộ dữ liệu nghiệp vụ, chạy allocation, điều chỉnh thủ công, công bố, export |
| `super_admin` | Quyền admin + quản lý user/role + cấu hình hệ thống + xem audit log đầy đủ |

Nguyên tắc: quyền được kiểm tra ở **backend** (dependency `require_role`), frontend chỉ ẩn/hiện UI cho gọn.

## 3. Vòng đời một kỳ Team Building (`events.status`)

```
draft → registration_open → registration_closed → allocation_processing
      → information_published → event_started → completed
                    ↑                    |
                    └──── reopen (admin) ┘
```

| Trạng thái | CBNV làm được gì | BTC làm được gì |
|---|---|---|
| `draft` | không thấy event | cấu hình master data |
| `registration_open` | đăng ký / sửa / huỷ | theo dõi dashboard |
| `registration_closed` | chỉ xem đăng ký của mình | nhập chuyến bay, slot |
| `allocation_processing` | chỉ xem đăng ký | chạy auto allocate, điều chỉnh, phân phòng, phân xe |
| `information_published` | xem **My Journey** đầy đủ, chọn ghế Gala | điều chỉnh + gửi thông báo thay đổi |
| `event_started` / `completed` | xem lịch sử | khoá thay đổi, export báo cáo |

Rule cứng:
- API ghi dữ liệu đăng ký chỉ chạy khi `status == registration_open`.
- My Journey chỉ trả dữ liệu phân bổ từ `information_published` trở đi; trước đó trả `"Đang chờ BTC công bố"`.

## 4. Năm module

1. **Đăng ký** – form nhiều bước, xác nhận quy định (lưu version), chọn ca, nhu cầu xe theo từng chặng, ghi chú, email xác nhận.
2. **Chuyến bay & Khách sạn** – CRUD + import chuyến bay/slot, **Auto Flight Allocation**, Manual Adjustment có validate slot, Audit log. Phòng: import Excel (MVP).
3. **Xe** – cấu hình xe theo từng chặng, auto phân xe theo chuyến bay + team, chỉ định Trưởng xe (tên + SĐT).
4. **Gala Dinner** – sơ đồ ghế trực quan, random thứ tự Team, chọn ghế theo lượt, seat lock chống trùng.
5. **My Team Building Journey** – dashboard cá nhân: thông tin cá nhân/Team, 2 chiều bay, các chặng xe, khách sạn/phòng, bàn/ghế Gala, lịch trình, thông báo.

Cộng thêm (yêu cầu mentor): **Chatbot RAG** trả lời câu hỏi về lịch trình, quy định, và hành trình của **chính người hỏi**.

## 5. Yêu cầu phi chức năng

| Nhóm | Yêu cầu |
|---|---|
| Cấu hình | Không hard-code số ca, chặng, sức chứa, team. Tất cả là dữ liệu gắn `event_id`. |
| Audit | Ghi log mọi thay đổi phân bổ: thời gian, người, giá trị trước/sau, lý do. |
| Validation | Cảnh báo trùng, vượt slot chuyến bay, vượt sức chứa xe/phòng, dữ liệu thiếu. |
| Responsive | Mobile-first cho CBNV (tra cứu tại sân bay), desktop cho Admin. |
| Bảo mật | JWT + bcrypt; interface sẵn sàng cắm SSO. CBNV không truy cập được dữ liệu người khác qua **bất kỳ** endpoint nào, kể cả chatbot. |
| Hiệu năng | Quy mô mục tiêu ≤ 1.000 CBNV / kỳ. Auto allocation ≤ 5 giây. |
| Ngôn ngữ | UI tiếng Việt, ngày `dd/MM/yyyy HH:mm`, timezone `Asia/Ho_Chi_Minh`. |

## 6. Ngoài phạm vi MVP (Phase 2)
Auto Room Allocation nâng cao; tích hợp SSO thật; Microsoft Teams notification; báo cáo BI;
tối ưu thuật toán bằng ILP/OR-Tools; mobile app native.
