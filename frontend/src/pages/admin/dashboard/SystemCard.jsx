import { Link } from 'react-router-dom'
import { Mail } from 'lucide-react'
import { useRagStatus } from '../../../hooks/useChat'
import { formatNumber, formatRelative } from '../../../utils/format'
import Card from '../../../components/common/Card'
import ChatMascot from '../../../components/chat/ChatMascot'

/**
 * Hai kênh tự động tới CBNV — email và trợ lý Tibi — gộp một thẻ: BTC chỉ cần biết "có đang chạy đúng
 * không". Chi tiết nằm ở trang Email và khung chat; email lỗi đã được nhắc trong "Việc cần làm".
 */
export default function SystemCard({ emails, published }) {
  return (
    <Card title="Email & trợ lý Tibi" bodyClassName="p-0">
      <EmailSection emails={emails} />
      <AssistantSection published={published} />
    </Card>
  )
}

function SectionTitle({ icon, children, action }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <p className="inline-flex items-center gap-1.5 text-xs font-semibold tracking-wide text-slate-500 uppercase">
        {icon}
        {children}
      </p>
      {action}
    </div>
  )
}

function EmailSection({ emails }) {
  return (
    <div className="px-4 py-3">
      <SectionTitle
        icon={<Mail className="size-3.5" aria-hidden="true" />}
        action={
          <Link to="/admin/email-logs" className="text-xs font-medium text-brand-700 hover:underline">
            Nhật ký
          </Link>
        }
      >
        Email
      </SectionTitle>
      <dl className="mt-2 grid grid-cols-3 gap-2">
        <Metric label="Đã gửi" value={emails.sent} />
        <Metric label="Lỗi" value={emails.failed} tone={emails.failed ? 'text-rose-700' : undefined} />
        <Metric label="Đang chờ" value={emails.queued} />
      </dl>
      {!emails.email_enabled && (
        <p className="mt-2 text-xs text-amber-700">Đang tắt gửi thật — email chỉ ghi vào nhật ký.</p>
      )}
    </div>
  )
}

function Metric({ label, value, tone = 'text-slate-900' }) {
  return (
    <div className="rounded-lg bg-slate-50 px-2.5 py-1.5">
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className={`font-semibold tabular-nums ${tone}`}>{formatNumber(value)}</dd>
    </div>
  )
}

/**
 * Nạp lại kiến thức sau khi sửa quy định / lịch trình, và NHẤT LÀ sau khi công bố — lúc đó chuyến bay,
 * xe, khách sạn, Gala mới vào knowledge base.
 */
function AssistantSection({ published }) {
  const { data, isLoading, error } = useRagStatus()

  const notEnabled = error && error.status === 404 && error.code !== 'NO_ACTIVE_EVENT'
  const stale = data && published && data.last_indexed_at && data.last_index_published_logistics === false
  const empty = data && !data.indexed_chunks

  return (
    <div className="border-t border-slate-100 px-4 py-3">
      <SectionTitle
        icon={<ChatMascot size={18} />}
        action={
          !notEnabled && (
            <Link to="/admin/settings?tab=documents" className="text-xs font-medium text-primary hover:underline">
              Nạp ở Tài liệu
            </Link>
          )
        }
      >
        Trợ lý Tibi
      </SectionTitle>

      {isLoading ? (
        <p className="mt-1.5 text-xs text-slate-500">Đang tải…</p>
      ) : notEnabled ? (
        <p className="mt-1.5 text-xs text-slate-500">Máy chủ chưa bật chatbot.</p>
      ) : error ? (
        <p className="mt-1.5 text-xs text-rose-600">{error.message}</p>
      ) : (
        <>
          <p className="mt-1.5 text-xs text-slate-500">
            <span className="font-medium text-slate-700 tabular-nums">{formatNumber(data.indexed_chunks)}</span> đoạn
            kiến thức · nạp {data.last_indexed_at ? formatRelative(data.last_indexed_at) : 'chưa lần nào'} ·{' '}
            <span className="whitespace-nowrap">
              {data.llm_configured ? data.model : 'chế độ thử (chưa có GEMINI_API_KEY)'}
            </span>
          </p>
          {(stale || empty) && (
            <p className="mt-2 rounded-md bg-amber-50 px-2.5 py-1.5 text-xs text-amber-800">
              {stale
                ? 'Đã công bố nhưng Tibi chưa biết chuyến bay, xe, khách sạn. Nạp lại ở tab Tài liệu.'
                : 'Tibi chưa có tài liệu nào để trả lời.'}
            </p>
          )}
        </>
      )}
    </div>
  )
}
