import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  allocateFlights,
  bulkMoveAssignments,
  createFlight,
  deleteFlight,
  fetchAssignments,
  fetchFlights,
  fetchFlightSummary,
  fetchPassengers,
  moveAssignment,
  removeAssignment,
  updateFlight,
} from '../api/flights'
import { QUERY_KEYS } from '../utils/constants'

export function useFlights(filters = {}) {
  return useQuery({
    queryKey: QUERY_KEYS.flights(filters),
    queryFn: () => fetchFlights(filters),
  })
}

export function useFlightSummary() {
  return useQuery({
    queryKey: QUERY_KEYS.flightSummary,
    queryFn: fetchFlightSummary,
  })
}

export function usePassengers(flightId, { enabled = true } = {}) {
  return useQuery({
    queryKey: QUERY_KEYS.passengers(flightId),
    queryFn: () => fetchPassengers(flightId),
    enabled: Boolean(flightId) && enabled,
  })
}

export function useAssignments(filters = {}, { enabled = true } = {}) {
  return useQuery({
    queryKey: QUERY_KEYS.assignments(filters),
    queryFn: () => fetchAssignments(filters),
    enabled,
  })
}

/**
 * Mọi thay đổi về chuyến bay hay phân bổ đều làm số liệu slot cũ.
 * Gom việc xoá cache vào một chỗ để không có màn hình nào hiện "còn 3 chỗ" sau khi
 * 3 chỗ đó vừa bị lấp.
 */
function useFlightInvalidator() {
  const queryClient = useQueryClient()
  return () => {
    queryClient.invalidateQueries({ queryKey: ['flights'] })
    queryClient.invalidateQueries({ queryKey: ['flight-assignments'] })
  }
}

export function useSaveFlight() {
  const invalidate = useFlightInvalidator()
  return useMutation({
    mutationFn: ({ flightId, payload }) =>
      flightId ? updateFlight(flightId, payload) : createFlight(payload),
    onSuccess: invalidate,
  })
}

export function useDeleteFlight() {
  const invalidate = useFlightInvalidator()
  return useMutation({
    mutationFn: (flightId) => deleteFlight(flightId),
    onSuccess: invalidate,
  })
}

/**
 * Chạy phân bổ. Dry-run KHÔNG xoá cache vì nó không đổi gì trên server;
 * chỉ lần ghi thật (`dryRun: false`) mới invalidate.
 */
export function useAllocateFlights() {
  const invalidate = useFlightInvalidator()
  return useMutation({
    mutationFn: (options) => allocateFlights(options),
    onSuccess: (_data, variables) => {
      if (variables?.dryRun === false) invalidate()
    },
  })
}

export function useMoveAssignment() {
  const invalidate = useFlightInvalidator()
  return useMutation({
    mutationFn: ({ assignmentId, flightId, reason }) =>
      moveAssignment(assignmentId, { flightId, reason }),
    onSuccess: invalidate,
  })
}

export function useBulkMove() {
  const invalidate = useFlightInvalidator()
  return useMutation({
    mutationFn: ({ registrationIds, flightId, reason }) =>
      bulkMoveAssignments({ registrationIds, flightId, reason }),
    onSuccess: invalidate,
  })
}

export function useRemoveAssignment() {
  const invalidate = useFlightInvalidator()
  return useMutation({
    mutationFn: ({ assignmentId, reason }) => removeAssignment(assignmentId, reason),
    onSuccess: invalidate,
  })
}
