import { api } from './client'
import { notifyParams } from './notify'

/** Khách sạn kèm room_count, bed_count, assigned_count. */
export async function fetchHotels() {
  const { data } = await api.get('/hotels')
  return data
}

export async function createHotel(payload) {
  const { data } = await api.post('/hotels', payload)
  return data
}

export async function updateHotel(hotelId, payload) {
  const { data } = await api.patch(`/hotels/${hotelId}`, payload, { params: notifyParams() })
  return data
}

export async function deleteHotel(hotelId) {
  await api.delete(`/hotels/${hotelId}`, { params: notifyParams() })
}

/** Phòng kèm occupied, remaining, has_captain. */
export async function fetchRooms(params = {}) {
  const { data } = await api.get('/rooms', { params })
  return data
}

/** Giường theo giới tính so với người tham gia, kèm `uncovered`. */
export async function fetchRoomSummary() {
  const { data } = await api.get('/rooms/summary')
  return data
}

export async function createRoom(payload) {
  const { data } = await api.post('/rooms', payload)
  return data
}

export async function updateRoom(roomId, payload) {
  const { data } = await api.patch(`/rooms/${roomId}`, payload, { params: notifyParams() })
  return data
}

export async function deleteRoom(roomId) {
  await api.delete(`/rooms/${roomId}`, { params: notifyParams() })
}

export async function fetchOccupants(roomId) {
  const { data } = await api.get(`/rooms/${roomId}/occupants`)
  return data
}

export async function fetchRoomAssignments(params = {}) {
  const { data } = await api.get('/room-assignments', { params })
  return data
}

/**
 * Xếp một người vào phòng. Cùng endpoint cho cả chuyển phòng (`replaceExisting`) và đặt
 * trưởng phòng (xếp lại vào chính phòng đó với `isRoomCaptain`).
 */
export async function assignRoom({
  registrationId,
  roomId,
  isRoomCaptain = false,
  replaceExisting = false,
  reason,
}) {
  const { data } = await api.post('/room-assignments', {
    registration_id: registrationId,
    room_id: roomId,
    is_room_captain: isRoomCaptain,
    replace_existing: replaceExisting,
    reason: reason || null,
  }, { params: notifyParams() })
  return data
}

export async function removeRoomAssignment(assignmentId, reason) {
  await api.delete(`/room-assignments/${assignmentId}`, { params: notifyParams({ reason }) })
}

/**
 * Xếp phòng tự động. `dryRun: true` chỉ trả bản xem trước, KHÔNG ghi gì — giao diện luôn gọi
 * dry-run trước, chỉ ghi khi BTC bấm "Áp dụng".
 */
export async function allocateRooms({ dryRun = true, forceReallocate = false } = {}) {
  const { data } = await api.post('/rooms/allocate', {
    dry_run: dryRun,
    force_reallocate: forceReallocate,
  }, { params: notifyParams() })
  return data
}

/** Import phân phòng từ .xlsx. `dryRun` chỉ kiểm tra; còn lỗi thì ghi thật cũng không ghi dòng nào. */
export async function importRooms(file, { dryRun = true, replaceExisting = false } = {}) {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post('/rooms/import', form, {
    params: notifyParams({ dry_run: dryRun, replace_existing: replaceExisting }),
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}
