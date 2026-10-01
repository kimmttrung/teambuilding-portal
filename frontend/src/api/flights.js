import { api } from './client'
import { notifyParams } from './notify'

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
  const { data } = await api.patch(`/flights/${flightId}`, payload, { params: notifyParams() })
  return data
}

export async function deleteFlight(flightId) {
  await api.delete(`/flights/${flightId}`, { params: notifyParams() })
}

export async function fetchPassengers(flightId) {
  const { data } = await api.get(`/flights/${flightId}/passengers`)
  return data
}

/**
 * Chạy phân bổ. `dry_run: true` chỉ trả preview và KHÔNG ghi gì —
 * giao diện luôn gọi dry-run trước, chỉ ghi khi BTC bấm "Áp dụng".
 */
export async function allocateFlights({
  direction,
  dryRun = true,
  forceReallocate = false,
  seed,
  priority,
  expectedAssignments,
}) {
  const { data } = await api.post(
    '/flights/allocate',
    {
      direction,
      dry_run: dryRun,
      force_reallocate: forceReallocate,
      ...(seed != null ? { seed } : {}),
      ...(priority ? { priority } : {}),
      ...(expectedAssignments ? { expected_assignments: expectedAssignments } : {}),
    },
    { params: notifyParams() },
  )
  return data
}

/** Bỏ toàn bộ phân bổ của một chiều — để sửa số ghế cho khớp vé thật rồi chạy lại. */
export async function resetFlightAllocation({ direction, reason, includeManual = false }) {
  const { data } = await api.post(
    '/flights/reset-allocation',
    { direction, reason, include_manual: includeManual },
    { params: notifyParams() },
  )
  return data
}

export async function fetchAssignments(params = {}) {
  const { data } = await api.get('/flight-assignments', { params })
  return data
}

export async function moveAssignment(assignmentId, { flightId, reason }) {
  const { data } = await api.patch(
    `/flight-assignments/${assignmentId}`,
    {
      flight_id: flightId,
      reason,
    },
    { params: notifyParams() },
  )
  return data
}

export async function bulkMoveAssignments({ registrationIds, flightId, reason }) {
  const { data } = await api.post(
    '/flight-assignments/bulk-move',
    {
      registration_ids: registrationIds,
      flight_id: flightId,
      reason,
    },
    { params: notifyParams() },
  )
  return data
}

export async function removeAssignment(assignmentId, reason) {
  await api.delete(`/flight-assignments/${assignmentId}`, { params: notifyParams({ reason }) })
}

/** Board phải đọc hết các trang, không bỏ người sau dòng 200. */
async function fetchAllPages(url, params, signal) {
  const items = []
  let page = 1
  let total = 0
  do {
    const { data } = await api.get(url, { params: { ...params, page, page_size: 200 }, signal })
    items.push(...data.items)
    total = data.total
    page += 1
    if (!data.items.length) break
  } while (items.length < total)
  return items
}

export async function fetchFlightBoard(direction, signal) {
  const [flightResponse, participants, assignments] = await Promise.all([
    api.get('/flights', { params: { direction }, signal }),
    fetchAllPages('/flight-assignments/participants', {}, signal),
    fetchAllPages('/flight-assignments', { direction }, signal),
  ])
  return { flights: flightResponse.data, participants, assignments }
}
