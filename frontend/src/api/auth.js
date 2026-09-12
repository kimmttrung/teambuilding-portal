import { api, tokenStore } from './client'

export async function login(email, password) {
  const { data } = await api.post('/auth/login', { email, password })
  tokenStore.save(data)
  return data.user
}

export async function logout() {
  const refreshToken = tokenStore.getRefresh()
  try {
    await api.post('/auth/logout', { refresh_token: refreshToken, all_devices: false })
  } finally {
    // Xoá token phía client kể cả khi gọi API thất bại — người dùng bấm đăng xuất
    // thì phải đăng xuất được, dù mạng có vấn đề.
    tokenStore.clear()
  }
}

export async function fetchMe() {
  const { data } = await api.get('/auth/me')
  return data
}

export async function updateProfile(patch) {
  const { data } = await api.patch('/auth/me', patch)
  return data
}

export async function changePassword(currentPassword, newPassword) {
  const { data } = await api.post('/auth/change-password', {
    current_password: currentPassword,
    new_password: newPassword,
  })
  return data
}

export async function uploadAvatar(file) {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post('/auth/me/avatar', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}
