import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  allocateBuses,
  assignRider,
  createBus,
  deleteBus,
  fetchBusAssignments,
  fetchBuses,
  moveBusAssignment,
  removeBusAssignment,
  setBusLeader,
  updateBus,
} from '../api/buses'
import { QUERY_KEYS } from '../utils/constants'

export function useBuses(filters = {}, { enabled = true } = {}) {
  return useQuery({
    queryKey: QUERY_KEYS.buses(filters),
    queryFn: () => fetchBuses(filters),
    enabled,
  })
}

export function useBusAssignments(filters = {}, { enabled = true } = {}) {
  return useQuery({
    queryKey: QUERY_KEYS.busAssignments(filters),
    queryFn: () => fetchBusAssignments(filters),
    enabled,
  })
}

/**
 * Mọi thay đổi về xe hay phân xe đều làm số chỗ cũ — kể cả số liệu trên dashboard.
 * Gom việc xoá cache vào một chỗ như bên chuyến bay.
 */
function useBusInvalidator() {
  const queryClient = useQueryClient()
  return () => {
    queryClient.invalidateQueries({ queryKey: ['buses'] })
    queryClient.invalidateQueries({ queryKey: ['bus-assignments'] })
    queryClient.invalidateQueries({ queryKey: ['admin'] })
  }
}

export function useSaveBus() {
  const invalidate = useBusInvalidator()
  return useMutation({
    mutationFn: ({ busId, payload }) => (busId ? updateBus(busId, payload) : createBus(payload)),
    onSuccess: invalidate,
  })
}

export function useDeleteBus() {
  const invalidate = useBusInvalidator()
  return useMutation({
    mutationFn: (busId) => deleteBus(busId),
    onSuccess: invalidate,
  })
}

export function useSetBusLeader() {
  const invalidate = useBusInvalidator()
  return useMutation({
    mutationFn: ({ busId, payload }) => setBusLeader(busId, payload),
    onSuccess: invalidate,
  })
}

/** Dry-run không đổi gì trên server nên không xoá cache; chỉ lần ghi thật mới làm mới. */
export function useAllocateBuses() {
  const invalidate = useBusInvalidator()
  return useMutation({
    mutationFn: (options) => allocateBuses(options),
    onSuccess: (_data, variables) => {
      if (variables?.dryRun === false) invalidate()
    },
  })
}

export function useAssignRider() {
  const invalidate = useBusInvalidator()
  return useMutation({
    mutationFn: ({ registrationId, busId, reason }) => assignRider({ registrationId, busId, reason }),
    onSuccess: invalidate,
  })
}

export function useMoveBusAssignment() {
  const invalidate = useBusInvalidator()
  return useMutation({
    mutationFn: ({ assignmentId, busId, reason }) => moveBusAssignment(assignmentId, { busId, reason }),
    onSuccess: invalidate,
  })
}

export function useRemoveBusAssignment() {
  const invalidate = useBusInvalidator()
  return useMutation({
    mutationFn: ({ assignmentId, reason }) => removeBusAssignment(assignmentId, reason),
    onSuccess: invalidate,
  })
}
