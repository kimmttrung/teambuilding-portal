import { useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchPersonLocation, searchPeople } from '../api/people'
import { QUERY_KEYS } from '../utils/constants'

/** Người đang được tra cứu nằm trong URL (`?person=`) — xem `usePersonLocation`. */
export const PERSON_PARAM = 'person'

export function usePeopleSearch(query, { enabled = true } = {}) {
  const text = (query ?? '').trim()
  return useQuery({
    queryKey: QUERY_KEYS.peopleSearch(text),
    queryFn: () => searchPeople(text),
    enabled: enabled && text.length >= 2,
    // Gõ tới đâu gọi tới đó nên giữ kết quả cũ một lúc, tránh nhấp nháy giữa các phím.
    staleTime: 30_000,
  })
}

/**
 * Người đang tra cứu + vị trí chính xác của họ, đọc từ `?person=<user_id>` trên URL.
 *
 * Để trong URL chứ không phải state vì ba lý do: F5 không mất, BTC gửi link "xem thằng này đang ở
 * đâu" cho nhau được, và khi bấm từ thanh tóm tắt sang màn hình khác thì người đang tra cứu đi theo.
 *
 * Mọi màn hình phân bổ dùng chung hook này để biết tô đỏ dòng/thẻ/ghế nào.
 */
export function usePersonLocation() {
  const [searchParams, setSearchParams] = useSearchParams()
  const raw = searchParams.get(PERSON_PARAM)
  const userId = Number(raw) || null

  const query = useQuery({
    queryKey: QUERY_KEYS.personLocation(userId),
    queryFn: () => fetchPersonLocation(userId),
    enabled: Boolean(userId),
  })

  function select(nextId) {
    const next = new URLSearchParams(searchParams)
    if (nextId) next.set(PERSON_PARAM, String(nextId))
    else next.delete(PERSON_PARAM)
    setSearchParams(next, { replace: true })
  }

  return { userId, location: query.data ?? null, isLoading: query.isLoading, error: query.error, select }
}

/**
 * Tập id cần tô đỏ trên màn hình hiện tại.
 *
 * Trả `Set` cho từng loại thay vì một id: một người đi 4 chặng xe nên có thể khớp nhiều thẻ xe cùng lúc.
 */
export function highlightTargets(location) {
  if (!location) return { flights: new Set(), buses: new Set(), rooms: new Set(), seats: new Set() }
  return {
    flights: new Set(
      [location.flights?.outbound?.flight_id, location.flights?.return?.flight_id].filter(Boolean),
    ),
    buses: new Set((location.buses ?? []).map((leg) => leg.bus_id).filter(Boolean)),
    rooms: new Set([location.room?.room_id].filter(Boolean)),
    seats: new Set([location.gala?.seat_id].filter(Boolean)),
  }
}
