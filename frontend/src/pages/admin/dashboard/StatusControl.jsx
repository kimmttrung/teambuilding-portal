import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, Undo2 } from 'lucide-react'
import { useChangeEventStatus } from '../../../hooks/useDashboard'
import { useToast } from '../../../context/ToastContext'
import { STATUS_CHANGE_HINTS } from '../../../utils/constants'
import Alert from '../../../components/common/Alert'
import Button from '../../../components/common/Button'
import Modal from '../../../components/common/Modal'
import Textarea from '../../../components/common/Textarea'

const NOTIFY_SCOPE_LABELS = {
  everyone: 'mọi CBNV đang có tài khoản',
  participants: 'mọi CBNV đang tham gia kỳ này',
}

/**
 * Nút chuyển trạng thái kỳ, đặt ngay trên dải tiêu đề dashboard. Chỉ hiện các bước backend cho phép
 * (không nhảy cóc); bước lùi là ngoại lệ nên nhạt hơn và đứng trước nút chính.
 * Luôn qua hộp thoại xác nhận: một cú bấm nhầm "công bố" là 120 người thấy phân bổ dở dang.
 */
export default function StatusControl({ event, checklist, gala }) {
  const [target, setTarget] = useState(null)

  if (event.next_statuses.length === 0) {
    return <p className="text-sm text-slate-500">Kỳ đã kết thúc, không còn bước nào.</p>
  }

  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        {event.next_statuses
          .filter((next) => !next.is_forward)
          .map((next) => (
            <Button
              key={next.status}
              variant="ghost"
              size="sm"
              icon={Undo2}
              title="Bước lùi được ghi nhật ký; lý do tuỳ chọn"
              onClick={() => setTarget(next)}
            >
              Quay lại: {next.label}
            </Button>
          ))}
        {event.next_statuses
          .filter((next) => next.is_forward)
          .map((next) => (
            <Button key={next.status} size="sm" icon={ArrowRight} onClick={() => setTarget(next)}>
              Chuyển sang: {next.label}
            </Button>
          ))}
      </div>

      {target && (
        <StatusChangeDialog
          key={target.status}
          event={event}
          target={target}
          checklist={checklist}
          gala={gala}
          onClose={() => setTarget(null)}
        />
      )}
    </>
  )
}

function StatusChangeDialog({ event, target, checklist, gala, onClose }) {
  const toast = useToast()
  const { mutateAsync, isPending } = useChangeEventStatus()
  const [reason, setReason] = useState('')
  // Mặc định KHÔNG gửi: BTC tích thì mới gửi, tránh spam CBNV khi thử nghiệm / bấm nhầm rồi lùi.
  const [notify, setNotify] = useState(false)
  const [error, setError] = useState(null)

  const publishing = target.status === 'information_published'
  // Xe lệch giờ bay là chặn CỨNG ở backend (TRANSPORT_TIME_MISMATCH): công bố lúc đó thì
  // lịch trình CBNV nhìn thấy tự mâu thuẫn. Các mục còn lại chỉ là nhắc việc.
  const timingGap = publishing ? checklist.find((item) => item.key === 'transport_timing' && !item.done) : null
  const blockers = publishing
    ? checklist.filter((item) => item.required && !item.done && item.key !== 'transport_timing')
    : []
  // Backend chặn cứng (GALA_SEATING_INCOMPLETE); báo trước để BTC khỏi bấm rồi mới biết.
  const galaGaps =
    target.status === 'event_started' && gala?.configured
      ? [
          gala.selection_status === 'open' && 'Các team vẫn đang chọn ghế',
          gala.teams_missing > 0 && `${gala.teams_missing} team chưa đủ ghế`,
          gala.unseated > 0 && `${gala.unseated} người tham gia chưa có ghế cụ thể`,
        ].filter(Boolean)
      : []

  async function submit() {
    setError(null)
    try {
      await mutateAsync({
        eventId: event.id,
        status: target.status,
        reason: reason.trim() || undefined,
        notify,
      })
      toast.success(
        `Đã chuyển kỳ sang "${target.label}".${notify ? ' Email báo CBNV đang được gửi.' : ''}`,
      )
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
            disabled={isPending || galaGaps.length > 0 || Boolean(timingGap)}
            onClick={submit}
          >
            Xác nhận
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-3">
        <p className="text-sm text-slate-700">{STATUS_CHANGE_HINTS[target.status]}</p>

        {galaGaps.length > 0 && (
          <Alert tone="error" title="Chưa xếp xong chỗ ngồi Gala">
            <ul className="mt-1 list-disc space-y-0.5 pl-4">
              {galaGaps.map((text) => (
                <li key={text}>{text}</li>
              ))}
            </ul>
            <p className="mt-1">
              Xếp đủ ghế ở{' '}
              <Link to="/admin/gala" className="font-medium underline">
                màn hình Gala Dinner
              </Link>{' '}
              (mở lại chọn ghế nếu cần) rồi chuyển trạng thái.
            </p>
          </Alert>
        )}

        {timingGap && (
          <Alert tone="error" title="Xe đưa đón lệch giờ chuyến bay">
            <p>{timingGap.detail}</p>
            <p className="mt-1">
              Sửa giờ xe hoặc chuyển hành khách ở{' '}
              <Link to="/admin/buses" className="font-medium underline">
                màn hình Xe đưa đón
              </Link>{' '}
              rồi công bố.
            </p>
          </Alert>
        )}

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

        <Textarea
          label={target.is_forward ? 'Ghi chú (không bắt buộc)' : 'Lý do (không bắt buộc)'}
          rows={2}
          maxLength={1000}
          value={reason}
          counterValue={reason}
          onChange={(changeEvent) => setReason(changeEvent.target.value)}
          hint={
            notify
              ? 'Ghi vào nhật ký và in trong email gửi CBNV.'
              : 'Ghi vào nhật ký để cả BTC biết vì sao đổi trạng thái.'
          }
        />

        <label className="inline-flex cursor-pointer items-start gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            className="mt-0.5 size-4 shrink-0 accent-brand-600"
            checked={notify}
            onChange={(changeEvent) => setNotify(changeEvent.target.checked)}
          />
          <span>
            Gửi email báo {NOTIFY_SCOPE_LABELS[target.notify_scope] ?? NOTIFY_SCOPE_LABELS.participants}
          </span>
        </label>

        {error && <Alert tone="error">{error}</Alert>}
      </div>
    </Modal>
  )
}
