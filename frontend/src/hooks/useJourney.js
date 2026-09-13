import { useQuery } from '@tanstack/react-query'
import { fetchMyJourney } from '../api/journey'
import { QUERY_KEYS } from '../utils/constants'

/**
 * Hành trình của tôi.
 *
 * Bật refetch khi quay lại tab (mặc định cả app đang tắt): CBNV mở màn hình này nhiều lần
 * trong ngày đi, và BTC có thể vừa đổi xe hoặc giờ tập trung.
 */
export function useMyJourney({ enabled = true } = {}) {
  return useQuery({
    queryKey: QUERY_KEYS.journey,
    queryFn: fetchMyJourney,
    enabled,
    staleTime: 60 * 1000,
    refetchOnWindowFocus: true,
  })
}
