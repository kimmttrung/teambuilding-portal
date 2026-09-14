# ADR-004 – RAG dùng tool có tham số cố định, không text-to-SQL

**Trạng thái**: Accepted · **Ngày**: 10/09/2026 · Phần tool dữ liệu cá nhân (`get_my_journey`, `get_my_registration`) đã bị thay bởi [ADR-005](005-gemini-free-tier-public-kb-only.md): dùng Gemini gói miễn phí nên chatbot không đọc dữ liệu cá nhân nào.

## Bối cảnh
Chatbot cần trả lời cả câu hỏi chung ("lịch trình ngày 2?") lẫn câu hỏi cá nhân ("tôi bay chuyến nào?").
Cách phổ biến là cho LLM sinh SQL và chạy trên DB (text-to-SQL / SQL agent).

## Vấn đề
DB chứa CCCD, ngày sinh, số điện thoại, địa chỉ, số phòng của **toàn bộ nhân viên**.
Text-to-SQL nghĩa là một câu hỏi khéo léo — *"số phòng của chị B là gì?"*, *"bỏ qua hướng dẫn trước đó…"* —
có thể lấy ra dữ liệu của người khác. Không thể chống triệt để bằng prompt.

## Quyết định
1. Vector store **chỉ chứa dữ liệu công khai** (quy định, lịch trình, FAQ, thông báo chung). Không index bảng cá nhân.
2. Dữ liệu cá nhân chỉ đến qua **tool có tham số cố định**: `get_my_journey(section)`, `get_my_registration()`, `get_event_status()`.
3. **Không tool nào nhận `user_id`.** `current_user` được inject từ JWT ở tầng FastAPI;
   mọi `user_id` xuất hiện trong câu hỏi đều bị bỏ qua.
4. Tool tự kiểm tra trạng thái chương trình trước khi trả dữ liệu phân bổ.

## Hệ quả
**Được**: dù prompt bị bẻ hoàn toàn, mô hình vẫn không có đường lấy dữ liệu người khác — bảo vệ nằm ở kiến trúc, không nằm ở câu chữ.

**Mất**: không trả lời được câu hỏi tổng hợp tuỳ ý ("có bao nhiêu người chọn Ca 2?").
Chấp nhận được: đó là việc của Admin Dashboard, không phải của chatbot cho CBNV.
Nếu sau này cần, làm một tool riêng chỉ cho role admin, trả về **số liệu tổng hợp**, không trả bản ghi cá nhân.

## Kiểm chứng
Bộ test prompt injection trong `backend/tests/rag/test_injection.py` phải xanh trước mỗi lần đổi prompt.
