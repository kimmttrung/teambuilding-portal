import { PlaneLanding, PlaneTakeoff } from 'lucide-react'
import { FLIGHT_DIRECTION_LABELS } from '../../../utils/constants'
import { formatDateWithWeekday, formatTime, TIMEZONE_NOTE } from '../../../utils/format'
import Badge from '../../../components/common/Badge'
import Card from '../../../components/common/Card'
import { AddToCalendarButton } from './TravelLinks'

export default function FlightCard({ flight }) {
  const Icon = flight.direction === 'return' ? PlaneLanding : PlaneTakeoff

  return (
    <Card
      title={`${FLIGHT_DIRECTION_LABELS[flight.direction] ?? 'Chuyến bay'} · ${flight.flight_code}`}
      description={flight.airline ?? undefined}
      action={<Icon className="size-4 text-slate-400" aria-hidden="true" />}
    >
      <div className="flex items-center gap-3">
        <Stop code={flight.departure_airport} time={flight.departure_time} label="Khởi hành" />
        <span className="h-px flex-1 border-t border-dashed border-slate-300" aria-hidden="true" />
        <Stop code={flight.arrival_airport} time={flight.arrival_time} label="Đến nơi" alignRight />
      </div>

      <p className="mt-2 text-xs text-slate-500">
        {formatDateWithWeekday(flight.departure_time)} · {TIMEZONE_NOTE}
      </p>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-3">
        <div className="flex flex-wrap gap-1.5">
          {flight.shift_code && <Badge tone="slate">{flight.shift_code}</Badge>}
          {flight.seat_number && <Badge tone="brand">Ghế {flight.seat_number}</Badge>}
          {flight.ticket_code && <Badge tone="slate">Vé {flight.ticket_code}</Badge>}
        </div>
        <AddToCalendarButton
          filename={`chuyen-bay-${flight.flight_code}`}
          event={{
            uid: `flight-${flight.direction}-${flight.flight_code}`,
            title: `Bay ${flight.flight_code} ${flight.departure_airport} → ${flight.arrival_airport}`,
            start: flight.departure_time,
            end: flight.arrival_time,
            location: `Sân bay ${flight.departure_airport}`,
            // Chuyến bay nhắc trước 3 tiếng: đủ để ra sân bay làm thủ tục.
            alarmMinutes: 180,
          }}
        />
      </div>
    </Card>
  )
}

function Stop({ code, time, label, alignRight = false }) {
  return (
    <div className={alignRight ? 'text-right' : ''}>
      <p className="text-xs tracking-wide text-slate-400 uppercase">{label}</p>
      <p className="text-2xl leading-tight font-bold text-slate-900">{code}</p>
      <p className="text-lg font-semibold text-brand-700 tabular-nums">{formatTime(time)}</p>
    </div>
  )
}
