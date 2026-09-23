import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Calendar, CheckCircle2, Clock, MapPin, UserRound, Users } from 'lucide-react'
import { useDashboard } from '../../hooks/useDashboard'
import { daysUntil, formatDate, formatNumber } from '../../utils/format'
import Alert from '../../components/common/Alert'
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
 * Dashboard BTC trả lời 3 câu theo thứ tự đọc: đang ở bước nào (dải đầu), còn việc gì (Việc cần làm),
 * xếp tới đâu rồi (tiến độ + team). Một request `/admin/dashboard` — số liệu do backend đếm.
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
  const responded = stats.submitted + stats.cancelled
  const remaining = daysUntil(event.start_date)

  return (
    <div className="flex flex-col gap-4">
      <section className="rounded-xl border border-slate-200 bg-white shadow-xs">
        <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 px-4 pt-3.5 pb-3 sm:px-5">
          <div className="min-w-0">
            <h1 className="text-lg font-bold text-balance text-slate-900 sm:text-xl">{event.name}</h1>
            <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-500">
              <span className="inline-flex items-center gap-1.5">
                <Calendar className="size-3.5" aria-hidden="true" />
                {formatDate(event.start_date)} – {formatDate(event.end_date)}
              </span>
              {event.destination && (
                <span className="inline-flex items-center gap-1.5">
                  <MapPin className="size-3.5" aria-hidden="true" />
                  {event.destination}
                </span>
              )}
              {remaining > 0 && (
                <span className="rounded-full bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700">
                  Còn {remaining} ngày
                </span>
              )}
            </div>
          </div>
          <StatusControl event={event} checklist={data.checklist} gala={data.gala} />
        </div>
        <div className="border-t border-slate-100 px-4 py-3 sm:px-5">
          <LifecycleStepper status={event.status} statusLabel={event.status_label} />
        </div>
      </section>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat icon={Users} label="Tổng nhân sự" value={stats.total_users} hint="Mọi tài khoản đang hoạt động, gồm BTC" />
        <Stat icon={CheckCircle2} label="Đã phản hồi" value={responded} total={stats.total_users} tone="emerald" />
        <Stat
          icon={UserRound}
          label="Xác nhận tham gia"
          value={stats.participating}
          hint={`${stats.not_participating} không đi · ${stats.cancelled} huỷ`}
          tone="brand"
        />
        <Stat
          icon={Clock}
          label="Chưa phản hồi"
          value={stats.not_submitted}
          hint={stats.not_submitted ? 'Bấm để xem danh sách' : 'Ai cũng đã phản hồi'}
          tone={stats.not_submitted ? 'amber' : 'slate'}
          to={stats.not_submitted ? '/admin/users?registration=none' : undefined}
        />
      </div>

      {/* Điện thoại: Việc cần làm lên ngay sau số liệu. Màn rộng: nằm đầu cột phải. */}
      <div className="grid gap-4 xl:grid-cols-12 xl:items-start">
        <div className="min-w-0 xl:col-span-4 xl:col-start-9 xl:row-start-1">
          <ActionCenter data={data} onRemind={setReminderKind} onAssignLeader={setLeaderTeam} />
        </div>

        <div className="flex min-w-0 flex-col gap-4 xl:col-span-8 xl:col-start-1 xl:row-span-2 xl:row-start-1">
          <AllocationProgress
            participants={stats.participating}
            flights={data.flights}
            buses={data.buses}
            rooms={data.rooms}
            gala={data.gala}
            shiftDemand={event.is_published ? null : stats.by_shift}
          />
          <TeamTable teams={data.teams} onAssignLeader={setLeaderTeam} />
        </div>

        <aside className="flex min-w-0 flex-col gap-4 xl:col-span-4 xl:col-start-9">
          <SystemCard emails={data.emails} published={event.is_published} />
          <ActivityFeed items={data.recent_activity} />
        </aside>
      </div>

      {reminderKind && <ReminderDialog kind={reminderKind} onClose={() => setReminderKind(null)} />}
      {leaderTeam && (
        <TeamLeaderDialog key={leaderTeam.team_id} team={leaderTeam} onClose={() => setLeaderTeam(null)} />
      )}
    </div>
  )
}

const STAT_TONES = {
  slate: 'bg-slate-100 text-slate-600',
  emerald: 'bg-emerald-50 text-emerald-600',
  amber: 'bg-amber-50 text-amber-600',
  brand: 'bg-brand-50 text-brand-600',
}

function Stat({ icon: Icon, label, value, hint, total, tone = 'slate', to }) {
  const percent = total ? Math.round((value / total) * 100) : null
  const body = (
    <>
      <span className={`grid size-9 shrink-0 place-items-center rounded-lg ${STAT_TONES[tone]}`}>
        <Icon className="size-4.5" aria-hidden="true" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-xs text-slate-500">{label}</p>
        <p className="text-xl leading-tight font-bold text-slate-900 tabular-nums">
          {formatNumber(value)}
          {percent !== null && <span className="ml-1.5 text-xs font-medium text-slate-400">{percent}%</span>}
        </p>
        {percent !== null ? (
          <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-slate-100">
            <div className="h-full rounded-full bg-emerald-500" style={{ width: `${Math.min(percent, 100)}%` }} />
          </div>
        ) : (
          hint && <p className="truncate text-xs text-slate-400">{hint}</p>
        )}
      </div>
    </>
  )

  const className = 'flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-xs'
  return to ? (
    <Link to={to} className={`${className} transition hover:border-amber-300 hover:bg-amber-50/40`}>
      {body}
    </Link>
  ) : (
    <div className={className}>{body}</div>
  )
}
