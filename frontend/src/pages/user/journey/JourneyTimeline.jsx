import {
  BedDouble,
  Bus,
  Crown,
  Flag,
  MapPin,
  PartyPopper,
  PlaneTakeoff,
  Users,
  UtensilsCrossed,
} from 'lucide-react'
import { FLIGHT_DIRECTION_LABELS, ROOM_TYPE_LABELS } from '../../../utils/constants'
import {
  formatDateWithWeekday,
  formatFullDateTime,
  formatTime,
  TIMEZONE_NOTE,
} from '../../../utils/format'
import Badge from '../../../components/common/Badge'
import Card from '../../../components/common/Card'
import EmptyState from '../../../components/common/EmptyState'
import { PassengersButton } from './LedBusCard'
import { AddToCalendarButton, InfoRow, MapLink, PhoneLink } from './TravelLinks'

/**
 * Trục thời gian hợp nhất của My Journey: lịch trình chung (xương sống) + vé cá nhân
 * (giờ thật từ phân bổ) gộp vào cùng một mốc.
 *
 * Nguyên tắc (theo yêu cầu CBNV):
 * - Giờ bay/xe lấy từ phân bổ (`journey.flights`/`journey.buses`), KHÔNG lấy giờ chữ
 *   trong lịch trình — lịch trình chỉ mô tả "làm gì ở đâu", vé của bạn mới nói "mấy giờ".
 * - Lịch trình là xương sống: gom mốc theo ngày, sắp theo giờ. Vé nào khớp được mốc
 *   (cùng ngày + tiêu đề/giờ gần nhau) thì gộp vào mốc đó; vé không khớp mốc nào thì
 *   thành mốc riêng để không mất thông tin.
 * - Xe mình phụ trách (Trưởng xe) có viền vàng + huy hiệu, nhìn lướt cũng thấy.
 */

const BUS_TITLE_HINT = /tập trung|điểm đón|đón\b|xe\b|ra sân bay|tiễn/i
const FLIGHT_TITLE_HINT = /chuyến bay|\bbay\b|HAN|PQC|Nội Bài|Phú Quốc|Sài Gòn|SGN/i
const HOTEL_TITLE_HINT = /nhận phòng|trả phòng|khách sạn|check-?in|check-?out/i
const GALA_TITLE_HINT = /gala|vinh danh/i
/** Vé và mốc chương trình lệch nhau trong khoảng này thì coi là cùng một việc. */
const MERGE_WINDOW_MINUTES = 120

const KIND_META = {
  flight: { label: 'Chuyến bay', Icon: PlaneTakeoff, ring: 'border-sky-300', chip: 'bg-sky-100 text-sky-800' },
  bus: { label: 'Xe đưa đón', Icon: Bus, ring: 'border-emerald-300', chip: 'bg-emerald-100 text-emerald-800' },
  hotel: { label: 'Khách sạn', Icon: BedDouble, ring: 'border-violet-300', chip: 'bg-violet-100 text-violet-800' },
  gala: { label: 'Gala', Icon: PartyPopper, ring: 'border-pink-300', chip: 'bg-pink-100 text-pink-800' },
  meal: { label: 'Ăn uống', Icon: UtensilsCrossed, ring: 'border-orange-300', chip: 'bg-orange-100 text-orange-800' },
  activity: { label: 'Hoạt động', Icon: Flag, ring: 'border-teal-300', chip: 'bg-teal-100 text-teal-800' },
  program: { label: 'Chương trình', Icon: MapPin, ring: 'border-slate-300', chip: 'bg-slate-100 text-slate-700' },
}

export default function JourneyTimeline({ journey, onOpenPassengers }) {
  const days = buildDays(journey)
  const next = findNext(days, new Date())
  const ledCount = (journey?.led_buses ?? []).length

  if (days.length === 0) {
    return (
      <Card title="Hành trình của bạn">
        <EmptyState
          icon={MapPin}
          title="Chưa có lịch trình"
          description="BTC sẽ đăng lịch trình chi tiết trước chuyến đi. Vé bay, xe, phòng của bạn sẽ hiện ở đây sau khi công bố."
        />
      </Card>
    )
  }

  return (
    <section aria-label="Hành trình của bạn">
      {next && <NextUpBanner next={next} isLeader={ledCount > 0} />}
      {ledCount > 0 && (
        <p className="mb-2 inline-flex items-center gap-1.5 rounded-lg bg-amber-100 px-2.5 py-1.5 text-xs font-semibold text-amber-900 ring-1 ring-amber-300 ring-inset">
          <Crown className="size-3.5" aria-hidden="true" />
          Bạn là Trưởng xe — các mốc viền vàng là xe bạn phụ trách
        </p>
      )}
      <div className="flex flex-col gap-4">
        {days.map((day, index) => (
          <DayCard key={day.date} day={day} dayIndex={index + 1} onOpenPassengers={onOpenPassengers} />
        ))}
      </div>
      <p className="mt-2 text-xs text-slate-400">{TIMEZONE_NOTE} · Giờ xe và giờ bay là giờ thật từ phân bổ của BTC.</p>
    </section>
  )
}

/** Mốc sắp tới gần nhất — thứ CBNV cần nhìn đầu tiên lúc ra khỏi nhà. */
function NextUpBanner({ next, isLeader }) {
  return (
    <div className="mb-3 rounded-xl bg-gradient-to-r from-brand-700 to-brand-600 px-4 py-3 text-white">
      <p className="text-xs text-brand-200">
        {next.isToday ? 'Tiếp theo · hôm nay' : `Tiếp theo · ${formatDateWithWeekday(next.dateObj)}`}
        {isLeader && next.isLed ? ' · xe bạn phụ trách' : ''}
      </p>
      <p className="mt-0.5 text-lg leading-snug font-bold">
        {next.timeLabel} — {next.title}
      </p>
      {next.location && <p className="mt-0.5 truncate text-sm text-brand-100">{next.location}</p>}
    </div>
  )
}

function DayCard({ day, dayIndex, onOpenPassengers }) {
  const allPast = day.nodes.every((node) => node.state === 'past')
  return (
    <Card
      title={`Ngày ${dayIndex} · ${formatDateWithWeekday(day.date)}`}
      description={`${day.nodes.length} mốc${day.isToday ? ' · hôm nay' : ''}${allPast ? ' · đã qua' : ''}`}
    >
      <ol className="relative ml-2 flex flex-col gap-3 border-l-2 border-slate-200 pl-0">
        {day.nodes.map((node) => (
          <TimelineNode key={node.key} node={node} onOpenPassengers={onOpenPassengers} />
        ))}
      </ol>
    </Card>
  )
}

function TimelineNode({ node, onOpenPassengers }) {
  const meta = KIND_META[node.kind] ?? KIND_META.program
  const { Icon } = meta
  const isLed = node.bookings.some((booking) => booking.led)
  const dotTone = node.state === 'past'
    ? 'bg-slate-300'
    : node.state === 'live'
      ? 'bg-brand-600 ring-4 ring-brand-100'
      : 'bg-white ring-2 ring-brand-400'

  return (
    <li className="relative pl-7">
      <span className={`absolute top-4 -left-[7px] size-3 rounded-full ${dotTone}`} aria-hidden="true" />
      <div
        className={`rounded-xl border bg-white px-3.5 py-3 shadow-xs ${isLed ? 'border-amber-400 bg-amber-50/60 ring-2 ring-amber-300' : meta.ring} ${node.state === 'past' ? 'opacity-70' : ''}`}
      >
        <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
          <span className="text-xl leading-none font-bold text-slate-900 tabular-nums">{node.timeLabel}</span>
          <span className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-semibold ${meta.chip}`}>
            <Icon className="size-3.5" aria-hidden="true" />
            {meta.label}
          </span>
          {node.audience && node.audience !== 'all' && (
            <Badge tone="slate">{node.audience}</Badge>
          )}
          {node.state === 'live' && <Badge tone="brand">Đang diễn ra</Badge>}
          {isLed && (
            <span className="inline-flex items-center gap-1 rounded-md bg-amber-400 px-1.5 py-0.5 text-[11px] font-bold text-amber-950">
              <Crown className="size-3.5" aria-hidden="true" />
              Bạn là Trưởng xe
            </span>
          )}
        </div>

        <p className="mt-1 text-[15px] leading-snug font-semibold text-slate-900">{node.title}</p>
        {node.location && (
          <p className="mt-0.5 flex items-center gap-1 text-sm text-slate-500">
            <MapPin className="size-3.5 shrink-0" aria-hidden="true" />
            <span className="truncate">{node.location}</span>
          </p>
        )}
        {node.description && <p className="mt-0.5 text-sm text-slate-500">{node.description}</p>}

        {node.bookings.map((booking) => (
          <BookingBox key={booking.key} booking={booking} onOpenPassengers={onOpenPassengers} />
        ))}
      </div>
    </li>
  )
}

/** Vé cá nhân gắn trong mốc: giờ thật từ phân bổ, kèm nút hành động. */
function BookingBox({ booking, onOpenPassengers }) {
  if (booking.type === 'bus') return <BusBooking booking={booking} onOpenPassengers={onOpenPassengers} />
  if (booking.type === 'flight') return <FlightBooking booking={booking} />
  if (booking.type === 'hotel') return <HotelBooking booking={booking} />
  return <GalaBooking booking={booking} />
}

function BookingShell({ children }) {
  return <div className="mt-2.5 rounded-lg bg-white/80 px-3 py-2.5 ring-1 ring-slate-200 ring-inset">{children}</div>
}

function BusBooking({ booking, onOpenPassengers }) {
  const { bus, led } = booking
  const gather = bus.gather_time || bus.departure_time
  return (
    <BookingShell>
      <p className="text-sm font-semibold text-slate-900">
        Xe {bus.bus_code}
        {bus.plate_number ? ` · ${bus.plate_number}` : ''}
        {bus.trip_leg?.name ? ` · ${bus.trip_leg.name}` : ''}
      </p>
      {gather && (
        <p className="mt-0.5 text-sm text-slate-700">
          Có mặt <strong className="tabular-nums">{formatTime(gather)}</strong>
          {bus.gather_time && bus.departure_time && (
            <> · xe chạy <span className="tabular-nums">{formatTime(bus.departure_time)}</span></>
          )}
        </p>
      )}
      <dl className="mt-1.5 flex flex-col gap-1.5">
        {bus.pickup_point && (
          <InfoRow label="Điểm đón">
            <MapLink place={bus.pickup_point} />
          </InfoRow>
        )}
        {bus.dropoff_point && <InfoRow label="Điểm trả">{bus.dropoff_point}</InfoRow>}
        {bus.linked_flight_code && <InfoRow label="Chuyến bay">{bus.linked_flight_code}</InfoRow>}
        {bus.leader && (
          <InfoRow label="Trưởng xe">
            <span className="inline-flex flex-wrap items-center justify-end gap-2">
              <span className="font-medium text-slate-900">{bus.leader.name}</span>
              {led ? <Badge tone="amber">Bạn</Badge> : <PhoneLink phone={bus.leader.phone} label="Gọi" />}
            </span>
          </InfoRow>
        )}
        {led && (
          <InfoRow label="Hành khách">
            <span className="tabular-nums">{led.passenger_count}/{led.capacity}</span>
          </InfoRow>
        )}
      </dl>
      <div className="mt-2 flex flex-wrap justify-end gap-2">
        {led && <PassengersButton bus={led} onClick={onOpenPassengers} />}
        {gather && (
          <AddToCalendarButton
            filename={`xe-${bus.bus_code}`}
            event={{
              uid: `bus-${bus.trip_leg?.id ?? bus.bus_id}-${bus.bus_code}`,
              title: `Tập trung xe ${bus.bus_code}`,
              start: gather,
              end: bus.departure_time || undefined,
              location: bus.pickup_point?.name ?? bus.pickup_point?.address,
              alarmMinutes: 60,
            }}
          />
        )}
      </div>
    </BookingShell>
  )
}

function FlightBooking({ booking }) {
  const { flight } = booking
  const label = FLIGHT_DIRECTION_LABELS[flight.direction] ?? 'Chuyến bay'
  return (
    <BookingShell>
      <p className="text-sm font-semibold text-slate-900">
        {label} · {flight.flight_code}
        {flight.airline ? ` · ${flight.airline}` : ''}
      </p>
      <p className="mt-0.5 text-sm text-slate-700">
        <strong>{flight.departure_airport}</strong>{' '}
        <span className="font-bold text-brand-700 tabular-nums">{formatTime(flight.departure_time)}</span>
        {' → '}
        <strong>{flight.arrival_airport}</strong>{' '}
        <span className="tabular-nums">{formatTime(flight.arrival_time)}</span>
      </p>
      <p className="mt-0.5 text-xs text-slate-500">{formatDateWithWeekday(flight.departure_time)}</p>
      <div className="mt-1.5 flex flex-wrap items-center justify-between gap-2">
        <span className="flex flex-wrap gap-1.5">
          {flight.seat_number && <Badge tone="brand">Ghế {flight.seat_number}</Badge>}
          {flight.ticket_code && <Badge tone="slate">Vé {flight.ticket_code}</Badge>}
        </span>
        <AddToCalendarButton
          filename={`chuyen-bay-${flight.flight_code}`}
          event={{
            uid: `flight-${flight.direction}-${flight.flight_code}`,
            title: `Bay ${flight.flight_code} ${flight.departure_airport} → ${flight.arrival_airport}`,
            start: flight.departure_time,
            end: flight.arrival_time,
            location: `Sân bay ${flight.departure_airport}`,
            alarmMinutes: 180,
          }}
        />
      </div>
    </BookingShell>
  )
}

function HotelBooking({ booking }) {
  const stay = booking.accommodation
  const roomMeta = [ROOM_TYPE_LABELS[stay.room_type] ?? stay.room_type, stay.floor ? `tầng ${stay.floor}` : null]
    .filter(Boolean)
    .join(' · ')
  return (
    <BookingShell>
      <p className="text-sm font-semibold text-slate-900">
        {stay.hotel_name} · Phòng <span className="text-base tabular-nums">{stay.room_number}</span>
        {roomMeta ? ` · ${roomMeta}` : ''}
      </p>
      {(stay.address || stay.map_url) && (
        <p className="mt-0.5">
          <MapLink place={{ name: 'Chỉ đường tới khách sạn', address: stay.address, map_url: stay.map_url }} />
        </p>
      )}
      {stay.check_in_at && <p className="mt-0.5 text-sm text-slate-600">Nhận phòng {formatFullDateTime(stay.check_in_at)}</p>}
      {stay.check_out_at && <p className="mt-0.5 text-sm text-slate-600">Trả phòng {formatFullDateTime(stay.check_out_at)}</p>}
      {stay.roommates?.length > 0 && (
        <p className="mt-1 text-sm text-slate-600">
          Ở cùng: {stay.roommates.map((mate) => mate.full_name).join(', ')}
        </p>
      )}
      {stay.roommates?.length > 0 && (
        <span className="mt-1.5 flex flex-wrap gap-1.5">
          {stay.roommates.map((mate) => (
            <PhoneLink key={mate.full_name} phone={mate.phone} label={`Gọi ${mate.full_name}`} />
          ))}
        </span>
      )}
    </BookingShell>
  )
}

function GalaBooking({ booking }) {
  const { gala } = booking
  return (
    <BookingShell>
      <p className="inline-flex items-center gap-1.5 text-sm font-semibold text-slate-900">
        <Users className="size-4 text-slate-400" aria-hidden="true" />
        Bàn {gala.table_code}{gala.table_name ? ` · ${gala.table_name}` : ''} · Ghế {gala.seat_number}
      </p>
      {gala.starts_at && <p className="mt-0.5 text-sm text-slate-600">Bắt đầu {formatFullDateTime(gala.starts_at)}</p>}
    </BookingShell>
  )
}

/* --- Dựng dữ liệu: lịch trình làm xương, vé cá nhân gộp vào --- */

function buildDays(journey) {
  if (!journey) return []
  const programs = (journey.itinerary ?? []).map((item) => ({
    key: `it-${item.id}`,
    day: item.day_date,
    minutes: parseClock(item.start_time),
    timeLabel: clockRange(item.start_time, item.end_time),
    title: item.title,
    location: item.location,
    description: item.description,
    audience: item.audience,
    kind: inferKind(item.title),
    dateObj: dayStart(item.day_date, item.start_time),
    bookings: [],
  }))

  const byDay = new Map()
  const atDay = (day) => {
    let list = byDay.get(day)
    if (!list) {
      list = []
      byDay.set(day, list)
    }
    return list
  }
  programs.forEach((node) => atDay(node.day).push(node))

  const ledByBusId = new Map((journey.led_buses ?? []).map((bus) => [bus.bus_id, bus]))
  const ownBusIds = new Set((journey.buses ?? []).map((bus) => bus.bus_id))

  // Xe mình đi — giờ hiển thị lấy từ phân bổ, gộp vào mốc "tập trung/đón" cùng ngày.
  for (const bus of journey.buses ?? []) {
    const minutes = minutesOf(bus.gather_time || bus.departure_time)
    const day = dayKeyOf(bus.gather_time || bus.departure_time)
    const booking = { key: `bus-${bus.bus_id}`, type: 'bus', bus, led: ledByBusId.get(bus.bus_id) ?? null, minutes }
    const host = findHost(byDay.get(day), minutes, (node) => node.kind === 'bus' || BUS_TITLE_HINT.test(node.title))
    if (host) host.bookings.push(booking)
    else if (day) atDay(day).push(standaloneBus(bus, booking))
  }

  // Chuyến bay — gộp vào mốc "chuyến bay" cùng ngày.
  for (const direction of ['outbound', 'return']) {
    const flight = journey.flights?.[direction]
    if (!flight) continue
    const minutes = minutesOf(flight.departure_time)
    const day = dayKeyOf(flight.departure_time)
    const booking = { key: `flight-${direction}`, type: 'flight', flight, minutes }
    const host = day ? findHost(byDay.get(day), minutes, (node) => node.kind === 'flight' || FLIGHT_TITLE_HINT.test(node.title)) : null
    if (host) host.bookings.push(booking)
    else if (day) atDay(day).push(standaloneFlight(flight, booking))
  }

  // Phòng — gộp vào mốc nhận phòng (giờ nhận/trả thật hiện trong hộp vé).
  if (journey.accommodation) {
    const booking = { key: 'hotel', type: 'hotel', accommodation: journey.accommodation }
    const host = programs.find((node) => HOTEL_TITLE_HINT.test(node.title))
      ?? programs.find((node) => node.kind === 'hotel')
    if (host) host.bookings.push(booking)
    else {
      const day = dayKeyOf(journey.accommodation.check_in_at)
      if (day) atDay(day).push({ ...emptyNode(`hotel-${day}`, day), title: journey.accommodation.hotel_name, kind: 'hotel', location: journey.accommodation.address, bookings: [booking] })
    }
  }

  // Gala — gộp vào mốc gala/vinh danh (giờ bắt đầu thật hiện trong hộp vé).
  if (journey.gala) {
    const booking = { key: 'gala', type: 'gala', gala: journey.gala }
    const host = programs.find((node) => GALA_TITLE_HINT.test(node.title))
      ?? programs.find((node) => node.kind === 'gala')
    if (host) host.bookings.push(booking)
    else {
      const day = dayKeyOf(journey.gala.starts_at)
      if (day) atDay(day).push({ ...emptyNode(`gala-${day}`, day), title: journey.gala.name, kind: 'gala', location: journey.gala.venue, bookings: [booking] })
    }
  }

  // Xe chỉ phụ trách mà không tự đi — mốc riêng viền vàng, không thể lẫn.
  for (const led of journey.led_buses ?? []) {
    if (ownBusIds.has(led.bus_id)) continue
    const day = dayKeyOf(led.gather_time || led.departure_time) ?? led.trip_leg?.leg_date
    if (!day) continue
    atDay(day).push({
      ...emptyNode(`led-${led.bus_id}`, day),
      minutes: minutesOf(led.gather_time || led.departure_time) ?? 0,
      timeLabel: led.gather_time || led.departure_time ? formatTime(led.gather_time || led.departure_time) : '—',
      title: `${led.trip_leg?.name ?? 'Xe đưa đón'} — xe bạn phụ trách`,
      location: led.pickup_point?.name ?? led.pickup_point?.address ?? null,
      kind: 'bus',
      dateObj: led.gather_time || led.departure_time ? new Date(led.gather_time || led.departure_time) : dayStart(day, null),
      bookings: [{ key: `led-bus-${led.bus_id}`, type: 'bus', bus: toBusLike(led), led, minutes: 0 }],
    })
  }

  const now = new Date()
  const todayKey = localKey(now)
  return [...byDay.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([date, nodes]) => {
      nodes.sort((left, right) => (left.minutes ?? 0) - (right.minutes ?? 0))
      nodes.forEach((node) => {
        node.state = nodeState(node, now)
      })
      return { date, isToday: date === todayKey, nodes }
    })
}

/** Tìm mốc cùng ngày để gộp vé vào: ưu tiên tiêu đề khớp, rồi giờ gần nhau. */
function findHost(nodes, minutes, matches) {
  if (!nodes || nodes.length === 0) return null
  const titled = nodes.filter(matches)
  if (titled.length > 0) {
    if (minutes == null) return titled[0]
    return closestByTime(titled, minutes) ?? titled[0]
  }
  if (minutes == null) return null
  return closestByTime(nodes, minutes)
}

function closestByTime(nodes, minutes) {
  let best = null
  let bestGap = MERGE_WINDOW_MINUTES
  for (const node of nodes) {
    if (node.minutes == null) continue
    const gap = Math.abs(node.minutes - minutes)
    if (gap <= bestGap) {
      best = node
      bestGap = gap
    }
  }
  return best
}

function standaloneBus(bus, booking) {
  const when = bus.gather_time || bus.departure_time
  return {
    ...emptyNode(`bus-solo-${bus.bus_id}`, dayKeyOf(when)),
    minutes: booking.minutes ?? 0,
    timeLabel: when ? formatTime(when) : '—',
    title: `Xe ${bus.bus_code}${bus.trip_leg?.name ? ` · ${bus.trip_leg.name}` : ''}`,
    location: bus.pickup_point?.name ?? bus.pickup_point?.address ?? bus.dropoff_point ?? null,
    kind: 'bus',
    dateObj: when ? new Date(when) : null,
    bookings: [booking],
  }
}

function standaloneFlight(flight, booking) {
  return {
    ...emptyNode(`flight-solo-${flight.direction}`, dayKeyOf(flight.departure_time)),
    minutes: booking.minutes ?? 0,
    timeLabel: flight.departure_time ? formatTime(flight.departure_time) : '—',
    title: `${FLIGHT_DIRECTION_LABELS[flight.direction] ?? 'Chuyến bay'} · ${flight.flight_code}`,
    location: `Sân bay ${flight.departure_airport}`,
    kind: 'flight',
    dateObj: flight.departure_time ? new Date(flight.departure_time) : null,
    bookings: [booking],
  }
}

/** Xe phụ trách (từ `led_buses`) thiếu trường của vé thường — vá đủ để hộp vé đọc được. */
function toBusLike(led) {
  return {
    bus_id: led.bus_id,
    bus_code: led.bus_code,
    plate_number: led.plate_number,
    trip_leg: led.trip_leg,
    gather_time: led.gather_time,
    departure_time: led.departure_time,
    pickup_point: led.pickup_point,
    dropoff_point: null,
    leader: null,
    linked_flight_code: led.linked_flight_code,
  }
}

function emptyNode(key, day) {
  return { key, day, minutes: null, timeLabel: '—', title: '', location: null, description: null, audience: null, kind: 'program', dateObj: null, bookings: [] }
}

function inferKind(title = '') {
  if (FLIGHT_TITLE_HINT.test(title)) return 'flight'
  if (BUS_TITLE_HINT.test(title)) return 'bus'
  if (HOTEL_TITLE_HINT.test(title)) return 'hotel'
  if (GALA_TITLE_HINT.test(title)) return 'gala'
  if (/ăn |trưa|tối|buffet|coffee|tea-?break/i.test(title)) return 'meal'
  if (/team building|trò chơi|tour|tự do|tham quan|vận động|bãi biển|hòn/i.test(title)) return 'activity'
  return 'program'
}

function nodeState(node, now) {
  const start = node.dateObj instanceof Date && !Number.isNaN(node.dateObj) ? node.dateObj : null
  if (!start) {
    const bookingDate = node.bookings
      .map((booking) => bookingDateOf(booking))
      .find((date) => date instanceof Date && !Number.isNaN(date))
    if (!bookingDate) return 'upcoming'
    return bookingDate.getTime() + 90 * 60 * 1000 < now.getTime() ? 'past' : 'upcoming'
  }
  const end = nodeEnd(node, start)
  if (end && now >= start && now <= end) return 'live'
  if (now > (end ?? new Date(start.getTime() + 90 * 60 * 1000))) return 'past'
  return 'upcoming'
}

function nodeEnd(node, start) {
  const match = /(\d{2}):(\d{2})/.exec(node.timeLabel.split('–')[1] ?? node.timeLabel.split('-')[1] ?? '')
  if (!match) return null
  const end = new Date(start)
  end.setHours(Number(match[1]), Number(match[2]), 0, 0)
  return end
}

function bookingDateOf(booking) {
  if (booking.type === 'bus') {
    const when = booking.bus.gather_time || booking.bus.departure_time
    return when ? new Date(when) : null
  }
  if (booking.type === 'flight') return booking.flight.departure_time ? new Date(booking.flight.departure_time) : null
  if (booking.type === 'hotel') return booking.accommodation.check_in_at ? new Date(booking.accommodation.check_in_at) : null
  if (booking.type === 'gala') return booking.gala.starts_at ? new Date(booking.gala.starts_at) : null
  return null
}

/** Mốc sắp tới: mốc đầu tiên chưa qua, kèm cờ hôm nay / xe phụ trách cho banner. */
function findNext(days, now) {
  const todayKey = localKey(now)
  for (const day of days) {
    for (const node of day.nodes) {
      if (node.state === 'past') continue
      return {
        timeLabel: node.timeLabel,
        title: node.title,
        location: node.location,
        isToday: day.date === todayKey,
        isLed: node.bookings.some((booking) => booking.led),
        dateObj: node.dateObj,
      }
    }
  }
  return null
}

/* --- Giờ giấc: chuỗi "HH:MM" của lịch trình so được bằng chuỗi, ISO của vé parse ra Date --- */

function parseClock(value) {
  const match = /^(\d{1,2}):(\d{2})/.exec(value ?? '')
  if (!match) return null
  return Number(match[1]) * 60 + Number(match[2])
}

function clockRange(start, end) {
  if (start && end) return `${start} – ${end}`
  return start ?? '—'
}

function minutesOf(iso) {
  if (!iso) return null
  const date = new Date(iso)
  if (Number.isNaN(date)) return null
  return date.getHours() * 60 + date.getMinutes()
}

/** Ngày (yyyy-MM-dd theo giờ máy) của một mốc ISO — để xếp vé đúng ngày đi. */
function dayKeyOf(iso) {
  if (!iso) return null
  const date = new Date(iso)
  return Number.isNaN(date) ? null : localKey(date)
}

function localKey(date) {
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
}

/** Mốc lịch trình "ngày + giờ chữ" thành Date giờ máy để so qua/sắp tới. */
function dayStart(dayDate, clock) {
  if (!dayDate) return null
  const parts = dayDate.split('-').map(Number)
  if (parts.length !== 3 || parts.some((part) => !Number.isFinite(part))) return null
  const match = /^(\d{1,2}):(\d{2})/.exec(clock ?? '')
  return new Date(parts[0], parts[1] - 1, parts[2], Number(match?.[1] ?? 0), Number(match?.[2] ?? 0))
}
