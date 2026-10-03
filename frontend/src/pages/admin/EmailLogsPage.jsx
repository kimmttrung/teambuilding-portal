import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ChevronLeft, ChevronRight, Eye, Inbox, RotateCcw, X } from 'lucide-react'
import { useEmailLogs, useEmailStats, useResendEmails } from '../../hooks/useEmailLogs'
import { useToast } from '../../context/ToastContext'
import { EMAIL_STATUS_META } from '../../utils/constants'
import { isInFlight, splitEmailError } from '../../utils/email'
import { formatDateTime, formatNumber } from '../../utils/format'
import Alert from '../../components/common/Alert'
import Badge from '../../components/common/Badge'
import Button from '../../components/common/Button'
import Card from '../../components/common/Card'
import EmptyState from '../../components/common/EmptyState'
import Modal from '../../components/common/Modal'
import PageHeader from '../../components/common/PageHeader'
import SearchBox from '../../components/common/SearchBox'
import Select from '../../components/common/Select'
import Spinner from '../../components/common/Spinner'
import EmailDetailModal from './emails/EmailDetailModal'

const PAGE_SIZE = 30
const FILTER_KEYS = ['status', 'template', 'q']
const STATUS_ORDER = ['sent', 'failed', 'queued']

/**
 * Nhật ký email: BTC trả lời được "tôi không nhận được mail" và gửi lại thư lỗi.
 * Bộ lọc nằm trên URL để dashboard và hộp thoại nhắc việc dẫn thẳng tới đúng nhóm thư.
 */
export default function EmailLogsPage() {
  const toast = useToast()
  const [searchParams, setSearchParams] = useSearchParams()
  const page = Math.max(Number(searchParams.get('page')) || 1, 1)
  const filters = Object.fromEntries(
    FILTER_KEYS.map((key) => [key, searchParams.get(key)]).filter(([, value]) => value),
  )
  const params = { ...filters, page, page_size: PAGE_SIZE }

  const { data, isLoading, isFetching, error } = useEmailLogs(params)
  const inFlight = Boolean(data?.items.some(isInFlight))
  const { data: stats } = useEmailStats({ poll: inFlight })
  const { mutateAsync: resend, isPending: resending } = useResendEmails()

  const [viewing, setViewing] = useState(null)
  const [confirmAll, setConfirmAll] = useState(false)

  function update(changes) {
    const next = new URLSearchParams(searchParams)
    for (const [key, value] of Object.entries(changes)) {
      if (value === null || value === undefined || value === '') next.delete(key)
      else next.set(key, String(value))
    }
    if (!('page' in changes)) next.delete('page')
    setSearchParams(next, { replace: true })
  }

  async function resendEmails(ids) {
    try {
      const result = await resend(ids)
      const skipped = result.skipped.length
      if (result.queued) {
        toast.success(
          `Đã gửi lại ${result.queued} thư${skipped ? `, bỏ qua ${skipped} thư không còn phù hợp` : ''}.`,
        )
      } else {
        toast.error(result.skipped[0]?.message ?? 'Không có thư nào để gửi lại.')
      }
      return result
    } catch (resendError) {
      toast.error(resendError.message)
      return null
    }
  }

  const templateOptions = Object.entries(stats?.template_labels ?? {}).map(([value, label]) => ({
    value,
    label,
  }))
  const totalPages = data ? Math.max(Math.ceil(data.total / PAGE_SIZE), 1) : 1
  const hasFilters = Object.keys(filters).length > 0

  return (
    <>
      <PageHeader
        title="Nhật ký email"
        description="Mọi email hệ thống đã gửi hoặc định gửi cho CBNV"
        action={
          stats?.failed ? (
            <Button variant="secondary" icon={RotateCcw} onClick={() => setConfirmAll(true)}>
              Gửi lại {formatNumber(stats.failed)} thư lỗi
            </Button>
          ) : undefined
        }
      />

      <div className="flex flex-col gap-4">
        {stats && !stats.email_enabled && (
          <Alert tone="info">
            Đang tắt gửi thật (<code>EMAIL_ENABLED=false</code>): thư chỉ được ghi vào nhật ký.
          </Alert>
        )}

        <div className="flex flex-wrap items-end gap-x-4 gap-y-3">
          <div
            className="flex max-w-full overflow-x-auto rounded-full bg-black/5 p-1"
            role="group"
            aria-label="Lọc theo trạng thái"
          >
            <StatusTab label="Tất cả" value={stats?.total} active={!filters.status} onClick={() => update({ status: null })} />
            {STATUS_ORDER.map((status) => (
              <StatusTab
                key={status}
                label={EMAIL_STATUS_META[status].label}
                value={stats?.[status]}
                alert={status === 'failed' && Boolean(stats?.failed)}
                active={filters.status === status}
                onClick={() => update({ status })}
              />
            ))}
          </div>
          <div className="min-w-56 flex-1">
            <SearchBox
              key={filters.q ?? ''}
              initial={filters.q ?? ''}
              placeholder="Email người nhận hoặc tiêu đề"
              onSearch={(q) => update({ q })}
            />
          </div>
          <div className="w-full sm:w-56">
            <Select
              aria-label="Loại thư"
              placeholder="Mọi loại thư"
              value={filters.template ?? ''}
              onChange={(changeEvent) => update({ template: changeEvent.target.value })}
              options={templateOptions}
            />
          </div>
          {hasFilters && (
            <Button
              variant="ghost"
              size="sm"
              icon={X}
              onClick={() => setSearchParams(new URLSearchParams(), { replace: true })}
            >
              Xoá bộ lọc
            </Button>
          )}
          {isFetching && !isLoading && <span className="text-caption text-ink-faint">Đang cập nhật…</span>}
        </div>

        {isLoading ? (
          <Spinner label="Đang tải nhật ký…" />
        ) : error ? (
          <Alert tone="error" title="Không tải được nhật ký email">
            {error.message}
          </Alert>
        ) : data.items.length === 0 ? (
          <Card>
            <EmptyState
              icon={Inbox}
              title="Không có thư nào"
              description={hasFilters ? 'Thử bỏ bớt bộ lọc.' : 'Hệ thống chưa gửi email nào.'}
            />
          </Card>
        ) : (
          <Card bodyClassName="p-0">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-caption">
                <thead>
                  <tr className="border-b border-hairline bg-canvas-soft text-left text-eyebrow whitespace-nowrap text-ink-muted">
                    <th scope="col" className="w-36 px-4 py-2.5">Lúc</th>
                    <th scope="col" className="px-4 py-2.5">Email</th>
                    <th scope="col" className="w-64 px-4 py-2.5">Kết quả</th>
                    <th scope="col" className="px-4 py-2.5 text-right">
                      <span className="sr-only">Thao tác</span>
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-hairline">
                  {data.items.map((log) => (
                    <EmailRow
                      key={log.id}
                      log={log}
                      resending={resending}
                      onView={() => setViewing(log)}
                      onResend={() => resendEmails([log.id])}
                    />
                  ))}
                </tbody>
              </table>
            </div>
            <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-hairline px-4 py-2.5">
              <p className="text-caption text-ink-muted">
                Trang {page}/{totalPages} · {formatNumber(data.total)} thư
                {inFlight && ' · đang gửi, tự cập nhật…'}
              </p>
              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  icon={ChevronLeft}
                  disabled={page <= 1}
                  onClick={() => update({ page: page - 1 })}
                >
                  Trước
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => update({ page: page + 1 })}
                >
                  Sau
                  <ChevronRight className="size-4" aria-hidden="true" />
                </Button>
              </div>
            </footer>
          </Card>
        )}
      </div>

      {viewing && (
        <EmailDetailModal
          log={viewing}
          resending={resending}
          onClose={() => setViewing(null)}
          onResend={async () => {
            const result = await resendEmails([viewing.id])
            if (result?.queued) setViewing(null)
          }}
        />
      )}

      <Modal
        open={confirmAll}
        onClose={() => setConfirmAll(false)}
        title={`Gửi lại ${stats?.failed ?? 0} thư lỗi?`}
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" size="sm" onClick={() => setConfirmAll(false)}>
              Huỷ
            </Button>
            <Button
              size="sm"
              icon={RotateCcw}
              loading={resending}
              disabled={resending}
              onClick={async () => {
                await resendEmails(null)
                setConfirmAll(false)
              }}
            >
              Gửi lại
            </Button>
          </div>
        }
      >
        <div className="flex flex-col gap-2 text-body-sm text-ink-secondary">
          <p>
            Nội dung được dựng lại từ dữ liệu hiện tại và gửi tới email hiện tại trong hồ sơ CBNV —
            sửa địa chỉ sai trong hồ sơ trước rồi mới gửi lại.
          </p>
          <p>
            Thư không còn phù hợp sẽ tự bỏ qua: đăng ký đã huỷ không nhận lại thư xác nhận, người đã bổ
            sung giấy tờ không nhận thư nhắc.
          </p>
          {stats && !stats.email_enabled && (
            <p className="text-amber-800">Đang tắt gửi thật: thư sẽ chỉ được ghi vào nhật ký.</p>
          )}
        </div>
      </Modal>
    </>
  )
}

function EmailRow({ log, resending, onView, onResend }) {
  const meta = EMAIL_STATUS_META[log.status] ?? { label: log.status, tone: 'slate' }
  const { detail, hint } = splitEmailError(log.error_message)
  const failed = log.status === 'failed'

  return (
    <tr className="align-top hover:bg-canvas-soft">
      <td className="px-4 py-3 whitespace-nowrap text-ink-muted tabular-nums">
        {formatDateTime(log.created_at)}
        {log.sent_at && (
          <span className="block text-eyebrow font-normal text-ink-faint">gửi {formatDateTime(log.sent_at)}</span>
        )}
      </td>
      <td className="max-w-[22rem] px-4 py-3">
        <p className="truncate text-body-sm font-semibold text-ink" title={log.subject}>
          {log.template_label}
        </p>
        <p className="truncate text-ink-muted" title={log.to_email}>
          {log.to_email}
        </p>
        <p className="truncate text-eyebrow font-normal text-ink-faint" title={log.subject}>
          {log.subject}
        </p>
      </td>
      <td className="px-4 py-3">
        <div className="flex flex-wrap items-center gap-1.5">
          {log.is_dev_only ? <Badge tone="slate">Chỉ ghi log</Badge> : <Badge tone={meta.tone}>{meta.label}</Badge>}
          {log.retry_count > 0 && (
            <span className="text-eyebrow font-normal text-ink-faint">gửi lại {log.retry_count} lần</span>
          )}
        </div>
        {failed && (hint || detail) && (
          <p className="mt-1 line-clamp-2 text-eyebrow font-normal text-rose-700" title={log.error_message}>
            {hint ?? detail}
          </p>
        )}
      </td>
      <td className="px-4 py-3">
        <div className="flex justify-end gap-1.5">
          <Button variant="ghost" size="sm" icon={Eye} onClick={onView}>
            Xem
          </Button>
          {failed && (
            <Button variant="secondary" size="sm" icon={RotateCcw} disabled={resending} onClick={onResend}>
              Gửi lại
            </Button>
          )}
        </div>
      </td>
    </tr>
  )
}

/** Một ô của thanh chọn trạng thái: nhãn kèm số thư, ô đang chọn nổi lên nền trắng. */
function StatusTab({ label, value, alert = false, active, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`min-h-11 rounded-full px-4 text-caption whitespace-nowrap transition sm:min-h-8 ${
        active ? 'bg-surface font-semibold text-ink shadow-soft' : 'font-medium text-ink-muted'
      }`}
    >
      {label}
      {value !== undefined && (
        <span className={`tabular-nums ${alert ? 'text-rose-700' : ''}`}> · {formatNumber(value)}</span>
      )}
    </button>
  )
}
