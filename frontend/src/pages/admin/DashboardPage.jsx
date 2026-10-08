import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useDashboard } from '../../hooks/useDashboard'
import { EVENT_STATUS } from '../../utils/constants'
import { daysUntil, formatDate, formatNumber, formatShortDateTime } from '../../utils/format'
import Alert from '../../components/common/Alert'
import Button from '../../components/common/Button'
import Spinner from '../../components/common/Spinner'
import ReminderDialog from '../../components/admin/ReminderDialog'
import ActionCenter from './dashboard/ActionCenter'
import AllocationProgress from './dashboard/AllocationProgress'
import LifecycleStepper from './dashboard/LifecycleStepper'
import StatusControl from './dashboard/StatusControl'

/**
 * Dashboard BTC cho người mở lần đầu: đang ở bước nào, bao nhiêu người đã phản hồi, còn việc gì,
 * phân bổ tới đâu. Email, Tibi và nhật ký thao tác nằm ở trang riêng trong Thiết lập.
 * Một request `/admin/dashboard` — số liệu do backend đếm.
 */
export default function DashboardPage() {
  const { data, isLoading, error } = useDashboard()
  const [reminderKind, setReminderKind] = useState(null)

  if (isLoading) return <Spinner label="Đang tải số liệu…" />
  if (error) {
    const noEvent = error.code === 'NO_ACTIVE_EVENT'
    return (
      <Alert
        tone={noEvent ? 'warning' : 'error'}
        title={noEvent ? 'Chưa có kỳ Team Building nào đang mở' : 'Không tải được dashboard'}
      >
        {noEvent ? 'Tạo kỳ mới và đặt làm kỳ đang chạy để bắt đầu.' : error.message}
      </Alert>
    )
  }

  const { event, registrations: stats } = data

  return (
    <div className="flex flex-col gap-9">
      <OverviewHeader
        event={event}
        stats={stats}
        buses={data.buses}
        onRemind={setReminderKind}
        statusAction={<StatusControl event={event} checklist={data.checklist} gala={data.gala} />}
      />

      <ActionCenter data={data} onRemind={setReminderKind} />
      <AllocationProgress
        status={event.status}
        participants={stats.participating}
        flights={data.flights}
        buses={data.buses}
        rooms={data.rooms}
        gala={data.gala}
        shiftDemand={event.is_published ? null : stats.by_shift}
      />

      {reminderKind && <ReminderDialog kind={reminderKind} onClose={() => setReminderKind(null)} />}
    </div>
  )
}

/** Dòng nhận diện kỳ: tên, điểm đến, ngày đi, còn bao nhiêu ngày. */
function identityLine(event) {
  const dates = `${formatDate(event.start_date)} – ${formatDate(event.end_date)}`
  const place = [event.name, event.destination].filter(Boolean).join(' · ')
  const remaining = daysUntil(event.start_date)
  return remaining > 0 ? `${place} · ${dates} · còn ${remaining} ngày` : `${place} · ${dates}`
}

function OverviewHeader({ event, stats, buses, onRemind, statusAction }) {
  const total = stats.total_users
  const notGoing = Math.max(total - stats.participating - stats.not_submitted, 0)
  const responded = total - stats.not_submitted
  const share = (value) => (total ? `${(value / total) * 100}%` : '0%')
  const shifts = Object.entries(stats.by_shift ?? {})
  const busRiders = buses.length ? Math.max(...buses.map((leg) => leg.demand)) : 0
  const canRemind = event.status === EVENT_STATUS.REGISTRATION_OPEN && stats.not_submitted > 0
  const closes = event.registration_closes_at ? formatShortDateTime(event.registration_closes_at) : null

  return (
    <section className="rounded-lg border border-hairline bg-surface p-5 sm:p-6" aria-labelledby="dashboard-responses">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-canvas-soft px-2.5 py-0.5 text-caption font-semibold text-ink">
              {event.code}
            </span>
            <span className="text-caption font-semibold text-ink-secondary">{event.status_label}</span>
          </div>
          <p className="mt-3 text-body-sm text-ink-secondary">{identityLine(event)}</p>
          <h1 id="dashboard-responses" className="mt-1 text-heading-1 text-balance text-ink tabular-nums sm:text-display-2">
            {formatNumber(responded)}
            <span className="text-ink-muted">/{formatNumber(total)}</span>{' '}
            <span className="text-heading-3 text-ink-secondary sm:text-page-title">người đã phản hồi</span>
          </h1>
          {event.status === EVENT_STATUS.REGISTRATION_OPEN && closes && (
            <p className="mt-1 text-caption text-ink-muted">Đăng ký đóng lúc {closes}</p>
          )}
        </div>
        <div className="flex flex-col items-stretch gap-2 sm:items-end">
          {statusAction}
          {canRemind && (
            <Button shape="pill" onClick={() => onRemind('not_registered')}>
              Gửi nhắc {formatNumber(stats.not_submitted)} người
            </Button>
          )}
        </div>
      </div>

      <div
        className="mt-4 flex h-2.5 overflow-hidden rounded-full bg-accent-orange/25"
        role="img"
        aria-label={`${stats.participating} tham gia, ${notGoing} không đi, ${stats.not_submitted} chưa phản hồi`}
      >
        <span className="h-full bg-accent-green" style={{ width: share(stats.participating) }} />
        <span className="h-full bg-ink-faint" style={{ width: share(notGoing) }} />
      </div>

      <ul className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
        <Stat dot="bg-accent-green" label="Tham gia" value={formatNumber(stats.participating)} />
        <Stat dot="bg-ink-faint" label="Không đi" value={formatNumber(notGoing)} />
        <Stat
          dot="bg-accent-orange"
          label="Chưa phản hồi"
          value={formatNumber(stats.not_submitted)}
          to={stats.not_submitted ? '/admin/users?registration=none' : undefined}
        />
        {shifts.length > 0 && (
          <Stat
            dot="bg-accent-sky"
            label="Nguyện vọng ca"
            value={shifts.map(([, count]) => formatNumber(count)).join(' · ')}
            note={shifts.map(([shift]) => shift).join(' · ')}
          />
        )}
        {busRiders > 0 && <Stat dot="bg-accent-teal" label="Cần xe" value={formatNumber(busRiders)} note="người" />}
      </ul>

      <LifecycleStepper status={event.status} statusLabel={event.status_label} showHeading={false} />
    </section>
  )
}

function Stat({ dot, label, value, note, to }) {
  const body = (
    <>
      <span className="flex items-center gap-2 text-caption text-ink-muted">
        <span className={`size-2.5 shrink-0 rounded-full ${dot}`} aria-hidden="true" />
        {label}
      </span>
      <span className="mt-1 block text-heading-2 text-ink tabular-nums">{value}</span>
      {note && <span className="block text-eyebrow font-normal text-ink-faint">{note}</span>}
    </>
  )
  const frame = 'block h-full rounded-lg border border-hairline bg-surface px-4 py-3.5'
  return (
    <li>
      {to ? (
        <Link to={to} className={`${frame} transition hover:border-primary hover:shadow-soft`}>
          {body}
        </Link>
      ) : (
        <div className={frame}>{body}</div>
      )}
    </li>
  )
}
