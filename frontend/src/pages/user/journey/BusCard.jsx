import { Bus, Clock } from 'lucide-react'
import { formatDateWithWeekday, formatTime } from '../../../utils/format'
import Badge from '../../../components/common/Badge'
import Card from '../../../components/common/Card'
import { PassengersButton } from './LedBusCard'
import { AddToCalendarButton, InfoRow, MapLink, PhoneLink } from './TravelLinks'

/**
 * Thẻ xe một chặng. Giờ tập trung là con số to nhất trên thẻ (docs/07 §3.2): đó là thứ duy
 * nhất CBNV cần nhìn lúc 4 giờ sáng — xe không chờ quá giờ.
 *
 * `ledBus` chỉ có khi người xem là Trưởng xe của **chính xe này** (My Journey truyền vào từ
 * `led_buses`): thêm huy hiệu và nút mở danh sách hành khách.
 */
export default function BusCard({ bus, ledBus = null, onOpenPassengers }) {
  const gather = bus.gather_time || bus.departure_time

  return (
    <Card
      title={bus.trip_leg.name}
      description={`Xe ${bus.bus_code}${bus.plate_number ? ` · ${bus.plate_number}` : ''}`}
      action={<Bus className="size-4 text-slate-400" aria-hidden="true" />}
    >
      {gather ? (
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-xs tracking-wide text-slate-400 uppercase">Có mặt lúc</p>
            <p className="text-3xl leading-none font-bold text-slate-900 tabular-nums">
              {formatTime(gather)}
            </p>
            <p className="mt-1 text-xs text-slate-500">{formatDateWithWeekday(gather)}</p>
          </div>
          {bus.gather_time && bus.departure_time && (
            <p className="inline-flex items-center gap-1 text-xs text-slate-500">
              <Clock className="size-3.5" aria-hidden="true" />
              Xe chạy {formatTime(bus.departure_time)}
            </p>
          )}
        </div>
      ) : (
        <p className="text-sm text-slate-500">BTC chưa chốt giờ tập trung.</p>
      )}

      <dl className="mt-3 flex flex-col gap-2 border-t border-slate-100 pt-3">
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
              {ledBus ? (
                <Badge tone="brand">Bạn</Badge>
              ) : (
                <PhoneLink phone={bus.leader.phone} label="Gọi" />
              )}
            </span>
          </InfoRow>
        )}
        {ledBus && (
          <InfoRow label="Hành khách">
            <span className="tabular-nums">
              {ledBus.passenger_count}/{ledBus.capacity}
            </span>
          </InfoRow>
        )}
      </dl>

      {ledBus && (
        <div className="mt-3 flex justify-end">
          <PassengersButton bus={ledBus} onClick={onOpenPassengers} />
        </div>
      )}

      {gather && (
        <div className="mt-3 flex justify-end">
          <AddToCalendarButton
            filename={`xe-${bus.bus_code}`}
            event={{
              uid: `bus-${bus.trip_leg.id}-${bus.bus_code}`,
              title: `Tập trung xe ${bus.bus_code} – ${bus.trip_leg.name}`,
              start: gather,
              end: bus.departure_time || undefined,
              location: bus.pickup_point?.name ?? bus.pickup_point?.address,
              alarmMinutes: 60,
            }}
          />
        </div>
      )}
    </Card>
  )
}
