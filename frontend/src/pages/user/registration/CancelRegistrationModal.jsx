import { useState } from 'react'
import { Ban, Send } from 'lucide-react'
import { useCancelRegistration, useRequestCancellation } from '../../../hooks/useRegistration'
import { useToast } from '../../../context/ToastContext'
import { formatDateTime } from '../../../utils/format'
import Alert from '../../../components/common/Alert'
import Button from '../../../components/common/Button'
import Modal from '../../../components/common/Modal'
import Textarea from '../../../components/common/Textarea'

const MIN_REASON = 3

/**
 * Huỷ đăng ký theo giai đoạn kỳ (backend trả `cancel_policy`):
 * - `self`: trước công bố — hệ thống huỷ ngay, giải phóng chỗ đã xếp và báo BTC.
 * - `request`: sau công bố — gửi yêu cầu kèm lý do, chỗ vẫn giữ tới khi BTC duyệt.
 * Bắt nhập lý do vì BTC dùng lý do này để quyết chuyện phí phạt.
 */
export default function CancelRegistrationModal({ open, mode = 'self', closesAt, onClose, onDone }) {
  const [reasonCategory, setReasonCategory] = useState('')
  const [note, setNote] = useState('')
  const toast = useToast()
  const cancel = useCancelRegistration()
  const request = useRequestCancellation()
  const isRequest = mode === 'request'
  const { mutateAsync, isPending } = isRequest ? request : cancel
  const afterDeadline = closesAt ? new Date(closesAt) <= new Date() : false
  const reason = [reasonCategory, note.trim()].filter(Boolean).join(' — ')

  async function submit() {
    try {
      await mutateAsync(reason.trim())
      toast.success(
        isRequest
          ? 'Đã gửi yêu cầu huỷ tới Ban tổ chức. Kết quả sẽ báo qua email.'
          : 'Đã huỷ đăng ký. Ban tổ chức đã được thông báo.',
      )
      setReasonCategory('')
      setNote('')
      onClose()
      onDone?.()
    } catch (error) {
      toast.error(error.message)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={isRequest ? 'Gửi yêu cầu huỷ đăng ký' : 'Huỷ đăng ký tham gia'}
      description={
        isRequest
          ? 'Ban tổ chức đã công bố vé, xe, phòng — việc huỷ cần được duyệt'
          : 'Hệ thống huỷ ngay và báo Ban tổ chức'
      }
      footer={
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" size="sm" onClick={onClose}>
            Không huỷ
          </Button>
          <Button
            type="button"
            variant="danger"
            size="sm"
            icon={isRequest ? Send : Ban}
            loading={isPending}
            disabled={reason.trim().length < MIN_REASON}
            onClick={submit}
          >
            {isRequest ? 'Gửi yêu cầu huỷ' : 'Xác nhận huỷ'}
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-3.5">
        {isRequest ? (
          <Alert tone="info" title="Chỗ của bạn vẫn được giữ trong lúc chờ duyệt">
            Ban tổ chức nhận yêu cầu kèm lý do, rồi duyệt hoặc từ chối và báo bạn qua email. Chỉ khi được
            duyệt, vé máy bay, xe, phòng và ghế Gala mới được giải phóng.
          </Alert>
        ) : (
          <Alert tone="info" title="Huỷ có hiệu lực ngay">
            Chuyến bay, xe, phòng và ghế Gala đã xếp cho bạn (nếu có) được giải phóng ngay, Ban tổ chức nhận
            thông báo kèm lý do.
          </Alert>
        )}
        <div className="rounded-xl border border-hairline bg-canvas-soft px-3.5 py-3">
          <p className="text-body-sm font-semibold text-ink">Chi phí có thể bị tính</p>
          <div className="mt-2 flex flex-col gap-1 text-caption text-ink-muted">
            <div className="flex justify-between gap-3">
              <span>Vé máy bay và phòng đã đặt</span>
              <span className="font-semibold text-ink">Theo thực tế</span>
            </div>
            <p>Số cuối cùng do BTC xác nhận theo quy định chương trình.</p>
          </div>
        </div>
        <Alert
          tone="warning"
          title={afterDeadline ? 'Bạn đang huỷ sau hạn đăng ký' : 'Huỷ trước hạn đăng ký'}
        >
          Hạn đăng ký: {closesAt ? formatDateTime(closesAt) : 'theo thông báo của Ban tổ chức'}.{' '}
          {afterDeadline
            ? `Bạn có thể phải chịu chi phí vé máy bay và phòng đã đặt${
                isRequest ? ' — Ban tổ chức quyết định khi duyệt.' : '.'
              }`
            : 'Huỷ trước hạn này không mất phí.'}
        </Alert>
        <fieldset className="flex flex-col gap-2">
          <legend className="text-caption font-medium text-ink">Lý do</legend>
          <div className="grid gap-2 sm:grid-cols-3">
            {['Việc gia đình', 'Sức khoẻ', 'Công việc'].map((item) => (
              <button
                key={item}
                type="button"
                aria-pressed={reasonCategory === item}
                onClick={() => setReasonCategory((current) => (current === item ? '' : item))}
                className={`rounded-lg border px-3 py-2.5 text-left text-body-sm transition ${
                  reasonCategory === item
                    ? 'border-primary bg-[#eef6fd] font-medium text-primary'
                    : 'border-hairline bg-surface text-ink-secondary hover:border-primary'
                }`}
              >
                {item}
              </button>
            ))}
          </div>
        </fieldset>
        <Textarea
          label="Thêm ghi chú cho BTC (không bắt buộc)"
          rows={2}
          maxLength={512}
          counterValue={note}
          value={note}
          onChange={(changeEvent) => setNote(changeEvent.target.value)}
          placeholder="Bạn có thể thêm thông tin để BTC xử lý nhanh hơn"
          hint={reasonCategory ? `Lý do đã chọn: ${reasonCategory}` : `Chọn một lý do hoặc nhập ghi chú (tối thiểu ${MIN_REASON} ký tự).`}
        />
      </div>
    </Modal>
  )
}
