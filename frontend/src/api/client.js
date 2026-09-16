import axios from 'axios'

const ACCESS_TOKEN_KEY = 'tb_access_token'
const REFRESH_TOKEN_KEY = 'tb_refresh_token'
const EVENT_ID_KEY = 'tb_event_id'

/**
 * Kỳ Team Building người dùng đang xem (docs/13 task 6).
 *
 * Gửi lên bằng header `X-Event-Id`. Bỏ trống = để backend lấy kỳ mặc định, nên lần đầu vào máy mới
 * vẫn chạy đúng mà không cần chọn gì.
 */
export const eventStore = {
  get: () => localStorage.getItem(EVENT_ID_KEY) || null,
  set(eventId) {
    if (eventId === null || eventId === undefined || eventId === '') {
      localStorage.removeItem(EVENT_ID_KEY)
    } else {
      localStorage.setItem(EVENT_ID_KEY, String(eventId))
    }
  },
  clear: () => localStorage.removeItem(EVENT_ID_KEY),
}

export const EVENT_HEADER = 'X-Event-Id'

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
    // Kỳ đã chọn thuộc về phiên đó: giữ lại thì người đăng nhập sau trên cùng máy thừa hưởng
    // lựa chọn của người trước, và có thể là kỳ họ không được phép xem.
    localStorage.removeItem(EVENT_ID_KEY)
  },
}

export const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = tokenStore.getAccess()
  if (token) config.headers.Authorization = `Bearer ${token}`
  // Gắn ở đây, không ở từng hàm api/*.js: backend quyết định kỳ tại MỘT dependency, frontend cũng
  // phải gửi ở MỘT chỗ — sót một request là màn hình đó lặng lẽ hiện dữ liệu của kỳ khác.
  const eventId = eventStore.get()
  if (eventId) config.headers[EVENT_HEADER] = eventId
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

    // Request tải file (`responseType: 'blob'`) nhận lỗi JSON dưới dạng Blob — đọc ra trước,
    // nếu không toast chỉ hiện "Máy chủ gặp sự cố" thay vì lý do thật.
    if (response?.data instanceof Blob) {
      response.data = await readBlobJson(response.data)
    }

    return Promise.reject(normalizeError(error))
  },
)

async function readBlobJson(blob) {
  try {
    return JSON.parse(await blob.text())
  } catch {
    return null
  }
}

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
