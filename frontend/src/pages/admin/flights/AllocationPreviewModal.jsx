import { useState } from 'react'
import { Check, Play, RotateCcw, Wand2 } from 'lucide-react'
import { useAllocateFlights } from '../../../hooks/useFlights'
import { useToast } from '../../../context/ToastContext'
import {
  ALLOCATION_FLAG_META,
  FLIGHT_DIRECTION_LABELS,
  FLIGHT_DIRECTIONS,
} from '../../../utils/constants'
import { formatPercent } from '../../../utils/format'
import Alert from '../../../components/common/Alert'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import FlagList from '../../../components/admin/FlagList'
import Modal from '../../../components/common/Modal'
import SlotBar from '../../../components/admin/SlotBar'
import Spinner from '../../../components/common/Spinner'

/**
 * Chạy phân bổ tự động: **luôn** dry-run trước, chỉ ghi khi BTC bấm "Áp dụng".
 *
 * Hai bước là cố ý, không phải rườm rà: bấm một nút mà đổi chỗ ngồi của 99 người thì không
 * ai dám bấm. Dry-run không ghi gì vào DB nên BTC thử bao nhiêu lần cũng được.
 */
export default function AllocationPreviewModal({ open, onClose, shiftCodes = {} }) {
  const toast = useToast()
  const [direction, setDirectionState] = useState(FLIGHT_DIRECTIONS.OUTBOUND)
  const [forceReallocate, setForceState] = useState(false)
  const [preview, setPreview] = useState(null)
  const [error, setError] = useState(null)
  const { mutateAsync: allocate, isPending } = useAllocateFlights()

  // Đổi chiều hoặc đổi cờ force thì bản preview cũ không còn đúng nữa: xoá ngay tại chỗ
  // đổi, không dùng effect (effect chạy sau render nên BTC sẽ thấy preview cũ loé lên).
  // Mở lại modal thì component được dựng mới, state tự sạch.
  function setDirection(value) {
    setDirectionState(value)
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
      const result = await allocate({ direction, dryRun, forceReallocate })
      if (dryRun) {
        setPreview(result)
        return
      }
      toast.success(
        `Đã ghi phân bổ ${FLIGHT_DIRECTION_LABELS[direction].toLowerCase()}: ` +
          `${result.summary.assigned} người có chỗ.`,
      )
      onClose()
    } catch (requestError) {
      setError(requestError)
    }
  }

  const blocking = (preview?.flags ?? []).filter(
    (flag) => ALLOCATION_FLAG_META[flag.type]?.blocking,
  )

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="lg"
      title="Phân bổ chuyến bay tự động"
      description="Xem trước không ghi gì vào hệ thống"
      footer={
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-slate-500">
            {preview
              ? `Seed ${preview.seed} — chạy lại cùng seed cho ra đúng kết quả này.`
              : 'Bấm "Xem trước" để chạy thử.'}
          </p>
          <div className="flex gap-2">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              icon={preview ? RotateCcw : Play}
              loading={isPending && !preview}
              onClick={() => run(true)}
            >
              {preview ? 'Chạy lại' : 'Xem trước'}
            </Button>
            <Button
              type="button"
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
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <p className="mb-1.5 text-sm font-medium text-slate-700">Chiều bay</p>
            <div className="flex gap-2">
              {Object.entries(FLIGHT_DIRECTION_LABELS).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setDirection(value)}
                  className={`flex-1 rounded-lg border-2 px-3 py-2 text-sm font-medium transition ${
                    direction === value
                      ? 'border-brand-600 bg-brand-50 text-brand-700'
                      : 'border-slate-200 text-slate-600 hover:border-slate-300'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          <label className="flex items-start gap-2.5 rounded-lg bg-slate-50 p-3">
            <input
              type="checkbox"
              className="mt-0.5 size-4 shrink-0 accent-brand-600"
              checked={forceReallocate}
              onChange={(event) => setForceReallocate(event.target.checked)}
            />
            <span className="text-xs leading-relaxed text-slate-600">
              <span className="block font-medium text-slate-900">Xếp lại cả người đã xếp tay</span>
              Mặc định giữ nguyên mọi quyết định thủ công của BTC. Bật ô này là xoá hết và để
              thuật toán xếp lại từ đầu.
            </span>
          </label>
        </div>

        {error && (
          <Alert tone="error" title="Không chạy được">
            {error.message}
          </Alert>
        )}

        {isPending && !preview && <Spinner label="Đang tính phương án…" />}

        {preview && (
          <>
            <div className="grid grid-cols-2 gap-2.5 lg:grid-cols-4">
              <Stat label="Tham gia" value={preview.summary.total_participants} />
              <Stat label="Có chỗ" value={preview.summary.assigned} tone="emerald" />
              <Stat
                label="Chưa có chỗ"
                value={preview.summary.unassigned}
                tone={preview.summary.unassigned ? 'rose' : 'slate'}
              />
              <Stat
                label="Đúng ca"
                value={formatPercent(preview.summary.shift_satisfaction_rate)}
                hint={`${preview.summary.teams_split} team bị tách`}
              />
            </div>

            {blocking.length > 0 ? (
              <Alert tone="warning" title="Có việc cần xử lý trước khi công bố">
                {blocking.length} trường hợp nghiêm trọng (không có chỗ, thiếu giấy tờ, vi phạm ca
                đã khoá). Vẫn áp dụng được, nhưng phải xử lý trước khi công bố cho CBNV.
              </Alert>
            ) : (
              <Alert tone="success">
                Không có trường hợp nghiêm trọng nào. Kết quả này áp dụng được ngay.
              </Alert>
            )}

            <section>
              <h3 className="mb-2 text-sm font-semibold text-slate-900">Từng chuyến</h3>
              <ul className="flex flex-col gap-2">
                {preview.flights.map((flight) => (
                  <li key={flight.flight_id} className="rounded-lg border border-slate-200 p-3">
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <p className="text-sm font-semibold text-slate-900">
                        {flight.flight_code}
                        <span className="ml-2 text-xs font-normal text-slate-500">
                          {shiftCodes[flight.shift_id] ?? 'chưa gán ca'}
                        </span>
                      </p>
                      <p className="text-xs text-slate-500">
                        {flight.capacity} ghế · giữ {flight.reserved}
                      </p>
                    </div>
                    <SlotBar
                      assigned={flight.assigned}
                      usable={flight.usable_capacity}
                      className="mt-2"
                    />
                    {flight.teams.length > 0 && (
                      <ul className="mt-2.5 flex flex-wrap gap-1.5">
                        {flight.teams.map((team) => (
                          <li
                            key={`${flight.flight_id}-${team.team_id ?? team.team_name}`}
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
            </section>

            <section>
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-slate-900">Cảnh báo</h3>
                <Badge tone="slate">{preview.flags.length}</Badge>
              </div>
              <FlagList flags={preview.flags} />
            </section>

            <p className="flex items-start gap-2 text-xs leading-relaxed text-slate-500">
              <Wand2 className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
              Trọng số đang dùng: giữ team {preview.params.team_weight} · đúng ca{' '}
              {preview.params.shift_weight} · phạt tách team {preview.params.split_penalty}. Đổi
              trong cấu hình kỳ, không cần sửa code.
            </p>
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
