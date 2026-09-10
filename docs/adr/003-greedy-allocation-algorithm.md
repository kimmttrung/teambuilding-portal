# ADR-003 – Greedy có trọng số cho Auto Allocation

**Trạng thái**: Accepted · **Ngày**: 10/09/2026

## Bối cảnh
Phân bổ chuyến bay là bài toán bin-packing có ràng buộc nhóm (giữ team cùng chuyến) — NP-hard.
Có 3 hướng: greedy, meta-heuristic (simulated annealing/GA), hoặc ILP (OR-Tools/PuLP).

## Quyết định
Dùng **Best-Fit Decreasing có trọng số** + một pha cải thiện cục bộ giới hạn 200 vòng lặp.
Các trọng số nằm trong `event_settings`, BTC đổi được không cần sửa code.

## Lý do
| Tiêu chí | Greedy | ILP |
|---|---|---|
| Thời gian code | ~4 giờ | ~2 ngày (mô hình hoá + tinh chỉnh) |
| Thời gian chạy (1000 người) | <1 giây | vài giây tới vài phút, khó đoán |
| Giải thích cho BTC | dễ ("xếp team lớn trước, ưu tiên chuyến vừa khít") | khó |
| Chất lượng lời giải | tốt ~90–95% tối ưu | tối ưu |
| Phụ thuộc thêm | không | OR-Tools (~100MB) |

Với deadline 4 ngày và việc **BTC vẫn phải điều chỉnh thủ công các ngoại lệ** (yêu cầu nghiệp vụ đã nói rõ),
chênh lệch 5–10% chất lượng không đáng để đánh đổi.

## Hệ quả
- Kết quả không đảm bảo tối ưu tuyệt đối → **bắt buộc** có Manual Adjustment và danh sách flag.
- Có seed cố định để chạy lại ra cùng kết quả, tiện đối chiếu với BTC.
- Interface `allocate_*(db, event_id, dry_run) -> AllocationResult` giữ nguyên nếu sau này thay bằng ILP.

## Phương án thay thế đã cân nhắc
- **ILP (OR-Tools CP-SAT)**: để Phase 2, khi quy tắc nghiệp vụ đã chốt và có thời gian tinh chỉnh.
- **Phân bổ thủ công hoàn toàn**: loại — chính là vấn đề hệ thống này sinh ra để giải quyết.
