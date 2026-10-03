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
import ActivityFeed from './dashboard/ActivityFeed'
import AllocationProgress from './dashboard/AllocationProgress'
import LifecycleStepper from './dashboard/LifecycleStepper'
import StatusControl from './dashboard/StatusControl'
import SystemCard from './dashboard/SystemCard'
import TeamLeaderDialog from './dashboard/TeamLeaderDialog'
import TeamTable from './dashboard/TeamTable'

/**
 * Dashboard BTC (Figma v2 · B1) trả lời 3 câu theo thứ tự đọc: đang ở bước nào (dải trạng thái), bao
 * nhiêu người đã phản hồi (con số lớn), còn việc gì và xếp tới đâu (hai cột bên dưới).
 * Một request `/admin/dashboard` — số liệu do backend đếm.
 */
export default function DashboardPage() {
  const { data, isLoading, error } = useDashboard()
  const [reminderKind, setReminderKind] = useState(null)
  const [leaderTeam, setLeaderTeam] = useState(null)

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
      <LifecycleStepper
        status={event.status}
        statusLabel={event.status_label}
        action={<StatusControl event={event} checklist={data.checklist} gala={data.gala} />}
      />

      <ResponseHero event={event} stats={stats} buses={data.buses} onRemind={setReminderKind} />

      {/* Điện thoại: một cột, "Việc cần làm" lên đầu. Màn rộng: cột phải cố định 400px như Figma. */}
      <div className="grid gap-x-10 gap-y-9 xl:grid-cols-[minmax(0,1fr)_400px] xl:items-start">
        <div className="flex min-w-0 flex-col gap-9">
          <ActionCenter data={data} onRemind={setReminderKind} onAssignLeader={setLeaderTeam} />
          <AllocationProgress
            status={event.status}
            participants={stats.participating}
            flights={data.flights}
            buses={data.buses}
            rooms={data.rooms}
            gala={data.gala}
            shiftDemand={event.is_published ? null : stats.by_shift}
          />
        </div>

        <aside className="flex min-w-0 flex-col gap-8">
          <TeamTable teams={data.teams} onAssignLeader={setLeaderTeam} />
          <ActivityFeed items={data.recent_activity} />
          <SystemCard emails={data.emails} published={event.is_published} />
        </aside>
      </div>

      {reminderKind && <ReminderDialog kind={reminderKind} onClose={() => setReminderKind(null)} />}
      {leaderTeam && (
        <TeamLeaderDialog key={leaderTeam.team_id} team={leaderTeam} onClose={() => setLeaderTeam(null)} />
      )}
    </div>
  )
}

/** Dòng nhỏ phía trên con số: đang mở đăng ký thì nhắc hạn đóng, các giai đoạn khác nhắc ngày đi. */
function heroEyebrow(event) {
  const dates = `${formatDate(event.start_date)} – ${formatDate(event.end_date)}`
  if (event.status === EVENT_STATUS.REGISTRATION_OPEN && event.registration_closes_at) {
    const left = daysUntil(event.registration_closes_at)
    const closes = formatShortDateTime(event.registration_closes_at)
    return left > 0 ? `Đăng ký · đóng sau ${left} ngày (${closes})` : `Đăng ký · đóng lúc ${closes}`
  }
  const remaining = daysUntil(event.start_date)
  const place = [event.name, event.destination].filter(Boolean).join(' · ')
  return remaining > 0 ? `${place} · ${dates} · còn ${remaining} ngày` : `${place} · ${dates}`
}

function ResponseHero({ event, stats, buses, onRemind }) {
  const total = stats.total_users
  const notGoing = Math.max(total - stats.participating - stats.not_submitted, 0)
  const responded = total - stats.not_submitted
  const share = (value) => (total ? `${(value / total) * 100}%` : '0%')
  const shifts = Object.entries(stats.by_shift ?? {})
  // Cùng một người cần xe ở nhiều chặng: lấy chặng đông nhất, không cộng dồn.
  const busRiders = buses.length ? Math.max(...buses.map((leg) => leg.demand)) : 0
  const canRemind = event.status === EVENT_STATUS.REGISTRATION_OPEN && stats.not_submitted > 0

  return (
    <section className="flex flex-wrap items-end gap-x-10 gap-y-5" aria-labelledby="dashboard-responses">
      <div className="min-w-0 flex-1 basis-80">
        <p className="text-caption font-medium text-ink-muted">{heroEyebrow(event)}</p>
        <h1
          id="dashboard-responses"
          className="mt-2 text-heading-1 text-balance text-ink tabular-nums sm:text-display-2"
        >
          {formatNumber(responded)}
          <span className="text-ink-faint">/{formatNumber(total)}</span>{' '}
          <span className="text-heading-3 sm:text-page-title">người đã phản hồi</span>
        </h1>

        <div
          className="mt-4.5 flex h-4 overflow-hidden rounded-full bg-accent-orange/25"
          role="img"
          aria-label={`${stats.participating} tham gia, ${notGoing} không đi, ${stats.not_submitted} chưa phản hồi`}
        >
          <span className="h-full bg-accent-green" style={{ width: share(stats.participating) }} />
          <span className="h-full bg-ink-faint" style={{ width: share(notGoing) }} />
        </div>
      </div>

      {canRemind && (
        <Button shape="pill" size="lg" onClick={() => onRemind('not_registered')}>
          Gửi nhắc {formatNumber(stats.not_submitted)} người
        </Button>
      )}

      {/* Ô số liệu: cùng màu chấm với từng đoạn của thanh phía trên. */}
      <ul className="grid basis-full grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
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
