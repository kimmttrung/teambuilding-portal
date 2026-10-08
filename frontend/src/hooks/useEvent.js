import { useCallback, useEffect, useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { eventStore } from '../api/client'
import {
  activateEvent,
  createEvent,
  deleteEvent,
  fetchActiveEvent,
  fetchConfigImpact,
  fetchEventSettings,
  fetchEvents,
  fetchSelectableEvents,
  fetchTermsVersions,
  saveEventSettings,
  updateEvent,
  chooseTermsVersion,
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

/** Danh sách mọi kỳ cho trang quản lý. Không cache lâu: thêm/xoá phải thấy ngay. */
export function useEvents() {
  return useQuery({
    queryKey: QUERY_KEYS.eventList,
    queryFn: fetchEvents,
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
 * Danh sách kỳ trong bộ chọn không đi qua `resetQueries` (reset làm ô chọn biến mất giữa chừng).
 * Phải ghi kỳ vừa tạo vào cache đó trước khi đổi header — nếu không, `<select>` không có option
 * của kỳ mới và trình duyệt vẽ kỳ đầu danh sách. Trang quản lý thì đã tải lại, nên hiện "Đang xem"
 * ở kỳ mới trong lúc thanh bên vẫn là kỳ cũ.
 */
export function useCreateEvent() {
  const queryClient = useQueryClient()
  const switchTo = useSelectEvent()
  return useMutation({
    mutationFn: createEvent,
    onSuccess: async (event) => {
      // Request danh sách kỳ đang bay có thể về sau và ghi đè cache vừa thêm.
      await queryClient.cancelQueries({ queryKey: QUERY_KEYS.selectableEvents })
      queryClient.setQueryData(QUERY_KEYS.selectableEvents, (current) => {
        const list = Array.isArray(current) ? current : []
        if (list.some((item) => String(item.id) === String(event.id))) return list
        return [event, ...list]
      })
      switchTo(event.id)
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.selectableEvents })
    },
  })
}

/**
 * Xoá một kỳ.
 *
 * Chỉ dọn cache toàn bộ khi kỳ vừa xoá là kỳ đang xem — nếu không, BTC đang sửa kỳ khác
 * bị đá về kỳ mặc định. Xoá đúng kỳ đang xem thì phải gỡ `X-Event-Id` trước khi tải lại,
 * vì header đó không còn trỏ tới kỳ nào.
 */
export function useDeleteEvent() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ eventId }) => deleteEvent(eventId),
    onSuccess: (_data, { viewing }) => {
      if (viewing) {
        eventStore.clear()
        queryClient.resetQueries({
          predicate: (query) => String(query.queryKey) !== String(QUERY_KEYS.selectableEvents),
        })
      } else {
        queryClient.invalidateQueries({ queryKey: QUERY_KEYS.eventList })
        queryClient.invalidateQueries({ queryKey: QUERY_KEYS.activeEvent })
      }
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.selectableEvents })
    },
  })
}

/** Sửa thông tin kỳ. Dọn cả `selectableEvents` vì tên kỳ hiện ngay trên bộ chọn. */
export function useUpdateEvent() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ eventId, payload }) => updateEvent(eventId, payload),
    onSuccess: (_data, { eventId }) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.activeEvent })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.selectableEvents })
      queryClient.invalidateQueries({ queryKey: ['admin'] })
      // Đổi ngày của kỳ là chuyến bay / xe / lịch trình đã nhập có thể rơi ra ngoài.
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.configImpact(eventId) })
      // Lưu quy định với phiên bản mới là bản cũ vừa vào lịch sử (khoá này cũng phủ `termsVersions`).
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.terms(eventId) })
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

/** Bản quy định đang dùng + các bản trước đây. Cũng là nguồn nội dung cho ô soạn quy định. */
export function useTermsVersions(eventId) {
  return useQuery({
    queryKey: QUERY_KEYS.termsVersions(eventId),
    queryFn: () => fetchTermsVersions(eventId),
    enabled: Boolean(eventId),
  })
}

/** Chọn lại một bản quy định cũ làm bản đang dùng. */
export function useChooseTermsVersion(eventId) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (version) => chooseTermsVersion(eventId, version),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.activeEvent })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.terms(eventId) })
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
    onSuccess: (data) => {
      queryClient.setQueryData(QUERY_KEYS.eventSettings(eventId), data)
      // Đổi số phút đệm xe là xe đã xếp có thể thành lệch giờ bay.
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.configImpact(eventId) })
    },
  })
}

/**
 * Những thứ đã xếp đang lệch với cấu hình kỳ. Lệch còn đến từ màn hình khác (sửa giờ bay, sửa xe),
 * nên hỏi lại mỗi lần mở trang thay vì tin cache.
 */
export function useConfigImpact(eventId) {
  return useQuery({
    queryKey: QUERY_KEYS.configImpact(eventId),
    queryFn: () => fetchConfigImpact(eventId),
    enabled: Boolean(eventId),
    staleTime: 0,
  })
}

export function useMyRegistration() {
  return useQuery({
    queryKey: QUERY_KEYS.myRegistration,
    queryFn: fetchMyRegistration,
  })
}
