import { useState } from 'react'
import { Check, Play, RotateCcw } from 'lucide-react'
import { useAllocateBuses } from '../../../hooks/useBuses'
import { useToast } from '../../../context/ToastContext'
import { ALLOCATION_FLAG_META, BUS_LABELS } from '../../../utils/constants'
import { formatPercent } from '../../../utils/format'
import Alert from '../../../components/common/Alert'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import FlagList from '../../../components/admin/FlagList'
import Modal from '../../../components/common/Modal'
import SlotBar from '../../../components/admin/SlotBar'
import Spinner from '../../../components/common/Spinner'

/**
 * Phân xe tự động cho một chặng: luôn xem trước, chỉ ghi khi BTC bấm "Áp dụng".
 * Nơi gọi dựng component mỗi lần mở nên state luôn sạch.
 */
export default function BusAllocationModal({
  legs = [],
  defaultLegId,
  event,
  onClose,
}) {
  const toast = useToast()
  const [legId, setLegIdState] = useState(defaultLegId ?? legs[0]?.id ?? null)
  const [forceReallocate, setForceState] = useState(false)
  const [preview, setPreview] = useState(null)
  const [error, setError] = useState(null)
  const { mutateAsync: allocate, isPending } = useAllocateBuses()

  const leg = legs.find((item) => item.id === legId) ?? null

  // Đổi chặng hoặc cờ force thì bản xem trước cũ sai: xoá ngay tại chỗ đổi, không dùng effect.
  function setLegId(value) {
    setLegIdState(value)
    setPreview(null)
    setError(null)
  }

  function setForceReallocate(value) {
    setForceState(value)
    setPreview(null)
    setError(null)
  }

  async function run(dryRun) {
    setError(null)
    if (dryRun) setPreview(null)
    try {
      const result = await allocate({
        tripLegId: legId,
        dryRun,
        forceReallocate,
        expectedAssignments: dryRun ? undefined : preview.assignments,
      })
      if (dryRun) {
        setPreview(result)
        return
      }
      toast.success(
        `Đã ghi phân xe chặng ${leg?.name ?? ''}: ${result.summary.assigned} người có xe.` +
          (result.removed_stale
            ? ` Dọn ${result.removed_stale} chỗ của người không còn cần xe.`
            : ''),
      )
      onClose()
    } catch (requestError) {
      setError(requestError)
      if (!dryRun) setPreview(null)
    }
  }

  const registrationOpen =
    !event || ['draft', 'registration_open'].includes(event.status)
  const preserved =
    preview?.assignments.filter((item) => item.pinned).length ?? 0
  const blocking = (preview?.flags ?? []).filter(
    (flag) => ALLOCATION_FLAG_META[flag.type]?.blocking,
  )

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title="Phân xe tự động"
      description="Xem trước không ghi gì vào hệ thống"
      footer={
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-caption text-ink-muted">
            {preview
              ? 'Ghi thật cần kỳ đã đóng đăng ký.'
              : 'Bấm "Xem trước" để chạy thử.'}
          </p>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="md"
              icon={preview ? RotateCcw : Play}
              loading={isPending && !preview}
              disabled={!legId || isPending}
              onClick={() => run(true)}
            >
              {preview ? 'Chạy lại' : 'Xem trước'}
            </Button>
            <Button
              size="md"
              icon={Check}
              disabled={!preview || registrationOpen || isPending}
              loading={isPending && Boolean(preview)}
              onClick={() => run(false)}
            >
              {BUS_LABELS.apply}
            </Button>
          </div>
        </div>
      }
    >
      <div className="flex flex-col gap-4">
        <div>
          <p className="mb-1.5 text-body-sm font-medium text-ink-secondary">
            Chặng
          </p>
          <div className="flex flex-wrap gap-2">
            {legs.map((item) => (
              <button
                key={item.id}
                type="button"
                disabled={isPending}
                onClick={() => setLegId(item.id)}
                aria-pressed={legId === item.id}
                className={`rounded-lg border-2 px-3 py-2 text-body-sm font-medium transition ${
                  legId === item.id
                    ? 'border-primary bg-primary/5 text-primary-active'
                    : 'border-hairline text-ink-muted hover:border-hairline'
                }`}
              >
                {item.name}
              </button>
            ))}
          </div>
        </div>

        {leg?.is_airport_linked && (
          <Alert tone="info">
            Chặng gắn sân bay: người bay cùng chuyến được xếp chung xe. Phải
            phân bổ chuyến bay chiều này trước, nếu không người chưa có chuyến
            sẽ bị báo lỗi.
          </Alert>
        )}

        <label className="flex items-start gap-2.5 rounded-lg bg-canvas-soft p-3">
          <input
            type="checkbox"
            className="mt-0.5 size-4 shrink-0 accent-primary"
            disabled={isPending}
            checked={forceReallocate}
            onChange={(changeEvent) =>
              setForceReallocate(changeEvent.target.checked)
            }
          />
          <span className="text-caption leading-relaxed text-ink-muted">
            <span className="block font-medium text-ink">
              Xếp lại cả người đã xếp tay
            </span>
            Mặc định giữ nguyên mọi quyết định thủ công của BTC. Bật ô này là
            cho phép thuật toán thay đổi cả phân bổ thủ công.
          </span>
        </label>

        {registrationOpen && (
          <Alert tone="info">
            Có thể xem trước lúc này. Đóng đăng ký trước khi áp dụng phân xe.
          </Alert>
        )}

        {error && (
          <Alert tone="error" title="Không chạy được">
            {error.message}
          </Alert>
        )}

        {isPending && !preview && <Spinner label="Đang tính phương án…" />}

        {preview && (
          <>
            <Alert tone="info">
              Xem trước · chưa ghi. Giữ nguyên {preserved} bản ghi chỉnh tay
              {forceReallocate ? ' (đã bật xếp lại cả người xếp tay)' : ''}.
            </Alert>
            <div className="grid grid-cols-2 gap-2.5 lg:grid-cols-4">
              <Stat label="Cần xe" value={preview.summary.total_riders} />
              <Stat
                label="Có xe"
                value={preview.summary.assigned}
                tone="emerald"
              />
              <Stat
                label="Chưa có xe"
                value={preview.summary.unassigned}
                tone={preview.summary.unassigned ? 'rose' : 'slate'}
              />
              <Stat
                label="Xe dùng"
                value={`${preview.summary.buses_used}/${preview.summary.buses_total}`}
                hint={`lấp đầy ${formatPercent(preview.summary.utilization)}`}
              />
            </div>

            {blocking.length > 0 ? (
              <Alert tone="warning" title="Có việc cần xử lý trước khi công bố">
                {blocking.length} trường hợp nghiêm trọng (không đủ ghế, chưa có
                chuyến bay). Vẫn áp dụng được, nhưng phải xử lý trước khi công
                bố cho CBNV.
              </Alert>
            ) : (
              <Alert tone="success">
                Không có trường hợp nghiêm trọng nào trong phương án xem trước.
              </Alert>
            )}

            <section>
              <h3 className="mb-2 text-body-sm font-semibold text-ink">
                Từng xe
              </h3>
              {preview.buses.length === 0 ? (
                <p className="text-body-sm text-ink-muted">
                  Chặng này chưa có xe nào.
                </p>
              ) : (
                <ul className="flex flex-col gap-2">
                  {preview.buses.map((bus) => (
                    <li
                      key={bus.bus_id}
                      className="rounded-lg border border-hairline p-3"
                    >
                      <div className="flex flex-wrap items-baseline justify-between gap-2">
                        <p className="text-body-sm font-semibold text-ink">
                          {bus.bus_code}
                        </p>
                        <div className="flex gap-1.5">
                          {bus.flight_ids.length > 1 && (
                            <Badge tone="amber">nhiều chuyến bay</Badge>
                          )}
                          {bus.assigned === 0 && (
                            <Badge tone="slate">không dùng</Badge>
                          )}
                        </div>
                      </div>
                      <SlotBar
                        assigned={bus.assigned}
                        usable={bus.capacity}
                        className="mt-2"
                      />
                      {bus.teams.length > 0 && (
                        <ul className="mt-2.5 flex flex-wrap gap-1.5">
                          {bus.teams.map((team) => (
                            <li
                              key={`${bus.bus_id}-${team.team_id ?? team.team_name}`}
                              className="rounded-md bg-hairline px-2 py-0.5 text-caption text-ink-secondary"
                            >
                              {team.team_name}{' '}
                              <span className="text-ink-muted">
                                ({team.count})
                              </span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section>
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-body-sm font-semibold text-ink">
                  Cảnh báo
                </h3>
                <Badge tone="slate">{preview.flags.length}</Badge>
              </div>
              <FlagList flags={preview.flags} />
            </section>
          </>
        )}
      </div>
    </Modal>
  )
}

const TONES = {
  slate: 'text-ink',
  emerald: 'text-accent-green',
  rose: 'text-rose-700',
}

function Stat({ label, value, hint, tone = 'slate' }) {
  return (
    <div className="rounded-lg border border-hairline px-3 py-2">
      <p className="text-caption text-ink-muted">{label}</p>
      <p className={`mt-0.5 text-title font-bold tabular-nums ${TONES[tone]}`}>
        {value}
      </p>
      {hint && <p className="text-caption text-ink-faint">{hint}</p>}
    </div>
  )
}
