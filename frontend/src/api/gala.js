import { api, tokenStore } from './client'

/** Sơ đồ + trạng thái từng ghế + thứ tự lượt + team của người xem, trong một response. */
export async function fetchGalaView() {
  const { data } = await api.get('/gala/layout')
  return data
}

/** Thành viên tham gia của team kèm ghế. Trưởng nhóm bỏ trống `teamId` (luôn là team mình). */
export async function fetchGalaTeamMembers(teamId) {
  const { data } = await api.get('/gala/team-members', { params: teamId ? { team_id: teamId } : {} })
  return data
}

// --- Trưởng nhóm ---

export async function holdGalaSeats(seatIds) {
  const { data } = await api.post('/gala/seats/hold', { seat_ids: seatIds })
  return data
}

/** Bỏ trống `seatIds` = nhả mọi ghế team đang giữ. */
export async function releaseGalaSeats(seatIds) {
  const { data } = await api.delete('/gala/seats/hold', {
    params: seatIds?.length ? { seat_ids: seatIds } : {},
    // FastAPI đọc `seat_ids=1&seat_ids=2`, không hiểu kiểu mặc định `seat_ids[]=1` của axios.
    paramsSerializer: { indexes: null },
  })
  return data
}

export async function confirmGalaSeats() {
  const { data } = await api.post('/gala/seats/confirm')
  return data
}

/** `registrationId = null` để bỏ gán người khỏi ghế. */
export async function assignGalaMember({ seatId, registrationId }) {
  const { data } = await api.post('/gala/seats/assign-member', {
    seat_id: seatId,
    registration_id: registrationId,
  })
  return data
}

// --- BTC: mọi thao tác trả về sơ đồ mới ---

export async function createGalaLayout(payload) {
  const { data } = await api.post('/gala/layout', payload)
  return data
}

export async function updateGalaLayout(payload) {
  const { data } = await api.patch('/gala/layout', payload)
  return data
}

export async function createGalaTable(payload) {
  const { data } = await api.post('/gala/tables', payload)
  return data
}

export async function updateGalaTable(tableId, payload) {
  const { data } = await api.patch(`/gala/tables/${tableId}`, payload)
  return data
}

export async function deleteGalaTable(tableId) {
  const { data } = await api.delete(`/gala/tables/${tableId}`)
  return data
}

export async function drawGalaOrder(seed) {
  const { data } = await api.post('/gala/draw', { seed: seed || null })
  return data
}

export async function nextGalaTurn({ skip = false } = {}) {
  const { data } = await api.post('/gala/turn/next', { skip })
  return data
}

export async function finalizeGala() {
  const { data } = await api.post('/gala/finalize')
  return data
}

/** `payload` chỉ chứa trường cần đổi (`team_id`, `registration_id`, `is_available`) + `reason`. */
export async function updateGalaSeat(seatId, payload) {
  const { data } = await api.patch(`/gala/seats/${seatId}`, payload)
  return data
}

/** Mở lại chọn ghế cho các team chưa đủ ghế (chỉ khi đã kết thúc). */
export async function reopenGala() {
  const { data } = await api.post('/gala/reopen')
  return data
}

/** Lượt của team mình — nhẹ, giao diện hỏi định kỳ để hiện banner nhắc Trưởng nhóm. */
export async function fetchGalaMyTurn() {
  const { data } = await api.get('/gala/my-turn')
  return data
}

/** Xếp ngẫu nhiên thành viên vào ghế team. `reshuffle` = xáo lại cả team. BTC truyền `teamId`. */
export async function autoAssignGalaMembers({ teamId = null, reshuffle = false } = {}) {
  const { data } = await api.post('/gala/seats/auto-assign', { team_id: teamId, reshuffle })
  return data
}

// --- Luồng SSE ---

/**
 * Đọc luồng `GET /gala/stream` tới khi server đóng hoặc `signal` huỷ.
 *
 * Không dùng `EventSource`: nó không gửi được header Authorization, còn đặt token vào URL thì
 * token nằm lại trong log của nginx. Luồng chỉ báo "sơ đồ vừa đổi" — dữ liệu lấy qua `/gala/layout`.
 */
export async function streamGalaChanges({ signal, onOpen, onChange }) {
  const token = tokenStore.getAccess()
  const response = await fetch(`${api.defaults.baseURL}/gala/stream`, {
    headers: { Accept: 'text/event-stream', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    cache: 'no-store',
    signal,
  })
  if (!response.ok || !response.body) {
    const error = new Error('Không kết nối được luồng cập nhật sơ đồ.')
    error.status = response.status
    throw error
  }

  onOpen?.()
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) return
    buffer += value.replaceAll('\r', '')
    let boundary = buffer.indexOf('\n\n')
    while (boundary >= 0) {
      const message = parseSseBlock(buffer.slice(0, boundary))
      buffer = buffer.slice(boundary + 2)
      if (message.event === 'change') onChange?.(message.data)
      boundary = buffer.indexOf('\n\n')
    }
  }
}

/** Một khối SSE -> `{ event, data }`. Dòng comment (`: ping`) và `retry:` bị bỏ qua. */
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
