import { api } from './client'

export async function fetchMyRegistration() {
  try {
    const { data } = await api.get('/registrations/me')
    return data
  } catch (error) {
    // Chưa đăng ký là trạng thái bình thường, không phải lỗi cần báo đỏ.
    if (error.code === 'REGISTRATION_NOT_FOUND') return null
    throw error
  }
}

export async function submitRegistration(payload) {
  const { data } = await api.post('/registrations', payload)
  return data
}

export async function updateRegistration(payload) {
  const { data } = await api.patch('/registrations/me', payload)
  return data
}

/** Tự huỷ (trước khi công bố) — backend gỡ chỗ đã xếp và báo BTC. */
export async function cancelRegistration(reason) {
  const { data } = await api.post('/registrations/me/cancel', { reason })
  return data
}

/** Sau khi công bố: gửi yêu cầu huỷ, chờ BTC duyệt (docs/04 §4.3). */
export async function requestCancellation(reason) {
  const { data } = await api.post('/registrations/me/cancellation-request', { reason })
  return data
}

export async function withdrawCancellationRequest() {
  const { data } = await api.delete('/registrations/me/cancellation-request')
  return data
}

export async function fetchRegistrationStats() {
  const { data } = await api.get('/registrations/stats')
  return data
}

export async function fetchRegistrations(params = {}) {
  const { data } = await api.get('/registrations', { params })
  return data
}
