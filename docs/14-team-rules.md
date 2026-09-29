# 14 – Quy tắc chung khi làm nhóm (BẮT BUỘC)

Áp dụng cho cả 4 thành viên trong đợt làm lại v2 (29/9 → 4/10/2026) và các đợt sau.
PR nào vi phạm quy tắc trong file này sẽ **không được merge**, kể cả khi tính năng chạy đúng.

| Thứ | Nguồn chuẩn |
|---|---|
| Giao diện | Figma v2: <https://www.figma.com/design/nVnHAq39rrSlnbysO6EFpt/TeamBuilding?node-id=1041-2> |
| Design system | Skill `design-notion`: [.claude/skills/design-notion/SKILL.md](../.claude/skills/design-notion/SKILL.md) |
| Schema DB | [03-data-model.md](03-data-model.md) (sau khi merge nhánh `feature/migrate-db` của An) |
| API | [04-api-spec.md](04-api-spec.md) |
| Chia việc | [15-task-assignment.md](15-task-assignment.md) + board Trello |

---

## 1. Git flow

```
main      ●───────────────────────────────────────────●  v2.0.0  (chỉ PM merge, khi phát hành)
           \                                         /
develop     ●────●──────●──────●──────●──────●──────●         (nhánh tích hợp, chỉ nhận PR)
                  \    /        \    /
feature/...        ●──●          ●──●                          (mỗi người một nhánh cho mỗi thẻ Trello)
```

- **`main`**: bản ổn định. Chỉ PM merge từ `develop` khi phát hành, rồi gắn tag (`v2.0.0`).
- **`develop`**: nhánh tích hợp. **Không ai push thẳng**, chỉ vào bằng Pull Request.
- **Nhánh làm việc**: rẽ từ `develop` mới nhất, tên gắn mã thẻ Trello:
  - `feature/<mã-thẻ>-<mô-tả-ngắn>`: `feature/F3-flight-board`
  - `fix/<mã-thẻ>-<mô-tả-ngắn>`: `fix/F7-seat-double-hold`
  - Chữ thường, gạch nối, tiếng Anh không dấu.
- Trước khi mở PR: `git fetch && git rebase origin/develop`, tự giải xung đột rồi chạy lại test.
- PR vào `develop` dùng **Squash and merge**: mỗi thẻ thành một commit trên develop, dễ revert.
- **Mỗi PR một việc**, nên dưới khoảng 600 dòng thay đổi (không tính `package-lock.json`). Tính năng lớn thì
  tách thành nhiều PR (BE trước, FE sau). Không dồn cả tuần vào một PR cuối cùng.
- Commit theo **Conventional Commits, tiếng Anh**:
  `feat(flights): redesign flight board per figma v2`, `fix(gala): release seat when hold expires`.
  Loại hay dùng: `feat` `fix` `refactor` `test` `docs` `style` `chore`.
- Không commit `.env`, `data/`, `*.db`, `node_modules/`, file build.

> Việc của PM một lần: bật **branch protection** cho `main` và `develop` trên GitHub
> (Settings → Branches: bắt buộc PR, bắt buộc 1 approve, cấm force push).

## 2. Hợp đồng API (backend ↔ frontend)

Frontend đã viết dựa trên các khuôn dưới đây. Trả khác đi là màn hình vỡ hoặc hiện sai lỗi.

### 2.1 Trả về khi thành công
Trả **thẳng** object theo Pydantic response schema, **không bọc** thêm `data`/`success`.

```python
# ✅
@router.get("/flights/{flight_id}", response_model=FlightOut)
def get_flight(...) -> FlightOut: ...
# → {"id": 3, "flight_code": "VN1234", "direction": "outbound", ...}

# ❌ bọc thêm một lớp, frontend đang đọc data.flight_code sẽ ra undefined
return {"success": True, "data": flight}
```

- **Không bao giờ trả ORM object** ra API, luôn qua schema (`UserPublic` / `UserSelf` / `UserAdmin`…).
  Trả ORM là lộ cả cột nhạy cảm (CCCD, hash mật khẩu).
- JSON dùng `snake_case`. Thời gian là **UTC ISO-8601** (`2026-10-04T01:00:00Z`); đổi sang giờ VN chỉ ở
  frontend, qua `utils/format.js`.

### 2.2 Danh sách có phân trang
Dùng `Page[T]` trong [backend/app/schemas/common.py](../backend/app/schemas/common.py):

```json
{ "items": [ ... ], "total": 340, "page": 1, "page_size": 50 }
```

Query: `?page=1&page_size=50` (`page_size` tối đa 200); lọc/sắp xếp `?q=&status=&team_id=&sort=full_name&order=asc`.

### 2.3 Lỗi
Mọi lỗi có **một khuôn duy nhất**, do [backend/app/core/exceptions.py](../backend/app/core/exceptions.py) sinh ra:

```json
{ "error": { "code": "FLIGHT_CAPACITY_EXCEEDED",
             "message": "Chuyến VN1234 chỉ còn 2 chỗ, cần 5 chỗ.",
             "details": { "flight_id": 3, "remaining": 2, "requested": 5 } } }
```

```python
# ✅ ném AppError hoặc lớp con
raise ConflictError("Mã chuyến VN1234 đã tồn tại ở chiều đi.", code="FLIGHT_CODE_DUPLICATED",
                    details={"flight_code": "VN1234"})

# ❌ ra khuôn {"detail": "..."} của FastAPI, frontend không đọc được message
raise HTTPException(status_code=409, detail="duplicated")
```

- `code`: UPPER_SNAKE, **bắt đầu bằng tên module** (`FLIGHT_…`, `BUS_…`, `GALA_…`, `REGISTRATION_…`).
  Frontend rẽ nhánh theo `code`, nên đã công bố một mã thì không đổi tên.
- `message`: tiếng Việt, viết cho **người dùng cuối** đọc (không phải stack trace).
- `details`: dữ liệu để frontend hiển thị thêm (id, số còn lại…), không có thì `{}`.

| HTTP | Lớp dùng | Khi nào |
|---|---|---|
| 400 | `AppError` | Dữ liệu vào sai về nghiệp vụ |
| 401 | `UnauthorizedError` | Thiếu hoặc hết hạn token |
| 403 | `PermissionDeniedError` | Sai vai trò, hoặc đụng dữ liệu người khác |
| 404 | `NotFoundError` | Không tồn tại (kể cả khi CBNV trỏ vào kỳ `draft`) |
| 409 | `ConflictError`, `CapacityExceededError`, `InvalidEventStatusError` | Vượt slot, ghế đã bị giữ, kỳ sai trạng thái |
| 422 | tự động (Pydantic) | Sai kiểu dữ liệu, thiếu trường |
| 429 | `AppError(status_code=429)` | Vượt rate limit |

### 2.4 Đường dẫn và kỳ đang chọn
- Path `/api/v1/<danh-từ-số-nhiều>` gạch nối: `/flights`, `/bus-assignments`, `/admin/email-logs`.
- Kỳ Team Building đang xem **chỉ** lấy qua dependency `ActiveEvent` (đọc header `X-Event-Id`). Service
  nhận `event` từ router, **không tự đi tìm** kỳ `is_active`. Lý do: đổi kỳ chỉ phải sửa một chỗ thay vì hàng trăm chỗ.
- Thêm endpoint hoặc đổi field → sửa [04-api-spec.md](04-api-spec.md) **trong cùng PR**. PR đổi API mà
  không sửa docs sẽ bị trả về.

## 3. Backend

- Luồng phụ thuộc `api → services → models`. **`services` không import từ `api`.**
- Router chỉ: khai báo schema vào/ra, gọi dependency phân quyền, gọi service. **Không viết logic nghiệp vụ
  trong router.**
- Phân quyền kiểm ở **backend** (`require_role`…). Frontend ẩn nút chỉ để cho gọn, không phải để bảo mật.
- Endpoint nhận `user_id` từ client → kiểm `user_id == current_user.id` hoặc người gọi là BTC.
- Mọi thay đổi phân bổ/trạng thái gọi `audit_service.log(...)` **trong cùng transaction**.
- Thao tác có tranh chấp (ghế Gala, đổi chuyến bay, gửi email chống trùng) dùng `BEGIN IMMEDIATE`, giữ
  transaction ngắn.
- Huỷ đăng ký **chỉ** đi qua `cancellation_service`, không tự đổi `registration.status`. Đổi trạng thái mà không gỡ vé bay/xe/phòng/ghế sẽ sinh "ghế ma" chiếm chỗ.
- Không hard-code số ca, số chặng, sức chứa, tên team: tất cả là dữ liệu gắn `event_id`.
- Đặt tên: model số ít (`Flight`), bảng số nhiều (`flights`), hàm service là động từ (`allocate_flights`).
- Python **3.13** (`py -3.13`), venv ở `backend/.venv`.

## 4. Database và migration

- Schema chuẩn là bản mới của An. Sau khi merge, [03-data-model.md](03-data-model.md) phải khớp từng bảng.
- **An là chủ schema.** PR nào có file trong `backend/alembic/versions/` hoặc sửa `backend/app/models/`
  thì cần **An approve** ngoài PM.
- Đổi schema: sửa `03-data-model.md` → sửa model → `alembic revision --autogenerate` → đọc lại file sinh ra
  → `alembic upgrade head` → `alembic check` không lệch.
- Mỗi PR **tối đa 1 migration**. **Không sửa migration đã merge**, muốn đổi thì viết migration mới.
- Hai PR cùng tạo migration: ai merge sau thì rebase rồi chạy `alembic merge heads`.
- Migration không được xoá dữ liệu thật để "cho chạy được". Dữ liệu cũ không hợp lệ thì chuyển đổi và ghi
  log (ví dụ migration `8a1d4e77b2c9`: đổi tên chuyến bay trùng thành `VN1234-T2` thay vì xoá).
- `seed.py --reset` phải chạy được sau mỗi PR đổi schema.

## 5. Frontend

**Giao diện**
- **Bắt buộc theo skill `design-notion` và Figma v2.** Không tự chế màu, font, bo góc, bóng đổ, khoảng cách.
- Chỉ dùng **token**. Tailwind 4 khai token trong khối `@theme` của `src/index.css`
  (`--color-canvas-soft` → class `bg-canvas-soft`). Việt chuyển token của skill design-notion (`colors`, `typography`, `rounded`, `spacing`) vào đó ở thẻ F0, **giữ đúng tên token**;
  sau đó **không ai viết mã màu hex hay `style={{...}}` màu sắc** trong component.

  ```jsx
  // ✅ class sinh từ token trong @theme
  <div className="bg-surface border border-hairline rounded-lg p-6 text-body-sm text-ink-muted">
  // ❌ mã màu cứng, đổi design là phải đi sửa từng file
  <div style={{ background: '#F7F6F3', color: '#37352F' }}>
  ```
- Thiếu token (màu, cỡ chữ, bóng) thì thêm vào `@theme` **và** skill design-notion trong cùng một PR riêng, báo nhóm, không tự đặt giá trị tại chỗ.
- Dùng component trong `src/components/common/` (`Button`, `Card`, `Modal`, `Input`, `Badge`…). Thiếu thì
  **thêm vào `common/`** cho cả nhóm dùng, không tự viết bản riêng trong trang.
- Trang dùng hết chiều ngang, không bọc `mx-auto max-w-3xl`. Màn hình CBNV làm **mobile trước**.

**Code**
- Dữ liệu server qua **TanStack Query**. Không `useEffect + useState` để fetch.
- Gọi API qua `src/api/<domain>.js`. Không gọi axios trực tiếp trong component.
- Header `X-Event-Id` và token **chỉ** gắn ở `src/api/client.js` và `src/api/sse.js`, không rải vào từng hàm.
- Form dùng React Hook Form + Zod, schema đặt trong `src/utils/schemas.js`.
- Chữ hiển thị tiếng Việt, nhãn cố định gom vào `src/utils/constants.js`.
- Ngày giờ qua helper trong `src/utils/format.js`, không gọi `toLocaleString` rải rác.
- Lỗi API hiện `error.message` từ khuôn ở §2.3, không tự viết câu lỗi khác cho cùng một mã.
- Icon lucide trùng tên API của JavaScript phải đặt alias: `import { Map as MapIcon }` (cũng vậy với
  `Image`, `Text`, `Link`, `Filter`, `Menu`), không thì trang trắng.
- **Mọi hook đặt trước mọi `return` sớm**, không thì trang trắng mà `check:render` không bắt được. Lỗi thường gặp: thêm `useQuery`/`useEffect` bên dưới `if (isLoading) return <Spinner />`.

## 6. Figma

- Mọi màn hình mới vẽ trong file Figma v2, theo style/variable của `design-notion`.
- Tên frame theo route: `/admin/flights`, `/my-journey – mobile`.
- Tên component Figma trùng tên component React (`Button`, `SeatMap`, `BusCard`) để tìm qua lại được.
- Màn hình hoặc trạng thái (rỗng, đang tải, lỗi) chưa có trong Figma thì **hỏi PM trước**, không tự vẽ ra
  kiểu riêng.

## 7. Test

Mỗi endpoint mới hoặc bị sửa phải có test cho ít nhất:
1. Trường hợp thành công.
2. Sai quyền: CBNV gọi API của BTC → 403; xem dữ liệu người khác → 403/404.
3. Dữ liệu sai hoặc xung đột → 409/422 với **đúng `code`**.

Thêm nữa:
- **Không xoá hoặc skip test cũ** để cho xanh. Test cũ sai vì schema mới thì sửa, và ghi lý do trong mô tả PR.
- Thuật toán phân bổ (bay/xe/phòng) giữ nguyên dạng hàm thuần và test không cần DB.
- Chạy lại các case tay liên quan trong [12-test-cases.md](12-test-cases.md) trước khi mở PR.

## 8. Checklist trước khi mở PR

Chép vào mô tả PR và tick từng dòng:

```markdown
- [ ] Thẻ Trello: <link>
- [ ] Đã rebase lên develop mới nhất
- [ ] cd backend && py -3.13 -m pytest -q   → xanh
- [ ] cd frontend && npm run build && npm run lint && npm run check:render   → sạch
- [ ] npx oxlint -A all -D no-undef src   → chỉ còn biến có sẵn của trình duyệt
- [ ] npx oxlint --react-plugin -A all -D react-hooks/rules-of-hooks src   → 0 vi phạm
- [ ] Ảnh chụp màn hình (desktop + mobile nếu là màn CBNV) đặt cạnh frame Figma tương ứng
- [ ] Đã cập nhật docs/04 (đổi API) / docs/03 (đổi schema)
- [ ] Không có .env, *.db, data/, console.log thừa
```

## 9. Review và phối hợp

- **PM review mọi PR** vào `develop`. PR có migration cần thêm **An approve**.
- Góp ý review phải được trả lời hoặc sửa trong **4 giờ** (giờ làm việc). Sửa xong thì bấm "Re-request review".
- **File dùng chung**, báo trong nhóm chat **trước khi sửa** để tránh hai người sửa cùng lúc:
  `components/layout/AppLayout.jsx`, `routes/AppRoutes.jsx`, `utils/constants.js`, `utils/schemas.js`,
  `api/client.js`, `api/sse.js`, `src/index.css`, `backend/app/models/`, `backend/app/core/`,
  `backend/app/api/router.py`.
- Không sửa code thuộc tính năng của người khác. Thấy lỗi thì báo chủ tính năng hoặc tạo thẻ `fix/` trên Trello.
- Dùng AI (Claude Code…) được, nhưng **người mở PR chịu trách nhiệm** từng dòng. Skill `design-notion` và
  file này nằm trong repo; khi giao việc cho AI, bảo nó đọc `docs/14-team-rules.md` trước.

## 10. Trello

- Cột: **Backlog → To do → In progress → Review → Done**.
- **Một thẻ = một nhánh = một PR.** Mã thẻ (`F3`, `F7`…) lấy từ [15-task-assignment.md](15-task-assignment.md), dán
  link PR vào thẻ.
- Chuyển sang **Review** khi đã mở PR. Chuyển sang **Done** chỉ khi PR đã merge vào `develop`.
- Thẻ đứng yên ở một cột **quá 1 ngày** → báo PM.
- Mỗi tối cập nhật 3 dòng trong nhóm chat: **đã làm / mai làm / đang vướng**.

## 11. Thế nào là "xong" (Definition of Done)

Một thẻ chỉ tính là xong khi đủ cả 5 điều:
1. PR đã merge vào `develop`.
2. Chạy được trên `docker compose up -d --build` từ `develop`, không chỉ trên máy mình.
3. Giao diện khớp Figma v2 (cả desktop và mobile nếu là màn CBNV).
4. Có test như §7, checklist §8 đã tick hết.
5. Tài liệu liên quan (docs/03, docs/04) đã cập nhật.
