import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchEmailLogs, fetchEmailStats, resendEmails } from '../api/emails'
import { QUERY_KEYS } from '../utils/constants'
import { isInFlight } from '../utils/email'

const POLL_MS = 2000

/**
 * Nhật ký email. Còn thư đang gửi thì hỏi lại mỗi 2 giây để BTC thấy trạng thái chuyển sang
 * "Đã gửi" hoặc "Lỗi" mà không phải tải lại trang; gửi xong thì thôi hỏi.
 */
export function useEmailLogs(params) {
  return useQuery({
    queryKey: QUERY_KEYS.emailLogs(params),
    queryFn: () => fetchEmailLogs(params),
    placeholderData: keepPreviousData,
    refetchInterval: (query) => (query.state.data?.items?.some(isInFlight) ? POLL_MS : false),
  })
}

export function useEmailStats({ poll = false } = {}) {
  return useQuery({
    queryKey: QUERY_KEYS.emailStats,
    queryFn: fetchEmailStats,
    refetchInterval: poll ? POLL_MS : false,
  })
}

export function useResendEmails() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (ids) => resendEmails(ids),
    // Nhật ký, thống kê, dashboard, danh sách nhắc đều nằm dưới khoá 'admin'.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin'] }),
  })
}
