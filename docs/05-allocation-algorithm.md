# 05 – Thuật toán phân bổ

## 1. Bài toán

Cho:
- Tập CBNV tham gia `P`, mỗi người thuộc team `t(p)` và có nguyện vọng ca `s(p)`.
- Tập chuyến bay `F` (theo `direction`), mỗi chuyến có `capacity_f` và thuộc ca `shift_f`.

Tìm ánh xạ `assign: P → F` sao cho:
- **C1 (cứng)**: `|{p : assign(p)=f}| ≤ capacity_f - reserved_f` với mọi `f`.
- **C2 (mềm, ưu tiên cao)**: tối đa hoá số người cùng team đi cùng chuyến.
- **C3 (mềm)**: tối đa hoá số người được đúng ca nguyện vọng.
- **C4 (cứng)**: `is_shift_locked = 1` thì bắt buộc đúng ca.

Đây là bài toán *bin-packing có ràng buộc nhóm* — NP-hard. Với n ≤ 1000 và deadline 4 ngày,
dùng **greedy có trọng số + bước cải thiện cục bộ**, không dùng ILP.

## 2. Hàm mục tiêu

```
score(assignment) = W_TEAM  * team_cohesion
                  + W_SHIFT * shift_satisfaction
                  - W_SPLIT * split_penalty
```

| Tham số | Mặc định | Lưu ở | Ý nghĩa |
|---|---|---|---|
| `W_TEAM` | 10 | `event_settings['allocation.team_weight']` | thưởng mỗi cặp cùng team cùng chuyến |
| `W_SHIFT` | 6 | `allocation.shift_weight` | thưởng mỗi người đúng ca |
| `W_SPLIT` | 25 | `allocation.split_penalty` | phạt mỗi lần một team bị chia thêm 1 mảnh |
| `MAX_SPLIT` | 2 | `allocation.max_split_per_team` | số mảnh tối đa 1 team bị tách |
| `MIN_CHUNK` | 3 | `allocation.min_chunk_size` | mảnh tách ra không được nhỏ hơn (tránh 1 người lạc lõng) |

`W_TEAM > W_SHIFT` phản ánh quyết định mặc định ở [00 §4 câu 1](00-review-of-draft.md).
BTC đổi ưu tiên chỉ bằng cách sửa 2 con số này — **không phải sửa code**.

## 3. Thuật toán Auto Flight Allocation

```
INPUT  event_id, direction
OUTPUT AllocationResult(assignments, flags, summary)

1. Chuẩn bị
   groups  = [team → danh sách registration tham gia, chưa bị khoá thủ công]
   flights = chuyến bay theo direction, mỗi chuyến remaining = capacity - reserved - đã gán thủ công
   Sắp xếp groups giảm dần theo size  (Best-Fit Decreasing: nhóm lớn khó xếp → xử lý trước)

2. Vòng 1 – xếp nguyên team
   for g in groups:
       cand = các chuyến còn remaining >= size(g)
       nếu cand rỗng → chuyển g sang hàng đợi SPLIT
       chọn f* trong cand tối đa hoá:
           preferred_shift_match(g, f) * W_SHIFT
         + tightness(f, g)                        # ưu tiên chuyến vừa khít → giảm phân mảnh
         + đã có người cùng team trên f ? bonus : 0
       gán toàn bộ g vào f*, trừ remaining

3. Vòng 2 – tách team (chỉ những g trong hàng đợi SPLIT)
   Chia g theo nguyện vọng ca trước: g_ca1, g_ca2
   for phần in [g_ca1, g_ca2] (giảm dần theo size):
       while phần chưa xếp hết:
           f = chuyến có remaining lớn nhất và ưu tiên đúng ca
           take = min(remaining_f, còn lại)
           nếu take < MIN_CHUNK và còn chuyến khác → thử chuyến kế tiếp
           gán take người (ưu tiên giữ cùng phòng ban / cùng điểm đón cạnh nhau)
           nếu số mảnh của g > MAX_SPLIT → flag TEAM_SPLIT_EXCEEDED
   Người không còn chỗ → flag UNASSIGNED (error)

4. Vòng 3 – cải thiện cục bộ (local search, giới hạn 200 vòng lặp)
   Thử hoán đổi (swap) 2 người khác team giữa 2 chuyến;
   nhận swap nếu score tăng và không vi phạm C1/C4.
   Dừng khi hết vòng lặp hoặc không còn swap cải thiện.

5. Sinh flags + summary; nếu dry_run=false → ghi DB trong 1 transaction + audit log
```

**Độ phức tạp**: bước 2–3 là `O(|P| · |F|)`; bước 4 giới hạn cứng. Với 1000 người / 10 chuyến → dưới 1 giây.

**Tính tái lập**: mọi bước random dùng `random.Random(seed)` với `seed` lưu trong kết quả,
để chạy lại ra cùng kết quả khi cần đối chiếu với BTC.

## 4. Loại flag

| Type | Severity | Ý nghĩa |
|---|---|---|
| `UNASSIGNED` | error | Không đủ slot cho người này |
| `TEAM_SPLIT` | warning | Team bị tách (kèm kích thước từng mảnh) |
| `TEAM_SPLIT_EXCEEDED` | error | Vượt `MAX_SPLIT` |
| `SHIFT_NOT_SATISFIED` | warning | Không đúng ca nguyện vọng |
| `SHIFT_LOCKED_VIOLATION` | error | Không xếp được người bị khoá ca (cần BTC can thiệp) |
| `TINY_CHUNK` | info | Mảnh nhỏ hơn `MIN_CHUNK` |
| `MISSING_ID_CARD` | error | Thiếu CCCD/ngày sinh → **không xuất được vé** |

`MISSING_ID_CARD` chạy như một bước pre-check trước khi phân bổ và hiển thị ngay trên dashboard.

## 5. Manual Adjustment – quy tắc kiểm tra

Khi `PATCH /flight-assignments/{id}`:

```
BEGIN IMMEDIATE
  remaining = capacity - reserved - COUNT(assignments của flight đích)
  if remaining <= 0            → 409 FLIGHT_CAPACITY_EXCEEDED   (chặn)
  if flight đích khác ca nguyện vọng → cảnh báo (không chặn)
  if thao tác làm team tăng số mảnh  → cảnh báo (không chặn)
  ghi assignment mới, assignment_mode='manual'
  ghi audit_logs(before, after, reason)
COMMIT
```

Người đã `assignment_mode='manual'` được **giữ nguyên** ở các lần chạy auto allocation sau
(cờ `is_pinned` suy ra từ `assignment_mode`), trừ khi Admin chọn `force_reallocate=true`.

## 6. Auto Bus Allocation

Chạy **sau** khi phân bổ chuyến bay xong, cho từng `trip_leg`.

```
INPUT event_id, trip_leg_id
1. demand = registration có needs_bus=1 ở chặng này
2. Với chặng liên quan sân bay (AIRPORT_TO_HOTEL, HOTEL_TO_AIRPORT):
       nhóm theo flight_id  → xe phải phục vụ đúng chuyến (giờ hạ cánh khác nhau)
   Với chặng nội thành (CITY_TO_AIRPORT, AIRPORT_TO_CITY):
       nhóm theo pickup_point_id, sau đó theo flight_id (giờ bay quyết định giờ đón)
3. Trong mỗi nhóm: sắp team giảm dần theo size, xếp Best-Fit vào các xe của chặng
   (ưu tiên xe đã có người cùng team; không vượt capacity)
4. Tối ưu công suất: nếu tổng người ≤ tổng ghế của (n-1) xe → dồn, báo xe thừa cho BTC
5. Flag: NO_BUS_CAPACITY, BUS_UNDERUTILIZED (<50%), MIXED_FLIGHT_ON_BUS
```

Ưu tiên (theo BRD 7.3): **(1) cùng chuyến bay → (2) cùng team → (3) tối ưu công suất → (4) không vượt sức chứa.**
Ràng buộc (4) là cứng, (1) là cứng với chặng sân bay, (2)(3) là mềm.

## 7. Room Allocation (Phase 2 – interface đã chừa sẵn)

MVP: BTC import Excel. Khi làm auto, thứ tự ràng buộc:
1. **Cứng**: cùng giới (`rooms.gender_policy`), không vượt `capacity`.
2. **Mềm**: cùng team → cùng phòng ban → gần tuổi.
3. Ghi nhận `dietary_restriction` / `health_note` để BTC xếp phòng gần thang máy, v.v.

Hàm ký sẵn: `allocate_rooms(db, event_id, dry_run) -> AllocationResult` cùng khuôn với flight/bus.

## 8. Test bắt buộc cho `services/allocator/`

| Test | Kỳ vọng |
|---|---|
| Đủ slot, team nhỏ | Không team nào bị tách, 100% đúng ca |
| Tổng slot = tổng người | Xếp hết, không vượt capacity |
| Thiếu slot | Có flag `UNASSIGNED`, không vượt capacity |
| 1 team lớn hơn mọi chuyến | Bị tách ≤ `MAX_SPLIT`, mảnh ≥ `MIN_CHUNK` |
| Toàn bộ chọn Ca 2, chỉ có chuyến Ca 1 | Xếp hết + flag `SHIFT_NOT_SATISFIED` cho tất cả |
| Có người `is_shift_locked` | Luôn đúng ca hoặc flag error |
| Có người đã gán thủ công | Không bị auto ghi đè |
| Chạy 2 lần cùng seed | Kết quả giống hệt |
| Property test | Với input ngẫu nhiên, **không bao giờ** vi phạm capacity |
