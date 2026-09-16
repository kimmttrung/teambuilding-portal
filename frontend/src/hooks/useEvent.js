import { useCallback } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { eventStore } from '../api/client'
import { fetchActiveEvent, fetchEventOverview, fetchSelectableEvents } from '../api/events'
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

export function useSelectableEvents({ enabled = true } = {}) {
  return useQuery({
    queryKey: QUERY_KEYS.selectableEvents,
    queryFn: fetchSelectableEvents,
    staleTime: 5 * 60 * 1000,
    enabled,
  })
}

/**
 * Đổi kỳ đang xem (docs/13 task 6).
 *
 * Phải `queryClient.clear()` chứ không `invalidateQueries`: mọi khoá cache đang giữ dữ liệu của kỳ
 * cũ mà khoá lại không mang `event_id`, nên chỉ đánh dấu cũ thôi là màn hình vẫn vẽ dữ liệu kỳ cũ
 * cho tới khi request mới về — đủ lâu để BTC bấm nhầm vào dữ liệu của kỳ khác.
 */
export function useSelectEvent() {
  const queryClient = useQueryClient()
  return useCallback(
    (eventId) => {
      if (String(eventStore.get() ?? '') === String(eventId ?? '')) return
      eventStore.set(eventId)
      queryClient.clear()
    },
    [queryClient],
  )
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
