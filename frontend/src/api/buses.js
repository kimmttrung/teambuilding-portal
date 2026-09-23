import { api } from './client'
import { notifyParams } from './notify'

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
  const { data } = await api.patch(`/buses/${busId}`, payload, { params: notifyParams() })
  return data
}

export async function deleteBus(busId) {
  await api.delete(`/buses/${busId}`, { params: notifyParams() })
}

/** `payload`: `{ leader_user_id }` | `{ leader_name, leader_phone }` | `{}` (bỏ Trưởng xe). */
export async function setBusLeader(busId, payload) {
  const { data } = await api.patch(`/buses/${busId}/leader`, payload, { params: notifyParams() })
  return data
}

/** Phân xe một chặng. Giao diện luôn gọi dry-run trước, chỉ ghi khi BTC bấm "Áp dụng". */
export async function allocateBuses({ tripLegId, dryRun = true, forceReallocate = false }) {
  const { data } = await api.post('/buses/allocate', {
    trip_leg_id: tripLegId,
    dry_run: dryRun,
    force_reallocate: forceReallocate,
  }, { params: notifyParams() })
  return data
}

/**
 * Hành khách một xe: tên, SĐT, điểm đón, team.
 *
 * Endpoint duy nhất về xe mà **Trưởng xe** gọi được (backend chỉ cho BTC và Trưởng xe của
 * chính xe đó) — mọi hàm còn lại trong file này đều là màn hình BTC.
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
  }, { params: notifyParams() })
  return data
}

export async function moveBusAssignment(assignmentId, { busId, reason }) {
  const { data } = await api.patch(`/bus-assignments/${assignmentId}`, { bus_id: busId, reason }, { params: notifyParams() })
  return data
}

export async function removeBusAssignment(assignmentId, reason) {
  await api.delete(`/bus-assignments/${assignmentId}`, { params: notifyParams({ reason }) })
}
