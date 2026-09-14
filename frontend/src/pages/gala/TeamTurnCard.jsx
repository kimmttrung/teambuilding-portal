import { Check, Hand, Timer, Undo2, X } from 'lucide-react'
import { useConfirmGalaSeats } from '../../hooks/useGala'
import { useToast } from '../../context/ToastContext'
import Alert from '../../components/common/Alert'
import Button from '../../components/common/Button'
import Card from '../../components/common/Card'
import Countdown from '../../components/gala/Countdown'

/** Tình trạng lượt của team người xem + nút giữ / xác nhận / nhả cho Trưởng nhóm. */
export default function TeamTurnCard({ view, offsetMs, picked, onHold, onClearPicked, onReleaseAll, holding, releasing }) {
  const toast = useToast()
  const { mutateAsync: confirm, isPending: confirming } = useConfirmGalaSeats()
  const team = view.my_team
  const status = view.layout.selection_status

  if (!team) {
    return (
      <Card title="Team của bạn">
        <p className="text-sm text-slate-600">
          Bạn chưa thuộc team nào nên không chọn ghế theo lượt. BTC sẽ xếp chỗ ngồi cho bạn.
        </p>
      </Card>
    )
  }

  const activeTeam = view.draw.orders.find((order) => order.team_id === view.draw.active_team_id)
  const hasOrder = team.draw_position != null

  async function confirmHeld() {
    try {
      const result = await confirm()
      toast.success(
        result.turn_finished
          ? `Đã chốt đủ ${result.confirmed_total} ghế — lượt chuyển cho team kế tiếp. Giờ hãy xếp thành viên vào ghế.`
          : `Đã chốt ${result.seat_ids.length} ghế (${result.confirmed_total}/${result.quota}).`,
      )
    } catch (confirmError) {
      toast.error(confirmError.message)
    }
  }

  return (
    <Card
      title={team.team_name}
      description={team.is_leader ? 'Bạn là Trưởng nhóm — người chọn ghế cho team' : 'Trưởng nhóm chọn ghế cho team'}
      action={
        <span
          className="size-3.5 rounded-full ring-1 ring-black/10"
          style={{ backgroundColor: team.team_color || '#94a3b8' }}
          aria-hidden="true"
        />
      }
    >
      <div className="flex flex-col gap-3">
        {hasOrder && (
          <dl className="grid grid-cols-4 gap-2 text-center">
            <Stat label="Lượt" value={`#${team.draw_position}`} />
            <Stat label="Quota" value={team.quota} />
            <Stat label="Đã chốt" value={team.confirmed} tone="brand" />
            <Stat label="Còn chọn" value={team.remaining} tone={team.remaining ? 'emerald' : 'slate'} />
          </dl>
        )}

        {status === 'closed' && <p className="text-sm text-slate-600">BTC chưa bốc thăm thứ tự chọn ghế.</p>}
        {status !== 'closed' && !hasOrder && (
          <Alert tone="warning">Team chưa có người xác nhận tham gia nên không có lượt chọn ghế.</Alert>
        )}
        {status === 'drawing' && hasOrder && (
          <p className="text-sm text-slate-600">
            Đã bốc thăm: team chọn ở lượt <strong>#{team.draw_position}</strong>. BTC sẽ mở chọn ghế sau khi công bố.
          </p>
        )}
        {status === 'finalized' && (
          <Alert tone="success" title="Đã chốt chỗ ngồi">
            Team có {team.confirmed} ghế. Xem ghế của bạn trong My Journey.
          </Alert>
        )}

        {status === 'open' && hasOrder && !team.is_my_turn && (
          <p className="text-sm text-slate-600">
            {team.status === 'waiting' ? (
              <>
                Đang tới lượt <strong>{activeTeam?.team_name ?? '—'}</strong>. Team bạn chọn ở lượt #{team.draw_position}.
              </>
            ) : (
              'Lượt chọn của team đã kết thúc.'
            )}
          </p>
        )}

        {status === 'open' && team.is_my_turn && (
          <div className="rounded-lg bg-emerald-50 p-3 ring-1 ring-emerald-200 ring-inset">
            <p className="flex items-center justify-between gap-2 text-sm font-semibold text-emerald-900">
              <span className="inline-flex items-center gap-1.5">
                <Timer className="size-4" aria-hidden="true" />
                Đang tới lượt team bạn
              </span>
              <Countdown endsAt={team.turn_ends_at} offsetMs={offsetMs} className="text-lg" />
            </p>
            {!team.is_leader && (
              <p className="mt-1 text-xs text-emerald-800">Trưởng nhóm đang chọn ghế cho cả team.</p>
            )}
            {team.held > 0 && (
              <p className="mt-1 text-xs text-emerald-800">
                Đang giữ {team.held} ghế — hết hạn sau{' '}
                <Countdown endsAt={team.hold_expires_at} offsetMs={offsetMs} className="font-semibold" />
              </p>
            )}
          </div>
        )}

        {status === 'open' && team.is_my_turn && team.is_leader && (
          <div className="flex flex-wrap gap-2">
            <Button size="sm" icon={Hand} disabled={picked.length === 0} loading={holding} onClick={onHold}>
              Giữ {picked.length} ghế
            </Button>
            <Button size="sm" variant="secondary" icon={Check} disabled={team.held === 0} loading={confirming} onClick={confirmHeld}>
              Xác nhận {team.held} ghế đang giữ
            </Button>
            {picked.length > 0 && (
              <Button size="sm" variant="ghost" icon={X} onClick={onClearPicked}>
                Bỏ chọn
              </Button>
            )}
            {team.held > 0 && (
              <Button size="sm" variant="ghost" icon={Undo2} loading={releasing} onClick={onReleaseAll}>
                Nhả ghế đang giữ
              </Button>
            )}
          </div>
        )}
      </div>
    </Card>
  )
}

const TONES = { slate: 'text-slate-900', brand: 'text-brand-700', emerald: 'text-emerald-700' }

function Stat({ label, value, tone = 'slate' }) {
  return (
    <div className="rounded-lg border border-slate-200 px-1.5 py-1.5">
      <dt className="text-[11px] text-slate-500">{label}</dt>
      <dd className={`text-base font-bold tabular-nums ${TONES[tone]}`}>{value}</dd>
    </div>
  )
}
