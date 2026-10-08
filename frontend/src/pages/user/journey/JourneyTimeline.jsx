import { BedDouble, Bus, CalendarPlus, MapPin, PartyPopper, Phone, Plane, Sparkles } from 'lucide-react'
import { formatTime } from '../../../utils/format'
import { ROOM_TYPE_LABELS } from '../../../utils/constants'
import { downloadIcs, mapsUrl, telHref } from '../../../utils/travel'
import { actionLine, buildTimeline, nextTimelineStep, stepMoment } from './timeline'

const MISSING = {
  flights: 'chuyến bay',
  buses: 'xe đưa đón',
  accommodation: 'phòng',
  gala: 'ghế Gala',
}

const KIND = {
  bus: { icon: Bus, label: 'Xe', tone: 'bg-accent-green/15 text-accent-green' },
  flight: { icon: Plane, label: 'Bay', tone: 'bg-accent-sky/20 text-secondary' },
  hotel: { icon: BedDouble, label: 'Phòng', tone: 'bg-accent-purple/25 text-accent-purple-deep' },
  gala: { icon: PartyPopper, label: 'Gala', tone: 'bg-accent-pink/15 text-accent-pink' },
  activity: { icon: Sparkles, label: 'Việc', tone: 'bg-canvas-soft text-ink-secondary' },
}

export default function JourneyTimeline({ journey, onOpenPassengers, ledBusIds = [] }) {
  const { days } = buildTimeline(journey)
  const next = nextTimelineStep(days)
  const now = new Date()
  const missing = (journey?.pending ?? [])
    .filter((part) => journey?.pending_reasons?.[part] === 'not_assigned' && MISSING[part])
    .map((part) => MISSING[part])

  if (!days.length) {
    return (
      <p className="rounded-xl border border-hairline bg-surface px-4 py-6 text-body-sm text-ink-muted shadow-soft">
        BTC chưa xếp lịch cho bạn. Khi có giờ cụ thể, từng việc sẽ hiện ở đây theo đúng ngày.
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      {days.map((day) => (
        <section key={day.date}>
          <header className="mb-2 flex items-baseline justify-between gap-3 px-1">
            <h3 className="text-heading-3 text-ink">
              {day.number ? `Ngày ${day.number}` : 'Lịch'}
              <span className="ml-2 text-body-sm font-normal text-ink-muted">{day.label}</span>
            </h3>
          </header>
          <ol className="overflow-hidden rounded-xl border border-hairline bg-surface shadow-soft">
            {day.steps.map((step) => (
              <TimelineStep
                key={step.key}
                step={step}
                now={now}
                isNext={next?.key === step.key}
                onOpenPassengers={onOpenPassengers}
                ledBusIds={ledBusIds}
              />
            ))}
          </ol>
        </section>
      ))}
      {missing.length > 0 && (
        <p className="rounded-xl border border-hairline bg-canvas-soft px-4 py-3 text-body-sm text-ink-secondary">
          BTC chưa xếp xong: {missing.join(', ')}. Phần này sẽ hiện vào đúng ngày khi có.
        </p>
      )}
    </div>
  )
}

function TimelineStep({ step, now, isNext, onOpenPassengers, ledBusIds }) {
  const meta = KIND[step.kind] || KIND.activity
  const Icon = meta.icon
  const moment = stepMoment(step)
  const end = step.endTime && /^\d{2}:\d{2}/.test(step.endTime)
    ? new Date(`${step.date}T${step.endTime}:00`)
    : null
  const happening = moment && end && moment <= now && now <= end
  const past = moment && (end || moment) < now && !happening
  const line = actionLine(step)
  const showPassengers = step.bus && (ledBusIds.includes(step.bus.bus_id) || step.bus.leader?.is_current_user)

  return (
    <li className={`grid grid-cols-[4.5rem_1fr] gap-3 border-t border-hairline px-4 py-4 first:border-t-0 ${past ? 'opacity-60' : ''}`}>
      <div className="pt-0.5 text-right">
        <p className="text-body-md font-semibold tabular-nums text-ink">{step.time || '—'}</p>
        {step.endTime && <p className="text-caption text-ink-faint">đến {step.endTime}</p>}
      </div>
      <div className="min-w-0">
        <div className="flex items-start gap-2.5">
          <span className={`mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg ${meta.tone}`}>
            <Icon className="size-4" />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-body-md font-semibold text-ink">{step.title}</p>
              {happening && <Status text="Đang diễn ra" />}
              {isNext && !happening && !past && <Status text="Tiếp theo" />}
            </div>
            {line && <p className="mt-0.5 text-body-sm text-ink-secondary">{line}</p>}
            <StepFacts
              step={step}
              showPassengers={showPassengers}
              onOpenPassengers={onOpenPassengers}
            />
          </div>
        </div>
      </div>
    </li>
  )
}

function Status({ text }) {
  return (
    <span className="rounded-full bg-primary/10 px-2 py-0.5 text-eyebrow text-primary">{text}</span>
  )
}

function StepFacts({ step, showPassengers, onOpenPassengers }) {
  const bus = step.bus
  const flight = step.flight
  const stay = step.hotel
  const gala = step.gala
  const hasFacts = bus || flight || stay || gala
  if (!hasFacts) return null

  return (
    <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-caption text-ink-muted">
      {bus?.plate_number && <span>Biển {bus.plate_number}</span>}
      {bus?.leader?.name && <span>Trưởng xe {bus.leader.name}</span>}
      {bus?.leader?.phone && <Call phone={bus.leader.phone} label="Gọi trưởng xe" />}
      {bus?.pickup_point && <MapPlace place={bus.pickup_point} />}
      {showPassengers && (
        <button type="button" onClick={() => onOpenPassengers?.(bus)} className="font-semibold text-primary hover:underline">
          Danh sách hành khách
        </button>
      )}
      {flight?.ticket_code && <span>Mã vé {flight.ticket_code}</span>}
      {flight && (
        <button type="button" onClick={() => addFlight(flight)} className="inline-flex items-center gap-1 font-semibold text-primary hover:underline">
          <CalendarPlus className="size-3.5" />
          Thêm vào lịch
        </button>
      )}
      {stay?.address && <span>{stay.address}</span>}
      {stay?.room_type && <span>{ROOM_TYPE_LABELS[stay.room_type] || stay.room_type}</span>}
      {stay?.phone && <Call phone={stay.phone} label="Gọi khách sạn" />}
      {stay?.map_url || stay?.address ? <MapPlace place={{ name: stay.hotel_name, address: stay.address, map_url: stay.map_url }} /> : null}
      {stay?.roommates?.length > 0 && (
        <span>Ở cùng {stay.roommates.map((person) => person.full_name).join(', ')}</span>
      )}
      {step.checkout?.check_out_at && !step.hotel && (
        <span>Trả phòng lúc {formatTime(step.checkout.check_out_at)}</span>
      )}
      {gala?.table_name && <span>{gala.table_name}</span>}
    </div>
  )
}

function Call({ phone, label }) {
  const href = telHref(phone)
  if (!href) return null
  return (
    <a href={href} className="inline-flex items-center gap-1 font-semibold text-primary hover:underline">
      <Phone className="size-3.5" />
      {label}
    </a>
  )
}

function MapPlace({ place }) {
  const href = mapsUrl(place)
  if (!href) return null
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 font-semibold text-primary hover:underline">
      <MapPin className="size-3.5" />
      Bản đồ
    </a>
  )
}

function addFlight(flight) {
  const end = flight.arrival_time || flight.departure_time
  downloadIcs(flight.flight_code || 'chuyen-bay', {
    uid: `flight-${flight.flight_code}-${flight.departure_time}`,
    title: `Chuyến bay ${flight.flight_code || ''}`.trim(),
    start: flight.departure_time,
    end,
    location: flight.departure_airport,
    description: `${flight.departure_airport} → ${flight.arrival_airport}`,
  })
}
