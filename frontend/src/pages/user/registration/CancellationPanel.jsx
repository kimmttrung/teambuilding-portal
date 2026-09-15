import { useState } from 'react'
import { Ban, Send, Undo2 } from 'lucide-react'
import { useWithdrawCancellation } from '../../../hooks/useRegistration'
import { useToast } from '../../../context/ToastContext'
import { formatDateTime, formatRelative } from '../../../utils/format'
import Alert from '../../../components/common/Alert'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import CancelRegistrationModal from './CancelRegistrationModal'

/**
 * Khối "Huỷ tham gia" khi đăng ký đã chốt (không sửa được nữa). Nội dung theo `cancel_policy` của
 * backend — frontend không tự suy luật theo trạng thái kỳ.
 */
export default function CancellationPanel({ event, registration }) {
  const [open, setOpen] = useState(false)
  const toast = useToast()
  const { mutateAsync: withdraw, isPending } = useWithdrawCancellation()

  const policy = registration.cancel_policy
  const latest = registration.latest_cancellation
  const pending = latest?.status === 'pending'
  const rejected = latest?.status === 'rejected'

  if (!policy) return null

  if (policy === 'contact_btc') {
    return (
      <Card title="Huỷ tham gia">
        <Alert tone="warning" title="Chương trình đã bắt đầu">
          Bạn không tự huỷ được trên hệ thống nữa. Có việc đột xuất, hãy liên hệ Ban tổ chức qua{' '}
          <a href="mailto:btc@company.vn" className="font-medium underline underline-offset-2">
            btc@company.vn
          </a>{' '}
          để được xử lý ngoại lệ.
        </Alert>
      </Card>
    )
  }

  async function handleWithdraw() {
    try {
      await withdraw()
      toast.success('Đã rút yêu cầu huỷ. Đăng ký của bạn giữ nguyên.')
    } catch (error) {
      toast.error(error.message)
    }
  }

  const isRequest = policy === 'request'

  return (
    <Card
      title="Huỷ tham gia"
      description={isRequest ? 'Đã công bố — cần Ban tổ chức duyệt' : 'Chưa công bố — huỷ có hiệu lực ngay'}
    >
      {pending ? (
        <div className="flex flex-col gap-3">
          <Alert tone="warning" title="Yêu cầu huỷ đang chờ Ban tổ chức duyệt">
            Gửi{' '}
            <time dateTime={latest.requested_at} title={formatDateTime(latest.requested_at)}>
              {formatRelative(latest.requested_at)}
            </time>
            . Lý do: “{latest.reason}”. Trong lúc chờ, vé máy bay, xe, phòng và ghế Gala của bạn vẫn được giữ.
          </Alert>
          <Button variant="secondary" size="sm" icon={Undo2} loading={isPending} onClick={handleWithdraw}>
            Rút yêu cầu huỷ
          </Button>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {rejected && (
            <Alert tone="error" title="Ban tổ chức chưa duyệt yêu cầu trước của bạn">
              {latest.decision_note}
            </Alert>
          )}
          <p className="text-sm text-slate-600">
            {isRequest
              ? 'Gửi yêu cầu kèm lý do. Ban tổ chức duyệt, quyết định phí phạt theo quy định rồi báo bạn qua email.'
              : 'Hệ thống huỷ ngay, giải phóng chỗ đã xếp cho bạn và báo Ban tổ chức.'}
          </p>
          <Button variant="danger" size="sm" icon={isRequest ? Send : Ban} onClick={() => setOpen(true)}>
            {isRequest ? 'Gửi yêu cầu huỷ' : 'Huỷ tham gia'}
          </Button>
        </div>
      )}

      <CancelRegistrationModal
        open={open}
        mode={policy}
        closesAt={event.registration_closes_at}
        onClose={() => setOpen(false)}
      />
    </Card>
  )
}
