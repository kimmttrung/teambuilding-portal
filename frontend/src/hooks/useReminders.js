import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchReminderPreview, sendReminders } from '../api/reminders'
import { QUERY_KEYS } from '../utils/constants'

/** Danh sách người nhận. Luôn tải mới khi mở hộp thoại: người khác có thể vừa gửi xong. */
export function useReminderPreview(kind) {
  return useQuery({
    queryKey: QUERY_KEYS.reminders(kind),
    queryFn: () => fetchReminderPreview(kind),
    staleTime: 0,
  })
}

export function useSendReminders(kind) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload) => sendReminders(kind, payload),
    // Dashboard (số email, hoạt động gần đây) và danh sách người nhận đều đổi.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin'] }),
  })
}
