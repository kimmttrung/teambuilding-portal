import { api } from './client'
import { saveBlob } from '../utils/files'

/**
 * Tải file từ API có kèm token rồi lưu xuống máy. Trả tên file đã lưu.
 *
 * Không mở thẳng URL bằng `<a href>`: endpoint export cần header Authorization, và link trần sẽ
 * để token (nếu gắn vào query) nằm lại trong lịch sử trình duyệt.
 */
export async function downloadFile(url, { params, fallbackName = 'export.xlsx' } = {}) {
  const response = await api.get(url, { params, responseType: 'blob' })
  const filename = filenameFromDisposition(response.headers?.['content-disposition']) || fallbackName
  saveBlob(response.data, filename)
  return filename
}

/** `attachment; filename="a.xlsx"; filename*=UTF-8''a.xlsx` -> `a.xlsx`. */
export function filenameFromDisposition(header) {
  if (!header) return null
  const encoded = /filename\*=UTF-8''([^;]+)/i.exec(header)
  if (encoded) {
    try {
      return decodeURIComponent(encoded[1])
    } catch {
      // Mã hoá hỏng: dùng filename thường bên dưới.
    }
  }
  const plain = /filename="?([^";]+)"?/i.exec(header)
  return plain ? plain[1] : null
}
