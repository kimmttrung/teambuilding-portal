import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchMe } from '../api/auth'
import {
  assignGalaMember,
  autoAssignGalaMembers,
  confirmGalaSeats,
  createGalaLayout,
  createGalaTable,
  deleteGalaTable,
  drawGalaOrder,
  fetchGalaMyTurn,
  fetchGalaTeamMembers,
  fetchGalaUnseated,
  fetchGalaView,
  finalizeGala,
  holdGalaSeats,
  nextGalaTurn,
  releaseGalaSeats,
  reopenGala,
  streamGalaChanges,
  updateGalaLayout,
  updateGalaSeat,
  updateGalaTable,
} from '../api/gala'
import { QUERY_KEYS } from '../utils/constants'

const NOT_RETRIED = new Set(['GALA_NOT_CONFIGURED', 'NO_ACTIVE_EVENT'])
const RECONNECT_MS = 3000

export function useGalaView() {
  return useQuery({
    queryKey: QUERY_KEYS.galaView,
    queryFn: fetchGalaView,
    // Luồng SSE là kênh chính; hỏi định kỳ chỉ là lưới an toàn khi mạng chặn luồng dài.
    refetchInterval: 30_000,
    retry: (failureCount, error) => !NOT_RETRIED.has(error.code) && failureCount < 2,
  })
}

export function useGalaTeamMembers(teamId, { enabled = true } = {}) {
  return useQuery({
    queryKey: QUERY_KEYS.galaMembers(teamId),
    queryFn: () => fetchGalaTeamMembers(teamId),
    enabled,
  })
}

/** BTC: người tham gia chưa có ghế. Khoá nằm dưới `['gala','members']` nên tự mới lại sau mỗi lần xếp. */
export function useGalaUnseated({ enabled = true } = {}) {
  return useQuery({ queryKey: QUERY_KEYS.galaUnseated, queryFn: fetchGalaUnseated, enabled })
}

/**
 * Giữ kết nối SSE khi màn hình sơ đồ đang mở; mỗi sự kiện `change` làm cũ cache sơ đồ.
 * Đây là đăng ký nhận sự kiện (subscription), không phải fetch dữ liệu — nên dùng effect.
 * Trả `connecting` · `live` · `offline` để hiện chỉ báo.
 */
export function useGalaLive({ enabled = true } = {}) {
  const queryClient = useQueryClient()
  const [status, setStatus] = useState('connecting')

  useEffect(() => {
    if (!enabled) return undefined
    const controller = new AbortController()
    let stopped = false

    async function run() {
      while (!stopped) {
        try {
          await streamGalaChanges({
            signal: controller.signal,
            onOpen: () => setStatus('live'),
            onChange: () => queryClient.invalidateQueries({ queryKey: ['gala'] }),
          })
        } catch (error) {
          if (stopped) return
          // Access token hết hạn: gọi một API thường để interceptor refresh token, rồi nối lại.
          if (error.status === 401) {
            try {
              await fetchMe()
            } catch {
              return
            }
          }
        }
        if (stopped) return
        setStatus('offline')
        await new Promise((resolve) => setTimeout(resolve, RECONNECT_MS))
      }
    }

    run()
    return () => {
      stopped = true
      controller.abort()
    }
  }, [enabled, queryClient])

  return enabled ? status : 'offline'
}

/** Đồng hồ cho các bộ đếm ngược. */
export function useNow(intervalMs = 1000) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), intervalMs)
    return () => clearInterval(timer)
  }, [intervalMs])
  return now
}

/**
 * Sau mutation: thao tác của BTC trả sẵn sơ đồ mới thì đặt thẳng vào cache; còn lại tải lại.
 * Chỗ ngồi hiện trong My Journey và dashboard nên làm cũ cả hai.
 */
function useGalaSync() {
  const queryClient = useQueryClient()
  return {
    onSuccess: (data) => {
      if (data?.layout && data?.tables) queryClient.setQueryData(QUERY_KEYS.galaView, data)
      else queryClient.invalidateQueries({ queryKey: QUERY_KEYS.galaView })
      queryClient.invalidateQueries({ queryKey: ['gala', 'members'] })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.galaMyTurn })
      queryClient.invalidateQueries({ queryKey: ['admin'] })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.journey })
    },
    // Lỗi tranh chấp (ghế vừa bị giữ, hết lượt): sơ đồ trên màn hình đã cũ.
    onError: () => queryClient.invalidateQueries({ queryKey: QUERY_KEYS.galaView }),
  }
}

export function useHoldGalaSeats() {
  return useMutation({ mutationFn: (seatIds) => holdGalaSeats(seatIds), ...useGalaSync() })
}

export function useReleaseGalaSeats() {
  return useMutation({ mutationFn: (seatIds) => releaseGalaSeats(seatIds), ...useGalaSync() })
}

export function useConfirmGalaSeats() {
  return useMutation({ mutationFn: () => confirmGalaSeats(), ...useGalaSync() })
}

export function useAssignGalaMember() {
  return useMutation({ mutationFn: (payload) => assignGalaMember(payload), ...useGalaSync() })
}

export function useSaveGalaLayout() {
  return useMutation({
    mutationFn: ({ isNew, payload }) => (isNew ? createGalaLayout(payload) : updateGalaLayout(payload)),
    ...useGalaSync(),
  })
}

export function useSaveGalaTable() {
  return useMutation({
    mutationFn: ({ tableId, payload }) => (tableId ? updateGalaTable(tableId, payload) : createGalaTable(payload)),
    ...useGalaSync(),
  })
}

export function useDeleteGalaTable() {
  return useMutation({ mutationFn: (tableId) => deleteGalaTable(tableId), ...useGalaSync() })
}

export function useDrawGala() {
  return useMutation({ mutationFn: (seed) => drawGalaOrder(seed), ...useGalaSync() })
}

export function useNextGalaTurn() {
  return useMutation({ mutationFn: (options) => nextGalaTurn(options), ...useGalaSync() })
}

export function useFinalizeGala() {
  return useMutation({ mutationFn: () => finalizeGala(), ...useGalaSync() })
}

/** Banner nhắc lượt: chỉ bật cho Trưởng nhóm, hỏi 15 giây một lần ở mọi trang. */
export function useGalaMyTurn({ enabled = true } = {}) {
  return useQuery({
    queryKey: QUERY_KEYS.galaMyTurn,
    queryFn: fetchGalaMyTurn,
    enabled,
    refetchInterval: 15_000,
    retry: false,
  })
}

export function useReopenGala() {
  return useMutation({ mutationFn: () => reopenGala(), ...useGalaSync() })
}

export function useAutoAssignGalaMembers() {
  return useMutation({
    mutationFn: ({ teamId, reshuffle }) => autoAssignGalaMembers({ teamId, reshuffle }),
    ...useGalaSync(),
  })
}

export function useUpdateGalaSeat() {
  return useMutation({
    mutationFn: ({ seatId, payload }) => updateGalaSeat(seatId, payload),
    ...useGalaSync(),
  })
}
