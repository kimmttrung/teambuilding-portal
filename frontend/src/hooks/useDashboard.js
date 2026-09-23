import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchDashboard } from '../api/admin'
import { changeEventStatus } from '../api/events'
import { QUERY_KEYS } from '../utils/constants'

/** Dashboard BTC. Refetch khi quay lại tab: BTC hay mở song song màn hình phân bổ. */
export function useDashboard() {
  return useQuery({
    queryKey: QUERY_KEYS.dashboard,
    queryFn: fetchDashboard,
    staleTime: 30 * 1000,
    refetchOnWindowFocus: true,
  })
}

/**
 * Chuyển trạng thái kỳ. Đổi trạng thái ảnh hưởng gần như mọi màn hình (form đăng ký
 * mở/khoá, My Journey hiện/ẩn phân bổ) nên làm mới rộng tay.
 */
export function useChangeEventStatus() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ eventId, ...payload }) => changeEventStatus(eventId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.dashboard })
      queryClient.invalidateQueries({ queryKey: ['events'] })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.journey })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.myRegistration })
    },
  })
}
