import { api } from './client'
import { notifyParams } from './notify'

export async function fetchActiveEvent() {
  const { data } = await api.get('/events/active')
  return data
}

/** Các kỳ người dùng được phép chọn. CBNV không thấy kỳ nháp; BTC thấy hết. */
export async function fetchSelectableEvents() {
  const { data } = await api.get('/events/selectable')
  return data
}

/** Mọi kỳ, kể cả nháp — chỉ BTC. Dùng cho trang quản lý kỳ. */
export async function fetchEvents() {
  const { data } = await api.get('/events')
  return data
}

/** BTC mở kỳ mới. Kỳ mới luôn ở trạng thái `draft` và KHÔNG tự thành kỳ mặc định. */
export async function createEvent(payload) {
  const { data } = await api.post('/events', payload)
  return data
}

export async function fetchTerms(eventId) {
  const { data } = await api.get(`/events/${eventId}/terms`)
  return data
}

/** Bản quy định đang dùng (`is_current`) và các bản đã bị thay, kèm số người đã đồng ý (BTC). */
export async function fetchTermsVersions(eventId) {
  const { data } = await api.get(`/events/${eventId}/terms/versions`)
  return data
}

/** Chọn lại một bản quy định cũ làm bản đang dùng (đúng nguyên văn đã lưu). */
export async function chooseTermsVersion(eventId, version) {
  const { data } = await api.post(
    `/events/${eventId}/terms/versions/${encodeURIComponent(version)}/use`,
    null,
    { params: notifyParams() },
  )
  return data
}

export async function changeEventStatus(eventId, { status, reason, notify = false }) {
  const { data } = await api.post(`/events/${eventId}/status`, { status, reason, notify })
  return data
}

export async function updateEvent(eventId, payload) {
  const { data } = await api.patch(`/events/${eventId}`, payload, { params: notifyParams() })
  return data
}

/** Đặt kỳ này làm kỳ mặc định — thứ người chưa chọn gì sẽ thấy. Backend tự tắt kỳ cũ. */
export async function activateEvent(eventId) {
  const { data } = await api.post(`/events/${eventId}/activate`)
  return data
}

/** Xoá một kỳ. Kỳ mặc định bị xoá thì kỳ tạo sau cùng được đặt làm mặc định. */
export async function deleteEvent(eventId) {
  await api.delete(`/events/${eventId}`)
}

export async function fetchEventSettings(eventId) {
  const { data } = await api.get(`/events/${eventId}/settings`)
  return data
}

/** Những thứ đã xếp không còn khớp cấu hình kỳ (ngày kỳ, giờ ca, số phút đệm xe). */
export async function fetchConfigImpact(eventId) {
  const { data } = await api.get(`/events/${eventId}/config-impact`)
  return data
}

export async function saveEventSettings(eventId, values) {
  const { data } = await api.put(`/events/${eventId}/settings`, { values })
  return data
}
