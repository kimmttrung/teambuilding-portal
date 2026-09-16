import { api } from './client'

/** Toàn bộ số liệu dashboard BTC trong một request (docs/04 §10). */
export async function fetchDashboard() {
  const { data } = await api.get('/admin/dashboard')
  return data
}

/** Chỉ định Trưởng nhóm — người được chọn phải thuộc team và đang xác nhận tham gia kỳ. */
export async function assignTeamLeader(teamId, userId) {
  const { data } = await api.put(`/admin/teams/${teamId}/leader`, { user_id: userId })
  return data
}

export async function fetchAuditLogs(params = {}) {
  const { data } = await api.get('/admin/audit-logs', { params })
  return data
}
