import { api } from './client'

export async function fetchEmailLogs(params = {}) {
  const { data } = await api.get('/admin/email-logs', { params })
  return data
}

export async function fetchEmailStats() {
  const { data } = await api.get('/admin/email-logs/stats')
  return data
}

/** `ids = null`: gửi lại mọi thư đang lỗi. */
export async function resendEmails(ids = null) {
  const { data } = await api.post('/admin/email-logs/resend', { ids })
  return data
}
