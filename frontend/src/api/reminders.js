import { api } from './client'

/** Ai sẽ nhận email nhắc, ai đã được nhắc gần đây. Không gửi gì. */
export async function fetchReminderPreview(kind) {
  const { data } = await api.get(`/admin/reminders/${kind}`)
  return data
}

/** `payload`: { user_ids, include_recently_reminded } */
export async function sendReminders(kind, payload) {
  const { data } = await api.post(`/admin/reminders/${kind}`, payload)
  return data
}
