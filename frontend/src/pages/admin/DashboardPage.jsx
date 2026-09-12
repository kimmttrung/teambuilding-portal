import { AlertTriangle, Bus, Calendar, CheckCircle2, MapPin, UserRound, Users, XCircle } from 'lucide-react'
import { useActiveEvent, useEventOverview, useRegistrationStats } from '../../hooks/useEvent'
import { EVENT_STATUS_META } from '../../utils/constants'
import { daysUntil, formatDate, formatNumber } from '../../utils/format'
import Alert from '../../components/common/Alert'
import Badge from '../../components/common/Badge'
import Card from '../../components/common/Card'
import Spinner from '../../components/common/Spinner'

export default function DashboardPage() {
  const { data: event, isLoading, error } = useActiveEvent()
  const { data: stats } = useRegistrationStats()
  const { data: overview } = useEventOverview(event?.id)

  if (isLoading) return <Spinner />
  if (error) {
    return (
      <Alert tone="warning" title="Chưa có kỳ Team Building nào đang mở">
        Tạo kỳ mới và đặt làm kỳ đang chạy để bắt đầu.
      </Alert>
    )
  }

  const statusMeta = EVENT_STATUS_META[event.status] ?? { label: event.status, tone: 'slate' }
  const responded = (stats?.submitted ?? 0) + (stats?.cancelled ?? 0)
  const responseRate = stats?.total_users ? Math.round((responded / stats.total_users) * 100) : 0
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
        <Badge tone={statusMeta.tone}>{statusMeta.label}</Badge>
      </header>

      {stats?.missing_flight_documents > 0 && (
        <Alert tone="warning" title="Có người chưa đủ giấy tờ để xuất vé">
          {stats.missing_flight_documents} CBNV đã xác nhận tham gia nhưng thiếu số CCCD hoặc ngày
          sinh. Cần nhắc bổ sung trước khi đặt vé máy bay.
        </Alert>
      )}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat icon={Users} label="Tổng CBNV" value={stats?.total_users} />
        <Stat
          icon={CheckCircle2}
          label="Đã phản hồi"
          value={stats?.submitted}
          hint={`${responseRate}% tổng số`}
          tone="emerald"
        />
        <Stat icon={UserRound} label="Xác nhận đi" value={stats?.participating} tone="brand" />
        <Stat
          icon={XCircle}
          label="Chưa phản hồi"
          value={stats?.not_submitted}
          tone={stats?.not_submitted ? 'amber' : 'slate'}
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-12">
        <Card
          title="Nguyện vọng theo ca"
          description="Cơ sở để mua slot từng chuyến bay"
          className="xl:col-span-4"
        >
          <Distribution data={stats?.by_shift} total={stats?.participating} empty="Chưa có ai chọn ca." />
        </Card>

        <Card
          title="Nhu cầu xe theo chặng"
          description="Số người đăng ký đi xe của BTC"
          className="xl:col-span-5"
        >
          <Distribution
            data={stats?.bus_demand_by_leg}
            total={stats?.participating}
            icon={Bus}
            empty="Chưa có nhu cầu xe nào."
          />
        </Card>

        <Card title="Trạng thái chương trình" className="xl:col-span-3">
          {overview ? (
            <div className="space-y-3 text-sm">
              <div>
                <p className="text-xs tracking-wide text-slate-400 uppercase">Hiện tại</p>
                <p className="mt-0.5 font-medium text-slate-900">{overview.status_label}</p>
              </div>
              <div>
                <p className="text-xs tracking-wide text-slate-400 uppercase">Chuyển được sang</p>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {overview.allowed_next_statuses.map((status) => (
                    <Badge key={status} tone="slate">
                      {EVENT_STATUS_META[status]?.label ?? status}
                    </Badge>
                  ))}
                </div>
              </div>
              <dl className="grid grid-cols-2 gap-2 border-t border-slate-100 pt-3">
                <MiniStat label="Không tham gia" value={stats?.not_participating} />
                <MiniStat label="Đã huỷ" value={stats?.cancelled} />
              </dl>
              <p className="text-xs text-slate-400">Nút chuyển trạng thái nằm ở bước 18.</p>
            </div>
          ) : (
            <p className="text-sm text-slate-500">Đang tải…</p>
          )}
        </Card>
      </div>
    </div>
  )
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
          {value === undefined ? '—' : formatNumber(value)}
        </p>
        {hint && <p className="truncate text-xs text-slate-400">{hint}</p>}
      </div>
    </div>
  )
}

function MiniStat({ label, value }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="text-base font-semibold text-slate-900 tabular-nums">
        {value === undefined ? '—' : formatNumber(value)}
      </dd>
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
        const percent = Math.min(100, Math.round((value / (total || 1)) * 100))
        return (
          <li key={label}>
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="inline-flex min-w-0 items-center gap-2 font-medium text-slate-700">
                <Icon className="size-3.5 shrink-0 text-slate-400" aria-hidden="true" />
                <span className="truncate">{label}</span>
              </span>
              <span className="shrink-0 tabular-nums text-slate-600">
                {formatNumber(value)} <span className="text-slate-400">({percent}%)</span>
              </span>
            </div>
            <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-100">
              <div className="h-full rounded-full bg-brand-500" style={{ width: `${percent}%` }} />
            </div>
          </li>
        )
      })}
    </ul>
  )
}
