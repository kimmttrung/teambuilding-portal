import { EVENT_HEADER, eventStore, tokenStore } from './client'

/**
 * Đọc Server-Sent Events từ một `Response` của fetch — dùng chung cho sơ đồ Gala và chatbot.
 *
 * Không dùng `EventSource`: nó chỉ làm được GET và không gửi được header Authorization, còn đặt token
 * vào URL thì token nằm lại trong log của nginx.
 */
export async function readSseStream(response, onEvent) {
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''

  const dispatch = (block) => {
    const message = parseSseBlock(block)
    if (message.event) onEvent(message)
  }

  for (;;) {
    const { value, done } = await reader.read()
    if (done) {
      if (buffer.trim()) dispatch(buffer)
      return
    }
    buffer += value.replaceAll('\r', '')
    let boundary = buffer.indexOf('\n\n')
    while (boundary >= 0) {
      dispatch(buffer.slice(0, boundary))
      buffer = buffer.slice(boundary + 2)
      boundary = buffer.indexOf('\n\n')
    }
  }
}

/** Một khối SSE -> `{ event, data }`. Dòng comment (`: ping`) và `retry:` cho `event: null`. */
export function parseSseBlock(block) {
  let event = 'message'
  const dataLines = []
  for (const line of block.split('\n')) {
    if (!line || line.startsWith(':')) continue
    const separator = line.indexOf(':')
    const field = separator < 0 ? line : line.slice(0, separator)
    const value = separator < 0 ? '' : line.slice(separator + 1).replace(/^ /, '')
    if (field === 'event') event = value
    else if (field === 'data') dataLines.push(value)
  }
  if (dataLines.length === 0) return { event: event === 'message' ? null : event, data: null }
  const text = dataLines.join('\n')
  try {
    return { event, data: JSON.parse(text) }
  } catch {
    return { event, data: text }
  }
}

/**
 * Header cho request fetch tự viết (không đi qua axios nên không có interceptor gắn token).
 *
 * Phải gắn cả `X-Event-Id`: luồng SSE của sơ đồ Gala và của chatbot đi bằng `fetch`, thiếu header
 * là hai thứ đó bám kỳ mặc định trong khi cả màn hình còn lại đã đổi sang kỳ khác.
 */
export function authHeaders(extra = {}) {
  const token = tokenStore.getAccess()
  const eventId = eventStore.get()
  return {
    ...extra,
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(eventId ? { [EVENT_HEADER]: eventId } : {}),
  }
}
