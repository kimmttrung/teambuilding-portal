import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createItineraryItem,
  deleteItineraryItem,
  fetchItinerary,
  reorderItineraryDay,
  updateItineraryItem,
} from '../api/itinerary'
import { QUERY_KEYS } from '../utils/constants'

export function useItinerary({ enabled = true } = {}) {
  return useQuery({
    queryKey: QUERY_KEYS.itinerary,
    queryFn: fetchItinerary,
    enabled,
  })
}

/**
 * Lịch trình đổi là My Journey của CBNV đổi theo — xoá cache hành trình luôn để
 * người đang mở app thấy lịch mới sau tối đa `staleTime`, không phải đăng nhập lại.
 */
function useItineraryInvalidator() {
  const queryClient = useQueryClient()
  return () => {
    queryClient.invalidateQueries({ queryKey: ['itinerary'] })
    queryClient.invalidateQueries({ queryKey: ['journey'] })
  }
}

export function useSaveItineraryItem() {
  const invalidate = useItineraryInvalidator()
  return useMutation({
    mutationFn: ({ itemId, payload }) =>
      (itemId ? updateItineraryItem(itemId, payload) : createItineraryItem(payload)),
    onSuccess: invalidate,
  })
}

export function useDeleteItineraryItem() {
  const invalidate = useItineraryInvalidator()
  return useMutation({
    mutationFn: (itemId) => deleteItineraryItem(itemId),
    onSuccess: invalidate,
  })
}

export function useReorderItineraryDay() {
  const invalidate = useItineraryInvalidator()
  return useMutation({
    mutationFn: ({ dayDate, orderedIds }) => reorderItineraryDay({ dayDate, orderedIds }),
    onSuccess: invalidate,
  })
}
