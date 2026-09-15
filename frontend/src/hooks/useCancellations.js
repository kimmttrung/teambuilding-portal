import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  approveCancellation,
  cancelOnBehalf,
  fetchCancellations,
  rejectCancellation,
} from '../api/cancellations'
import { QUERY_KEYS } from '../utils/constants'

export function useCancellationList(params) {
  return useQuery({
    queryKey: QUERY_KEYS.cancellations(params),
    queryFn: () => fetchCancellations(params),
    placeholderData: keepPreviousData,
  })
}

/**
 * Duyệt huỷ / huỷ thay gỡ vé bay, xe, phòng, ghế Gala — mọi màn hình phân bổ đang mở phải tải lại,
 * nếu không BTC thấy ghế vẫn "đầy" và xếp nhầm.
 */
const RELEASE_KEYS = [
  ['registrations'],
  ['flights'],
  ['flight-assignments'],
  ['buses'],
  ['bus-assignments'],
  ['hotels'],
  ['rooms'],
  ['room-assignments'],
  ['gala'],
]

function useRefreshAfterDecision() {
  const queryClient = useQueryClient()
  return (released) => {
    queryClient.invalidateQueries({ queryKey: QUERY_KEYS.cancellationsAll })
    queryClient.invalidateQueries({ queryKey: QUERY_KEYS.dashboard })
    if (released) {
      for (const queryKey of RELEASE_KEYS) queryClient.invalidateQueries({ queryKey })
    }
  }
}

export function useApproveCancellation() {
  const refresh = useRefreshAfterDecision()
  return useMutation({
    mutationFn: ({ id, ...payload }) => approveCancellation(id, payload),
    onSuccess: () => refresh(true),
  })
}

export function useRejectCancellation() {
  const refresh = useRefreshAfterDecision()
  return useMutation({
    mutationFn: ({ id, decisionNote }) => rejectCancellation(id, decisionNote),
    onSuccess: () => refresh(false),
  })
}

export function useCancelOnBehalf() {
  const refresh = useRefreshAfterDecision()
  return useMutation({
    mutationFn: cancelOnBehalf,
    onSuccess: () => refresh(true),
  })
}
