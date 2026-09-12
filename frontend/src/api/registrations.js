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

export async function cancelRegistration(reason) {
  const { data } = await api.post('/registrations/me/cancel', { reason })
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
