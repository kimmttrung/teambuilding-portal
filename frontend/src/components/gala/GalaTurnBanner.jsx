import { Link, useLocation } from 'react-router-dom'
import { BellRing, Hourglass } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { useGalaMyTurn } from '../../hooks/useGala'
import { ROLES } from '../../utils/constants'
import { serverOffset } from '../../utils/gala'
import Countdown from './Countdown'

/**
 * Banner trên mọi trang cho Trưởng nhóm: "đến lượt team bạn chọn ghế Gala" (kèm đồng hồ) hoặc
 * "sắp tới lượt". Email cũng được gửi khi lượt bắt đầu — banner dành cho người đang mở cổng.
 * Ẩn ở chính trang /gala, nơi đã có khung lượt chi tiết.
 */
export default function GalaTurnBanner() {
  const { user } = useAuth()
  const location = useLocation()
  const enabled = user?.role === ROLES.TEAM_LEADER
  const { data, dataUpdatedAt } = useGalaMyTurn({ enabled })

  if (!enabled || !data?.is_leader || location.pathname.startsWith('/gala')) return null
  const offsetMs = serverOffset(data.server_time, dataUpdatedAt)

  if (data.is_my_turn) {
    return (
      <div role="alert" className="mb-4 flex flex-wrap items-center gap-3 rounded-xl bg-emerald-600 px-4 py-3 text-white shadow-sm">
        <BellRing className="size-5 shrink-0 animate-bounce" aria-hidden="true" />
        <p className="min-w-0 flex-1 text-sm">
          <span className="font-semibold">Đến lượt {data.team_name} chọn ghế Gala Dinner!</span> Còn{' '}
          <Countdown endsAt={data.turn_ends_at} offsetMs={offsetMs} className="font-semibold" /> để chọn đủ{' '}
          {data.remaining} ghế.
        </p>
        <Link
          to="/gala"
          className="rounded-lg bg-white px-3 py-1.5 text-sm font-semibold text-emerald-700 transition hover:bg-emerald-50"
        >
          Chọn ghế ngay
        </Link>
      </div>
    )
  }

  if (data.selection_status === 'open' && data.status === 'waiting' && data.teams_ahead === 1) {
    return (
      <div role="status" className="mb-4 flex flex-wrap items-center gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-amber-900">
        <Hourglass className="size-5 shrink-0" aria-hidden="true" />
        <p className="min-w-0 flex-1 text-sm">
          <span className="font-semibold">Sắp tới lượt {data.team_name} chọn ghế Gala.</span>{' '}
          {data.active_team_name ? `${data.active_team_name} đang chọn, ` : ''}team bạn chọn ngay sau đó.
        </p>
        <Link to="/gala" className="text-sm font-semibold text-amber-800 underline">
          Xem sơ đồ
        </Link>
      </div>
    )
  }

  return null
}
