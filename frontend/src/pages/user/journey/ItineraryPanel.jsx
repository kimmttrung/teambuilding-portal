import { Link } from 'react-router-dom'
import { CalendarDays, MapPin } from 'lucide-react'
import { formatDateWithWeekday } from '../../../utils/format'
import Card from '../../../components/common/Card'
import EmptyState from '../../../components/common/EmptyState'

/**
 * Lịch trình theo ngày.
 *
 * Mốc gắn chặng xe (tập trung tại điểm đón) chỉ có trong lịch của người ĐI XE chặng đó, và giờ
 * là giờ xe của chính họ — backend đã lọc và thay sẵn (`journey_service._itinerary`), frontend
 * chỉ đánh dấu "Riêng bạn" để không ai tưởng đó là mốc chung của cả đoàn.
 * - `compact`: 2 ngày gần nhất, đặt ở cột phụ của My Journey.
 * - `full`: mọi ngày, mỗi ngày một thẻ, dùng cho trang /schedule.
 */
export default function ItineraryPanel({ items = [], variant = 'compact' }) {
  const days = groupByDay(items)

  if (variant === 'compact') {
    const today = localDateKey(new Date())
    const upcoming = days.filter((day) => day.date >= today)
    const shown = (upcoming.length ? upcoming : days).slice(0, 2)

    return (
      <Card
        title="Lịch trình"
        description={days.length ? `${days.length} ngày` : undefined}
        action={
          <Link to="/schedule" className="text-xs font-medium text-brand-700 hover:underline">
            Xem tất cả
          </Link>
        }
      >
        {days.length === 0 ? (
          <p className="text-sm text-slate-500">BTC chưa đăng lịch trình.</p>
        ) : (
          <div className="flex flex-col gap-3">
            {shown.map((day) => (
              <DayBlock key={day.date} day={day} />
            ))}
          </div>
        )}
      </Card>
    )
  }

  if (days.length === 0) {
    return (
      <Card>
        <EmptyState
          icon={CalendarDays}
          title="Chưa có lịch trình"
          description="BTC sẽ đăng lịch trình chi tiết trước chuyến đi."
        />
      </Card>
    )
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
      {days.map((day) => (
        <Card
          key={day.date}
          title={formatDateWithWeekday(day.date)}
          description={`${day.items.length} hoạt động`}
        >
          <DayBlock day={day} hideTitle />
        </Card>
      ))}
    </div>
  )
}

function DayBlock({ day, hideTitle = false }) {
  return (
    <div>
      {!hideTitle && (
        <p className="mb-1.5 text-xs font-semibold tracking-wide text-slate-400 uppercase">
          {formatDateWithWeekday(day.date)}
        </p>
      )}
      <ol className="flex flex-col gap-2">
        {day.items.map((item) => (
          // Mốc "tự di chuyển" do hệ thống sinh nên không có id — ghép khoá từ nội dung.
          <li key={item.id ?? `${item.day_date}-${item.start_time}-${item.title}`} className="flex gap-3">
            <span className="w-12 shrink-0 text-sm font-semibold text-slate-900 tabular-nums">
              {item.start_time ?? '—'}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-sm text-slate-800">
                {item.title}
                {item.is_personal && (
                  <span className="ml-1.5 rounded bg-amber-100 px-1.5 py-0.5 align-middle text-[11px] font-medium text-amber-800">
                    Riêng bạn
                  </span>
                )}
              </span>
              {item.location && (
                <span className="mt-0.5 inline-flex items-center gap-1 text-xs text-slate-500">
                  <MapPin className="size-3" aria-hidden="true" />
                  {item.location}
                </span>
              )}
              {item.description && (
                <span className="mt-0.5 block text-xs text-slate-500">{item.description}</span>
              )}
            </span>
          </li>
        ))}
      </ol>
    </div>
  )
}

function groupByDay(items) {
  const byDay = new Map()
  for (const item of items) {
    const list = byDay.get(item.day_date)
    if (list) list.push(item)
    else byDay.set(item.day_date, [item])
  }
  return [...byDay.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([date, list]) => ({ date, items: list }))
}

/** Ngày theo giờ máy (không phải UTC): trước 7 giờ sáng giờ VN, ngày UTC vẫn là hôm qua. */
function localDateKey(date) {
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
}
