import skipIcon from '../../../assets/gala/skip.svg'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import {
  useDrawGala,
  useFinalizeGala,
  useNextGalaTurn,
  useReopenGala,
} from '../../../hooks/useGala'
import { useToast } from '../../../context/ToastContext'
import {
  GALA_UI,
  EVENT_STATUS,
  EVENT_STATUS_META,
  GALA_SELECTION_STATUS_META,
} from '../../../utils/constants'
import { galaDrawSchema } from '../../../utils/schemas'
import Alert from '../../../components/common/Alert'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import Input from '../../../components/common/Input'
import Modal from '../../../components/common/Modal'
import Countdown from '../../../components/gala/Countdown'

const STATUS_ORDER = Object.values(EVENT_STATUS)
export default function GalaControlPanel({ view, event, offsetMs }) {
  const toast = useToast()
  const { mutateAsync: draw, isPending: drawing } = useDrawGala()
  const { mutateAsync: next, isPending: advancing } = useNextGalaTurn()
  const { mutateAsync: finalize, isPending: finalizing } = useFinalizeGala()
  const { mutateAsync: reopen, isPending: reopening } = useReopenGala()
  const [confirmation, setConfirmation] = useState(null)
  const [actionError, setActionError] = useState(null)
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(galaDrawSchema),
    defaultValues: { seed: '' },
    mode: 'onTouched',
  })
  const status = view.layout.selection_status
  const meta = GALA_SELECTION_STATUS_META[status] ?? GALA_SELECTION_STATUS_META.closed
  const active = view.draw.orders.find((order) => order.team_id === view.draw.active_team_id)
  const missingTeams = view.draw.orders.filter((order) => order.confirmed < order.quota)
  const published = Boolean(
    event &&
    STATUS_ORDER.indexOf(event.status) >= STATUS_ORDER.indexOf(EVENT_STATUS.INFORMATION_PUBLISHED),
  )
  const busy = drawing || advancing || finalizing || reopening
  async function run(action, message) {
    setActionError(null)
    try {
      await action()
      toast.success(message)
      setConfirmation(null)
    } catch (err) {
      setActionError(err.message)
    }
  }
  function drawOrder(values) {
    const action = () => draw(values.seed ? Number(values.seed) : null)
    if (status === 'drawing')
      setConfirmation({
        title: 'Bốc thăm lại?',
        description: 'Thứ tự hiện tại sẽ được thay bằng kết quả mới.',
        action,
        message: 'Đã bốc thăm lại.',
      })
    else run(action, 'Đã bốc thăm thứ tự team.')
  }
  return (
    <>
      {status === 'open' ? (
        <section
          aria-label="Điều hành lượt Gala"
          className="rounded-xl bg-secondary p-5 text-on-primary sm:p-6"
        >
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="mb-2 text-caption text-on-primary/75">
                Lượt {active?.position ?? '—'}/{view.draw.orders.length}
              </p>
              <h2 className="text-title">{active?.team_name ?? 'Đang chuyển lượt'}</h2>
              <p className="mt-1 text-caption text-on-primary/75">
                {active?.leader_name ?? 'Chưa có Trưởng nhóm'} · {active?.confirmed ?? 0}/
                {active?.quota ?? 0} ghế đã chốt{active?.held ? ` · giữ ${active.held}` : ''}
              </p>
            </div>
            <Countdown
              endsAt={active?.turn_ends_at}
              offsetMs={offsetMs}
              className="text-heading-1 font-bold sm:text-display-2"
            />
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button
              variant="secondary"
              shape="pill"
              disabled={busy}
              onClick={() =>
                setConfirmation({
                  title: 'Chuyển lượt?',
                  description:
                    'Lượt hiện tại kết thúc, ghế đang giữ được nhả và team kế tiếp bắt đầu.',
                  action: () => next({ skip: false }),
                  message: 'Đã chuyển lượt.',
                })
              }
            >
              {GALA_UI.advance}
            </Button>
            <Button
              variant="ghost"
              shape="pill"
              className="bg-surface text-ink hover:bg-canvas-soft"
              disabled={busy}
              onClick={() =>
                setConfirmation({
                  title: `Bỏ lượt ${active?.team_name ?? ''}?`,
                  description: 'Ghế đang giữ sẽ được nhả. Các ghế đã xác nhận được giữ nguyên.',
                  action: () => next({ skip: true }),
                  message: 'Đã bỏ lượt.',
                })
              }
            >
              <img src={skipIcon} alt="" />{GALA_UI.skip}
            </Button>
            <Button
              variant="ghost"
              shape="pill"
              className="text-on-primary hover:bg-on-primary/10"
              disabled={busy}
              onClick={() =>
                setConfirmation({
                  title: 'Kết thúc chọn ghế?',
                  description: 'Các team còn chờ sẽ không chọn ghế được cho tới khi BTC mở lại.',
                  action: () => finalize(),
                  message: 'Đã kết thúc chọn ghế.',
                })
              }
            >
              {GALA_UI.finalize}
            </Button>
          </div>
          <p className="mt-3 text-xs text-on-primary/75">
            Hết giờ hoặc chốt đủ quota, hệ thống tự chuyển lượt.
          </p>
        </section>
      ) : (
        <Card title="Điều hành chọn ghế" action={<Badge tone={meta.tone}>{meta.label}</Badge>}>
          <div className="space-y-4">
            {['closed', 'drawing'].includes(status) && (
              <form onSubmit={handleSubmit(drawOrder)} noValidate className="space-y-3">
                <Input
                  label="Seed (tuỳ chọn)"
                  type="number"
                  min={1}
                  max={2147483647}
                  placeholder="Để trống = ngẫu nhiên"
                  error={errors.seed?.message}
                  {...register('seed')}
                />
                {view.layout.draw_seed != null && (
                  <p className="text-caption text-ink-muted">
                    Seed gần nhất: {view.layout.draw_seed}
                  </p>
                )}
                <p className="text-caption text-ink-muted">
                  Quota luôn tính từ số người đang tham gia của mỗi team.
                </p>
                <Button type="submit" disabled={busy} loading={drawing}>
                  {status === 'drawing' ? 'Bốc thăm lại' : 'Bốc thăm thứ tự team'}
                </Button>
              </form>
            )}
            {status === 'drawing' && (
              <>
                {!published && (
                  <Alert tone="warning">
                    Kỳ đang “{EVENT_STATUS_META[event?.status]?.label ?? 'chưa công bố'}”. Công bố
                    thông tin trước khi mở chọn ghế.
                  </Alert>
                )}
                <Button
                  variant="secondary"
                  disabled={busy || !published}
                  loading={advancing}
                  onClick={() => run(() => next({ skip: false }), 'Đã mở chọn ghế.')}
                >
                  Mở chọn ghế
                </Button>
              </>
            )}
            {status === 'finalized' && (
              <>
                <Alert
                  tone={missingTeams.length ? 'warning' : 'success'}
                  title={
                    missingTeams.length
                      ? `${missingTeams.length} team chưa đủ ghế`
                      : 'Đã chốt chỗ ngồi'
                  }
                >
                  {missingTeams.length
                    ? missingTeams
                        .map((order) => `${order.team_name}: ${order.confirmed}/${order.quota}`)
                        .join(' · ')
                    : 'Xếp thành viên vào các ghế đã xác nhận.'}
                </Alert>
                <Button
                  variant="secondary"
                  disabled={busy || !published || !missingTeams.length}
                  loading={reopening}
                  onClick={() =>
                    setConfirmation({
                      title: 'Mở lại chọn ghế?',
                      description:
                        'Team còn thiếu chọn tiếp theo thứ tự đã bốc; team đủ ghế giữ nguyên chỗ.',
                      action: () => reopen(),
                      message: 'Đã mở lại chọn ghế.',
                    })
                  }
                >
                  Mở lại chọn ghế
                </Button>
              </>
            )}
          </div>
        </Card>
      )}
      {actionError && !confirmation && <Alert tone="error">{actionError}</Alert>}
      {confirmation && (
        <Modal
          open
          title={confirmation.title}
          description={confirmation.description}
          onClose={() => setConfirmation(null)}
          footer={
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setConfirmation(null)}>
                {GALA_UI.cancel}
              </Button>
              <Button loading={busy} onClick={() => run(confirmation.action, confirmation.message)}>
                Xác nhận
              </Button>
            </div>
          }
        >
          {actionError && <Alert tone="error">{actionError}</Alert>}
        </Modal>
      )}
    </>
  )
}
