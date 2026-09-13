# 10 – Lộ trình & kế hoạch thực thi

**Hạn nộp: Thứ 2, 14/09/2026.** Hôm nay 10/09/2026 (Thứ 5) → còn **4 ngày làm việc thực tế**.

## 1. Nguyên tắc cắt phạm vi

Không thể làm hết 5 module + RAG trong 4 ngày ở mức production. Ưu tiên theo thứ tự:

```
PHẢI CÓ (demo được, chạy được)      NÊN CÓ (nếu kịp)          ĐỂ SAU (nói rõ trong bản trình bày)
─────────────────────────────      ──────────────────        ────────────────────────────────
Auth + phân quyền                  Import/Export Excel        Auto Room Allocation
Form đăng ký đầy đủ                Email thật (SMTP)          SSO thật
Admin: chuyến bay + slot           Audit log UI               Teams notification
Auto Flight Allocation ★            Sơ đồ Gala + seat lock     Báo cáo BI
Manual Adjustment + validate       Quản lý xe + Trưởng xe     Tối ưu thuật toán ILP
My Journey                         Dashboard biểu đồ
Chatbot RAG ★                       Thông báo
Docker chạy 1 lệnh
```
★ = hai điểm ăn điểm nhất khi trình bày: **thuật toán phân bổ** và **RAG**. Đừng để hết thời gian trước khi làm xong 2 phần này.

## 2. Kế hoạch theo commit

> ✅ = đã hoàn thành và đã commit. Cập nhật dấu này sau mỗi bước.

Mỗi bước là một commit. Tên commit tiếng Anh, conventional commits.

### Ngày 0 – 10/09 (hôm nay)

| # | Việc | Commit |
|---|---|---|
| ✅ 1 | Tài liệu kiến trúc + CLAUDE.md + README + .gitignore | `docs: add architecture documentation and project guide` |
| ✅ 2 | Khung backend: FastAPI app, config, database + PRAGMA, health check | `feat(backend): bootstrap FastAPI app with SQLite setup` |
| ✅ 3 | Toàn bộ SQLAlchemy models + Alembic migration đầu tiên | `feat(backend): add database models and initial migration` |
| ✅ 4 | Auth: JWT, bcrypt, login/refresh/me, dependencies phân quyền | `feat(auth): add JWT authentication and role-based access` |
| ✅ 5 | Seed dữ liệu mẫu (1 event, 8 team, ~120 CBNV, 4 chuyến bay, 10 xe) | `feat(backend): add database seed script` |

### Ngày 1 – 11/09

| # | Việc | Commit |
|---|---|---|
| ✅ 6 | Master data API + Event API + đổi trạng thái chương trình | `feat(api): add event lifecycle and master data endpoints` |
| ✅ 7 | API đăng ký + consent + validate theo trạng thái | `feat(api): add team building registration endpoints` |
| ✅ 8 | Khung frontend: Vite, Tailwind, router, AuthContext, layout | `feat(frontend): bootstrap React app with routing and auth` |
| ✅ 9 | Form đăng ký 5 bước + trang hồ sơ cá nhân | `feat(frontend): add multi-step registration form and profile page` |
| ✅ 10 | Email service + 3 template đăng ký + nhật ký email | `feat(backend): add email notification service` |

### Ngày 2 – 12/09 (ngày nặng nhất)

| # | Việc | Commit |
|---|---|---|
| ✅ 11 | CRUD chuyến bay + tổng quan slot theo chiều/ca | `feat(api): add flight management endpoints` |
| ✅ 12 | **Thuật toán Auto Flight Allocation** + 25 unit test | `feat(allocator): implement automatic flight allocation` |
| ✅ 13 | API allocate (dry-run/commit) + điều chỉnh thủ công + audit log | `feat(api): add flight allocation and manual adjustment` |
| ✅ 14 | Màn hình admin chuyến bay + preview allocation + bảng điều chỉnh | `feat(frontend): add flight allocation admin screens` |
| ✅ 15 | Xe: CRUD + auto bus allocation + Trưởng xe | `feat(backend): add bus management and allocation` |

### Ngày 3 – 13/09

| # | Việc | Commit |
|---|---|---|
| ✅ 16 | Khách sạn/phòng: CRUD + import Excel | `feat(backend): add hotel and room management` |
| 17 | API `journey/me` + màn hình My Journey | `feat(frontend): add my team building journey dashboard` |
| 18 | Admin dashboard + thống kê | `feat(frontend): add admin dashboard with statistics` |
| 19 | **RAG**: vector store, indexer, engine, tool, SSE endpoint | `feat(rag): add RAG chatbot with knowledge base` |
| 20 | Widget chat frontend | `feat(frontend): add chat assistant widget` |
| 21 | Import/Export Excel | `feat(backend): add excel import and export` |

### Ngày 4 – 14/09 (buổi sáng)

| # | Việc | Commit |
|---|---|---|
| 22 | Gala: model + API seat hold/confirm + sơ đồ (nếu kịp) | `feat(gala): add seat selection with concurrency control` |
| 23 | Docker hoá hoàn chỉnh + healthcheck + nginx | `chore: add docker compose setup for full stack` |
| 24 | README hướng dẫn chạy demo + ảnh chụp màn hình | `docs: add setup and demo guide` |
| 25 | Sửa lỗi, đánh bóng UI | `fix: polish ui and resolve demo issues` |

## 3. Nếu bị trễ – thứ tự hy sinh

1. Gala Dinner (bước 22) → chỉ demo sơ đồ tĩnh, nói rõ cơ chế seat lock đã thiết kế.
2. Import/Export Excel (21) → làm export trước, import sau.
3. Auto Bus Allocation (15) → cho phép gán thủ công, thuật toán để Phase 2.
4. Email thật → chỉ log ra console, có ảnh chụp template.

**Không được hy sinh**: Auto Flight Allocation, My Journey, RAG, Docker.

## 4. Chuẩn bị cho buổi trình bày

| Cần có | Ghi chú |
|---|---|
| `docker compose up` chạy được từ máy sạch | thử trên máy khác trước |
| Dữ liệu seed đẹp: ~120 CBNV, 8 team, 4 chuyến bay có chuyến gần đầy | để demo được cả trường hợp thiếu slot |
| Kịch bản demo 8 phút | đăng ký → admin chạy allocation → thấy flag → chỉnh tay → công bố → CBNV mở My Journey → hỏi chatbot |
| Sẵn 3 tài khoản demo | `employee@`, `leader@`, `admin@` – mật khẩu ghi trong README |
| Trả lời được 6 câu IT phải phản hồi (BRD mục 17) | kiến trúc, tích hợp, thuật toán, effort, timeline, rủi ro — nằm rải trong docs/ |

## 5. Effort ước lượng cho bản production thật (trả lời BRD mục 17)

| Module | Effort (người-ngày) |
|---|---|
| Nền tảng (auth, phân quyền, master data, audit) | 8 |
| Module 1 – Đăng ký | 6 |
| Module 2 – Chuyến bay + allocation | 12 |
| Khách sạn/phòng (có auto allocation) | 8 |
| Module 3 – Xe | 8 |
| Module 4 – Gala Dinner | 10 |
| Module 5 – My Journey | 5 |
| Admin dashboard + import/export | 8 |
| Email/notification | 4 |
| Chatbot RAG | 8 |
| Test + triển khai + tài liệu | 10 |
| **Tổng** | **~87 người-ngày ≈ 2 tháng cho 2 dev** |

Bản MVP 4 ngày này là **prototype chứng minh khả thi**, không phải bản triển khai thật — cần nói rõ khi trình bày.

## 6. Rủi ro & phụ thuộc (trả lời BRD mục 17.6)

| Rủi ro | Ảnh hưởng | Giảm thiểu |
|---|---|---|
| BTC chưa chốt 10 câu hỏi nghiệp vụ | Thuật toán phải làm lại | Đưa vào `event_settings`, đổi bằng cấu hình |
| Không có SSO/API nhân sự | Phải nhập tay dữ liệu CBNV | Làm import Excel trước, tách interface auth |
| Dữ liệu CCCD/ngày sinh thiếu | Không xuất được vé | Pre-check `MISSING_ID_CARD` hiện ngay trên dashboard |
| SQLite giới hạn ghi đồng thời | Nghẽn lúc mở Gala Dinner | WAL + transaction ngắn + seat hold; nếu >1000 user đồng thời thì chuyển Postgres |
| Chi phí LLM | Phát sinh chi phí vận hành | Prompt caching, giới hạn rate, có chế độ mock |
| Đổi chuyến bay sát ngày đi | Sai lệch thông tin xe/phòng | Single Source of Truth + email tự động khi thay đổi |
