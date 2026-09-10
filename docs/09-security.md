# 09 – Bảo mật & phân quyền

## 1. Xác thực

- **MVP**: email + mật khẩu, hash bằng `bcrypt` (passlib), 12 rounds. Tài khoản do BTC import,
  mật khẩu ban đầu sinh ngẫu nhiên, `must_change_password = 1`.
- **JWT**: access token 60 phút, refresh token 7 ngày. Payload: `{sub: user_id, role, jti, exp}`.
  Không nhét dữ liệu cá nhân vào token.
- **Refresh token** lưu hash trong DB để thu hồi được khi logout / đổi mật khẩu.
- **SSO (Phase 2)**: đã tách sẵn interface.
  ```python
  class AuthProvider(Protocol):
      def authenticate(self, credentials) -> User | None: ...
  # LocalAuthProvider (MVP)  |  AzureADProvider (Phase 2)
  ```
  Khi cắm SSO, chỉ đăng ký provider mới trong `core/security.py`, không sửa API layer.

## 2. Phân quyền – 3 lớp

```python
# Lớp 1: role
@router.get("/flights", dependencies=[Depends(require_role("admin", "super_admin"))])

# Lớp 2: ownership — CBNV chỉ đọc dữ liệu của chính mình
def get_own_registration(current_user = Depends(get_current_user), db = Depends(get_db)):
    ...  # luôn lọc theo current_user.id, KHÔNG nhận user_id từ query param

# Lớp 3: trạng thái chương trình
@router.post("/registrations", dependencies=[Depends(require_event_status("registration_open"))])
```

**Quy tắc vàng**: endpoint nào nhận `user_id` từ client thì phải kiểm tra
`user_id == current_user.id or current_user.role in ADMIN_ROLES`. Không có ngoại lệ.
Đây là lỗ hổng IDOR phổ biến nhất trong loại ứng dụng này.

## 3. Ma trận quyền

| Tài nguyên | employee | team_leader | admin | super_admin |
|---|---|---|---|---|
| Đăng ký của mình | CRU | CRU | R | R |
| Đăng ký người khác | – | R (trong team, ẩn CCCD/SĐT cá nhân) | RU | RU |
| Hồ sơ của mình | RU | RU | R | RUD |
| Hồ sơ người khác | – | R (rút gọn) | RU | CRUD |
| Chuyến bay / xe / phòng | R (của mình) | R (của mình) | CRUD | CRUD |
| Chạy allocation | – | – | ✔ | ✔ |
| Sơ đồ Gala | R | R + chọn ghế cho team | CRUD | CRUD |
| Audit log | – | – | R | R |
| Đổi role người dùng | – | – | – | ✔ |
| Đổi trạng thái chương trình | – | – | ✔ | ✔ |

## 4. Dữ liệu nhạy cảm

| Trường | Ai thấy |
|---|---|
| `id_card_number`, `date_of_birth`, `address`, `health_note` | chính chủ + admin |
| `phone` | chính chủ + admin + **Trưởng xe thấy SĐT hành khách xe mình** (nhu cầu điều phối thật) |
| `room_number` + danh sách bạn cùng phòng | người trong cùng phòng + admin |
| `wish_note` | chính chủ + admin |
| Ghế Gala | mọi người thấy **team** sở hữu ghế, không thấy tên cá nhân người ngoài team |

Response schema Pydantic tách riêng: `UserPublic` (tên, avatar, team) · `UserSelf` (đầy đủ) ·
`UserAdmin` (đầy đủ + audit). Không bao giờ trả thẳng ORM object ra API.

## 5. Chống các lỗi thường gặp

| Rủi ro | Biện pháp |
|---|---|
| IDOR (đổi id trên URL để xem dữ liệu người khác) | Lớp 2 §2 + test tự động cho mỗi endpoint có `{id}` |
| SQL Injection | Chỉ dùng SQLAlchemy ORM/`text()` có bind param. Cấm f-string vào SQL |
| XSS | React escape mặc định; nội dung markdown (quy định, thông báo) render qua `DOMPurify` |
| Brute force đăng nhập | Khoá 15 phút sau 5 lần sai / IP + email |
| Upload độc hại | Chỉ nhận jpg/png/webp, kiểm tra magic bytes, đổi tên file, ≤ 2MB, phục vụ từ đường dẫn tĩnh riêng |
| Rate limit chat | 20 tin / 10 phút / user |
| Rò rỉ qua chatbot | Xem [06 §5](06-rag-chatbot.md) |
| Mất dữ liệu do thao tác nhầm | Auto backup trước allocation + audit log đủ để dựng lại |
| Secret lọt vào git | `.env` trong `.gitignore`, chỉ commit `.env.example` |

## 6. Audit log — ghi những gì

Bắt buộc ghi (`audit_service.log(...)`):
- Mọi thay đổi `*_assignments` (tạo/sửa/xoá), cả auto lẫn manual.
- Đổi `events.status`.
- Đổi role, reset mật khẩu, tạo/xoá user.
- Import Excel (số dòng, tên file, số lỗi).
- Publish thông báo, gửi email hàng loạt.
- Xác nhận/ép gán ghế Gala.

Không ghi: request GET thông thường, đăng nhập thành công (chỉ cập nhật `last_login_at`).

## 7. Quyền riêng tư (PDPD Việt Nam – Nghị định 13/2023)

Hệ thống thu thập CCCD, ngày sinh, số điện thoại, địa chỉ → là **dữ liệu cá nhân cơ bản**. Cần:
1. Nêu rõ mục đích thu thập ngay trên form đăng ký ("dùng để xuất vé máy bay và bố trí phòng").
2. Lưu bằng chứng đồng ý → bảng `consents`.
3. Có kế hoạch xoá/ẩn dữ liệu sau khi kết thúc chương trình (đề xuất: 90 ngày sau `completed`,
   xoá `id_card_*`, giữ lại dữ liệu tổng hợp).
4. Hạn chế export: file Excel chứa CCCD chỉ `admin` tải được, và mỗi lần tải ghi audit log.
