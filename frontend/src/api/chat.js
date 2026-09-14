import { api } from './client'
import { fetchMe } from './auth'
import { authHeaders, readSseStream } from './sse'

/** `{ enabled, llm_configured, indexed_chunks, model }` — trợ lý đã sẵn sàng tới đâu. */
export async function fetchChatStatus() {
  const { data } = await api.get('/chat/status')
  return data
}

/** Các cuộc trò chuyện của CHÍNH người đang đăng nhập, mới nhất trước. */
export async function fetchChatSessions() {
  const { data } = await api.get('/chat/sessions')
  return data
}

export async function fetchChatMessages(sessionId) {
  const { data } = await api.get(`/chat/sessions/${sessionId}/messages`)
  return data
}

export async function deleteChatSession(sessionId) {
  await api.delete(`/chat/sessions/${sessionId}`)
}

/** BTC: knowledge base đã nạp tới đâu, lần nạp gần nhất, AI đã bật chưa. */
export async function fetchRagStatus() {
  const { data } = await api.get('/admin/rag/status')
  return data
}

/** BTC: nạp lại knowledge base của kỳ đang chạy. Trả `{documents, chunks, by_source, published_logistics}`. */
export async function reindexRag() {
  const { data } = await api.post('/admin/rag/reindex')
  return data
}

/**
 * Gửi câu hỏi và nhận câu trả lời dạng luồng (SSE qua `POST /chat`).
 *
 * `onEvent({ event, data })` nhận lần lượt:
 *   session `{session_id, title}` · sources `[{index, title, source_type}]` · delta `{text}`
 *   · done `{message_id, latency_ms, refused}` · error `{code, message}`.
 * Lỗi xảy ra TRƯỚC khi luồng bắt đầu (429 hết lượt hỏi, 404 chưa có kỳ...) được ném ra như lỗi
 * đã chuẩn hoá của axios: `{ message, code, status, details }`.
 */
export async function streamChat({ sessionId, message, signal, onEvent }, { retried = false } = {}) {
  const response = await fetch(`${api.defaults.baseURL}/chat`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json', Accept: 'text/event-stream' }),
    body: JSON.stringify({ session_id: sessionId ?? null, message }),
    signal,
  })

  // Access token hết hạn: gọi một API thường để interceptor của axios refresh token, rồi gửi lại.
  if (response.status === 401 && !retried) {
    await fetchMe()
    return streamChat({ sessionId, message, signal, onEvent }, { retried: true })
  }
  if (!response.ok || !response.body) throw await toError(response)

  await readSseStream(response, onEvent)
}

async function toError(response) {
  let payload = null
  try {
    payload = (await response.json())?.error ?? null
  } catch {
    // Body không phải JSON (proxy trả trang lỗi): dùng thông điệp chung bên dưới.
  }
  const error = new Error(
    payload?.message ||
      (response.status >= 500 ? 'Trợ lý đang gặp sự cố. Thử lại sau ít phút.' : 'Không gửi được câu hỏi.'),
  )
  error.code = payload?.code || 'CHAT_FAILED'
  error.status = response.status
  error.details = payload?.details || {}
  return error
}
