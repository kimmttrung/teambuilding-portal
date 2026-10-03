import assert from 'node:assert/strict'
import axios from 'axios'
import { renderToString } from 'react-dom/server'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import ProtectedRoute from '../src/routes/ProtectedRoute'
import { missingProfileFields, selfProfileSchema } from '../src/utils/schemas'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { api, tokenStore, setSessionExpiredHandler } from '../src/api/client'
import { changePassword } from '../src/api/auth'
import ProfilePage from '../src/pages/user/ProfilePage'
import { ImportResult } from '../src/pages/admin/users/UserImportModal'
import { ToastProvider } from '../src/context/ToastContext'
import { FAKE_USER } from './stub-auth'

const result = { total_rows: 3, valid_rows: 3, error_count: 0, to_create: 0, to_update: 0, unchanged: 3, errors: [] }
for (const [label, data, expected] of [
  ['Import CBNV — kiểm tra unchanged', result, 'Giữ nguyên'],
  ['Import CBNV — kết quả unchanged', { ...result, committed: true }, 'Đã import:'],
  ['Import CBNV — lỗi xung đột', { ...result, error_count: 1, errors: [{ row: 2, code: 'EMAIL_TAKEN', message: 'Email đã được sử dụng.' }] }, 'Email đã được sử dụng.'],
]) {
  assert.ok(renderToString(<ImportResult result={data} />).includes(expected))
  console.log(`${label}: OK`)
}

const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
const page = (element, entry = '/profile') => renderToString(
  <QueryClientProvider client={qc}><MemoryRouter initialEntries={[entry]}><ToastProvider>{element}</ToastProvider></MemoryRouter></QueryClientProvider>,
)
try {
  // Tài khoản dùng mật khẩu BTC cấp: route nào cũng chỉ ra trang đổi mật khẩu, không có nút Huỷ, không có menu.
  globalThis.__SSR_AUTH_USER__ = { ...FAKE_USER, must_change_password: true }
  const forced = page(
    <Routes><Route element={<ProtectedRoute />}><Route path="*" element={<p>NỘI DUNG ĐƯỢC BẢO VỆ</p>} /></Route></Routes>,
    '/my-journey',
  )
  assert.ok(forced.includes('Đổi mật khẩu để tiếp tục'))
  assert.ok(forced.includes('name="current_password"') && forced.includes('name="new_password"'))
  assert.ok(!forced.includes('NỘI DUNG ĐƯỢC BẢO VỆ'))
  assert.ok(!forced.includes('>Huỷ</button>'))
  console.log('Bắt đổi mật khẩu lần đầu — chặn mọi route, không có đường lui: OK')

  // FAKE_USER thiếu CCCD và ngày cấp: banner nêu đúng trường thiếu, nút lưu bấm được để ô thiếu báo đỏ.
  globalThis.__SSR_AUTH_USER__ = FAKE_USER
  const incomplete = page(<ProfilePage />)
  assert.ok(incomplete.includes('Còn thiếu') && incomplete.includes('Số CCCD/Hộ chiếu, Ngày cấp'))
  assert.ok(incomplete.includes('Lưu hồ sơ') && incomplete.includes('Bảo mật'))
  assert.ok(!incomplete.includes('name="current_password"'))
  console.log('Hồ sơ — thiếu trường bắt buộc thì báo rõ, form mật khẩu đóng sẵn: OK')

  globalThis.__SSR_AUTH_USER__ = { ...FAKE_USER, id_card_type: 'cccd', id_card_number: '001095012345', id_card_issue_date: '2021-05-20' }
  assert.ok(!page(<ProfilePage />).includes('Còn thiếu'))
  console.log('Hồ sơ — đủ 6 trường bắt buộc thì không còn cảnh báo: OK')

  assert.deepEqual(missingProfileFields({ gender: 'male', date_of_birth: '1990-01-01', phone: ' ', id_card_type: 'cccd' }), ['Số điện thoại', 'Số CCCD/Hộ chiếu', 'Ngày cấp'])
  assert.equal(selfProfileSchema.safeParse({ display_name: 'Chỉ có tên' }).success, false)
  console.log('Hồ sơ — schema từ chối khi chỉ điền tên: OK')
} finally {
  delete globalThis.__SSR_AUTH_USER__
  qc.clear()
}

// Kiểm thử interceptor thật, không gọi mạng: axios adapter là API sẵn có của thư viện.
const store = new Map()
const oldStorage = globalThis.localStorage
globalThis.localStorage = {
  getItem: (key) => store.get(key) ?? null,
  setItem: (key, value) => store.set(key, value),
  removeItem: (key) => store.delete(key),
}
const oldApiAdapter = api.defaults.adapter
const oldAxiosAdapter = axios.defaults.adapter
const ok = (config, data) => ({ config, data, status: 200, statusText: 'OK', headers: {} })
const unauthorized = (config, code) => Promise.reject({ config, response: { status: 401, data: { error: { code, message: 'Không hợp lệ.', details: {} } } } })
try {
  tokenStore.save({ access_token: 'expired', refresh_token: 'refresh-old' })
  let refreshCalls = 0
  axios.defaults.adapter = async (config) => {
    refreshCalls++
    await new Promise((resolve) => setTimeout(resolve, 5))
    return ok(config, { access_token: 'access-new', refresh_token: 'refresh-new' })
  }
  api.defaults.adapter = async (config) => config._retried
    ? ok(config, { id: 1 }) : unauthorized(config, 'TOKEN_EXPIRED')
  await Promise.all([api.get('/auth/me'), api.get('/auth/me')])
  assert.equal(refreshCalls, 1)
  assert.equal(tokenStore.getRefresh(), 'refresh-new')
  console.log('Auth — /me hết hạn và request đồng thời chỉ refresh một lần: OK')

  api.defaults.adapter = async (config) => {
    if (config._retried) return ok(config, new Blob(['xlsx']))
    return Promise.reject({ config, response: { status: 401,
      data: new Blob([JSON.stringify({ error: { code: 'TOKEN_EXPIRED', message: 'Hết hạn.' } })], { type: 'application/json' }),
    } })
  }
  await api.get('/admin/users/export', { responseType: 'blob' })
  assert.equal(refreshCalls, 2)
  console.log('Auth — xuất Excel với lỗi Blob 401 cũng refresh được: OK')

  api.defaults.adapter = async (config) => unauthorized(config, 'INVALID_CREDENTIALS')
  await assert.rejects(api.post('/auth/login', {}), { code: 'INVALID_CREDENTIALS' })
  await assert.rejects(api.post('/auth/change-password', {}), { code: 'INVALID_CREDENTIALS' })
  assert.equal(refreshCalls, 2)
  console.log('Auth — sai mật khẩu không tự refresh: OK')

  api.defaults.adapter = async (config) => ok(config, { access_token: 'changed-access', refresh_token: 'changed-refresh', user: { ...FAKE_USER, must_change_password: false } })
  await changePassword('OldPass123', 'NewPass456')
  assert.equal(tokenStore.getRefresh(), 'changed-refresh')
  console.log('Auth — đổi mật khẩu lưu cặp token mới: OK')

  let expired = false
  setSessionExpiredHandler(() => { expired = true })
  api.defaults.adapter = async (config) => unauthorized(config, 'TOKEN_EXPIRED')
  axios.defaults.adapter = async (config) => unauthorized(config, 'SESSION_REVOKED')
  await assert.rejects(api.get('/auth/me'), { code: 'TOKEN_EXPIRED' })
  assert.equal(tokenStore.getRefresh(), null)
  assert.equal(expired, true)
  console.log('Auth — refresh bị thu hồi xoá phiên khi khôi phục /me: OK')
} finally {
  api.defaults.adapter = oldApiAdapter
  axios.defaults.adapter = oldAxiosAdapter
  setSessionExpiredHandler(() => {})
  globalThis.localStorage = oldStorage
}