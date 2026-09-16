import { api } from './client'

export async function fetchActiveEvent() {
  const { data } = await api.get('/events/active')
  return data
}

/** Các kỳ người dùng được phép chọn. CBNV không thấy kỳ nháp; BTC thấy hết. */
export async function fetchSelectableEvents() {
  const { data } = await api.get('/events/selectable')
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

export async function fetchEventOverview(eventId) {
  const { data } = await api.get(`/events/${eventId}/overview`)
  return data
}

export async function changeEventStatus(eventId, status, reason) {
  const { data } = await api.post(`/events/${eventId}/status`, { status, reason })
  return data
}

export async function updateEvent(eventId, payload) {
  const { data } = await api.patch(`/events/${eventId}`, payload)
  return data
}

/** Đặt kỳ này làm kỳ mặc định — thứ người chưa chọn gì sẽ thấy. Backend tự tắt kỳ cũ. */
export async function activateEvent(eventId) {
  const { data } = await api.post(`/events/${eventId}/activate`)
  return data
}

export async function fetchEventSettings(eventId) {
  const { data } = await api.get(`/events/${eventId}/settings`)
  return data
}

export async function saveEventSettings(eventId, values) {
  const { data } = await api.put(`/events/${eventId}/settings`, { values })
  return data
}
