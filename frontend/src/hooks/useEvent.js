import { useCallback, useEffect, useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { eventStore } from '../api/client'
import {
  activateEvent,
  createEvent,
  fetchActiveEvent,
  fetchEventSettings,
  fetchSelectableEvents,
  saveEventSettings,
  updateEvent,
} from '../api/events'
import { fetchMyRegistration } from '../api/registrations'
import { QUERY_KEYS } from '../utils/constants'

const EVENT_POLL_MS = 20 * 1000

/**
 * Kỳ đang xem. Trạng thái kỳ do BTC đổi từ máy khác, nên phải tự hỏi lại server: khi quay về tab và
 * mỗi 20 giây lúc tab đang mở (TanStack tự dừng khi tab ẩn). Trước đây để `staleTime` 5 phút và
 * không tải lại khi focus → BTC mở/đóng đăng ký mà CBNV phải F5 mới thấy.
 * Mọi màn hình dùng chung query này nên chỉ là một request nhỏ mỗi 20 giây cho mỗi người.
 */
export function useActiveEvent() {
  return useQuery({
    queryKey: QUERY_KEYS.activeEvent,
    queryFn: fetchActiveEvent,
    staleTime: EVENT_POLL_MS,
    refetchInterval: EVENT_POLL_MS,
    refetchOnWindowFocus: true,
    retry: (failureCount, error) => error.code !== 'NO_ACTIVE_EVENT' && failureCount < 2,
  })
}

/**
 * Trạng thái kỳ đổi thì những thứ suy ra từ nó cũng cũ: đăng ký còn sửa được không (`can_edit`,
 * `cancel_policy`), My Journey đã có dữ liệu phân bổ chưa. Gọi một lần ở AppLayout.
 */
export function useEventStatusSync() {
  const queryClient = useQueryClient()
  const { data: event } = useActiveEvent()
  const statusKey = event ? `${event.id}:${event.status}` : null
  const previous = useRef(statusKey)

  useEffect(() => {
    if (statusKey && previous.current && previous.current !== statusKey) {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.myRegistration })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.journey })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.formOptions })
    }
    previous.current = statusKey
  }, [queryClient, statusKey])
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

/** Sửa thông tin kỳ. Dọn cả `selectableEvents` vì tên kỳ hiện ngay trên bộ chọn. */
export function useUpdateEvent() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ eventId, payload }) => updateEvent(eventId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.activeEvent })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.selectableEvents })
      queryClient.invalidateQueries({ queryKey: ['admin'] })
    },
  })
}

/**
 * Đặt kỳ này làm kỳ mặc định.
 *
 * Kỳ mặc định là thứ người chưa chọn gì sẽ thấy, nên đổi nó ảnh hưởng **mọi CBNV** chứ không riêng
 * người bấm — màn hình phải hỏi xác nhận trước khi gọi.
 */
export function useActivateEvent() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: activateEvent,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.activeEvent })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.selectableEvents })
    },
  })
}

export function useEventSettings(eventId) {
  return useQuery({
    queryKey: QUERY_KEYS.eventSettings(eventId),
    queryFn: () => fetchEventSettings(eventId),
    enabled: Boolean(eventId),
  })
}

export function useSaveEventSettings(eventId) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (values) => saveEventSettings(eventId, values),
    onSuccess: (data) => queryClient.setQueryData(QUERY_KEYS.eventSettings(eventId), data),
  })
}

export function useMyRegistration() {
  return useQuery({
    queryKey: QUERY_KEYS.myRegistration,
    queryFn: fetchMyRegistration,
  })
}
