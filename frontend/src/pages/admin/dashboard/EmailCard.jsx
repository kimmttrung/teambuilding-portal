import { Link } from 'react-router-dom'
import { Mail } from 'lucide-react'
import { formatNumber } from '../../../utils/format'
import Card from '../../../components/common/Card'

export default function EmailCard({ emails }) {
  return (
    <Card
      title="Email thông báo"
      action={
        <Link to="/admin/email-logs" className="inline-flex items-center gap-1 text-xs font-medium text-brand-700 hover:underline">
          <Mail className="size-3.5" aria-hidden="true" />
          Nhật ký
        </Link>
      }
    >
      <dl className="grid grid-cols-3 gap-2">
        <Metric label="Đã gửi" value={emails.sent} />
        <Metric label="Lỗi" value={emails.failed} tone={emails.failed ? 'text-rose-700' : undefined} />
        <Metric label="Đang chờ" value={emails.queued} />
      </dl>
      {emails.failed > 0 && (
        <Link
          to="/admin/email-logs?status=failed"
          className="mt-2 inline-block text-xs font-medium text-rose-700 hover:underline"
        >
          Xem {formatNumber(emails.failed)} thư lỗi và gửi lại
        </Link>
      )}
      {!emails.email_enabled && (
        <p className="mt-3 border-t border-slate-100 pt-3 text-xs text-amber-700">
          Đang tắt gửi thật (<code>EMAIL_ENABLED=false</code>): email chỉ ghi vào nhật ký.
        </p>
      )}
    </Card>
  )
}

function Metric({ label, value, tone = 'text-slate-900' }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className={`text-lg font-semibold tabular-nums ${tone}`}>{formatNumber(value)}</dd>
    </div>
  )
}
