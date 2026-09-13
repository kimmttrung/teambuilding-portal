import { RotateCcw } from 'lucide-react'
import { EMAIL_STATUS_META } from '../../../utils/constants'
import { splitEmailError } from '../../../utils/email'
import { formatDateTime } from '../../../utils/format'
import Alert from '../../../components/common/Alert'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Modal from '../../../components/common/Modal'

/** Chi tiết một thư: trạng thái, lý do lỗi kèm cách sửa, và nội dung đã gửi. */
export default function EmailDetailModal({ log, onClose, onResend, resending }) {
  const meta = EMAIL_STATUS_META[log.status] ?? { label: log.status, tone: 'slate' }
  const { detail, hint } = splitEmailError(log.error_message)
  const failed = log.status === 'failed'

  return (
    <Modal
      open
      size="lg"
      onClose={onClose}
      title={log.subject}
      description={log.template_label}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="sm" onClick={onClose}>
            Đóng
          </Button>
          {failed && (
            <Button size="sm" icon={RotateCcw} loading={resending} disabled={resending} onClick={onResend}>
              Gửi lại
            </Button>
          )}
        </div>
      }
    >
      <div className="flex flex-col gap-3">
        <dl className="grid gap-x-4 gap-y-2.5 text-sm sm:grid-cols-2">
          <Field label="Người nhận">{log.to_email}</Field>
          <Field label="Trạng thái">
            {log.is_dev_only ? <Badge tone="slate">Chỉ ghi log</Badge> : <Badge tone={meta.tone}>{meta.label}</Badge>}
          </Field>
          <Field label="Lần thử gần nhất">{formatDateTime(log.created_at)}</Field>
          <Field label="Gửi thành công lúc">{log.sent_at ? formatDateTime(log.sent_at) : '—'}</Field>
          <Field label="Số lần gửi lại">{log.retry_count}</Field>
          <Field label="Liên quan">
            {log.related_type ? `${log.related_type} #${log.related_id}` : '—'}
          </Field>
        </dl>

        {failed && detail && (
          <Alert tone="error" title="Lý do lỗi">
            {hint && <p className="font-medium">{hint}</p>}
            <p className={`font-mono text-xs break-words ${hint ? 'mt-1 opacity-80' : ''}`}>{detail}</p>
          </Alert>
        )}
        {log.is_dev_only && (
          <Alert tone="info">
            Thư này chỉ được ghi vào nhật ký vì <code>EMAIL_ENABLED=false</code>, sẽ không tự gửi đi.
          </Alert>
        )}
        {failed && (
          <p className="text-xs text-slate-500">
            Gửi lại sẽ dựng nội dung từ dữ liệu hiện tại và gửi tới email hiện tại trong hồ sơ CBNV.
            Thư không còn phù hợp (đăng ký đã đổi, đã bổ sung giấy tờ) sẽ được bỏ qua.
          </p>
        )}

        <div>
          <p className="mb-1 text-xs tracking-wide text-slate-400 uppercase">Nội dung (bản text)</p>
          <pre className="max-h-96 overflow-auto rounded-lg bg-slate-50 p-3 font-sans text-sm whitespace-pre-wrap break-words text-slate-700 ring-1 ring-slate-200">
            {log.body_preview || '—'}
          </pre>
        </div>
      </div>
    </Modal>
  )
}

function Field({ label, children }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="mt-0.5 break-words text-slate-900">{children}</dd>
    </div>
  )
}
