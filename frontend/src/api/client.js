import axios from 'axios'

const ACCESS_TOKEN_KEY = 'tb_access_token'
const REFRESH_TOKEN_KEY = 'tb_refresh_token'

export const tokenStore = {
  getAccess: () => localStorage.getItem(ACCESS_TOKEN_KEY),
  getRefresh: () => localStorage.getItem(REFRESH_TOKEN_KEY),
  save({ access_token, refresh_token }) {
    if (access_token) localStorage.setItem(ACCESS_TOKEN_KEY, access_token)
    // Backend xoay vòng refresh token mỗi lần gọi /auth/refresh: token cũ bị thu hồi
    // ngay. Không lưu đè token mới thì lần refresh sau chắc chắn thất bại.
    if (refresh_token) localStorage.setItem(REFRESH_TOKEN_KEY, refresh_token)
  },
  clear() {
    localStorage.removeItem(ACCESS_TOKEN_KEY)
    localStorage.removeItem(REFRESH_TOKEN_KEY)
  },
}

export const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = tokenStore.getAccess()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

/** Gọi khi phiên hết hạn hẳn — AuthContext đăng ký hàm này để đưa về trang đăng nhập. */
let onSessionExpired = () => {}
export function setSessionExpiredHandler(handler) {
  onSessionExpired = handler
}

// Nhiều request cùng nhận 401 một lúc thì chỉ gọi /auth/refresh MỘT lần,
// các request còn lại xếp hàng chờ kết quả. Nếu không, mỗi request sẽ tự refresh
// và token xoay vòng sẽ vô hiệu hoá lẫn nhau.
let refreshPromise = null

async function refreshAccessToken() {
  const refreshToken = tokenStore.getRefresh()
  if (!refreshToken) throw new Error('Không có refresh token')

  // Dùng axios gốc để request này không bị interceptor bắt lại thành vòng lặp.
  const { data } = await axios.post('/api/v1/auth/refresh', { refresh_token: refreshToken })
  tokenStore.save(data)
  return data.access_token
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const { response, config } = error
    const status = response?.status

    if (status === 401 && config && !config._retried && !config.url?.includes('/auth/')) {
      config._retried = true
      try {
        refreshPromise = refreshPromise || refreshAccessToken()
        const accessToken = await refreshPromise
        refreshPromise = null
        config.headers.Authorization = `Bearer ${accessToken}`
        return api(config)
      } catch {
        refreshPromise = null
        tokenStore.clear()
        onSessionExpired()
      }
    }

    return Promise.reject(normalizeError(error))
  },
)

/**
 * Quy về một hình dạng lỗi duy nhất để component không phải đào trong response.
 * Backend luôn trả {"error": {code, message, details}} (docs/04-api-spec.md §1).
 */
export function normalizeError(error) {
  const payload = error.response?.data?.error
  if (payload) {
    const normalized = new Error(payload.message || 'Đã có lỗi xảy ra.')
    normalized.code = payload.code
    normalized.details = payload.details || {}
    normalized.status = error.response.status
    return normalized
  }

  const fallback = new Error(
    error.response
      ? 'Máy chủ gặp sự cố. Vui lòng thử lại sau.'
      : 'Không kết nối được máy chủ. Kiểm tra lại mạng và thử lại.',
  )
  fallback.code = error.response ? 'SERVER_ERROR' : 'NETWORK_ERROR'
  fallback.status = error.response?.status ?? 0
  fallback.details = {}
  return fallback
}
