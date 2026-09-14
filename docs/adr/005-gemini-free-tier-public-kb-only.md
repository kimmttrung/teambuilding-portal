# ADR-005 – Chatbot dùng Gemini gói miễn phí, chỉ trả lời từ knowledge base công khai

**Trạng thái**: Accepted · **Ngày**: 14/09/2026 · **Thay thế một phần**: ADR-004 (bỏ các tool dữ liệu cá nhân)

## Bối cảnh
Thiết kế ban đầu (docs/06, ADR-004) gọi Claude và có tool `get_my_journey` để trả lời "tôi bay chuyến nào".
Dự án không có Claude API; lựa chọn khả thi là **Google Gemini gói miễn phí** (Google AI Studio).

Điều khoản gói miễn phí cho phép Google dùng nội dung gửi lên để cải thiện sản phẩm. Hệ thống chứa CCCD,
ngày sinh, số điện thoại, chuyến bay, số phòng của toàn bộ CBNV. Yêu cầu nghiệp vụ: **nghiêm cấm hỏi và trả
lời thông tin nhạy cảm của người dùng**; knowledge base là thông tin chung BTC công bố.

## Quyết định
1. LLM: Gemini qua SDK `google-genai`, model cấu hình `LLM_MODEL` (mặc định `gemini-3.6-flash`,
   `thinking_level=minimal`; `gemini-2.5-flash` ban đầu đã bị Google đóng với API key mới).
   Không có `GEMINI_API_KEY` → chế độ thử trả lời bằng trích đoạn tài liệu, không gọi mạng.
2. **Không có tool nào đọc dữ liệu cá nhân, kể cả của chính người hỏi.** Dữ liệu gửi sang Google chỉ gồm
   câu hỏi + đoạn tài liệu công khai + lịch sử hội thoại của chính phiên đó.
3. Knowledge base chỉ gồm: thông tin kỳ, quy định/FAQ/hướng dẫn, lịch trình, thông báo gửi tất cả; và — chỉ
   sau khi công bố — danh sách chuyến bay, xe từng chặng + điểm đón, khách sạn, địa điểm Gala. Không có tên/SĐT
   Trưởng xe, tài xế, người ở cùng phòng, ai ngồi đâu.
4. Guard chạy **trước** khi gọi Gemini: câu tấn công prompt và câu hỏi thông tin của người khác bị từ chối
   ngay; câu hỏi hành trình của chính mình được chỉ sang trang Hành trình. Sau khi gọi: che số giống CCCD và
   số điện thoại không có trong tài liệu, ngay trên luồng stream.
5. Embedding chạy local (fastembed, `paraphrase-multilingual-MiniLM-L12-v2`) — tài liệu không phải gửi đi
   để tạo vector, không tốn quota.

## Hệ quả
**Được**: không có đường nào để dữ liệu cá nhân rời hệ thống qua chatbot, kể cả khi prompt bị bẻ hoàn toàn;
chạy được không tốn tiền; demo được cả khi không có mạng (chế độ thử).

**Mất**: chatbot không trả lời "tôi bay chuyến nào" — chỉ dẫn sang My Journey (một chạm). Gói miễn phí có giới
hạn tần suất; hết lượt → sự kiện `error` `LLM_QUOTA_EXCEEDED` với thông điệp tiếng Việt.

**Nếu sau này có gói trả phí** (dữ liệu không bị dùng để huấn luyện): có thể bật lại tool `get_my_journey`
theo đúng ADR-004 — `user_id` từ JWT, trả danh sách trường được phép, không bao giờ có CCCD/ngày sinh.

## Kiểm chứng
`tests/test_rag_chat.py`: knowledge base không chứa CCCD/SĐT/tên CBNV; câu hỏi bị guard từ chối không bao giờ
tới mô hình; nội dung gửi lên mô hình không chứa dữ liệu cá nhân. `tests/test_rag_units.py`: bộ câu tấn công.
