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
| `FIT_WEIGHT` | 10 | `allocation.fit_weight` | thưởng tối đa khi xếp vừa khít một chuyến, tính theo **tỉ lệ** ghế trống |
| `SHIFT_SPLIT_PCT` | 30 | `allocation.shift_split_percent` | tách team theo ca ngay ở vòng 1 khi phe thiểu số đạt ngần này % (0 = không tách) |

`W_TEAM > W_SHIFT` phản ánh quyết định mặc định ở [00 §4 câu 1](00-review-of-draft.md).
BTC đổi ưu tiên chỉ bằng cách sửa 2 con số này — **không phải sửa code**.

## 3. Thuật toán Auto Flight Allocation

```
INPUT  event_id, direction
OUTPUT AllocationResult(assignments, flags, summary)

1. Chuẩn bị
   groups  = [team → danh sách registration tham gia, chưa bị khoá thủ công]
   flights = chuyến bay theo direction, mỗi chuyến remaining = capacity - reserved - đã gán thủ công
   Team có nguyện vọng chia đôi (phe thiểu số >= SHIFT_SPLIT_PCT và mọi mảnh >= MIN_CHUNK)
   được tách sẵn theo ca thành các nhóm con — mỗi nhóm con từ đây là một "nhóm gắn kết"
   riêng, kể cả ở vòng 3.
   Sắp xếp groups giảm dần theo size  (Best-Fit Decreasing: nhóm lớn khó xếp → xử lý trước)

2. Vòng 1 – xếp nguyên nhóm
   for g in groups:
       cand = các chuyến còn remaining >= size(g)
       nếu cand rỗng → chuyển g sang hàng đợi SPLIT
       chọn f* trong cand tối đa hoá:
           preferred_shift_match(g, f) * W_SHIFT
         - FIT_WEIGHT * (ghế thừa sau khi xếp g / sức chứa dùng được)   # chống phân mảnh
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

**Vì sao độ vừa khít tính theo tỉ lệ (sửa sau khi test tay)**: bản đầu trừ thẳng SỐ ghế còn
thừa, tức một ghế trống = 1 điểm còn một người đúng ca = 6 điểm. Chuyến to và rỗng vì vậy bị
phạt nặng nhất — ngược hẳn mong đợi — và càng nhiều người vào chuyến nhỏ thì nó càng "khít"
nên càng hút tiếp. Trên dữ liệu thật: 96/98 người dồn vào CA2 dù 38 người xin CA1, và tăng
`shift_weight` từ 6 lên 30 cũng không đổi được gì (tức là ô cấu hình vô nghĩa). Tính theo tỉ lệ
thì độ khít nhiều nhất đáng `FIT_WEIGHT` điểm, không bao giờ đè nổi nguyện vọng của vài người.

**Vì sao tách team theo ca ngay ở vòng 1**: xếp nguyên team nghĩa là phe thiểu số mất trắng
nguyện vọng. Với team chia gần đôi thì tách hợp lý hơn — vẫn còn hai khối lớn đi cùng nhau.
Mảnh tách có chủ ý được tính là hai NHÓM riêng trong hàm mục tiêu ở §2; nếu vẫn coi là một
team thì vòng 3 gom ngay chúng về một chuyến (190 cặp cùng team = 1900 điểm, đổi lại 10 người
đúng ca chỉ 60 điểm) và việc tách bị hoàn tác. Flag `TEAM_SPLIT` vẫn sinh ra để BTC thấy.
Đo trên dữ liệu dev: đúng ca 62.2% → 94.9%, đổi lại 6/8 team bị tách.

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

**Bỏ toàn bộ phân bổ một chiều**: `POST /flights/reset-allocation` `{direction, reason,
include_manual}`. Cần vì hạ sức chứa xuống dưới số người đang ngồi bị chặn — muốn sửa số ghế
cho khớp vé thật sự mua được thì phải dọn trước rồi chạy lại. Giữ bản ghi `manual` trừ khi
`include_manual=true`, ghi audit `flight_allocation.reset` kèm lý do bắt buộc.

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
5. Flag: NO_BUS_CAPACITY (error, kèm lý do full | no_matching_bus),
         MISSING_FLIGHT_ASSIGNMENT (error, chặng sân bay mà người đó chưa có chuyến bay),
         BUS_UNDERUTILIZED (<50%), MIXED_FLIGHT_ON_BUS, SURPLUS_BUS (info: xe trống / có thể bớt 1 xe)
```

Ưu tiên (theo BRD 7.3): **(1) cùng chuyến bay → (2) cùng team → (3) tối ưu công suất → (4) không vượt sức chứa.**
Ràng buộc (4) là cứng, (1) là cứng với chặng sân bay, (2)(3) là mềm.

**Đã hiện thực (bước 15)** ở `services/allocator/buses.py`, với ba điểm cụ thể hoá:
- "Chặng gắn sân bay" đọc từ `trip_legs.is_airport_linked`, **không** đoán theo mã chặng —
  số chặng và tính chất từng chặng là dữ liệu BTC khai (CLAUDE.md cạm bẫy #3).
- Xe đã gán điểm đón chỉ nhận người chọn đúng điểm đó (hoặc người không chọn điểm) — ràng
  buộc cứng ở mọi chặng, vì một xe không thể có mặt ở hai toà nhà cùng lúc.
- Người chưa có chuyến bay ở chặng sân bay nhận `MISSING_FLIGHT_ASSIGNMENT` thay vì
  `NO_BUS_CAPACITY`: gộp chung sẽ khiến BTC đi thuê thêm xe trong khi việc cần làm là phân bổ
  chuyến bay trước.

## 7. Room Allocation (Phase 2 – interface đã chừa sẵn)

MVP: BTC import Excel. Khi làm auto, thứ tự ràng buộc:
1. **Cứng**: cùng giới (`rooms.gender_policy`), không vượt `capacity`.
2. **Mềm**: cùng team → cùng phòng ban → gần tuổi.
3. Ghi nhận `dietary_restriction` / `health_note` để BTC xếp phòng gần thang máy, v.v.

Hàm ký sẵn: `allocate_rooms(db, event_id, dry_run) -> AllocationResult` cùng khuôn với flight/bus.

**Đã hiện thực (bước 16)** phần MVP: xếp tay (`POST /room-assignments`) và import Excel, cả hai chặn
cứng sức chứa + `gender_policy`. Người chưa khai giới tính nam/nữ chỉ vào được phòng `any` — không
đoán thay họ. `GET /rooms/summary` tính
`uncovered = max(thiếu_nam + thiếu_nữ + người_chỉ_ở_được_phòng_any − giường_any, 0)`: tổng giường đủ
chưa chắc đủ, vì phòng nam không nhận nữ.

**Đã hiện thực (bước 18d)** xếp phòng tự động — `services/allocator/rooms.py` (hàm thuần),
`room_loader.py`, `room_allocation_service.py`, `POST /rooms/allocate {dry_run, force_reallocate}`:

| Loại | Quy tắc |
|---|---|
| Cứng | đúng `gender_policy`; không vượt `capacity`; **không trộn giới trong một phòng, kể cả phòng `any`**; người chưa khai nam/nữ chỉ vào phòng `any`; giữ bản ghi `manual` trừ khi `force_reallocate` |
| Mềm | điểm mỗi cặp ở chung phòng: cùng team `rooms.team_weight` (10) > cùng chuyến bay chiều đi `rooms.flight_weight` (4) > cùng phòng ban `rooms.department_weight` (1) — sửa trong `event_settings` |

Các bước:
1. Đặt người xếp tay vào phòng của họ (sai giới / vượt chỗ → flag `PINNED_ROOM_CONFLICT`, vẫn giữ).
2. Người chưa khai giới tính vào phòng `any` trước — để phần tràn của nam/nữ không chiếm mất.
3. Nam, nữ vào đúng phòng của mình; phần tràn sang phòng `any`, giới tràn nhiều hơn chọn trước.
   Mỗi team một nhóm, team đông trước; trong nhóm sắp theo chuyến bay rồi phòng ban. Chọn phòng
   theo điểm: vào tiếp phòng đồng đội đang ở > vừa khít > lấp kín phòng (phòng to trước) > lấp
   phòng đang dở > cùng chuyến bay; thừa giường bị trừ điểm.
4. Cải thiện cục bộ: đổi chỗ hai người / chuyển một người sang phòng còn chỗ giữa hai phòng cùng
   giới khi tổng điểm tăng; bỏ qua cặp phòng không có team/chuyến/phòng ban chung.
5. Xếp lại người còn thiếu một lượt (bước 4 có thể làm trống hẳn một phòng `any`).
6. Trưởng phòng: giữ người BTC chọn; không có thì trưởng nhóm → người thuộc team đông nhất trong phòng.

Flag: `NO_ROOM_CAPACITY`, `MISSING_GENDER` (error — người chưa có phòng) · `PINNED_ROOM_CONFLICT`
(warning) · `ALONE_FROM_TEAM`, `HEALTH_NOTE` (chỉ báo có ghi chú, không có nội dung), `EMPTY_ROOM`
(info). Không có bước ngẫu nhiên: cùng đầu vào cho cùng kết quả bất kể thứ tự. Dữ liệu dev
(100 người, 50 phòng): 98 có phòng — 2 nam thiếu vì chỉ có 55 giường nam — 91.7% ở cùng đồng đội,
100% cùng chuyến bay, ~6 ms.

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
