import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  allocateRooms,
  assignRoom,
  createHotel,
  createRoom,
  deleteHotel,
  deleteRoom,
  fetchHotels,
  fetchOccupants,
  fetchRoomAssignments,
  fetchRooms,
  fetchRoomSummary,
  importRooms,
  removeRoomAssignment,
  updateHotel,
  updateRoom,
} from '../api/rooms'
import { QUERY_KEYS } from '../utils/constants'

export function useHotels() {
  return useQuery({ queryKey: QUERY_KEYS.hotels, queryFn: fetchHotels })
}

export function useRooms(filters = {}, { enabled = true } = {}) {
  return useQuery({
    queryKey: QUERY_KEYS.rooms(filters),
    queryFn: () => fetchRooms(filters),
    enabled,
  })
}

export function useRoomSummary() {
  return useQuery({ queryKey: QUERY_KEYS.roomSummary, queryFn: fetchRoomSummary })
}

export function useOccupants(roomId) {
  return useQuery({
    queryKey: QUERY_KEYS.occupants(roomId),
    queryFn: () => fetchOccupants(roomId),
    enabled: Boolean(roomId),
  })
}

export function useRoomAssignments(filters = {}, { enabled = true } = {}) {
  return useQuery({
    queryKey: QUERY_KEYS.roomAssignments(filters),
    queryFn: () => fetchRoomAssignments(filters),
    enabled,
  })
}

/**
 * Mọi thay đổi về khách sạn, phòng hay phân phòng đều làm số giường cũ — gồm cả thẻ trên
 * dashboard. Xoá cache một chỗ như bên chuyến bay và xe.
 */
function useRoomInvalidator() {
  const queryClient = useQueryClient()
  return () => {
    queryClient.invalidateQueries({ queryKey: ['hotels'] })
    queryClient.invalidateQueries({ queryKey: ['rooms'] })
    queryClient.invalidateQueries({ queryKey: ['room-assignments'] })
    queryClient.invalidateQueries({ queryKey: ['admin'] })
  }
}

export function useSaveHotel() {
  const invalidate = useRoomInvalidator()
  return useMutation({
    mutationFn: ({ hotelId, payload }) => (hotelId ? updateHotel(hotelId, payload) : createHotel(payload)),
    onSuccess: invalidate,
  })
}

export function useDeleteHotel() {
  const invalidate = useRoomInvalidator()
  return useMutation({ mutationFn: (hotelId) => deleteHotel(hotelId), onSuccess: invalidate })
}

export function useSaveRoom() {
  const invalidate = useRoomInvalidator()
  return useMutation({
    mutationFn: ({ roomId, payload }) => (roomId ? updateRoom(roomId, payload) : createRoom(payload)),
    onSuccess: invalidate,
  })
}

export function useDeleteRoom() {
  const invalidate = useRoomInvalidator()
  return useMutation({ mutationFn: (roomId) => deleteRoom(roomId), onSuccess: invalidate })
}

export function useAssignRoom() {
  const invalidate = useRoomInvalidator()
  return useMutation({ mutationFn: (options) => assignRoom(options), onSuccess: invalidate })
}

export function useRemoveRoomAssignment() {
  const invalidate = useRoomInvalidator()
  return useMutation({
    mutationFn: ({ assignmentId, reason }) => removeRoomAssignment(assignmentId, reason),
    onSuccess: invalidate,
  })
}

/** Xếp phòng tự động. Dry-run không đổi gì trên server nên không xoá cache. */
export function useAllocateRooms() {
  const invalidate = useRoomInvalidator()
  return useMutation({
    mutationFn: (options) => allocateRooms(options),
    onSuccess: (_data, variables) => {
      if (variables?.dryRun === false) invalidate()
    },
  })
}

/** Kiểm tra file không đổi gì trên server nên không xoá cache; chỉ lần ghi thật mới làm mới. */
export function useImportRooms() {
  const invalidate = useRoomInvalidator()
  return useMutation({
    mutationFn: ({ file, dryRun, replaceExisting }) => importRooms(file, { dryRun, replaceExisting }),
    onSuccess: (_data, variables) => {
      if (variables?.dryRun === false) invalidate()
    },
  })
}
