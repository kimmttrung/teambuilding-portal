# Teambuilding – Tổng quan sản phẩm

## 1. Tên sản phẩm

**Teambuilding** – Cổng quản lý Team Building nội bộ (One-stop Portal).

## 2. Mô tả ngắn

Một cổng web duy nhất để CBNV đăng ký tham gia Team Building và xem toàn bộ hành trình của mình
(chuyến bay, xe, phòng, ghế Gala, lịch trình) trên một màn hình, còn Ban tổ chức (BTC) quản lý
và phân bổ tự động mọi thứ ở cùng một chỗ.

## 3. Vấn đề đang giải quyết

Một kỳ Team Building có hàng trăm người, nhiều ca bay, nhiều chặng xe, nhiều khách sạn và một buổi
Gala Dinner. Khi làm bằng Excel, email và nhóm chat:

- **Dữ liệu rải rác, lệch nhau.** Đổi chuyến bay của một người thì danh sách xe, danh sách phòng và
  thông báo gửi đi không tự đổi theo. Portal là **nguồn sự thật duy nhất** – sửa một chỗ, mọi màn hình
  (xe, My Journey, file export) phản ánh ngay.
- **Phân bổ thủ công tốn công và dễ sai.** Xếp ~100–1.000 người vào chuyến bay, xe, phòng sao cho không
  vượt chỗ, không trộn giới tính trong phòng, không tách team… mất nhiều ngày. Hệ thống phân bổ tự động
  trong vài mili giây, BTC chỉ còn chỉnh ngoại lệ.
- **CBNV không biết mình đi đâu, lúc nào.** Thông tin nằm trong nhiều file và tin nhắn. Mỗi người có
  màn hình **My Journey** trên điện thoại, tra được ngay tại sân bay.
- **Hỏi đáp lặp lại.** BTC phải trả lời đi trả lời lại cùng một câu hỏi về lịch trình, quy định.
  Chatbot **Tibi** trả lời thay dựa trên tài liệu công khai.
- **Tranh chấp và thiếu minh bạch.** Chọn ghế Gala theo lượt có khoá chống trùng; mọi thay đổi phân bổ
  đều ghi nhật ký (ai, lúc nào, trước/sau, lý do).

## 4. Đối tượng người dùng

| Vai trò | Là ai | Dùng để làm gì |
|---|---|---|
| **CBNV** (`employee`) | Nhân viên tham gia | Đăng ký, xem hành trình của riêng mình, hỏi chatbot, xin huỷ tham gia |
| **Trưởng nhóm** (`team_leader`) | Người đại diện một team | Quyền CBNV + xem thành viên team, chọn ghế Gala và xếp chỗ cho team |
| **Trưởng xe** | CBNV được BTC chỉ định | Xem danh sách hành khách xe mình phụ trách (tên, điểm đón, SĐT) |
| **BTC** (`admin`) | Ban tổ chức | Cấu hình kỳ, nhập dữ liệu, chạy phân bổ, điều chỉnh, công bố, gửi thông báo, xuất báo cáo |
| **Super admin** | Quản trị hệ thống | Quyền BTC + quản lý tài khoản/vai trò, cấu hình hệ thống, xem nhật ký đầy đủ |

Quy mô mục tiêu: ≤ 1.000 CBNV mỗi kỳ. CBNV dùng chủ yếu trên điện thoại, BTC dùng trên máy tính.

## 5. Tính năng chính

**Cho CBNV**
- **Đăng ký 5 bước**: thông tin cá nhân, xác nhận quy định (bắt cuộn hết), chọn ca, nhu cầu xe theo
  từng chặng, lưu nháp; nhận email xác nhận.
- **My Journey**: một màn hình gồm chuyến bay đi/về, các chặng xe, khách sạn/phòng, ghế Gala, lịch trình;
  thêm vào lịch (`.ics`), mở Google Maps, bấm gọi Trưởng xe.
- **Huỷ tham gia theo giai đoạn**: trước công bố tự huỷ; sau công bố gửi yêu cầu để BTC duyệt.
- **Chatbot Tibi**: hỏi đáp về chương trình, quy định, lịch trình, có trích nguồn.

**Cho BTC**
- **Vòng đời kỳ**: nháp → mở đăng ký → đóng → phân bổ → công bố → diễn ra → kết thúc; chặn nhảy cóc,
  bước lùi phải có lý do.
- **Phân bổ tự động** ★ chuyến bay, xe, phòng: giữ team đi cùng nhau, không vượt sức chứa, không trộn
  giới tính, không ghi đè phần BTC đã chỉnh tay; có chế độ xem trước (dry-run) trước khi ghi.
- **Điều chỉnh thủ công**: bảng kéo-thả chuyến bay, xếp/chuyển người lên xe, sơ đồ phòng theo tầng;
  kiểm tra giờ xe khớp giờ bay.
- **Gala Dinner** ★: bốc thăm thứ tự team, chọn ghế theo lượt có giới hạn thời gian, sơ đồ cập nhật
  trực tiếp (SSE), khoá ghế chống trùng.
- **Dashboard "Việc cần làm"**: tiến độ đăng ký/bay/xe/phòng, checklist trước khi công bố, hoạt động gần đây.
- **Thông báo & email**: đăng thông báo theo đối tượng (tất cả / team / chuyến bay / xe / cá nhân),
  nhắc thiếu giấy tờ hoặc chưa đăng ký, tự báo khi đổi lịch trình/chuyến bay, nhật ký email + gửi lại thư lỗi.
- **Tra cứu một người**: tìm theo tên, xem ngay người đó đang ở chuyến bay, xe, phòng, ghế nào.
- **Import/Export Excel**: CBNV, phòng khách sạn, danh sách bay, xe, phân phòng.
- **Quản lý CBNV, master data, cấu hình kỳ**; chạy **nhiều kỳ song song** (vd. TB2026 Nha Trang, TB2027 Đà Nẵng).
- **Bảo mật & nhật ký**: JWT + phân quyền 3 lớp, chặn dò mật khẩu theo IP, audit log mọi thay đổi phân bổ.

## 6. Công nghệ sử dụng

### Frontend
| Thành phần | Công nghệ |
|---|---|
| Framework | React 19 + Vite 8 |
| Giao diện | Tailwind CSS 4, icon lucide-react |
| Điều hướng | React Router 7 |
| Dữ liệu server | TanStack Query 5, Axios |
| Form & kiểm tra | React Hook Form + Zod |
| Ngày giờ | date-fns (hiển thị theo `Asia/Ho_Chi_Minh`) |
| Kiểm tra chất lượng | oxlint, `check:render` (render thử mọi trang bằng react-dom/server) |

### Backend
| Thành phần | Công nghệ |
|---|---|
| Ngôn ngữ / framework | Python 3.13, FastAPI, Uvicorn |
| ORM / migration | SQLAlchemy 2.0, Alembic |
| Cơ sở dữ liệu | SQLite (chế độ WAL, bật foreign key) |
| Xác thực | JWT (PyJWT) + bcrypt, refresh token xoay vòng |
| Excel | openpyxl |
| Chatbot RAG | Google Gemini (`google-genai`), ChromaDB (vector store), fastembed (embedding chạy local) |
| Realtime | Server-Sent Events (sơ đồ Gala, chatbot) |
| Test | pytest (~495 test) |

### Triển khai
Docker Compose: **nginx** (phục vụ SPA + proxy `/api/`, tắt buffering cho SSE) → **uvicorn**;
dữ liệu SQLite trong named volume, có script sao lưu an toàn khi đang chạy.
