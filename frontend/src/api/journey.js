import { api } from './client'

/** Toàn bộ hành trình của người đang đăng nhập trong một request (docs/04 §9). */
export async function fetchMyJourney() {
  const { data } = await api.get('/journey/me')
  return data
}

/** BTC tra cứu hộ hành trình của một CBNV. */
export async function fetchJourneyOf(userId) {
  const { data } = await api.get(`/journey/${userId}`)
  return data
}
