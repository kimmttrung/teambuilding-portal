import { api } from './client'

/** Toàn bộ thông báo của kỳ (cả nháp) — chỉ BTC. CBNV đọc bản lọc qua /journey/me. */
export async function fetchAnnouncements() {
  const { data } = await api.get('/admin/announcements')
  return data
}

/** Ai sẽ nhận nếu đăng với đối tượng này — cho màn hình soạn xem trước. */
export async function fetchRecipientPreview({ targetType, targetId }) {
  const { data } = await api.get('/admin/announcements/recipients', {
    params: { target_type: targetType, ...(targetId ? { target_id: targetId } : {}) },
  })
  return data
}

export async function createAnnouncement(payload) {
  const { data } = await api.post('/admin/announcements', payload)
  return data
}

export async function updateAnnouncement(itemId, payload) {
  const { data } = await api.patch(`/admin/announcements/${itemId}`, payload)
  return data
}

export async function deleteAnnouncement(itemId) {
  await api.delete(`/admin/announcements/${itemId}`)
}

/** Đăng: hiện trong My Journey + tuỳ chọn gửi email. Trả `{id, published_at, queued}`. */
export async function publishAnnouncement(itemId, { sendEmail = false } = {}) {
  const { data } = await api.post(`/admin/announcements/${itemId}/publish`, {
    send_email: sendEmail,
  })
  return data
}

/** Gỡ bản đã đăng về nháp — biến mất khỏi My Journey. */
export async function unpublishAnnouncement(itemId) {
  const { data } = await api.post(`/admin/announcements/${itemId}/unpublish`)
  return data
}
