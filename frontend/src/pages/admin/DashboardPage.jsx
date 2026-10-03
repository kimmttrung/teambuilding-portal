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
        <p className="text-eyebrow text-ink-muted">{heroEyebrow(event)}</p>
        <h1
          id="dashboard-responses"
          className="mt-2 text-heading-1 text-balance text-ink tabular-nums sm:text-display-2"
        >
          {formatNumber(responded)}
          <span className="text-ink-faint">/{formatNumber(total)}</span>{' '}
          <span className="text-heading-3 sm:text-page-title">người đã phản hồi</span>
        </h1>

        <div
          className="mt-4.5 flex h-2.5 max-w-3xl overflow-hidden rounded-full bg-hairline"
          role="img"
          aria-label={`${stats.participating} tham gia, ${notGoing} không đi, ${stats.not_submitted} chưa phản hồi`}
        >
          <span className="h-full bg-ink" style={{ width: share(stats.participating) }} />
          <span className="h-full bg-ink-faint" style={{ width: share(notGoing) }} />
        </div>

        <ul className="mt-3 flex flex-wrap items-center gap-x-6 gap-y-1.5 text-caption text-ink tabular-nums">
          <Legend dot="bg-ink" label="Tham gia" value={stats.participating} />
          <Legend dot="bg-ink-faint" label="Không đi" value={notGoing} />
          <Legend
            dot="bg-hairline ring-1 ring-input-border"
            label="Chưa phản hồi"
            value={stats.not_submitted}
            to={stats.not_submitted ? '/admin/users?registration=none' : undefined}
          />
          {shifts.length > 0 && (
            <li className="text-ink-muted">{shifts.map(([shift, count]) => `${shift}: ${count}`).join(' · ')}</li>
          )}
          {busRiders > 0 && <li className="text-ink-muted">Xe: {busRiders} người cần</li>}
        </ul>
      </div>

      {canRemind && (
        <Button shape="pill" size="lg" onClick={() => onRemind('not_registered')}>
          Gửi nhắc {formatNumber(stats.not_submitted)} người
        </Button>
      )}
    </section>
  )
}

function Legend({ dot, label, value, to }) {
  const body = (
    <>
      <span className={`size-2 shrink-0 rounded-full ${dot}`} aria-hidden="true" />
      {label} <b className="font-semibold">{formatNumber(value)}</b>
    </>
  )
  return (
    <li>
      {to ? (
        <Link to={to} className="inline-flex items-center gap-1.5 hover:text-primary hover:underline">
          {body}
        </Link>
      ) : (
        <span className="inline-flex items-center gap-1.5">{body}</span>
      )}
    </li>
  )
}
