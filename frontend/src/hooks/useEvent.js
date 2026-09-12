import { useQuery } from '@tanstack/react-query'
import { fetchActiveEvent, fetchEventOverview } from '../api/events'
import { fetchMyRegistration, fetchRegistrationStats } from '../api/registrations'
import { QUERY_KEYS } from '../utils/constants'

export function useActiveEvent() {
  return useQuery({
    queryKey: QUERY_KEYS.activeEvent,
    queryFn: fetchActiveEvent,
    // Kỳ Team Building hiếm khi đổi trong một phiên làm việc.
    staleTime: 5 * 60 * 1000,
    retry: (failureCount, error) => error.code !== 'NO_ACTIVE_EVENT' && failureCount < 2,
  })
}

export function useMyRegistration() {
  return useQuery({
    queryKey: QUERY_KEYS.myRegistration,
    queryFn: fetchMyRegistration,
  })
}

export function useRegistrationStats() {
  return useQuery({
    queryKey: QUERY_KEYS.registrationStats,
    queryFn: fetchRegistrationStats,
  })
}

export function useEventOverview(eventId) {
  return useQuery({
    queryKey: QUERY_KEYS.eventOverview(eventId),
    queryFn: () => fetchEventOverview(eventId),
    enabled: Boolean(eventId),
  })
}
