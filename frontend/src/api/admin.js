import { api } from './client'

/** Toàn bộ số liệu dashboard BTC trong một request (docs/04 §10). */
export async function fetchDashboard() {
  const { data } = await api.get('/admin/dashboard')
  return data
}

export async function fetchAuditLogs(params = {}) {
  const { data } = await api.get('/admin/audit-logs', { params })
  return data
}
