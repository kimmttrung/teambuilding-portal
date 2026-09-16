import { Bus, Clock, Users } from 'lucide-react'
import { formatDateWithWeekday, formatTime } from '../../../utils/format'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import { InfoRow, MapLink } from './TravelLinks'

/**
 * Xe người này **phụ trách** nhưng không tự đi (xe mình đi thì nút nằm ngay trên `BusCard`).
 *
 * Cùng bố cục với thẻ xe thường để Trưởng xe không phải học hai kiểu thẻ: giờ tập trung là
 * con số to nhất, rồi điểm đón, rồi nút mở danh sách hành khách.
 */
export default function LedBusCard({ bus, onOpenPassengers }) {
  const gather = bus.gather_time || bus.departure_time

  return (
    <Card
      title={bus.trip_leg.name}
      description={`Xe ${bus.bus_code}${bus.plate_number ? ` · ${bus.plate_number}` : ''}`}
      action={<Bus className="size-4 text-slate-400" aria-hidden="true" />}
    >
      <div className="flex flex-wrap items-end justify-between gap-3">
        {gather ? (
          <div>
            <p className="text-xs tracking-wide text-slate-400 uppercase">Có mặt lúc</p>
            <p className="text-3xl leading-none font-bold text-slate-900 tabular-nums">
              {formatTime(gather)}
            </p>
            <p className="mt-1 text-xs text-slate-500">{formatDateWithWeekday(gather)}</p>
          </div>
        ) : (
          <p className="text-sm text-slate-500">BTC chưa chốt giờ tập trung.</p>
        )}
        <Badge tone="brand">Bạn là Trưởng xe</Badge>
      </div>

      {bus.gather_time && bus.departure_time && (
        <p className="mt-2 inline-flex items-center gap-1 text-xs text-slate-500">
          <Clock className="size-3.5" aria-hidden="true" />
          Xe chạy {formatTime(bus.departure_time)}
        </p>
      )}

      <dl className="mt-3 flex flex-col gap-2 border-t border-slate-100 pt-3">
        {bus.pickup_point && (
          <InfoRow label="Điểm đón">
            <MapLink place={bus.pickup_point} />
          </InfoRow>
        )}
        {bus.linked_flight_code && <InfoRow label="Chuyến bay">{bus.linked_flight_code}</InfoRow>}
        <InfoRow label="Hành khách">
          <span className="tabular-nums">
            {bus.passenger_count}/{bus.capacity}
          </span>
        </InfoRow>
      </dl>

      <div className="mt-3 flex justify-end">
        <PassengersButton bus={bus} onClick={onOpenPassengers} />
      </div>
    </Card>
  )
}

/** Dùng chung với `BusCard` để nút trên hai loại thẻ giống hệt nhau. */
export function PassengersButton({ bus, onClick }) {
  return (
    <Button type="button" variant="secondary" size="sm" icon={Users} onClick={() => onClick(bus)}>
      Danh sách hành khách
    </Button>
  )
}
