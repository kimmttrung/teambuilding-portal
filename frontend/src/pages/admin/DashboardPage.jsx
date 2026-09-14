import { useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, Bus, Calendar, CheckCircle2, MapPin, UserRound, Users, XCircle } from 'lucide-react'
import { useDashboard } from '../../hooks/useDashboard'
import { EVENT_STATUS_META } from '../../utils/constants'
import { daysUntil, formatDate, formatNumber } from '../../utils/format'
import Alert from '../../components/common/Alert'
import Badge from '../../components/common/Badge'
import Card from '../../components/common/Card'
import Spinner from '../../components/common/Spinner'
import ReminderDialog from '../../components/admin/ReminderDialog'
import ActivityFeed from './dashboard/ActivityFeed'
import AllocationProgress from './dashboard/AllocationProgress'
import EmailCard from './dashboard/EmailCard'
import PublishChecklist from './dashboard/PublishChecklist'
import ReminderCard from './dashboard/ReminderCard'
import StatusControl from './dashboard/StatusControl'
import TeamTable from './dashboard/TeamTable'

/**
 * Dashboard BTC: trả lời "đang ở bước nào, còn thiếu gì trước khi công bố".
 * Một request `/admin/dashboard` — số liệu đều do backend đếm, client không tự cộng trừ.
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
  const statusMeta = EVENT_STATUS_META[event.status] ?? { tone: 'slate' }
  const responded = stats.submitted + stats.cancelled
  const remaining = daysUntil(event.start_date)

  return (
    <div className="flex flex-col gap-4">
      {/* Dải tiêu đề gộp tên kỳ, ngày, trạng thái và đếm ngược */}
      <header className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 rounded-xl border border-slate-200 bg-white px-4 py-3">
        <div className="min-w-0">
          <h1 className="truncate text-lg font-bold text-slate-900">{event.name}</h1>
          <div className="mt-0.5 flex flex-wrap items-center gap-x-4 gap-y-0.5 text-sm text-slate-500">
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
            {remaining > 0 && <span>Còn {remaining} ngày</span>}
          </div>
        </div>
        <Badge tone={statusMeta.tone}>{event.status_label}</Badge>
      </header>

      {stats.missing_flight_documents > 0 && (
        <Alert tone="warning" title="Có người chưa đủ giấy tờ để xuất vé">
          {stats.missing_flight_documents} CBNV đã xác nhận tham gia nhưng thiếu số CCCD hoặc ngày
          sinh.{' '}
          <Link
            to="/admin/registrations?missing_documents=true"
            className="font-medium underline underline-offset-2"
          >
            Xem danh sách
          </Link>
          {' · '}
          <button
            type="button"
            onClick={() => setReminderKind('missing_documents')}
            className="font-medium underline underline-offset-2"
          >
            Gửi email nhắc
          </button>
        </Alert>
      )}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat icon={Users} label="Tổng CBNV" value={stats.total_users} />
        <Stat
          icon={CheckCircle2}
          label="Đã phản hồi"
          value={responded}
          hint={`${percent(responded, stats.total_users)}% tổng số`}
          tone="emerald"
        />
        <Stat
          icon={UserRound}
          label="Xác nhận đi"
          value={stats.participating}
          hint={`${stats.not_participating} không đi · ${stats.cancelled} huỷ`}
          tone="brand"
        />
        <Stat
          icon={XCircle}
          label="Chưa phản hồi"
          value={stats.not_submitted}
          tone={stats.not_submitted ? 'amber' : 'slate'}
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-12">
        <div className="flex min-w-0 flex-col gap-4 xl:col-span-8">
          <AllocationProgress
            participants={stats.participating}
            flights={data.flights}
            buses={data.buses}
            rooms={data.rooms}
            gala={data.gala}
          />
          <TeamTable teams={data.teams} />

          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Nguyện vọng theo ca" description="Cơ sở để mua slot từng chuyến bay">
              <Distribution
                data={stats.by_shift}
                total={stats.participating}
                empty="Chưa có ai chọn ca."
              />
            </Card>
            <Card title="Nhu cầu xe theo chặng" description="Số người đăng ký đi xe của BTC">
              <Distribution
                data={stats.bus_demand_by_leg}
                total={stats.participating}
                icon={Bus}
                empty="Chưa có nhu cầu xe nào."
              />
            </Card>
          </div>
        </div>

        <aside className="flex min-w-0 flex-col gap-4 xl:col-span-4">
          <StatusControl event={event} checklist={data.checklist} gala={data.gala} />
          <PublishChecklist
            items={data.checklist}
            ready={data.ready_to_publish}
            published={event.is_published}
          />
          <ReminderCard stats={stats} event={event} onRemind={setReminderKind} />
          <EmailCard emails={data.emails} />
          <ActivityFeed items={data.recent_activity} />
        </aside>
      </div>

      {reminderKind && <ReminderDialog kind={reminderKind} onClose={() => setReminderKind(null)} />}
    </div>
  )
}

function percent(value, total) {
  return total ? Math.round((value / total) * 100) : 0
}

const STAT_TONES = {
  slate: 'bg-slate-100 text-slate-600',
  emerald: 'bg-emerald-50 text-emerald-600',
  amber: 'bg-amber-50 text-amber-600',
  brand: 'bg-brand-50 text-brand-600',
}

function Stat({ icon: Icon, label, value, hint, tone = 'slate' }) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3">
      <span className={`grid size-9 shrink-0 place-items-center rounded-lg ${STAT_TONES[tone]}`}>
        <Icon className="size-4.5" aria-hidden="true" />
      </span>
      <div className="min-w-0">
        <p className="truncate text-xs text-slate-500">{label}</p>
        <p className="text-xl leading-tight font-bold text-slate-900 tabular-nums">
          {formatNumber(value)}
        </p>
        {hint && <p className="truncate text-xs text-slate-400">{hint}</p>}
      </div>
    </div>
  )
}

/** Thanh tỉ lệ: đọc được bằng số lẫn độ dài, không chỉ dựa vào màu. */
function Distribution({ data, total, icon: Icon = AlertTriangle, empty }) {
  const entries = Object.entries(data ?? {})
  if (!entries.length) return <p className="text-sm text-slate-500">{empty}</p>

  return (
    <ul className="space-y-2.5">
      {entries.map(([label, value]) => {
        const width = Math.min(100, percent(value, total || 1))
        return (
          <li key={label}>
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="inline-flex min-w-0 items-center gap-2 font-medium text-slate-700">
                <Icon className="size-3.5 shrink-0 text-slate-400" aria-hidden="true" />
                <span className="truncate">{label}</span>
              </span>
              <span className="shrink-0 text-slate-600 tabular-nums">
                {formatNumber(value)} <span className="text-slate-400">({width}%)</span>
              </span>
            </div>
            <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-100">
              <div className="h-full rounded-full bg-brand-500" style={{ width: `${width}%` }} />
            </div>
          </li>
        )
      })}
    </ul>
  )
}
