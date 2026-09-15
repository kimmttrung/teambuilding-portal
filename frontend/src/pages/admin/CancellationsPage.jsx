import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Ban, CheckCircle2, ChevronLeft, ChevronRight, UserX, XCircle } from 'lucide-react'
import { useCancellationList } from '../../hooks/useCancellations'
import {
  CANCELLATION_MODE_LABELS,
  CANCELLATION_STATUS_META,
  RELEASED_LABELS,
} from '../../utils/constants'
import { formatDateTime, formatNumber, formatRelative } from '../../utils/format'
import Alert from '../../components/common/Alert'
import Badge from '../../components/common/Badge'
import Button from '../../components/common/Button'
import Card from '../../components/common/Card'
import EmptyState from '../../components/common/EmptyState'
import PageHeader from '../../components/common/PageHeader'
import SearchBox from '../../components/common/SearchBox'
import Select from '../../components/common/Select'
import Spinner from '../../components/common/Spinner'
import {
  ApproveCancellationDialog,
  CancelOnBehalfDialog,
  RejectCancellationDialog,
} from './cancellations/CancellationDialogs'

const PAGE_SIZE = 20
const ALL = 'all'
const STATUS_TABS = [
  { value: 'pending', label: 'Chờ duyệt' },
  { value: 'approved', label: 'Đã huỷ' },
  { value: 'rejected', label: 'Từ chối' },
  { value: 'withdrawn', label: 'CBNV đã rút' },
  { value: ALL, label: 'Tất cả' },
]

/**
 * Mọi lần huỷ đăng ký của kỳ: ai huỷ, lúc nào, lý do gì, ở giai đoạn nào, đã gỡ những gì.
 * Mở mặc định ở tab "Chờ duyệt" — việc BTC cần xử lý. Bộ lọc nằm trên URL để dashboard và
 * email báo BTC dẫn thẳng tới đúng tab.
 */
export default function CancellationsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const status = searchParams.get('status') ?? 'pending'
  const mode = searchParams.get('mode') ?? ''
  const q = searchParams.get('q') ?? ''
  const page = Math.max(Number(searchParams.get('page')) || 1, 1)
  const params = {
    ...(status !== ALL && { status }),
    ...(mode && { mode }),
    ...(q && { q }),
    page,
    page_size: PAGE_SIZE,
  }

  const { data, isLoading, isFetching, error } = useCancellationList(params)
  const [approving, setApproving] = useState(null)
  const [rejecting, setRejecting] = useState(null)
  const [cancellingOnBehalf, setCancellingOnBehalf] = useState(false)

  function update(changes) {
    const next = new URLSearchParams(searchParams)
    for (const [key, value] of Object.entries(changes)) {
      if (value === null || value === undefined || value === '') next.delete(key)
      else next.set(key, String(value))
    }
    if (!('page' in changes)) next.delete('page')
    setSearchParams(next, { replace: true })
  }

  const totalPages = data ? Math.max(Math.ceil(data.total / PAGE_SIZE), 1) : 1

  return (
    <>
      <PageHeader
        title="Huỷ đăng ký"
        description="Ai huỷ, lúc nào, lý do gì — trước công bố hệ thống tự xử lý, sau công bố cần BTC duyệt"
        action={
          <Button variant="secondary" icon={Ban} onClick={() => setCancellingOnBehalf(true)}>
            Huỷ thay CBNV
          </Button>
        }
      />

      <div className="flex flex-col gap-4">
        <Card bodyClassName="flex flex-col gap-3">
          <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Trạng thái">
            {STATUS_TABS.map((tab) => {
              const active = status === tab.value
              return (
                <button
                  key={tab.value}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  onClick={() => update({ status: tab.value === 'pending' ? null : tab.value })}
                  className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${
                    active ? 'bg-brand-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  {tab.label}
                </button>
              )
            })}
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="sm:col-span-2">
              <SearchBox key={q} initial={q} placeholder="Tên, email, mã nhân viên" onSearch={(value) => update({ q: value })} />
            </div>
            <Select
              label="Hình thức"
              placeholder="Tất cả"
              value={mode}
              onChange={(changeEvent) => update({ mode: changeEvent.target.value })}
              options={Object.entries(CANCELLATION_MODE_LABELS).map(([value, label]) => ({ value, label }))}
            />
          </div>
        </Card>

        {error ? (
          <Alert tone="error" title="Không tải được danh sách huỷ">
            {error.message}
          </Alert>
        ) : isLoading ? (
          <Spinner label="Đang tải…" />
        ) : data.items.length === 0 ? (
          <Card>
            <EmptyState
              icon={UserX}
              title={status === 'pending' ? 'Không có yêu cầu nào chờ duyệt' : 'Chưa có lần huỷ nào'}
              description="Khi CBNV huỷ hoặc gửi yêu cầu huỷ, Ban tổ chức nhận email và danh sách hiện ở đây."
            />
          </Card>
        ) : (
          <Card
            title={`${formatNumber(data.total)} lần huỷ`}
            action={isFetching ? <span className="text-xs text-slate-400">Đang cập nhật…</span> : undefined}
            bodyClassName="p-0"
          >
            <ul className="divide-y divide-slate-100">
              {data.items.map((item) => (
                <CancellationRow
                  key={item.id}
                  item={item}
                  onApprove={() => setApproving(item)}
                  onReject={() => setRejecting(item)}
                />
              ))}
            </ul>
            {totalPages > 1 && (
              <div className="flex items-center justify-between gap-3 border-t border-slate-100 px-4 py-2.5 text-sm text-slate-500">
                <span>
                  Trang {page}/{totalPages}
                </span>
                <div className="flex gap-2">
                  <Button variant="secondary" size="sm" icon={ChevronLeft} disabled={page <= 1} onClick={() => update({ page: page - 1 })}>
                    Trước
                  </Button>
                  <Button variant="secondary" size="sm" disabled={page >= totalPages} onClick={() => update({ page: page + 1 })}>
                    Sau
                    <ChevronRight className="size-4" aria-hidden="true" />
                  </Button>
                </div>
              </div>
            )}
          </Card>
        )}
      </div>

      {approving && <ApproveCancellationDialog key={approving.id} item={approving} onClose={() => setApproving(null)} />}
      {rejecting && <RejectCancellationDialog key={rejecting.id} item={rejecting} onClose={() => setRejecting(null)} />}
      {cancellingOnBehalf && <CancelOnBehalfDialog onClose={() => setCancellingOnBehalf(false)} />}
    </>
  )
}

function CancellationRow({ item, onApprove, onReject }) {
  const statusMeta = CANCELLATION_STATUS_META[item.status] ?? { label: item.status, tone: 'slate' }
  const released = Object.entries(RELEASED_LABELS).filter(([key]) => item.released?.[key]?.length)
  const pending = item.status === 'pending'

  return (
    <li className={`flex flex-col gap-3 px-4 py-3.5 lg:flex-row lg:items-start lg:gap-6 ${pending ? 'bg-amber-50/40' : ''}`}>
      <div className="min-w-0 lg:w-64 lg:shrink-0">
        <p className="font-medium text-slate-900">{item.user.full_name}</p>
        <p className="truncate text-xs text-slate-500">
          {[item.user.employee_code, item.user.team_name ?? 'Chưa gán team'].filter(Boolean).join(' · ')}
        </p>
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          <Badge tone={statusMeta.tone}>{statusMeta.label}</Badge>
          <Badge tone="slate">{CANCELLATION_MODE_LABELS[item.mode] ?? item.mode}</Badge>
        </div>
      </div>

      <div className="min-w-0 flex-1 text-sm">
        <p className="text-slate-900">“{item.reason}”</p>
        <p className="mt-1 text-xs text-slate-500">
          <time dateTime={item.requested_at} title={formatDateTime(item.requested_at)}>
            {formatDateTime(item.requested_at)} ({formatRelative(item.requested_at)})
          </time>
          {' · '}
          {item.event_status_label}
          {' · '}
          <span className={item.after_deadline ? 'font-medium text-amber-700' : ''}>
            {item.after_deadline ? 'Sau hạn đăng ký' : 'Trong hạn đăng ký'}
          </span>
        </p>

        {released.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {released.map(([key, label]) => (
              <span key={key} className="rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                {label}: {item.released[key].join(', ')}
              </span>
            ))}
          </div>
        )}

        {item.decided_at && item.status !== 'withdrawn' && (
          <p className="mt-2 text-xs text-slate-600">
            <span className="font-medium">{item.decided_by_name ?? 'Hệ thống'}</span> xử lý {formatRelative(item.decided_at)}
            {item.status === 'approved' && (
              <>
                {' · Phí phạt: '}
                <span className={item.penalty_applied ? 'font-medium text-rose-700' : ''}>
                  {item.penalty_applied ? item.penalty_note || 'Có' : 'Không'}
                </span>
              </>
            )}
            {item.decision_note && <span className="italic"> · “{item.decision_note}”</span>}
          </p>
        )}
      </div>

      {pending && (
        <div className="flex shrink-0 gap-2">
          <Button size="sm" icon={CheckCircle2} onClick={onApprove}>
            Duyệt
          </Button>
          <Button size="sm" variant="secondary" icon={XCircle} onClick={onReject}>
            Từ chối
          </Button>
        </div>
      )}
    </li>
  )
}
