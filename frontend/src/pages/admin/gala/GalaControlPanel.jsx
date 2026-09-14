import { useState } from 'react'
import { Flag, Play, RotateCcw, Shuffle, SkipForward, StepForward } from 'lucide-react'
import { useDrawGala, useFinalizeGala, useNextGalaTurn, useReopenGala } from '../../../hooks/useGala'
import { useToast } from '../../../context/ToastContext'
import { EVENT_STATUS, EVENT_STATUS_META, GALA_SELECTION_STATUS_META } from '../../../utils/constants'
import Alert from '../../../components/common/Alert'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import Input from '../../../components/common/Input'
import Countdown from '../../../components/gala/Countdown'

const STATUS_ORDER = Object.values(EVENT_STATUS)

/** Bốc thăm → mở chọn ghế → chuyển / bỏ lượt → kết thúc. Nút hiện theo trạng thái hiện tại. */
export default function GalaControlPanel({ view, event, offsetMs }) {
  const toast = useToast()
  const { mutateAsync: draw, isPending: drawing } = useDrawGala()
  const { mutateAsync: next, isPending: advancing } = useNextGalaTurn()
  const { mutateAsync: finalize, isPending: finalizing } = useFinalizeGala()
  const { mutateAsync: reopen, isPending: reopening } = useReopenGala()
  const [seed, setSeed] = useState('')

  const { selection_status: status, draw_seed: drawSeed } = view.layout
  const meta = GALA_SELECTION_STATUS_META[status] ?? GALA_SELECTION_STATUS_META.closed
  const active = view.draw.orders.find((order) => order.team_id === view.draw.active_team_id)
  const missingTeams = view.draw.orders.filter((order) => order.confirmed < order.quota)
  const published = event ? STATUS_ORDER.indexOf(event.status) >= STATUS_ORDER.indexOf(EVENT_STATUS.INFORMATION_PUBLISHED) : false

  async function run(action, message) {
    try {
      await action()
      toast.success(message)
    } catch (actionError) {
      toast.error(actionError.message)
    }
  }

  function handleDraw() {
    if (status === 'drawing' && !window.confirm('Bốc thăm lại sẽ thay toàn bộ thứ tự hiện tại. Tiếp tục?')) return
    const value = seed.trim() ? Number(seed) : null
    run(() => draw(value), 'Đã bốc thăm thứ tự team.')
  }

  return (
    <Card title="Điều hành chọn ghế" action={<Badge tone={meta.tone}>{meta.label}</Badge>}>
      <div className="flex flex-col gap-3">
        {(status === 'closed' || status === 'drawing') && (
          <>
            {drawSeed != null && (
              <p className="text-xs text-slate-500">
                Seed lần bốc gần nhất: <span className="font-mono text-slate-900">{drawSeed}</span> — nhập lại seed này
                để ra đúng thứ tự cũ.
              </p>
            )}
            <div className="flex items-end gap-2">
              <div className="flex-1">
                <Input
                  label="Seed (tuỳ chọn)"
                  type="number"
                  min={1}
                  placeholder="Để trống = ngẫu nhiên"
                  value={seed}
                  onChange={(changeEvent) => setSeed(changeEvent.target.value)}
                />
              </div>
              <Button variant={status === 'drawing' ? 'secondary' : 'primary'} icon={Shuffle} loading={drawing} onClick={handleDraw}>
                {status === 'drawing' ? 'Bốc lại' : 'Bốc thăm'}
              </Button>
            </div>
            <p className="text-xs text-slate-500">Quota mỗi team = số thành viên đã xác nhận tham gia.</p>
          </>
        )}

        {status === 'drawing' && (
          <>
            {!published && (
              <Alert tone="warning">
                Kỳ đang ở trạng thái “{EVENT_STATUS_META[event?.status]?.label ?? event?.status ?? '—'}”. Công bố thông tin phân
                bổ trước khi mở chọn ghế.
              </Alert>
            )}
            <Button
              icon={Play}
              disabled={!published}
              loading={advancing}
              onClick={() => run(() => next({ skip: false }), 'Đã mở chọn ghế — team số 1 bắt đầu lượt.')}
            >
              Mở chọn ghế
            </Button>
          </>
        )}

        {status === 'open' && (
          <>
            <div className="rounded-lg bg-emerald-50 p-3 ring-1 ring-emerald-200 ring-inset">
              <p className="text-xs text-emerald-800">Đang tới lượt</p>
              <p className="flex items-center justify-between gap-2 font-semibold text-emerald-900">
                <span className="truncate">{active?.team_name ?? '—'}</span>
                {active && <Countdown endsAt={active.turn_ends_at} offsetMs={offsetMs} className="text-lg" />}
              </p>
              {active && (
                <p className="text-xs text-emerald-800 tabular-nums">
                  {active.confirmed}/{active.quota} ghế đã chốt{active.held ? ` · đang giữ ${active.held}` : ''}
                </p>
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                icon={StepForward}
                loading={advancing}
                onClick={() => run(() => next({ skip: false }), 'Đã chuyển lượt.')}
              >
                Chuyển lượt
              </Button>
              <Button
                size="sm"
                variant="secondary"
                icon={SkipForward}
                disabled={advancing}
                onClick={() => {
                  if (window.confirm(`Bỏ lượt của ${active?.team_name ?? 'team này'}? Ghế team đang giữ sẽ được nhả.`)) {
                    run(() => next({ skip: true }), 'Đã bỏ lượt.')
                  }
                }}
              >
                Bỏ lượt
              </Button>
              <Button
                size="sm"
                variant="danger"
                icon={Flag}
                loading={finalizing}
                onClick={() => {
                  if (window.confirm('Kết thúc chọn ghế cho mọi team? Các team chưa tới lượt sẽ không chọn được nữa.')) {
                    run(() => finalize(), 'Đã kết thúc chọn ghế.')
                  }
                }}
              >
                Kết thúc
              </Button>
            </div>
            <p className="text-xs text-slate-500">
              Hết giờ, hoặc team chốt đủ quota, hệ thống tự chuyển lượt. Trưởng nhóm được báo qua email và banner
              trên cổng khi tới lượt.
            </p>
          </>
        )}

        {status === 'finalized' && (
          <>
            {missingTeams.length > 0 ? (
              <Alert tone="warning" title={`${missingTeams.length} team chưa đủ ghế`}>
                <ul className="mt-1 list-disc space-y-0.5 pl-4">
                  {missingTeams.map((order) => (
                    <li key={order.team_id}>
                      {order.team_name}: {order.confirmed}/{order.quota} ghế
                    </li>
                  ))}
                </ul>
                <p className="mt-1">Chưa xếp đủ ghế thì kỳ không chuyển sang “Đang diễn ra” được.</p>
              </Alert>
            ) : (
              <Alert tone="success" title="Đã chốt chỗ ngồi">
                Mọi team đã đủ ghế. Bấm vào ghế trên sơ đồ để ép gán, gỡ hoặc khoá ghế — mọi thay đổi đều ghi lý do.
              </Alert>
            )}
            <Button
              variant={missingTeams.length ? 'primary' : 'secondary'}
              icon={RotateCcw}
              disabled={!published}
              loading={reopening}
              onClick={() => {
                const first = missingTeams[0]?.team_name
                if (
                  window.confirm(
                    `Mở lại chọn ghế? Các team chưa đủ ghế chọn tiếp theo đúng thứ tự đã bốc thăm${first ? `, bắt đầu từ ${first}` : ''}. Team đủ ghế giữ nguyên ghế. Trưởng nhóm được báo qua email.`,
                  )
                ) {
                  run(() => reopen(), 'Đã mở lại chọn ghế cho các team chưa đủ ghế.')
                }
              }}
            >
              Mở lại chọn ghế
            </Button>
          </>
        )}
      </div>
    </Card>
  )
}
