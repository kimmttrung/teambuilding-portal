# F1 – Đăng nhập, hồ sơ và quản lý CBNV

## Phạm vi bàn giao

- Nhánh làm việc hiện tại: `feature/F1-login-manageUser`.
- Schema theo xác nhận chủ task: 27 bảng, Alembic `7d2a9e41c027`. Không thêm migration.
- Figma v2 trả HTTP 403 khi truy cập bằng công cụ hiện có. Chưa đối chiếu frame,
  chưa chỉnh layout/style theo Figma. Thay đổi FE chỉ sửa luồng tài khoản/import.
- Không sửa file `ERD.MD` chưa được theo dõi hay DB phát triển.

## Thay đổi

1. `/auth/me` có thể refresh access token hết hạn; nhiều request trong cùng tab gộp một lần refresh.
   Sai mật khẩu khi login/đổi mật khẩu không kích hoạt refresh.
2. Đổi mật khẩu thu hồi mọi refresh token cũ và cấp cặp token/hồ sơ mới cho thiết bị hiện tại.
   FE lưu cả hai token và xoá cờ bắt đổi mật khẩu từ hồ sơ trả về.
3. Refresh đồng thời cùng token chỉ một request được xoay vòng.
4. Bắt đổi mật khẩu lần đầu: chuyển thẳng `/profile`, form mở sẵn, không có nút Huỷ.
5. Ngày hồ sơ/CBNV phải tồn tại trong lịch; tên tạo mới không được chỉ có khoảng trắng.
6. Import kiểm email bằng `EmailStr`, chuẩn hoá mã NV chữ hoa. Export dùng mã tổ chức duy nhất.
   File vừa export nhập lại giữ nguyên cả dòng BTC và tài khoản cũ chưa có mã.
7. Import không có tài khoản mới vẫn giữ báo cáo kết quả, hiển thị số unchanged.
8. Hết thời gian khoá bắt đầu chu kỳ sai mới; chặn mật khẩu quá 72 byte ở đầu vào.
   Logout vẫn xoá AuthContext dù request thất bại. Export lỗi Blob 401 cũng refresh được.

## Kiểm tra kỹ thuật

Lệnh từ thư mục tương ứng:

```powershell
# D:/teambuilding-portal/backend
& D:/teambuilding-portal/backend/.venv/Scripts/python.exe -m pytest tests/test_auth.py tests/test_admin_users.py tests/test_user_import.py -o addopts= -q
# D:/teambuilding-portal/frontend
npm run build
npm run lint
npm run check:render
```

Test bổ sung gồm: đổi mật khẩu lần đầu và refresh phiên mới; refresh đồng thời;
ngày không tồn tại; export/import thường + nhạy cảm; team trùng tên; tài khoản thiếu mã NV;
email sai; kiểm thử tích hợp trên DB được dựng bằng toàn bộ Alembic migration.
`check:render` bổ sung cả kiểm tra interceptor axios thật qua adapter không gọi mạng.

### Kết quả thực chạy (01/10/2026)

| Kiểm tra | Kết quả |
|---|---|
| 3 file pytest F1 | **73 passed**, 146.36 giây; giữ nguyên toàn bộ test cũ |
| Test DB qua Alembic | Xanh; revision `7d2a9e41c027`, 27 bảng; export → import = unchanged |
| `npm run build` | Xanh; còn cảnh báo bundle trên 500 kB |
| `npm run lint` | Exit 0, **0 lỗi / 16 cảnh báo**; không coi là sạch cảnh báo |
| `npm run check:render` | **198 kịch bản OK**, không có báo cáo `: LỖI` |
| Quét `react-hooks/rules-of-hooks` | 0 lỗi / 0 cảnh báo |
| Quét `no-undef` | Chỉ 17 loại global trình duyệt có sẵn, không có biến ứng dụng chưa định nghĩa |
| Ruff trên các file BE sửa, không xét E501 | Xanh; E501 còn dòng dài theo phong cách cũ, chưa chuẩn hoá toàn module |

Log máy chạy nằm trong `D:/teambuilding-portal/backend/data/` (không commit):
`f1-pytest-final2.log`, `f1-render-final.log`, `f1-lint-final.log`, `f1-collect.log`.

**Giới hạn kiểm tra toàn repo:** `pytest --collect-only -q` còn 19 lỗi collection của các
module ngoài F1, do test cũ vẫn import model đã bỏ ở schema v2 (`RoomAssignment`,
`BusAssignment`, `RegistrationBusNeed`, …). Không xoá/skip hay sửa test các module đó.

## Hạng mục chưa nghiệm thu

- Link PR: chưa tạo/push PR trong phiên làm việc này.
- Ảnh desktop/mobile: chưa chụp tương tác trình duyệt cho các trạng thái yêu cầu.
- So sánh cạnh nhau Figma: bị chặn bởi quyền truy cập Figma.
- Ảnh Excel export → import: có test tự động, chưa có ảnh thao tác Excel/trình duyệt.
- Python chuẩn nhóm là 3.13; venv máy hiện tại là 3.12.4. Cần chạy lại trên Python 3.13/CI.
- `check:render` là SSR, không thay thế kiểm tra mobile, bàn phím hay luồng tương tác thực.
- Access token cũ vẫn sống đến hạn; đổi mật khẩu thu hồi refresh token, không có blacklist access token.
- Schema 24 bảng trong docs/03 còn cần chủ F-DB đồng bộ toàn bộ với bản 27 bảng đã chốt cho F1.

Không chuyển thẻ sang Done khi còn thiếu PR/review và nghiệm thu giao diện.