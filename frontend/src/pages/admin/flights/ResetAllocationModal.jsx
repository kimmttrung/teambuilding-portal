import { useCallback, useState } from 'react'
import { Eraser } from 'lucide-react'
import { useResetFlightAllocation } from '../../../hooks/useFlights'
import { useToast } from '../../../context/ToastContext'
import { FLIGHT_DIRECTION_LABELS, FLIGHT_DIRECTIONS } from '../../../utils/constants'
import Alert from '../../../components/common/Alert'
import Button from '../../../components/common/Button'
import Modal from '../../../components/common/Modal'
import Textarea from '../../../components/common/Textarea'

const MIN_REASON = 3

/**
 * Bỏ toàn bộ phân bổ của một chiều, trả các chuyến về trống.
 *
 * Việc thật cần nó: hạ số ghế của một chuyến bị chặn khi còn người ngồi, nên muốn sửa sức chứa
 * cho khớp vé thật sự mua được thì phải dọn trước rồi phân bổ lại.
 */
export default function ResetAllocationModal({
  onClose,
  direction: initialDirection = FLIGHT_DIRECTIONS.OUTBOUND,
}) {
  const toast = useToast()
  const [direction, setDirection] = useState(initialDirection)
  const [includeManual, setIncludeManual] = useState(false)
  const [reason, setReason] = useState('')
  const [error, setError] = useState(null)
  const { mutateAsync: reset, isPending } = useResetFlightAllocation()

  async function submit() {
    setError(null)
    try {
      const result = await reset({ direction, reason: reason.trim(), includeManual })
      toast.success(
        `Đã bỏ ${result.removed} lượt xếp chỗ.` +
          (result.kept_manual ? ` Giữ ${result.kept_manual} bản ghi BTC xếp tay.` : ''),
      )
      onClose()
    } catch (resetError) {
      setError(resetError.message)
    }
  }

  const close = useCallback(() => {
    if (!isPending) onClose()
  }, [isPending, onClose])

  return (
    <Modal
      open
      onClose={close}
      title="Bỏ toàn bộ phân bổ của một chiều?"
      description="Các chuyến của chiều này trở về trống, sau đó sửa số ghế rồi phân bổ lại."
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="sm" disabled={isPending} onClick={onClose}>
            Huỷ
          </Button>
          <Button
            size="sm"
            variant="danger"
            icon={Eraser}
            loading={isPending}
            disabled={isPending || reason.trim().length < MIN_REASON}
            onClick={submit}
          >
            Bỏ phân bổ
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-3">
        <div className="flex gap-1 rounded-lg border border-hairline bg-surface p-1">
          {Object.entries(FLIGHT_DIRECTION_LABELS).map(([value, label]) => (
            <button
              key={value}
              type="button"
              disabled={isPending}
              onClick={() => setDirection(value)}
              className={`flex-1 rounded-md px-3 py-1.5 text-body-sm font-medium transition ${
                direction === value
                  ? 'bg-primary text-on-primary'
                  : 'text-ink-secondary hover:bg-canvas-soft'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        <Textarea
          label="Lý do"
          required
          rows={2}
          maxLength={500}
          disabled={isPending}
          value={reason}
          counterValue={reason}
          onChange={(changeEvent) => setReason(changeEvent.target.value)}
          hint="Ghi vào nhật ký — thao tác này gỡ chỗ của cả đoàn."
        />

        <label className="inline-flex cursor-pointer items-start gap-2 text-body-sm text-ink-secondary">
          <input
            type="checkbox"
            className="mt-0.5 size-4 shrink-0 accent-primary"
            disabled={isPending}
            checked={includeManual}
            onChange={(changeEvent) => setIncludeManual(changeEvent.target.checked)}
          />
          <span>
            Bỏ cả những người BTC đã xếp tay
            <span className="block text-caption text-ink-muted">
              Không tích thì các bản ghi xếp tay được giữ nguyên, như khi chạy phân bổ tự động.
            </span>
          </span>
        </label>

        <Alert tone="warning">
          Kỳ đã công bố thì CBNV sẽ thấy phần chuyến bay trở lại "đang chờ" ngay sau khi bỏ.
        </Alert>

        {error && <Alert tone="error">{error}</Alert>}
      </div>
    </Modal>
  )
}
