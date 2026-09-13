import { api } from './client'

/** Chuyến bay kèm số liệu slot (assigned_count, remaining_slots, load_ratio). */
export async function fetchFlights(params = {}) {
  const { data } = await api.get('/flights', { params })
  return data
}

/** Tổng quan slot theo chiều và theo ca, kèm `shortfall`. */
export async function fetchFlightSummary() {
  const { data } = await api.get('/flights/summary')
  return data
}

export async function createFlight(payload) {
  const { data } = await api.post('/flights', payload)
  return data
}

export async function updateFlight(flightId, payload) {
  const { data } = await api.patch(`/flights/${flightId}`, payload)
  return data
}

export async function deleteFlight(flightId) {
  await api.delete(`/flights/${flightId}`)
}

export async function fetchPassengers(flightId) {
  const { data } = await api.get(`/flights/${flightId}/passengers`)
  return data
}

/**
 * Chạy phân bổ. `dry_run: true` chỉ trả preview và KHÔNG ghi gì —
 * giao diện luôn gọi dry-run trước, chỉ ghi khi BTC bấm "Áp dụng".
 */
export async function allocateFlights({ direction, dryRun = true, forceReallocate = false, seed }) {
  const { data } = await api.post('/flights/allocate', {
    direction,
    dry_run: dryRun,
    force_reallocate: forceReallocate,
    ...(seed != null ? { seed } : {}),
  })
  return data
}

export async function fetchAssignments(params = {}) {
  const { data } = await api.get('/flight-assignments', { params })
  return data
}

export async function moveAssignment(assignmentId, { flightId, reason }) {
  const { data } = await api.patch(`/flight-assignments/${assignmentId}`, {
    flight_id: flightId,
    reason,
  })
  return data
}

export async function bulkMoveAssignments({ registrationIds, flightId, reason }) {
  const { data } = await api.post('/flight-assignments/bulk-move', {
    registration_ids: registrationIds,
    flight_id: flightId,
    reason,
  })
  return data
}

export async function removeAssignment(assignmentId, reason) {
  await api.delete(`/flight-assignments/${assignmentId}`, { params: { reason } })
}
