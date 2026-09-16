import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { assignTeamLeader } from '../api/admin'
import { fetchTeams } from '../api/masterData'
import { QUERY_KEYS } from '../utils/constants'

/** Danh sách team kèm `leader_user_id` — biết một CBNV có đang là Trưởng nhóm không. */
export function useTeams({ enabled = true } = {}) {
  return useQuery({ queryKey: QUERY_KEYS.teams, queryFn: fetchTeams, enabled, staleTime: 60 * 1000 })
}

/**
 * Đổi Trưởng nhóm đổi luôn quyền chọn ghế Gala và nhãn vai trò — làm mới dashboard, Gala,
 * danh sách huỷ và danh sách CBNV.
 */
export function useAssignTeamLeader() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ teamId, userId }) => assignTeamLeader(teamId, userId),
    onSuccess: () => {
      for (const queryKey of [QUERY_KEYS.dashboard, QUERY_KEYS.teams, QUERY_KEYS.cancellationsAll, ['gala'], ['users']]) {
        queryClient.invalidateQueries({ queryKey })
      }
    },
  })
}
