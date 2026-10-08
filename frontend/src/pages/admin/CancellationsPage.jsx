import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  ArrowLeft,
  Ban,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  Clock3,
  Eye,
  Search,
  UserX,
  XCircle,
} from 'lucide-react'
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
import Modal from '../../components/common/Modal'
import PageHeader from '../../components/common/PageHeader'
import Spinner from '../../components/common/Spinner'
import {
  ApproveCancellationDialog,
  CancelOnBehalfDialog,
  PENALTY_RULE,
  RejectCancellationDialog,
  RELEASE_WARNING,
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
 * Mọi lần huỷ đăng ký của kỳ, dạng bảng để duyệt nhanh.
 * Mở mặc định ở "Chờ duyệt". Bộ lọc nằm trên URL để tổng quan và email dẫn đúng tab.
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
  const [viewing, setViewing] = useState(null)

  function update(changes) {
    const next = new URLSearchParams(searchParams)
    for (const [key, value] of Object.entries(changes)) {
      if (value === null || value === undefined || value === '') next.delete(key)
      else next.set(key, String(value))
    }
    if (!('page' in changes)) next.delete('page')
    setSearchParams(next, { replace: true })
  }

  function decide(item, kind) {
    setViewing(null)
    if (kind === 'approve') setApproving(item)
    else setRejecting(item)
  }

  const totalPages = data ? Math.max(Math.ceil(data.total / PAGE_SIZE), 1) : 1

  return (
    <>
      <PageHeader
        title="Yêu cầu huỷ"
        description="Xem lý do, phí phạt theo quy định, rồi chấp nhận hoặc từ chối."
        className="mb-6 max-md:hidden"
        action={
          <Button variant="secondary" icon={Ban} onClick={() => setCancellingOnBehalf(true)}>
            Huỷ thay CBNV
          </Button>
        }
      />

      <div className="mb-4 flex items-center gap-3 md:hidden">
        <Link to="/admin/registrations" className="grid size-8 place-items-center text-ink" aria-label="Về danh sách đăng ký">
          <ArrowLeft className="size-5" />
        </Link>
        <h1 className="min-w-0 flex-1 text-page-title text-ink">Yêu cầu huỷ</h1>
        <Button variant="secondary" size="sm" icon={Ban} onClick={() => setCancellingOnBehalf(true)}>
          Huỷ thay
        </Button>
      </div>

      <div className="mb-4 flex flex-col gap-3">
        <div className="flex gap-2 overflow-x-auto pb-1" role="tablist" aria-label="Trạng thái">
          {STATUS_TABS.map((tab) => {
            const active = status === tab.value
            return (
              <button
                key={tab.value}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => update({ status: tab.value === 'pending' ? null : tab.value })}
                className={`shrink-0 rounded-full px-3 py-1.5 text-body-sm font-medium transition ${
                  active ? 'bg-primary text-on-primary' : 'bg-canvas-soft text-ink-muted hover:text-ink'
                }`}
              >
                {tab.label}
              </button>
            )
          })}
        </div>
        <SearchField key={q} initial={q} onSearch={(value) => update({ q: value })} />
      </div>

      {error ? (
        <Alert tone="error" title="Không tải được danh sách huỷ">{error.message}</Alert>
      ) : isLoading ? (
        <Spinner label="Đang tải danh sách huỷ…" />
      ) : data.items.length === 0 ? (
        <Card>
          <EmptyState
            icon={UserX}
            title={status === 'pending' ? 'Không có yêu cầu nào chờ duyệt' : 'Chưa có lần huỷ nào'}
            description="Khi CBNV huỷ hoặc gửi yêu cầu huỷ, Ban tổ chức nhận email và dòng hiện ở bảng này."
          />
        </Card>
      ) : (
        <div className="overflow-hidden rounded-lg border border-hairline bg-surface">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[880px] border-collapse text-left text-body-sm">
              <thead className="bg-canvas-soft text-caption text-ink-muted">
                <tr>
                  {['CBNV', 'Team', 'Gửi lúc', 'Trạng thái', 'Lý do'].map((label) => (
                    <th key={label} scope="col" className="px-4 py-2.5 font-semibold">{label}</th>
                  ))}
                  <th scope="col" className="px-4 py-2.5 font-semibold">
                    <span className="sr-only">Thao tác</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item) => (
                  <CancellationTableRow
                    key={item.id}
                    item={item}
                    onView={() => setViewing(item)}
                    onApprove={() => decide(item, 'approve')}
                    onReject={() => decide(item, 'reject')}
                  />
                ))}
              </tbody>
            </table>
          </div>
          <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-hairline px-4 py-3 text-caption text-ink-muted">
            <p>Trang {page}/{totalPages} · {data.total} yêu cầu</p>
            {totalPages > 1 && (
              <div className="flex gap-2">
                <Button variant="secondary" size="sm" icon={ChevronLeft} disabled={page <= 1} onClick={() => update({ page: page - 1 })}>
                  Trước
                </Button>
                <Button variant="secondary" size="sm" disabled={page >= totalPages} onClick={() => update({ page: page + 1 })}>
                  Sau <ChevronRight className="size-4" aria-hidden="true" />
                </Button>
              </div>
            )}
          </footer>
        </div>
      )}

      {viewing && (
        <CancellationDetailModal
          key={viewing.id}
          item={viewing}
          onClose={() => setViewing(null)}
          onApprove={() => decide(viewing, 'approve')}
          onReject={() => decide(viewing, 'reject')}
        />
      )}
      {approving && <ApproveCancellationDialog key={approving.id} item={approving} onClose={() => setApproving(null)} />}
      {rejecting && <RejectCancellationDialog key={rejecting.id} item={rejecting} onClose={() => setRejecting(null)} />}
      {cancellingOnBehalf && <CancelOnBehalfDialog onClose={() => setCancellingOnBehalf(false)} />}
    </>
  )
}

function SearchField({ initial = '', onSearch }) {
  const [value, setValue] = useState(initial)
  return (
    <form
      role="search"
      className="relative max-w-sm"
      onSubmit={(submitEvent) => {
        submitEvent.preventDefault()
        onSearch(value.trim())
      }}
    >
      <button type="submit" aria-label="Tìm theo tên, email, mã nhân viên" className="absolute inset-y-0 left-0 grid w-9 place-items-center text-ink-faint">
        <Search className="size-4" aria-hidden="true" />
      </button>
      <input
        aria-label="Tìm theo tên, email, mã nhân viên"
        type="search"
        value={value}
        onChange={(changeEvent) => setValue(changeEvent.target.value)}
        placeholder="Tìm tên, email, mã nhân viên"
        className="min-h-10 w-full rounded-md border border-input-border bg-surface py-2 pl-9 pr-3 text-body-sm text-ink outline-none focus:border-primary"
      />
    </form>
  )
}

function CancellationTableRow({ item, onView, onApprove, onReject }) {
  const statusMeta = CANCELLATION_STATUS_META[item.status] ?? { label: item.status, tone: 'slate' }
  const pending = item.status === 'pending'

  return (
    <tr className="border-t border-hairline align-top">
      <td className="px-4 py-3">
        <p className="font-semibold text-ink">{item.user.full_name}</p>
        <p className="text-caption text-ink-muted">{item.user.employee_code || item.user.email}</p>
      </td>
      <td className="px-4 py-3 text-ink-secondary">{item.user.team_name ?? 'Chưa gán team'}</td>
      <td className="whitespace-nowrap px-4 py-3">
        <p className="text-ink">{formatDateTime(item.requested_at)}</p>
        <p className="text-caption text-ink-muted">{formatRelative(item.requested_at)}</p>
      </td>
      <td className="px-4 py-3">
        <div className="flex flex-col items-start gap-1">
          <Badge tone={statusMeta.tone}>{statusMeta.label}</Badge>
          <span className="text-caption text-ink-muted">{CANCELLATION_MODE_LABELS[item.mode] ?? item.mode}</span>
        </div>
      </td>
      <td className="max-w-xs px-4 py-3 text-ink-secondary">
        <p className="line-clamp-2">“{item.reason}”</p>
      </td>
      <td className="px-4 py-3">
        <div className="flex flex-wrap items-center justify-end gap-1.5">
          <button
            type="button"
            onClick={onView}
            aria-label={`Chi tiết ${item.user.full_name}`}
            title="Xem lý do và quy định"
            className="grid size-8 place-items-center rounded-full text-ink-muted hover:bg-black/5 hover:text-primary"
          >
            <Eye className="size-4" aria-hidden="true" />
          </button>
          {pending && (
            <>
              <Button variant="secondary" size="sm" icon={XCircle} onClick={onReject}>Từ chối</Button>
              <Button size="sm" icon={CheckCircle2} onClick={onApprove}>Chấp nhận</Button>
            </>
          )}
        </div>
      </td>
    </tr>
  )
}

function CancellationDetailModal({ item, onClose, onApprove, onReject }) {
  const statusMeta = CANCELLATION_STATUS_META[item.status] ?? { label: item.status, tone: 'slate' }
  const pending = item.status === 'pending'
  const released = Object.entries(RELEASED_LABELS).filter(([key]) => item.released?.[key]?.length)

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={item.user.full_name}
      description={[item.user.team_name ?? 'Chưa gán team', item.user.employee_code, item.event_status_label].filter(Boolean).join(' · ')}
      footer={
        pending ? (
          <div className="flex flex-wrap justify-end gap-2">
            <Button variant="secondary" icon={XCircle} onClick={onReject}>Từ chối</Button>
            <Button icon={CheckCircle2} onClick={onApprove}>Chấp nhận</Button>
          </div>
        ) : null
      }
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={statusMeta.tone}>{statusMeta.label}</Badge>
        <Badge tone="slate">{CANCELLATION_MODE_LABELS[item.mode] ?? item.mode}</Badge>
      </div>
      <p className="mt-4 text-body-md leading-relaxed text-ink">“{item.reason}”</p>
      <p className="mt-2 inline-flex items-center gap-1.5 text-caption text-ink-muted">
        <Clock3 className="size-3.5" aria-hidden="true" />
        {formatDateTime(item.requested_at)} · {formatRelative(item.requested_at)}
      </p>

      <section className="mt-5 rounded-lg border border-hairline px-4 py-4">
        <h3 className="text-body-sm font-semibold text-ink">Theo quy định của kỳ</h3>
        <p className="mt-2 text-body-sm text-ink-secondary">
          {item.after_deadline ? 'Yêu cầu gửi sau hạn đăng ký. ' : 'Yêu cầu gửi trong hạn đăng ký. '}
          {PENALTY_RULE}
        </p>
        <p className="mt-2 text-body-sm text-ink">
          {item.penalty_applied
            ? `Đã áp phí phạt${item.penalty_note ? `: ${item.penalty_note}` : ''}.`
            : pending
              ? 'Chưa quyết định phí phạt. Chấp nhận thì chọn có tính phí hay không.'
              : 'Miễn phí phạt.'}
        </p>
      </section>

      <section className="mt-3 rounded-lg border border-hairline px-4 py-4">
        <h3 className="text-body-sm font-semibold text-ink">
          {released.length > 0 ? 'Đã gỡ khi huỷ' : 'Khi chấp nhận, hệ thống sẽ'}
        </h3>
        {released.length > 0 ? (
          <ul className="mt-2 flex flex-col gap-1.5 text-body-sm text-ink-secondary">
            {released.map(([key, label]) => (
              <li key={key}>Gỡ {label}: {item.released[key].join(', ')}</li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-body-sm text-ink-secondary">{RELEASE_WARNING}</p>
        )}
      </section>

      {item.decided_at && (
        <p className="mt-4 text-caption text-ink-muted">
          <strong className="text-ink">{item.decided_by_name ?? 'Hệ thống'}</strong> đã xử lý lúc {formatDateTime(item.decided_at)}.
          {item.decision_note && <span> Ghi chú: “{item.decision_note}”</span>}
        </p>
      )}

      {pending && (
        <p className="mt-4 inline-flex items-center gap-2 text-caption text-amber-800">
          <CircleAlert className="size-4" aria-hidden="true" />
          Chấp nhận hoặc từ chối được ghi vào nhật ký thao tác.
        </p>
      )}
    </Modal>
  )
}
