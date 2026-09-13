import { useState } from 'react'
import { ArrowRight, Undo2 } from 'lucide-react'
import { useChangeEventStatus } from '../../../hooks/useDashboard'
import { useToast } from '../../../context/ToastContext'
import { EVENT_STATUS_META, STATUS_CHANGE_HINTS } from '../../../utils/constants'
import Alert from '../../../components/common/Alert'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import Modal from '../../../components/common/Modal'
import Textarea from '../../../components/common/Textarea'

/**
 * Chuyển trạng thái kỳ. Chỉ hiện các bước backend cho phép (không nhảy cóc), bước tiến trước.
 * Luôn qua hộp thoại xác nhận: một cú bấm nhầm "công bố" là 120 người thấy phân bổ dở dang.
 */
export default function StatusControl({ event, checklist }) {
  const [target, setTarget] = useState(null)
  const meta = EVENT_STATUS_META[event.status] ?? { tone: 'slate' }

  return (
    <>
      <Card title="Trạng thái chương trình" action={<Badge tone={meta.tone}>{event.status_label}</Badge>}>
        {event.next_statuses.length === 0 ? (
          <p className="text-sm text-slate-500">Kỳ đã kết thúc, không còn bước nào.</p>
        ) : (
          <div className="flex flex-col gap-2">
            {event.next_statuses.map((next) => (
              <Button
                key={next.status}
                variant={next.is_forward ? 'primary' : 'secondary'}
                size="sm"
                icon={next.is_forward ? ArrowRight : Undo2}
                fullWidth
                onClick={() => setTarget(next)}
              >
                {next.is_forward ? `Chuyển sang: ${next.label}` : `Quay lại: ${next.label}`}
              </Button>
            ))}
          </div>
        )}
        <p className="mt-3 text-xs text-slate-400">Mỗi lần chuyển đều ghi nhật ký. Bước lùi phải nêu lý do.</p>
      </Card>

      {target && (
        <StatusChangeDialog
          key={target.status}
          event={event}
          target={target}
          checklist={checklist}
          onClose={() => setTarget(null)}
        />
      )}
    </>
  )
}

const MIN_REASON = 3

function StatusChangeDialog({ event, target, checklist, onClose }) {
  const toast = useToast()
  const { mutateAsync, isPending } = useChangeEventStatus()
  const [reason, setReason] = useState('')
  const [error, setError] = useState(null)

  const blockers =
    target.status === 'information_published'
      ? checklist.filter((item) => item.required && !item.done)
      : []
  const reasonMissing = target.requires_reason && reason.trim().length < MIN_REASON

  async function submit() {
    setError(null)
    try {
      await mutateAsync({
        eventId: event.id,
        status: target.status,
        reason: reason.trim() || undefined,
      })
      toast.success(`Đã chuyển kỳ sang "${target.label}".`)
      onClose()
    } catch (changeError) {
      setError(changeError.message)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={target.is_forward ? `Chuyển sang "${target.label}"?` : `Quay lại "${target.label}"?`}
      description={`Hiện tại: ${event.status_label}`}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="sm" onClick={onClose}>
            Huỷ
          </Button>
          <Button
            size="sm"
            variant={target.is_forward ? 'primary' : 'danger'}
            loading={isPending}
            disabled={reasonMissing || isPending}
            onClick={submit}
          >
            Xác nhận
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-3">
        <p className="text-sm text-slate-700">{STATUS_CHANGE_HINTS[target.status]}</p>

        {blockers.length > 0 && (
          <Alert tone="warning" title={`Còn ${blockers.length} việc chưa xong`}>
            <ul className="mt-1 list-disc space-y-0.5 pl-4">
              {blockers.map((item) => (
                <li key={item.key}>
                  {item.label}
                  {item.detail ? ` — ${item.detail}` : ''}
                </li>
              ))}
            </ul>
            <p className="mt-1">Vẫn công bố được, nhưng CBNV sẽ thấy phần chưa xếp là "đang chờ".</p>
          </Alert>
        )}

        {target.requires_reason && (
          <Textarea
            label="Lý do"
            required
            rows={3}
            maxLength={1000}
            value={reason}
            counterValue={reason}
            onChange={(changeEvent) => setReason(changeEvent.target.value)}
            hint="Ghi vào nhật ký để cả BTC biết vì sao lùi trạng thái."
          />
        )}

        {error && <Alert tone="error">{error}</Alert>}
      </div>
    </Modal>
  )
}
