import { api } from './client'

/** Danh sách CBNV có lọc + phân trang. Không có CCCD/ngày sinh — xem chi tiết mới có. */
export async function fetchUsers(params = {}) {
  const { data } = await api.get('/admin/users', { params })
  return data
}

export async function fetchUser(userId) {
  const { data } = await api.get(`/admin/users/${userId}`)
  return data
}

/** Tạo tài khoản. Trả `{ user, temporary_password }` — mật khẩu tạm chỉ có ở response này. */
export async function createUser(payload) {
  const { data } = await api.post('/admin/users', payload)
  return data
}

export async function updateUser(userId, payload) {
  const { data } = await api.patch(`/admin/users/${userId}`, payload)
  return data
}

export async function changeUserRole(userId, { role, reason }) {
  const { data } = await api.patch(`/admin/users/${userId}/role`, { role, reason: reason || null })
  return data
}

export async function setUserStatus(userId, { isActive, reason }) {
  const { data } = await api.patch(`/admin/users/${userId}/status`, { is_active: isActive, reason })
  return data
}

/** Trả `{ temporary_password, sessions_revoked }`. */
export async function resetUserPassword(userId) {
  const { data } = await api.post(`/admin/users/${userId}/reset-password`)
  return data
}

/**
 * Import danh sách CBNV từ Excel. `dryRun` chỉ kiểm tra. Lần ghi thật trả `created_accounts`
 * kèm mật khẩu tạm — chỉ có ở response này.
 */
export async function importUsers(file, { dryRun = true } = {}) {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post('/admin/users/import', form, {
    params: { dry_run: dryRun },
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function unlockUser(userId) {
  const { data } = await api.post(`/admin/users/${userId}/unlock`)
  return data
}
