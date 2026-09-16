import { useCallback } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { eventStore } from '../api/client'
import {
  createEvent,
  fetchActiveEvent,
  fetchEventOverview,
  fetchSelectableEvents,
} from '../api/events'
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
 * Dùng `resetQueries`, KHÔNG dùng `clear()` và cũng không `invalidateQueries`:
 *
 * - `clear()` chỉ xoá cache và **không báo cho observer đang gắn** (query-core: `queryCache.clear()`
 *   rồi thôi). Màn hình đang mở vì thế đứng im tới khi người dùng F5 — đúng lỗi đã gặp.
 * - `invalidateQueries` chỉ đánh dấu cũ, dữ liệu kỳ trước vẫn nằm đó và vẫn được vẽ cho tới khi
 *   request mới về — đủ lâu để BTC bấm nhầm vào dữ liệu của kỳ khác. Khoá cache không mang
 *   `event_id` nên không phân biệt được.
 * - `resetQueries` làm đúng cả hai: `query.reset()` đưa mọi query về trạng thái ban đầu (dữ liệu kỳ
 *   cũ biến mất ngay, màn hình hiện skeleton) rồi `refetchQueries({type:'active'})` tải lại đúng
 *   những query đang có người xem, với header `X-Event-Id` mới.
 *
 * Trừ danh sách kỳ ra: nó không phụ thuộc kỳ đang chọn, reset luôn thì bộ chọn kỳ tự biến mất giữa
 * chừng rồi hiện lại.
 */
export function useSelectEvent() {
  const queryClient = useQueryClient()
  return useCallback(
    (eventId) => {
      if (String(eventStore.get() ?? '') === String(eventId ?? '')) return
      eventStore.set(eventId)
      queryClient.resetQueries({
        predicate: (query) => String(query.queryKey) !== String(QUERY_KEYS.selectableEvents),
      })
    },
    [queryClient],
  )
}

/**
 * Tạo kỳ mới rồi chuyển sang luôn.
 *
 * Không `invalidateQueries` như mutation khác: `switchTo` đã `queryClient.clear()`, gọi thêm cũng
 * vô nghĩa. Kỳ mới ở trạng thái `draft` nên chỉ BTC vào được — CBNV chưa thấy gì cho tới khi mở đăng ký.
 */
export function useCreateEvent() {
  const switchTo = useSelectEvent()
  return useMutation({
    mutationFn: createEvent,
    onSuccess: (event) => switchTo(event.id),
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
