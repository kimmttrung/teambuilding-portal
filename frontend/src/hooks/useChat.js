import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  deleteChatSession,
  fetchChatMessages,
  fetchChatSessions,
  fetchChatStatus,
  fetchRagStatus,
  reindexRag,
} from '../api/chat'
import { QUERY_KEYS } from '../utils/constants'

export function useChatStatus({ enabled = true } = {}) {
  return useQuery({
    queryKey: QUERY_KEYS.chatStatus,
    queryFn: fetchChatStatus,
    enabled,
    staleTime: 60_000,
    retry: false,
  })
}

export function useChatSessions({ enabled = true } = {}) {
  return useQuery({ queryKey: QUERY_KEYS.chatSessions, queryFn: fetchChatSessions, enabled })
}

/** Lịch sử một cuộc trò chuyện. Không thử lại: phiên đã xoá (404) thì mở cuộc mới luôn. */
export function useChatMessages(sessionId, { enabled = true } = {}) {
  return useQuery({
    queryKey: QUERY_KEYS.chatMessages(sessionId),
    queryFn: () => fetchChatMessages(sessionId),
    enabled: Boolean(sessionId) && enabled,
    retry: false,
    staleTime: Infinity,
  })
}

export function useRagStatus() {
  return useQuery({ queryKey: QUERY_KEYS.ragStatus, queryFn: fetchRagStatus, retry: false })
}

export function useReindexRag() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => reindexRag(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.ragStatus })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.chatStatus })
    },
  })
}

export function useDeleteChatSession() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (sessionId) => deleteChatSession(sessionId),
    onSuccess: (_data, sessionId) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.chatSessions })
      queryClient.removeQueries({ queryKey: QUERY_KEYS.chatMessages(sessionId) })
    },
  })
}
