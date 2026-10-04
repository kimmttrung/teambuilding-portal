import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ArrowLeft, Ban, CheckCircle2, ChevronLeft, ChevronRight, CircleAlert, Clock3, UserX, XCircle } from 'lucide-react'
import { useCancellationList } from '../../hooks/useCancellations'
import {
  CANCELLATION_MODE_LABELS,
  CANCELLATION_STATUS_META,
  RELEASED_LABELS,
} from '../../utils/constants'
import { formatDateTime, formatRelative } from '../../utils/format'
import Alert from '../../components/common/Alert'
import Badge from '../../components/common/Badge'
import Button from '../../components/common/Button'
import Card from '../../components/common/Card'
import EmptyState from '../../components/common/EmptyState'
import PageHeader from '../../components/common/PageHeader'
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

  const { data, isLoading, error } = useCancellationList(params)
  const [approving, setApproving] = useState(null)
  const [rejecting, setRejecting] = useState(null)
  const [cancellingOnBehalf, setCancellingOnBehalf] = useState(false)
  const [selectedId, setSelectedId] = useState(null)

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
        title="Yêu cầu huỷ"
        className="mb-8 max-md:hidden"
        action={
          <Button variant="secondary" icon={Ban} onClick={() => setCancellingOnBehalf(true)}>
            Huỷ thay CBNV
          </Button>
        }
      />

      <div className="mb-4 flex items-center gap-3 md:hidden">
        <Link to="/admin" className="grid size-8 place-items-center text-ink" aria-label="Quay lại"><ArrowLeft className="size-5" /></Link>
        <h1 className="text-page-title text-ink">Yêu cầu huỷ</h1>
        <span className="rounded-md bg-accent-orange/15 px-2 py-1 text-caption font-semibold text-accent-orange-deep">{data?.total ?? 0} chờ duyệt</span>
      </div>

      <div className="grid gap-6 md:grid-cols-[330px_minmax(0,1fr)]">
        <section className="hidden min-w-0 md:block">
          <div className="mb-4 flex rounded-full bg-stone-200 p-1" role="tablist" aria-label="Trạng thái">
            {STATUS_TABS.slice(0, 2).map((tab) => {
              const active = status === tab.value || (tab.value === 'pending' && !searchParams.get('status'))
              return <button key={tab.value} type="button" role="tab" aria-selected={active} onClick={() => update({ status: tab.value === 'pending' ? null : 'approved' })} className={`flex-1 rounded-full px-3 py-2 text-body-sm font-medium transition ${active ? 'bg-surface text-ink shadow-soft' : 'text-ink-muted hover:text-ink'}`}>{tab.value === 'pending' ? `Chờ duyệt · ${data?.total ?? 0}` : 'Đã xử lý'}</button>
            })}
          </div>
          {error ? <Alert tone="error" title="Không tải được danh sách huỷ">{error.message}</Alert> : isLoading ? <Spinner label="Đang tải…" /> : data.items.length === 0 ? <Card><EmptyState icon={UserX} title={status === 'pending' ? 'Không có yêu cầu nào chờ duyệt' : 'Chưa có lần huỷ nào'} description="Khi CBNV huỷ hoặc gửi yêu cầu huỷ, Ban tổ chức nhận email và danh sách hiện ở đây." /></Card> : <Card elevated bodyClassName="p-0">
            <ul className="divide-y divide-hairline">
              {data.items.map((item) => <CancellationRow key={item.id} item={item} selected={selectedId === item.id} onSelect={() => setSelectedId(item.id)} />)}
            </ul>
            {totalPages > 1 && <div className="flex items-center justify-between gap-3 border-t border-hairline px-4 py-2.5 text-body-sm text-ink-muted"><span>Trang {page}/{totalPages}</span><div className="flex gap-2"><Button variant="secondary" size="sm" icon={ChevronLeft} disabled={page <= 1} onClick={() => update({ page: page - 1 })}>Trước</Button><Button variant="secondary" size="sm" disabled={page >= totalPages} onClick={() => update({ page: page + 1 })}>Sau <ChevronRight className="size-4" aria-hidden="true" /></Button></div></div>}
          </Card>}
        </section>

        <section className="min-w-0">
          {error ? <div className="md:hidden"><Alert tone="error" title="Không tải được danh sách huỷ">{error.message}</Alert></div> : isLoading ? <div className="md:hidden"><Spinner label="Đang tải…" /></div> : data.items.length === 0 ? <div className="md:hidden"><Card><EmptyState icon={UserX} title="Chưa có lần huỷ nào" description="Khi CBNV huỷ hoặc gửi yêu cầu huỷ, danh sách hiện ở đây." /></Card></div> : <>
            <div className="hidden md:block"><CancellationDetail item={data.items.find((entry) => entry.id === selectedId) ?? data.items[0]} onApprove={setApproving} onReject={setRejecting} /></div>
            <div className="md:hidden"><CancellationMobileView items={data.items} onApprove={setApproving} onReject={setRejecting} /></div>
          </>}
        </section>
      </div>

      {approving && <ApproveCancellationDialog key={approving.id} item={approving} onClose={() => setApproving(null)} />}
      {rejecting && <RejectCancellationDialog key={rejecting.id} item={rejecting} onClose={() => setRejecting(null)} />}
      {cancellingOnBehalf && <CancelOnBehalfDialog onClose={() => setCancellingOnBehalf(false)} />}
    </>
  )
}

function CancellationRow({ item, selected, onSelect }) {
  const statusMeta = CANCELLATION_STATUS_META[item.status] ?? { label: item.status, tone: 'slate' }
  const pending = item.status === 'pending'

  return (
    <li
      tabIndex={0}
      role="button"
      aria-pressed={selected}
      onClick={onSelect}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') onSelect()
      }}
      className={`cursor-pointer px-4 py-3.5 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary ${selected ? 'bg-brand-50' : pending ? 'bg-accent-orange/10' : 'hover:bg-canvas-soft'}`}
    >
      <div className="flex flex-col gap-3">
        <div className="min-w-0">
          <p className="font-medium text-ink">{item.user.full_name}</p>
          <p className="truncate text-caption text-ink-muted">
            {[item.user.employee_code, item.user.team_name ?? 'Chưa gán team'].filter(Boolean).join(' · ')}
          </p>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            <Badge tone={statusMeta.tone}>{statusMeta.label}</Badge>
            <Badge tone="slate">{CANCELLATION_MODE_LABELS[item.mode] ?? item.mode}</Badge>
          </div>
        </div>
        <p className="line-clamp-2 text-body-sm text-ink-secondary">“{item.reason}”</p>
        <p className="text-caption text-ink-muted">{formatRelative(item.requested_at)} · {item.event_status_label}</p>
        {pending && <span className="text-caption font-semibold text-primary">Mở để xử lý →</span>}
      </div>
    </li>
  )
}

function CancellationMobileView({ items, onApprove, onReject }) {
  const [expandedId, setExpandedId] = useState(items[0]?.id)
  const selected = items.find((item) => item.id === expandedId) ?? items[0]
  if (!selected) return null

  // Điện thoại dùng đúng thẻ chi tiết của màn rộng: phí phạt và phần đã gỡ đọc từ dữ liệu thật,
  // quyết định phí nằm trong hộp thoại duyệt.
  return (
    <div className="flex flex-col gap-3">
      <CancellationDetail item={selected} onApprove={onApprove} onReject={onReject} />
      {items.filter((item) => item.id !== selected.id).map((item) => (
        <button key={item.id} type="button" onClick={() => setExpandedId(item.id)} className="flex items-center gap-3 rounded-xl border border-hairline bg-surface px-4 py-3 text-left shadow-soft">
          <span className="grid size-9 place-items-center rounded-full bg-accent-sky text-caption font-semibold text-white">{item.user.full_name?.slice(0, 1)}</span>
          <span className="min-w-0 flex-1"><strong className="block truncate text-body-sm text-ink">{item.user.full_name}</strong><span className="block truncate text-caption text-ink-muted">{item.user.team_name ?? 'Chưa gán team'} · {formatRelative(item.requested_at)}</span></span><span className="text-ink-faint">›</span>
        </button>
      ))}
    </div>
  )
}

function CancellationDetail({ item, onApprove, onReject }) {
  const statusMeta = CANCELLATION_STATUS_META[item.status] ?? { label: item.status, tone: 'slate' }
  const pending = item.status === 'pending'
  const released = Object.entries(RELEASED_LABELS).filter(([key]) => item.released?.[key]?.length)

  return (
    <Card elevated bodyClassName="p-0">
      <div className="border-b border-hairline px-5 py-5 sm:px-7">
        <div className="flex items-start justify-between gap-4">
          <div className="flex min-w-0 items-center gap-3">
            <span className="grid size-12 shrink-0 place-items-center rounded-full bg-accent-orange text-white text-title font-semibold">
              {item.user.full_name?.slice(0, 1)}
            </span>
            <div className="min-w-0">
              <h2 className="truncate text-heading-3 text-ink">{item.user.full_name}</h2>
              <p className="truncate text-body-sm text-ink-muted">
                {[item.user.team_name ?? 'Chưa gán team', item.user.employee_code, item.event_status_label].filter(Boolean).join(' · ')}
              </p>
            </div>
          </div>
          <Badge tone={statusMeta.tone}>{statusMeta.label}</Badge>
        </div>
        <p className="mt-5 text-body-md leading-relaxed text-ink">“{item.reason}”</p>
        <p className="mt-2 inline-flex items-center gap-1.5 text-caption text-ink-muted">
          <Clock3 className="size-3.5" /> {formatDateTime(item.requested_at)} · {formatRelative(item.requested_at)}
        </p>
      </div>

      <div className="grid gap-4 px-5 py-5 sm:px-7 lg:grid-cols-2">
        <section className="rounded-xl border border-hairline px-4 py-4">
          <h3 className="text-body-sm font-semibold text-ink">Quyết định phí phạt</h3>
          <p className="mt-2 text-body-sm text-ink-secondary">
            {item.after_deadline ? 'Yêu cầu gửi sau hạn đăng ký.' : 'Yêu cầu gửi trong hạn đăng ký.'}
          </p>
          <div className="mt-3 rounded-lg bg-canvas-soft px-3 py-2.5 text-body-sm">
            <span className="text-ink-muted">Trạng thái: </span>
            <strong className={item.penalty_applied ? 'text-rose-700' : 'text-ink'}>
              {item.penalty_applied ? item.penalty_note || 'Có phí phạt' : pending ? 'Chưa quyết định' : 'Miễn phí'}
            </strong>
          </div>
        </section>

        <section className="rounded-xl border border-hairline px-4 py-4">
          <h3 className="text-body-sm font-semibold text-ink">Khi duyệt, hệ thống sẽ</h3>
          {released.length > 0 ? (
            <ul className="mt-3 flex flex-col gap-2 text-body-sm text-ink-secondary">
              {released.map(([key, label]) => <li key={key}>✓ Gỡ {label}: {item.released[key].join(', ')}</li>)}
            </ul>
          ) : (
            <p className="mt-2 text-body-sm text-ink-muted">Giữ nguyên chỗ hiện tại cho tới khi BTC duyệt.</p>
          )}
        </section>
      </div>

      {item.decided_at && (
        <div className="mx-5 mb-5 rounded-lg bg-canvas-soft px-4 py-3 text-caption text-ink-muted sm:mx-7">
          <strong className="text-ink">{item.decided_by_name ?? 'Hệ thống'}</strong> đã xử lý lúc {formatDateTime(item.decided_at)}.
          {item.decision_note && <span> Ghi chú: “{item.decision_note}”</span>}
        </div>
      )}

      <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-hairline bg-canvas-soft px-5 py-4 sm:px-7">
        {pending ? (
          <>
            <div className="inline-flex items-center gap-2 text-caption text-amber-800"><CircleAlert className="size-4" /> Hành động này sẽ được ghi vào nhật ký.</div>
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" icon={XCircle} onClick={() => onReject(item)}>Từ chối</Button>
              <Button icon={CheckCircle2} onClick={() => onApprove(item)}>Duyệt huỷ</Button>
            </div>
          </>
        ) : (
          <span className="text-caption text-ink-muted">Bản ghi huỷ chỉ đọc · dữ liệu phân bổ đã được cập nhật.</span>
        )}
      </footer>
    </Card>
  )
}
