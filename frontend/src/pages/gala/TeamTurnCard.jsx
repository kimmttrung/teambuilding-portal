import { GALA_UI } from '../../utils/constants'
import { useState } from 'react'
import { useConfirmGalaSeats } from '../../hooks/useGala'
import { useToast } from '../../context/ToastContext'
import Alert from '../../components/common/Alert'
import Button from '../../components/common/Button'
import Card from '../../components/common/Card'
import Countdown from '../../components/gala/Countdown'

/** Quota và đồng hồ luôn lấy từ response mới nhất, không dùng snapshot bốc thăm. */
export default function TeamTurnCard({
  view,
  offsetMs,
  picked,
  onHold,
  onClearPicked,
  onReleaseAll,
  holding,
  releasing,
  offline = false,
}) {
  const toast = useToast()
  const { mutateAsync: confirm, isPending: confirming } = useConfirmGalaSeats()
  const [error, setError] = useState(null)
  const team = view.my_team
  const status = view.layout.selection_status
  const busy = holding || releasing || confirming || offline
  async function confirmHeld() {
    setError(null)
    try {
      const result = await confirm()
      toast.success(
        result.turn_finished
          ? 'Đã xác nhận đủ ghế. Lượt đã chuyển sang team kế tiếp.'
          : `Đã xác nhận ${result.seat_ids.length} ghế.`,
      )
    } catch (err) {
      setError(err.message)
    }
  }
  if (!team)
    return (
      <Card title="Chỗ ngồi của bạn">
        <p className="text-caption text-ink-muted">
          Bạn chưa thuộc team. Ban tổ chức sẽ xếp ghế cho bạn.
        </p>
      </Card>
    )
  if (status === 'open' && team.is_my_turn)
    return (
      <section
        className="rounded-xl bg-secondary p-5 text-on-primary sm:p-6"
        aria-label="Lượt chọn ghế của team"
      >
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="mb-2 flex items-center gap-2 text-caption">
              <span className="size-2 rounded-full bg-accent-green" />
              Đến lượt {team.team_name}
            </p>
            <h2 className="text-title">{GALA_UI.chooseForTeam}</h2>
            <p className="mt-1 text-caption text-on-primary/75">
              Đã xác nhận {team.confirmed}/{team.quota} ghế · đang giữ {team.held}
            </p>
          </div>
          <div>
            <Countdown
              endsAt={team.turn_ends_at}
              offsetMs={offsetMs}
              className="text-heading-1 font-bold sm:text-display-2"
            />
            <span className="ml-2 text-caption text-on-primary/70">còn lại</span>
          </div>
          {team.is_leader && (
            <div className="flex flex-wrap gap-2 max-sm:fixed max-sm:inset-x-0 max-sm:bottom-[calc(4.5rem+env(safe-area-inset-bottom))] max-sm:z-30 max-sm:justify-center max-sm:border-t max-sm:border-hairline max-sm:bg-surface max-sm:p-3 max-sm:pr-20">
              {picked.length > 0 && (
                <Button shape="pill" loading={holding} disabled={busy} onClick={onHold}>
                  Giữ {picked.length} ghế
                </Button>
              )}
              <Button
                variant="secondary"
                className={!picked.length ? 'max-sm:bg-primary max-sm:text-on-primary max-sm:disabled:opacity-50' : ''}
                shape="pill"
                loading={confirming}
                disabled={busy || team.held === 0}
                onClick={confirmHeld}
              >
                Xác nhận {team.held} ghế
              </Button>
            </div>
          )}
        </div>
        {team.held > 0 && (
          <p className="mt-3 text-caption text-on-primary/75">
            Ghế đang giữ hết hạn sau <Countdown endsAt={team.hold_expires_at} offsetMs={offsetMs} />
            . Xác nhận trước khi hết giờ.
          </p>
        )}
        {team.is_leader && (
          <div className="mt-3 flex flex-wrap gap-2">
            {picked.length > 0 && (
              <Button
                variant="ghost"
                className="text-on-primary hover:bg-on-primary/10"
                disabled={busy}
                onClick={onClearPicked}
              >
                {GALA_UI.clearPicks}
              </Button>
            )}
            {team.held > 0 && (
              <Button
                variant="ghost"
                className="text-on-primary hover:bg-on-primary/10"
                disabled={busy}
                onClick={onReleaseAll}
              >
                {GALA_UI.releaseHeld}
              </Button>
            )}
          </div>
        )}
        {error && (
          <div role="alert" className="mt-3">
            <Alert tone="error">{error}</Alert>
          </div>
        )}
      </section>
    )
  const ahead = view.draw.orders.filter(
    (order) => order.position < team.draw_position && ['waiting', 'active'].includes(order.status),
  ).length
  return (
    <Card
      title={team.team_name}
      description={team.is_leader ? 'Bạn là Trưởng nhóm' : 'Trưởng nhóm chọn ghế cho team'}
    >
      {team.status === 'waiting' && status === 'open' ? (
        <h2 className="mb-4 text-heading-2">
          {ahead ? `Còn ${ahead} team nữa là tới lượt bạn.` : 'Team bạn sắp tới lượt.'}
        </h2>
      ) : null}
      <dl className="grid grid-cols-3 gap-3">
        <Stat
          label="Lượt của bạn"
          value={team.draw_position ? `${team.draw_position}/${view.draw.orders.length}` : '—'}
        />
        <Stat label="Quota hiện tại" value={team.quota} />
        <Stat label="Đã xác nhận" value={team.confirmed} />
      </dl>
      <p className="mt-4 text-caption text-ink-muted">
        {status === 'closed'
          ? 'BTC chưa bốc thăm thứ tự chọn ghế.'
          : status === 'drawing'
            ? 'Đã bốc thăm. Chờ BTC mở chọn ghế.'
            : status === 'finalized'
              ? 'Đợt chọn ghế đã kết thúc. Trưởng nhóm vẫn có thể xếp thành viên vào ghế đã xác nhận.'
              : team.status === 'waiting'
                ? `Mỗi lượt có ${Math.round(view.layout.turn_seconds / 60)} phút. Bạn sẽ nhận thông báo khi tới lượt.`
                : 'Lượt của team đã kết thúc.'}
      </p>
    </Card>
  )
}
function Stat({ label, value }) {
  return (
    <div>
      <dt className="text-xs text-ink-faint">{label}</dt>
      <dd className="mt-1 text-title font-semibold tabular-nums text-ink">{value}</dd>
    </div>
  )
}
