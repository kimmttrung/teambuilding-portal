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

        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatusTile
            label="Tất cả"
            value={stats?.total}
            active={!filters.status}
            onClick={() => update({ status: null })}
          />
          {STATUS_ORDER.map((status) => (
            <StatusTile
              key={status}
              label={EMAIL_STATUS_META[status].label}
              value={stats?.[status]}
              tone={EMAIL_STATUS_META[status].tone}
              active={filters.status === status}
              onClick={() => update({ status })}
            />
          ))}
        </div>

        <Card>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="sm:col-span-2">
              <SearchBox
                key={filters.q ?? ''}
                initial={filters.q ?? ''}
                placeholder="Email người nhận hoặc tiêu đề"
                onSearch={(q) => update({ q })}
              />
            </div>
            <Select
              label="Trạng thái"
              placeholder="Tất cả"
              value={filters.status ?? ''}
              onChange={(changeEvent) => update({ status: changeEvent.target.value })}
              options={STATUS_ORDER.map((status) => ({ value: status, label: EMAIL_STATUS_META[status].label }))}
            />
            <Select
              label="Loại thư"
              placeholder="Tất cả"
              value={filters.template ?? ''}
              onChange={(changeEvent) => update({ template: changeEvent.target.value })}
              options={templateOptions}
            />
          </div>
          {(hasFilters || (isFetching && !isLoading)) && (
            <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3">
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
              {isFetching && !isLoading && <span className="text-xs text-slate-400">Đang cập nhật…</span>}
            </div>
          )}
        </Card>

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
              <table className="w-full min-w-[880px] text-sm">
                <thead>
                  <tr className="border-b border-slate-100 text-left text-xs tracking-wide text-slate-400 uppercase">
                    <th scope="col" className="px-4 py-2 font-medium">Thời gian</th>
                    <th scope="col" className="px-3 py-2 font-medium">Người nhận</th>
                    <th scope="col" className="px-3 py-2 font-medium">Loại thư</th>
                    <th scope="col" className="px-3 py-2 font-medium">Trạng thái</th>
                    <th scope="col" className="px-4 py-2 text-right font-medium">
                      <span className="sr-only">Thao tác</span>
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
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
            <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 px-4 py-2.5">
              <p className="text-xs text-slate-500">
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
        <div className="flex flex-col gap-2 text-sm text-slate-700">
          <p>
            Nội dung được dựng lại từ dữ liệu hiện tại và gửi tới email hiện tại trong hồ sơ CBNV —
            sửa địa chỉ sai trong hồ sơ trước rồi mới gửi lại.
          </p>
          <p>
            Thư không còn phù hợp sẽ tự bỏ qua: đăng ký đã huỷ không nhận lại thư xác nhận, người đã bổ
            sung giấy tờ không nhận thư nhắc.
          </p>
          {stats && !stats.email_enabled && (
            <p className="text-amber-700">Đang tắt gửi thật: thư sẽ chỉ được ghi vào nhật ký.</p>
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
    <tr className="align-top hover:bg-slate-50/60">
      <td className="px-4 py-2.5 text-xs whitespace-nowrap text-slate-600">
        {formatDateTime(log.created_at)}
        {log.sent_at && <span className="block text-slate-400">gửi {formatDateTime(log.sent_at)}</span>}
      </td>
      <td className="max-w-[16rem] px-3 py-2.5">
        <p className="truncate text-slate-900" title={log.to_email}>
          {log.to_email}
        </p>
        <p className="truncate text-xs text-slate-500" title={log.subject}>
          {log.subject}
        </p>
      </td>
      <td className="px-3 py-2.5 text-slate-700">{log.template_label}</td>
      <td className="max-w-[20rem] px-3 py-2.5">
        <div className="flex flex-wrap items-center gap-1.5">
          {log.is_dev_only ? (
            <Badge tone="slate">Chỉ ghi log</Badge>
          ) : (
            <Badge tone={meta.tone}>{meta.label}</Badge>
          )}
          {log.retry_count > 0 && <span className="text-xs text-slate-400">gửi lại {log.retry_count} lần</span>}
        </div>
        {failed && (hint || detail) && (
          <p className="mt-1 line-clamp-2 text-xs text-rose-700" title={log.error_message}>
            {hint ?? detail}
          </p>
        )}
      </td>
      <td className="px-4 py-2.5">
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

const TILE_TONES = {
  slate: 'text-slate-900',
  emerald: 'text-emerald-700',
  rose: 'text-rose-700',
  blue: 'text-blue-700',
}

function StatusTile({ label, value, tone = 'slate', active, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`rounded-xl border bg-white px-4 py-3 text-left transition hover:border-slate-300 ${
        active ? 'border-brand-500 ring-1 ring-brand-500' : 'border-slate-200'
      }`}
    >
      <p className="text-xs text-slate-500">{label}</p>
      <p className={`text-xl leading-tight font-bold tabular-nums ${TILE_TONES[tone] ?? TILE_TONES.slate}`}>
        {value === undefined ? '—' : formatNumber(value)}
      </p>
    </button>
  )
}
