import { RefreshCw } from 'lucide-react'
import { useRagStatus, useReindexRag } from '../../../hooks/useChat'
import { useToast } from '../../../context/ToastContext'
import { formatNumber, formatRelative } from '../../../utils/format'
import Alert from '../../../components/common/Alert'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import Spinner from '../../../components/common/Spinner'
import ChatMascot from '../../../components/chat/ChatMascot'

/**
 * Kiến thức của trợ lý Tibi. Nạp lại sau khi sửa quy định / lịch trình / thông báo, và NHẤT LÀ sau khi
 * công bố — lúc đó chuyến bay, xe, khách sạn, Gala mới vào knowledge base.
 */
export default function AssistantCard({ published }) {
  const toast = useToast()
  const { data, isLoading, error } = useRagStatus()
  const { mutateAsync: reindex, isPending } = useReindexRag()

  async function run() {
    try {
      const result = await reindex()
      toast.success(
        `Đã nạp ${formatNumber(result.documents)} tài liệu (${formatNumber(result.chunks)} đoạn)` +
          (result.published_logistics ? ', gồm chuyến bay, xe, khách sạn, Gala.' : '.'),
      )
    } catch (reindexError) {
      toast.error(reindexError.message)
    }
  }

  const notEnabled = error && error.status === 404 && error.code !== 'NO_ACTIVE_EVENT'
  const stale = data && published && data.last_indexed_at && data.last_index_published_logistics === false

  return (
    <Card title="Trợ lý Tibi" description="Kiến thức chatbot dùng để trả lời CBNV" action={<ChatMascot size={30} />}>
      {isLoading ? (
        <Spinner label="Đang tải…" />
      ) : notEnabled ? (
        <p className="text-sm text-slate-500">Máy chủ chưa bật chatbot (bước 19).</p>
      ) : error ? (
        <p className="text-sm text-rose-600">{error.message}</p>
      ) : (
        <div className="flex flex-col gap-3">
          <dl className="grid grid-cols-2 gap-2 text-sm">
            <div className="rounded-lg bg-slate-50 px-3 py-2">
              <dt className="text-xs text-slate-500">Đã nạp</dt>
              <dd className="font-semibold text-slate-900 tabular-nums">{formatNumber(data.indexed_chunks)} đoạn</dd>
            </div>
            <div className="rounded-lg bg-slate-50 px-3 py-2">
              <dt className="text-xs text-slate-500">Lần nạp gần nhất</dt>
              <dd className="font-semibold text-slate-900">{data.last_indexed_at ? formatRelative(data.last_indexed_at) : 'Chưa nạp'}</dd>
            </div>
          </dl>
          <p className="text-xs text-slate-500">
            AI: {data.llm_configured ? <span className="font-medium text-slate-700">{data.model}</span> : 'chế độ thử — chưa có GEMINI_API_KEY'}
          </p>
          {(stale || (!data.indexed_chunks && !isPending)) && (
            <Alert tone="warning">
              {stale
                ? 'Đã công bố thông tin nhưng trợ lý chưa biết chuyến bay, xe, khách sạn. Nạp lại ngay.'
                : 'Trợ lý chưa có tài liệu nào để trả lời.'}
            </Alert>
          )}
        </div>
      )}
      {!notEnabled && (
        <Button size="sm" variant="secondary" icon={RefreshCw} loading={isPending} onClick={run} fullWidth className="mt-3">
          Nạp lại kiến thức
        </Button>
      )}
    </Card>
  )
}
