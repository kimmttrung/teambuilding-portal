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
  const [reason, setReason] = useState('')
  const toast = useToast()
  const cancel = useCancelRegistration()
  const request = useRequestCancellation()
  const isRequest = mode === 'request'
  const { mutateAsync, isPending } = isRequest ? request : cancel
  const afterDeadline = closesAt ? new Date(closesAt) <= new Date() : false

  async function submit() {
    try {
      await mutateAsync(reason.trim())
      toast.success(
        isRequest
          ? 'Đã gửi yêu cầu huỷ tới Ban tổ chức. Kết quả sẽ báo qua email.'
          : 'Đã huỷ đăng ký. Ban tổ chức đã được thông báo.',
      )
      setReason('')
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
        <Alert
          tone="warning"
          title={afterDeadline ? 'Bạn đang huỷ sau hạn đăng ký' : 'Huỷ sau hạn đăng ký có thể phải chịu chi phí'}
        >
          Hạn đăng ký: {closesAt ? formatDateTime(closesAt) : 'theo thông báo của Ban tổ chức'}.{' '}
          {afterDeadline
            ? `Theo quy định chương trình, bạn có thể phải chịu chi phí vé máy bay và phòng đã đặt${
                isRequest ? ' — Ban tổ chức quyết định khi duyệt.' : '.'
              }`
            : 'Huỷ trước hạn này không mất phí.'}
        </Alert>
        <Textarea
          label="Lý do huỷ"
          required
          rows={3}
          maxLength={512}
          counterValue={reason}
          value={reason}
          onChange={(changeEvent) => setReason(changeEvent.target.value)}
          placeholder="Ví dụ: trùng lịch công tác, lý do sức khoẻ…"
          hint={`Tối thiểu ${MIN_REASON} ký tự. Ban tổ chức đọc lý do này khi xử lý.`}
        />
      </div>
    </Modal>
  )
}
