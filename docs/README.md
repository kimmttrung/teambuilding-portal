# Tài liệu dự án – Team Building Portal

Đọc theo thứ tự nếu bạn mới vào dự án.

| File | Nội dung | Đọc khi |
|---|---|---|
| [00-review-of-draft.md](00-review-of-draft.md) | Đánh giá bản thiết kế nháp, những gì đã sửa/bổ sung | muốn biết vì sao thiết kế khác bản draft ban đầu |
| [01-requirements.md](01-requirements.md) | Yêu cầu, vai trò, vòng đời chương trình, phạm vi MVP | bắt đầu |
| [02-architecture.md](02-architecture.md) | Stack, sơ đồ triển khai, cấu trúc thư mục, luồng nghiệp vụ | trước khi viết dòng code đầu tiên |
| [03-data-model.md](03-data-model.md) | **Toàn bộ schema SQLite + PRAGMA + invariants** | khi làm model / migration |
| [04-api-spec.md](04-api-spec.md) | Danh sách endpoint, request/response mẫu, mã lỗi | khi làm API hoặc gọi API từ FE |
| [05-allocation-algorithm.md](05-allocation-algorithm.md) | Thuật toán phân chuyến bay & xe, flag, test | khi làm `services/allocator/` |
| [06-rag-chatbot.md](06-rag-chatbot.md) | Pipeline RAG, prompt, tool, **bảo mật dữ liệu cá nhân** | khi làm chatbot |
| [07-frontend.md](07-frontend.md) | Route, màn hình, quy ước code React | khi làm frontend |
| [08-devops.md](08-devops.md) | Biến môi trường, Docker, backup, lệnh hằng ngày | khi setup máy hoặc deploy |
| [09-security.md](09-security.md) | Phân quyền, ma trận quyền, dữ liệu nhạy cảm, audit | khi làm bất kỳ endpoint nào |
| [10-roadmap.md](10-roadmap.md) | Kế hoạch 4 ngày, danh sách commit, effort, rủi ro | mỗi sáng |
| [adr/](adr/) | Các quyết định kiến trúc và lý do | khi muốn thay đổi một quyết định lớn |

## Quy tắc cập nhật tài liệu
- Đổi schema → sửa `03-data-model.md` **trước**, rồi mới viết migration.
- Thêm endpoint → thêm vào `04-api-spec.md` trong cùng commit.
- Đổi một quyết định lớn → viết ADR mới, đánh dấu ADR cũ `Superseded`.
