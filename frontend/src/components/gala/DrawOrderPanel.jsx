import { GALA_DRAW_STATUS_META, GALA_SELECTION_STATUS_META } from '../../utils/constants'
import { formatNumber } from '../../utils/format'
import Badge from '../common/Badge'
import Card from '../common/Card'
import Countdown from './Countdown'

/** Thứ tự bốc thăm, team đang tới lượt kèm đồng hồ, ghế đã chốt so với quota của từng team. */
export default function DrawOrderPanel({ draw, myTeamId, offsetMs = 0, showLeaders = false }) {
  const status = GALA_SELECTION_STATUS_META[draw.selection_status] ?? GALA_SELECTION_STATUS_META.closed

  return (
    <Card
      title="Thứ tự chọn ghế"
      description={draw.orders.length ? `${draw.orders.length} team · quota ${formatNumber(draw.total_quota)} ghế` : undefined}
      action={<Badge tone={status.tone}>{status.label}</Badge>}
      bodyClassName="p-0"
    >
      {draw.orders.length === 0 ? (
        <p className="px-4 py-3.5 text-sm text-slate-500">BTC chưa bốc thăm thứ tự các team.</p>
      ) : (
        <ol className="divide-y divide-slate-100">
          {draw.orders.map((order) => {
            const meta = GALA_DRAW_STATUS_META[order.status] ?? GALA_DRAW_STATUS_META.waiting
            const active = order.status === 'active'
            return (
              <li
                key={order.team_id}
                className={`flex items-center gap-3 px-4 py-2.5 ${active ? 'bg-emerald-50/70' : ''} ${
                  order.team_id === myTeamId ? 'border-l-4 border-brand-500 pl-3' : ''
                }`}
                aria-current={active ? 'step' : undefined}
              >
                <span className="grid size-7 shrink-0 place-items-center rounded-full bg-slate-100 text-xs font-bold text-slate-700 tabular-nums">
                  {order.position}
                </span>
                <span
                  className="size-3 shrink-0 rounded-full ring-1 ring-black/10"
                  style={{ backgroundColor: order.team_color || '#94a3b8' }}
                  aria-hidden="true"
                />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-slate-900">
                    {order.team_name}
                    {order.team_id === myTeamId && <span className="ml-1 text-xs text-brand-700">(team bạn)</span>}
                  </p>
                  <p className="text-xs text-slate-500 tabular-nums">
                    {order.confirmed}/{order.quota} ghế
                    {order.held > 0 && ` · đang giữ ${order.held}`}
                  </p>
                  {showLeaders && (
                    <p className={`truncate text-xs ${order.leader_name ? 'text-slate-500' : 'font-medium text-amber-700'}`}>
                      {order.leader_name ? `Trưởng nhóm: ${order.leader_name}` : 'Chưa có Trưởng nhóm — không ai chọn ghế được'}
                    </p>
                  )}
                </div>
                {active && order.turn_ends_at ? (
                  <Countdown endsAt={order.turn_ends_at} offsetMs={offsetMs} className="text-sm font-semibold text-emerald-700" />
                ) : (
                  <Badge tone={meta.tone}>{meta.label}</Badge>
                )}
              </li>
            )
          })}
        </ol>
      )}
    </Card>
  )
}
