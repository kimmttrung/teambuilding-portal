import { api } from './client'

/** Huỷ đăng ký — phía BTC (docs/04-api-spec.md §4.3). */
export async function fetchCancellations(params = {}) {
  const { data } = await api.get('/admin/cancellations', { params })
  return data
}

export async function approveCancellation(id, payload) {
  const { data } = await api.post(`/admin/cancellations/${id}/approve`, payload)
  return data
}

export async function rejectCancellation(id, decisionNote) {
  const { data } = await api.post(`/admin/cancellations/${id}/reject`, { decision_note: decisionNote })
  return data
}

/** BTC huỷ thay CBNV — trường hợp ngoại lệ, kể cả khi chương trình đã bắt đầu. */
export async function cancelOnBehalf(payload) {
  const { data } = await api.post('/admin/cancellations', payload)
  return data
}
