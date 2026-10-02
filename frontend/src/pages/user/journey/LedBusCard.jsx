import { Users } from 'lucide-react'
import { formatDateWithWeekday, formatTime } from '../../../utils/format'
import { telHref } from '../../../utils/travel'
import { BUS_LABELS } from '../../../utils/constants'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import leaderBadge from '../../../assets/buses/leader-badge.svg'

/** Hỗ trợ cả BusOut của F4 và cấu trúc bus lồng trong hành trình F6. */
export default function LedBusCard({ bus, onOpenPassengers }) {
  const gather = bus.gather_time || bus.departure_time
  const legName = bus.trip_leg?.name ?? bus.trip_leg_name
  const pickup = bus.pickup_point?.name ?? bus.pickup_point_name
  return (
    <Card bodyClassName="p-0">
      <div className="p-4 sm:p-6">
        <header className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-body-md font-semibold">
            {bus.bus_code} · {legName}
          </h3>
          <span className="inline-flex items-center gap-1.5 rounded-sm bg-accent-green/10 px-2 py-1 text-eyebrow text-accent-green">
            <img src={leaderBadge} alt="" />
            {BUS_LABELS.leaderBadge}
          </span>
        </header>
        <div className="mt-4 grid grid-cols-2 gap-4">
          <div>
            <p className="text-heading-2 font-bold tabular-nums">
              {gather ? formatTime(gather) : '—'}
            </p>
            <p className="mt-1 text-eyebrow text-ink-muted">
              {BUS_LABELS.gather} · {pickup ?? 'BTC chưa chốt điểm đón'}
            </p>
            {gather && (
              <p className="mt-1 text-caption text-ink-muted">
                {formatDateWithWeekday(gather)}
              </p>
            )}
          </div>
          <div>
            <p className="break-words text-title font-semibold">
              {bus.plate_number ?? 'Chưa có biển số'}
            </p>
            <p className="mt-1 text-caption text-ink-muted">
              {bus.driver_name
                ? `Tài xế: ${bus.driver_name}`
                : 'BTC chưa chốt tài xế'}
            </p>
            {bus.driver_phone && (
              <a
                href={telHref(bus.driver_phone)}
                className="inline-flex min-h-11 items-center text-caption text-primary"
              >
                {bus.driver_phone}
              </a>
            )}
          </div>
        </div>
        {bus.dropoff_point && (
          <p className="mt-3 text-caption text-ink-muted">
            Điểm trả: {bus.dropoff_point}
          </p>
        )}
        {bus.linked_flight_code && (
          <p className="mt-2 text-caption text-ink-muted">
            Chuyến bay: {bus.linked_flight_code}
          </p>
        )}
        <footer className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-hairline pt-4">
          <p className="text-caption text-ink-muted">
            <strong className="text-ink">
              {bus.passenger_count ?? bus.assigned_count ?? 0}
            </strong>
            /{bus.capacity} hành khách
          </p>
          <PassengersButton bus={bus} onClick={onOpenPassengers} />
        </footer>
      </div>
    </Card>
  )
}

export function PassengersButton({ bus, onClick }) {
  return (
    <Button
      variant="secondary"
      size="sm"
      className="min-h-11"
      icon={Users}
      onClick={() => onClick(bus)}
    >
      {BUS_LABELS.passengerList}
    </Button>
  )
}
