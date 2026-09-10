# ADR-002 – Tách bảng gán thay vì cột khoá ngoại trên `registrations`

**Trạng thái**: Accepted · **Ngày**: 10/09/2026

## Bối cảnh
Bản thiết kế nháp đặt `flight_id`, `bus_id_1..4`, `room_id`, `gala_seat_id` làm cột trên `registrations`.

## Vấn đề
1. Một CBNV có **hai** chuyến bay (đi và về) — một cột `flight_id` không đủ.
2. `bus_id_1..4` khoá cứng số chặng ở 4, trái yêu cầu "cấu hình được".
3. Không có chỗ lưu **ai gán, lúc nào, tự động hay thủ công, lý do** → không đáp ứng được yêu cầu Audit Log.
4. Muốn biết "chuyến VN1234 còn mấy chỗ" phải quét toàn bảng `registrations`.

## Quyết định
Mỗi loại phân bổ là một bảng riêng: `flight_assignments`, `bus_assignments`, `room_assignments`,
`gala_seat_assignments`. Mỗi bảng có `assignment_mode` (`auto|manual`), `assigned_by`, `assigned_at`, `note`,
và ràng buộc `UNIQUE` diễn đạt đúng quy tắc nghiệp vụ (1 người / 1 chiều bay; 1 người / 1 chặng xe; 1 ghế / 1 người).

## Hệ quả
**Được**: audit đầy đủ, mở rộng số chặng bằng dữ liệu, đếm slot bằng index, phân bổ lại mà không đụng bảng đăng ký,
và `assignment_mode='manual'` cho phép auto allocation lần sau **không ghi đè** chỉnh tay của BTC.

**Mất**: đọc hành trình một người cần JOIN nhiều bảng → gom vào một service `journey_service.get_journey(user_id)`
và một endpoint `GET /journey/me`, frontend chỉ gọi 1 request.
