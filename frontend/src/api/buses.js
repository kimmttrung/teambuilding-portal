import { api } from './client'

/** Xe kèm số liệu chỗ (assigned_count, remaining_seats, load_ratio). */
export async function fetchBuses(params = {}) {
  const { data } = await api.get('/buses', { params })
  return data
}

export async function createBus(payload) {
  const { data } = await api.post('/buses', payload)
  return data
}

export async function updateBus(busId, payload) {
  const { data } = await api.patch(`/buses/${busId}`, payload)
  return data
}

export async function deleteBus(busId) {
  await api.delete(`/buses/${busId}`)
}

/** `payload`: `{ leader_user_id }` | `{ leader_name, leader_phone }` | `{}` (bỏ Trưởng xe). */
export async function setBusLeader(busId, payload) {
  const { data } = await api.patch(`/buses/${busId}/leader`, payload)
  return data
}

/** Phân xe một chặng. Giao diện luôn gọi dry-run trước, chỉ ghi khi BTC bấm "Áp dụng". */
export async function allocateBuses({ tripLegId, dryRun = true, forceReallocate = false, expectedAssignments }) {
  const { data } = await api.post('/buses/allocate', {
    trip_leg_id: tripLegId,
    dry_run: dryRun,
    force_reallocate: forceReallocate,
    ...(expectedAssignments ? { expected_assignments: expectedAssignments } : {}),
  })
  return data
}

/**
 * Hành khách một xe: tên, SĐT, điểm đón, team.
 *
 * Endpoint hành khách mà **Trưởng xe** gọi được (backend chỉ cho BTC và Trưởng xe của
 * chính xe đó). `/buses/led` cung cấp các xe được chỉ định cho người gọi.
 */
export async function fetchBusPassengers(busId) {
  const { data } = await api.get(`/buses/${busId}/passengers`)
  return data
}

export async function fetchBusAssignments(params = {}) {
  const { data } = await api.get('/bus-assignments', { params })
  return data
}

/** Xếp tay một người chưa có xe ở chặng của xe này. */
export async function assignRider({ registrationId, busId, reason }) {
  const { data } = await api.post('/bus-assignments', {
    registration_id: registrationId,
    bus_id: busId,
    reason,
  })
  return data
}

export async function moveBusAssignment(assignmentId, { busId, reason }) {
  const { data } = await api.patch(`/bus-assignments/${assignmentId}`, { bus_id: busId, reason })
  return data
}

export async function removeBusAssignment(assignmentId, reason) {
  await api.delete(`/bus-assignments/${assignmentId}`, { params: { reason } })
}

/** Người cần xe chưa được xếp, phân trang trên server theo schema v2. */
export async function fetchUnassignedBusRiders(params) {
  const { data } = await api.get('/bus-assignments/unassigned', { params })
  return data
}

/** Trưởng xe chỉ đọc các xe mình phụ trách, sau công bố. */
export async function fetchLedBuses() {
  const { data } = await api.get('/buses/led')
  return data
}
