import { useState } from 'react'
import {
  BedDouble,
  Bus,
  CalendarDays,
  Flag,
  MapPin,
  PartyPopper,
  Plane,
  Utensils,
  Waves,
} from 'lucide-react'
import { useMyJourney } from '../../hooks/useJourney'
import { formatDate, formatDateWithWeekday, formatTime } from '../../utils/format'
import { buildIcs } from '../../utils/travel'
import Alert from '../../components/common/Alert'
import EmptyState from '../../components/common/EmptyState'
import Spinner from '../../components/common/Spinner'
import PageContainer from '../../components/layout/PageContainer'

const TYPE_META = {
  bus: { Icon: Bus, icon: 'bg-accent-green text-white', match: /xe|đón|đưa|sân bay/i },
  flight: { Icon: Plane, icon: 'bg-accent-sky text-white', match: /chuyến bay|flight|han|pqc|sgn/i },
  hotel: { Icon: BedDouble, icon: 'bg-accent-purple-deep text-white', match: /phòng|nhận phòng|trả phòng|khách sạn/i },
  gala: { Icon: PartyPopper, icon: 'bg-accent-pink text-white', match: /gala|dinner|vinh danh/i },
  meal: { Icon: Utensils, icon: 'bg-accent-orange text-white', match: /ăn|sáng|trưa|tối|bbq|buffet|coffee/i },
  activity: { Icon: Waves, icon: 'bg-accent-teal text-white', match: /biển|bãi|team|chơi|tự do|tham quan/i },
  program: { Icon: Flag, icon: 'bg-slate-300 text-white', match: /.*/i },
}

export default function SchedulePage() {
  const { data: journey, isLoading, error } = useMyJourney()

  if (isLoading) return <Spinner label="Đang tải lịch trình…" />
  if (error) {
    return (
      <Alert tone="warning" title="Chưa xem được lịch trình">
        {error.message}
      </Alert>
    )
  }

  const event = journey?.event
  const items = journey?.itinerary ?? []
  const days = groupByDay(items)
  const eventDays = buildEventDays(event, days)
  const nextKey = findNextKey(items)

  if (!event) return <EmptyState icon={CalendarDays} title="Chưa có kỳ Team Building" />

  return (
    <PageContainer>
      <div className="md:hidden">
        <MobileSchedule
          event={event}
          items={items}
          days={eventDays}
          nextKey={nextKey}
          onDownload={() => downloadScheduleIcs(items, event)}
        />
      </div>

      <div className="hidden md:block">
        <header className="mb-7 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-page-title text-ink">Lịch trình</h1>
            <p className="mt-1 text-body-sm text-ink-muted">Giờ Việt Nam</p>
          </div>
          <button
            type="button"
            onClick={() => downloadScheduleIcs(items, event)}
            disabled={items.length === 0}
            className="inline-flex items-center gap-2 rounded-lg border border-hairline bg-surface px-3 py-2 text-body-sm font-medium text-ink shadow-soft transition hover:border-primary/40 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <CalendarDays className="size-4" />
            Thêm cả {eventDays.length || ''} ngày vào lịch (.ics)
          </button>
        </header>

        {!event.is_published && (
          <Alert tone="info" className="mb-5">
            Lịch trình chung sẽ được cập nhật thêm khi BTC công bố kết quả phân bổ.
          </Alert>
        )}

        {days.length === 0 ? (
          <div className="rounded-xl border border-hairline bg-surface p-8">
            <EmptyState
              icon={CalendarDays}
              title="Chưa có lịch trình"
              description="BTC sẽ cập nhật các hoạt động trước chuyến đi."
            />
          </div>
        ) : (
          <div className="grid items-start gap-4 lg:grid-cols-3">
            {days.map((day, index) => (
              <ScheduleDay key={day.date} day={day} dayIndex={index + 1} nextKey={nextKey} />
            ))}
          </div>
        )}
      </div>
    </PageContainer>
  )
}

function MobileSchedule({ event, items, days, nextKey, onDownload }) {
  const [selectedDate, setSelectedDate] = useState(days[0]?.date)
  const selectedDay = days.find((day) => day.date === selectedDate) ?? days[0]
  const updatedTime = event.updated_at ? formatTime(event.updated_at) : null

  return (
    <div className="pb-3">
      <header className="mb-5 px-1">
        <h1 className="text-page-title text-ink">Lịch trình</h1>
        <p className="mt-1 text-body-sm text-ink-muted">
          Giờ Việt Nam{updatedTime ? ` · cập nhật ${updatedTime} hôm nay` : ''}
        </p>
      </header>

      <div className="mb-5 grid grid-cols-3 gap-2">
        {days.map((day) => {
          const selected = day.date === selectedDay?.date
          return (
            <button
              key={day.date}
              type="button"
              onClick={() => setSelectedDate(day.date)}
              className={`rounded-xl border px-3 py-2 text-left transition ${
                selected
                  ? 'border-primary bg-primary text-on-primary'
                  : 'border-hairline bg-surface text-ink-secondary hover:border-ink/30'
              }`}
            >
              <span className={`block text-caption ${selected ? 'text-white/70' : 'text-ink-muted'}`}>
                {mobileWeekday(day.date)}
              </span>
              <strong className="mt-0.5 block text-body-md font-semibold">{formatDate(day.date).slice(0, 5)}</strong>
            </button>
          )
        })}
      </div>

      {!event.is_published && (
        <p className="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-caption leading-relaxed text-amber-900">
          Lịch trình sẽ được cập nhật thêm khi BTC công bố thông tin phân bổ.
        </p>
      )}

      {selectedDay?.items.length ? (
        <div className="relative">
          <span className="absolute bottom-4 left-[19px] top-3 w-px bg-hairline" aria-hidden="true" />
          <div className="relative flex flex-col gap-2.5">
            {selectedDay.items.map((item, index) => (
              <MobileScheduleItem
                key={item.id ?? `${item.day_date}-${item.start_time}-${item.title}-${index}`}
                item={item}
                isNext={itemKey(item, index) === nextKey}
              />
            ))}
          </div>
        </div>
      ) : (
        <div className="rounded-xl border border-dashed border-hairline px-4 py-8 text-center text-body-sm text-ink-muted">
          BTC chưa cập nhật mốc cho ngày này.
        </div>
      )}

      <button
        type="button"
        onClick={onDownload}
        disabled={items.length === 0}
        className="mt-6 flex w-full items-center justify-center gap-2 rounded-full border border-hairline bg-surface px-4 py-3 text-body-md font-medium text-ink shadow-soft disabled:cursor-not-allowed disabled:opacity-50"
      >
        <CalendarDays className="size-4" />
        Thêm cả {days.length} ngày vào lịch (.ics)
      </button>
    </div>
  )
}

function MobileScheduleItem({ item, isNext }) {
  const meta = itemMeta(item)
  const Icon = meta.Icon
  const detail = item.description || item.location || (item.audience !== 'all' ? item.audience : '')

  return (
    <div className="flex min-w-0 gap-3">
      <time className="w-10 shrink-0 pt-1 text-caption font-semibold tabular-nums text-ink-muted">
        {item.start_time || '—'}
      </time>
      <article
        className={`min-w-0 flex-1 rounded-xl border bg-surface px-3.5 py-3 shadow-soft ${
          isNext ? 'border-primary ring-1 ring-brand-100' : 'border-hairline'
        }`}
      >
        <div className="flex min-w-0 items-start gap-3">
          <span className={`mt-0.5 grid size-7 shrink-0 place-items-center rounded-lg ${meta.icon}`}>
            <Icon className="size-4" aria-hidden="true" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-body-sm font-semibold leading-tight text-ink">{item.title}</p>
            {detail && <p className="mt-1 text-caption leading-relaxed text-ink-muted">{detail}</p>}
          </div>
          {isNext && (
            <span className="shrink-0 rounded-md bg-brand-50 px-2 py-1 text-eyebrow font-semibold text-primary">
              Tiếp theo
            </span>
          )}
        </div>
      </article>
    </div>
  )
}

function ScheduleDay({ day, dayIndex, nextKey }) {
  return (
    <section>
      <header className="mb-3 flex items-center gap-2 px-1">
        <h2 className="text-heading-3 text-ink">{formatDate(day.date).slice(0, 5)}</h2>
        <span className="text-body-md text-ink-muted">{weekday(day.date)}</span>
        {dayIndex === 1 && (
          <span className="ml-auto rounded-md bg-brand-50 px-2 py-1 text-eyebrow font-semibold text-primary">
            Ngày 1
          </span>
        )}
      </header>
      <div className="flex flex-col gap-2">
        {day.items.map((item, index) => (
          <ScheduleItemCard
            key={item.id ?? `${item.day_date}-${item.start_time}-${item.title}-${index}`}
            item={item}
            isNext={itemKey(item, index) === nextKey}
          />
        ))}
      </div>
    </section>
  )
}

function ScheduleItemCard({ item, isNext }) {
  const meta = itemMeta(item)
  const Icon = meta.Icon

  return (
    <article
      className={`rounded-xl border bg-surface px-3.5 py-3 shadow-soft transition ${
        isNext ? 'border-primary ring-2 ring-brand-100' : 'border-hairline'
      }`}
    >
      <div className="flex items-center gap-3">
        <span className="w-10 shrink-0 text-body-sm font-semibold tabular-nums text-ink-muted">
          {item.start_time || '—'}
        </span>
        <span className={`grid size-7 shrink-0 place-items-center rounded-lg ${meta.icon}`}>
          <Icon className="size-4" aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-body-md font-semibold text-ink">{item.title}</p>
          {item.end_time && (
            <p className="text-caption text-ink-muted">đến {item.end_time}</p>
          )}
        </div>
        {isNext && (
          <span className="shrink-0 rounded-md bg-brand-50 px-2 py-1 text-eyebrow font-semibold text-primary">
            Tiếp theo
          </span>
        )}
      </div>
      {(item.location || item.description || item.audience !== 'all') && (
        <div className="mt-2 pl-[4.75rem] text-caption text-ink-muted">
          {item.location && (
            <p className="flex items-center gap-1 truncate">
              <MapPin className="size-3.5 shrink-0" aria-hidden="true" />
              {item.location}
            </p>
          )}
          {item.description && <p className="mt-1 line-clamp-2">{item.description}</p>}
          {item.audience !== 'all' && (
            <p className="mt-1 text-eyebrow text-ink-faint">{item.audience}</p>
          )}
        </div>
      )}
    </article>
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
    .map(([date, dayItems]) => ({
      date,
      items: dayItems
        .map((item, index) => ({ item, index }))
        .sort((left, right) => {
          const leftTime = left.item.start_time || '99:99'
          const rightTime = right.item.start_time || '99:99'
          return leftTime.localeCompare(rightTime) || left.index - right.index
        })
        .map(({ item }) => item),
    }))
}

function buildEventDays(event, groupedDays) {
  if (!event?.start_date || !event?.end_date) return groupedDays

  const grouped = new Map(groupedDays.map((day) => [day.date, day.items]))
  const start = new Date(`${event.start_date}T00:00:00Z`)
  const end = new Date(`${event.end_date}T00:00:00Z`)
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return groupedDays

  const days = []
  for (const cursor = new Date(start); cursor <= end; cursor.setUTCDate(cursor.getUTCDate() + 1)) {
    const date = cursor.toISOString().slice(0, 10)
    days.push({ date, items: grouped.get(date) ?? [] })
  }
  return days
}

function findNextKey(items) {
  const now = new Date()
  const upcoming = items
    .map((item, index) => ({ item, index, date: itemDate(item) }))
    .filter(({ date }) => date && date >= now)
    .sort((left, right) => left.date - right.date)[0]

  if (upcoming) return itemKey(upcoming.item, upcoming.index)
  return items.length ? itemKey(items[0], 0) : null
}

function itemKey(item) {
  return item.id ?? `${item.day_date}-${item.start_time}-${item.title}`
}

function itemDate(item) {
  if (!item.day_date) return null
  const date = new Date(`${item.day_date}T${item.start_time || '00:00'}:00+07:00`)
  return Number.isNaN(date.getTime()) ? null : date
}

function itemMeta(item) {
  const text = `${item.title} ${item.location || ''}`
  return Object.values(TYPE_META).find((meta) => meta.match.test(text)) ?? TYPE_META.program
}

function weekday(value) {
  const text = formatDateWithWeekday(value)
  return text.split(',')[0]
}

function mobileWeekday(value) {
  return new Intl.DateTimeFormat('vi-VN', { weekday: 'long', timeZone: 'Asia/Ho_Chi_Minh' })
    .format(new Date(`${value}T00:00:00+07:00`))
    .replace(/^./, (letter) => letter.toUpperCase())
}

function downloadScheduleIcs(items, event) {
  const blocks = []
  const scheduledDates = new Set()

  for (const item of items) {
    if (!item.day_date) continue

    const hasTime = Boolean(item.start_time)
    const ics = buildIcs({
      uid: `itinerary-${item.id ?? `${item.day_date}-${item.start_time ?? 'all-day'}-${item.title}`}`,
      title: item.title,
      start: hasTime ? `${item.day_date}T${item.start_time}:00+07:00` : item.day_date,
      end: hasTime && item.end_time ? `${item.day_date}T${item.end_time}:00+07:00` : undefined,
      location: item.location,
      description: [item.description, event.name].filter(Boolean).join(' · '),
      allDay: !hasTime,
      alarmMinutes: hasTime ? 60 : null,
    })
    blocks.push(eventBlock(ics))
    scheduledDates.add(item.day_date)
  }

  // Giữ đủ toàn bộ ngày của kỳ, kể cả ngày chưa có mốc có giờ trong lịch.
  for (const day of buildEventDays(event, [])) {
    if (scheduledDates.has(day.date)) continue
    const ics = buildIcs({
      uid: `event-day-${day.date}`,
      title: `Team Building · ${event.destination || event.name}`,
      start: day.date,
      description: event.name,
      alarmMinutes: null,
      allDay: true,
    })
    blocks.push(eventBlock(ics))
  }

  if (blocks.length === 0) return
  const blob = new Blob(
    [
      ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Team Building Portal//VI', 'CALSCALE:GREGORIAN', ...blocks, 'END:VCALENDAR'].join('\r\n'),
    ],
    { type: 'text/calendar;charset=utf-8' },
  )
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'lich-trinh-team-building.ics'
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function eventBlock(ics) {
  const start = ics.indexOf('BEGIN:VEVENT')
  const end = ics.indexOf('END:VEVENT') + 'END:VEVENT'.length
  return ics.slice(start, end)
}
