import assert from 'node:assert/strict'
import axios from 'axios'
import { renderToString } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
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

globalThis.__SSR_AUTH_USER__ = { ...FAKE_USER, must_change_password: true }
const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
try {
  const html = renderToString(
    <QueryClientProvider client={qc}><MemoryRouter><ToastProvider><ProfilePage /></ToastProvider></MemoryRouter></QueryClientProvider>,
  )
  assert.ok(html.includes('name="current_password"'))
  assert.ok(html.includes('name="new_password"'))
  assert.ok(!html.includes('>Huỷ</button>'))
  console.log('Hồ sơ — mở sẵn form bắt đổi mật khẩu: OK')
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