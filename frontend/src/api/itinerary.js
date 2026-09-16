import { api } from './client'

/** Toàn bộ mốc lịch trình thô của kỳ (kể cả mốc riêng ca/team) — chỉ BTC. */
export async function fetchItinerary() {
  const { data } = await api.get('/itinerary')
  return data
}

export async function createItineraryItem(payload) {
  const { data } = await api.post('/itinerary', payload)
  return data
}

export async function updateItineraryItem(itemId, payload) {
  const { data } = await api.patch(`/itinerary/${itemId}`, payload)
  return data
}

export async function deleteItineraryItem(itemId) {
  await api.delete(`/itinerary/${itemId}`)
}

/** Xếp lại thứ tự các mốc trong một ngày — `orderedIds` là đủ mốc của ngày đó. */
export async function reorderItineraryDay({ dayDate, orderedIds }) {
  const { data } = await api.post('/itinerary/reorder', {
    day_date: dayDate,
    ordered_ids: orderedIds,
  })
  return data
}
