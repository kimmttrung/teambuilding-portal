import { useState } from 'react'
import { Check, Play, RotateCcw } from 'lucide-react'
import { useAllocateBuses } from '../../../hooks/useBuses'
import { useToast } from '../../../context/ToastContext'
import { ALLOCATION_FLAG_META } from '../../../utils/constants'
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
export default function BusAllocationModal({ legs = [], defaultLegId, onClose }) {
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
    try {
      const result = await allocate({ tripLegId: legId, dryRun, forceReallocate })
      if (dryRun) {
        setPreview(result)
        return
      }
      toast.success(
        `Đã ghi phân xe chặng ${leg?.name ?? ''}: ${result.summary.assigned} người có xe.` +
          (result.removed_stale ? ` Dọn ${result.removed_stale} chỗ của người không còn cần xe.` : ''),
      )
      onClose()
    } catch (requestError) {
      setError(requestError)
    }
  }

  const blocking = (preview?.flags ?? []).filter((flag) => ALLOCATION_FLAG_META[flag.type]?.blocking)

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title="Phân xe tự động"
      description="Xem trước không ghi gì vào hệ thống"
      footer={
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-slate-500">
            {preview ? 'Ghi thật cần kỳ đã đóng đăng ký.' : 'Bấm "Xem trước" để chạy thử.'}
          </p>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              icon={preview ? RotateCcw : Play}
              loading={isPending && !preview}
              disabled={!legId}
              onClick={() => run(true)}
            >
              {preview ? 'Chạy lại' : 'Xem trước'}
            </Button>
            <Button
              size="sm"
              icon={Check}
              disabled={!preview}
              loading={isPending && Boolean(preview)}
              onClick={() => run(false)}
            >
              Áp dụng vào hệ thống
            </Button>
          </div>
        </div>
      }
    >
      <div className="flex flex-col gap-4">
        <div>
          <p className="mb-1.5 text-sm font-medium text-slate-700">Chặng</p>
          <div className="flex flex-wrap gap-2">
            {legs.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setLegId(item.id)}
                aria-pressed={legId === item.id}
                className={`rounded-lg border-2 px-3 py-2 text-sm font-medium transition ${
                  legId === item.id
                    ? 'border-brand-600 bg-brand-50 text-brand-700'
                    : 'border-slate-200 text-slate-600 hover:border-slate-300'
                }`}
              >
                {item.name}
              </button>
            ))}
          </div>
        </div>

        {leg?.is_airport_linked && (
          <Alert tone="info">
            Chặng gắn sân bay: người bay cùng chuyến được xếp chung xe. Phải phân bổ chuyến bay chiều này
            trước, nếu không người chưa có chuyến sẽ bị báo lỗi.
          </Alert>
        )}

        <label className="flex items-start gap-2.5 rounded-lg bg-slate-50 p-3">
          <input
            type="checkbox"
            className="mt-0.5 size-4 shrink-0 accent-brand-600"
            checked={forceReallocate}
            onChange={(changeEvent) => setForceReallocate(changeEvent.target.checked)}
          />
          <span className="text-xs leading-relaxed text-slate-600">
            <span className="block font-medium text-slate-900">Xếp lại cả người đã xếp tay</span>
            Mặc định giữ nguyên mọi quyết định thủ công của BTC. Bật ô này là xoá hết và để thuật toán
            xếp lại từ đầu.
          </span>
        </label>

        {error && (
          <Alert tone="error" title="Không chạy được">
            {error.message}
          </Alert>
        )}

        {isPending && !preview && <Spinner label="Đang tính phương án…" />}

        {preview && (
          <>
            <div className="grid grid-cols-2 gap-2.5 lg:grid-cols-4">
              <Stat label="Cần xe" value={preview.summary.total_riders} />
              <Stat label="Có xe" value={preview.summary.assigned} tone="emerald" />
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
                {blocking.length} trường hợp nghiêm trọng (không đủ ghế, chưa có chuyến bay). Vẫn áp dụng
                được, nhưng phải xử lý trước khi công bố cho CBNV.
              </Alert>
            ) : (
              <Alert tone="success">Không có trường hợp nghiêm trọng nào. Kết quả này áp dụng được ngay.</Alert>
            )}

            <section>
              <h3 className="mb-2 text-sm font-semibold text-slate-900">Từng xe</h3>
              {preview.buses.length === 0 ? (
                <p className="text-sm text-slate-500">Chặng này chưa có xe nào.</p>
              ) : (
                <ul className="flex flex-col gap-2">
                  {preview.buses.map((bus) => (
                    <li key={bus.bus_id} className="rounded-lg border border-slate-200 p-3">
                      <div className="flex flex-wrap items-baseline justify-between gap-2">
                        <p className="text-sm font-semibold text-slate-900">{bus.bus_code}</p>
                        <div className="flex gap-1.5">
                          {bus.flight_ids.length > 1 && <Badge tone="amber">nhiều chuyến bay</Badge>}
                          {bus.assigned === 0 && <Badge tone="slate">không dùng</Badge>}
                        </div>
                      </div>
                      <SlotBar assigned={bus.assigned} usable={bus.capacity} className="mt-2" />
                      {bus.teams.length > 0 && (
                        <ul className="mt-2.5 flex flex-wrap gap-1.5">
                          {bus.teams.map((team) => (
                            <li
                              key={`${bus.bus_id}-${team.team_id ?? team.team_name}`}
                              className="rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-700"
                            >
                              {team.team_name} <span className="text-slate-500">({team.count})</span>
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
                <h3 className="text-sm font-semibold text-slate-900">Cảnh báo</h3>
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
  slate: 'text-slate-900',
  emerald: 'text-emerald-700',
  rose: 'text-rose-700',
}

function Stat({ label, value, hint, tone = 'slate' }) {
  return (
    <div className="rounded-lg border border-slate-200 px-3 py-2">
      <p className="text-xs text-slate-500">{label}</p>
      <p className={`mt-0.5 text-lg font-bold tabular-nums ${TONES[tone]}`}>{value}</p>
      {hint && <p className="text-xs text-slate-400">{hint}</p>}
    </div>
  )
}
