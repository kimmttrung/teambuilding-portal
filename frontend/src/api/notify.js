/**
 * Ô "Gửi email cho CBNV bị ảnh hưởng" ở đầu các trang quản trị (bay, xe, phòng, Gala, cấu hình kỳ).
 *
 * Một công tắc cho CẢ trang thay vì một ô trong từng hộp thoại: phần lớn thao tác ở đây là kéo-thả
 * hoặc bấm nhanh không có hộp xác nhận. Mặc định TẮT và tự tắt khi rời trang (`NotifyToggle`), nên
 * không có chuyện quên bật từ hôm trước rồi thử nghiệm là spam cả công ty.
 *
 * Các hàm trong `api/*.js` gọi `notifyParams()` để gắn `?notify=true` — backend chỉ gửi khi có cờ
 * này, và chỉ cho người có hành trình của CHÍNH MÌNH thay đổi.
 */
let enabled = false
const listeners = new Set()

export const notifyStore = {
  get: () => enabled,
  set(value) {
    enabled = Boolean(value)
    listeners.forEach((listener) => listener())
  },
  subscribe(listener) {
    listeners.add(listener)
    return () => listeners.delete(listener)
  },
}

/** Query params cho request ghi: thêm `notify: true` khi công tắc đang bật. */
export function notifyParams(extra) {
  return enabled ? { ...extra, notify: true } : extra
}
