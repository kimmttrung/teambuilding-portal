import { api } from './client'

export async function fetchActiveEvent() {
  const { data } = await api.get('/events/active')
  return data
}

export async function fetchTerms(eventId) {
  const { data } = await api.get(`/events/${eventId}/terms`)
  return data
}

export async function fetchEventOverview(eventId) {
  const { data } = await api.get(`/events/${eventId}/overview`)
  return data
}

export async function changeEventStatus(eventId, status, reason) {
  const { data } = await api.post(`/events/${eventId}/status`, { status, reason })
  return data
}
