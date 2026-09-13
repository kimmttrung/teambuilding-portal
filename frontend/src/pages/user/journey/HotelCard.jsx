import { BedDouble, Crown } from 'lucide-react'
import { ROOM_TYPE_LABELS } from '../../../utils/constants'
import { formatFullDateTime } from '../../../utils/format'
import Badge from '../../../components/common/Badge'
import Card from '../../../components/common/Card'
import { InfoRow, MapLink, PhoneLink } from './TravelLinks'

export default function HotelCard({ accommodation }) {
  const stay = accommodation
  const roomMeta = [ROOM_TYPE_LABELS[stay.room_type] ?? stay.room_type, stay.floor ? `tầng ${stay.floor}` : null]
    .filter(Boolean)
    .join(' · ')

  return (
    <Card
      title={stay.hotel_name}
      description="Khách sạn"
      action={<BedDouble className="size-4 text-slate-400" aria-hidden="true" />}
    >
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs tracking-wide text-slate-400 uppercase">Phòng</p>
          <p className="text-3xl leading-none font-bold text-slate-900 tabular-nums">
            {stay.room_number}
          </p>
          {roomMeta && <p className="mt-1 text-xs text-slate-500">{roomMeta}</p>}
        </div>
        {stay.is_room_captain && (
          <Badge tone="brand">
            <Crown className="mr-1 size-3" aria-hidden="true" />
            Trưởng phòng
          </Badge>
        )}
      </div>

      <dl className="mt-3 flex flex-col gap-2 border-t border-slate-100 pt-3">
        {(stay.address || stay.map_url) && (
          <InfoRow label="Địa chỉ">
            <MapLink place={{ name: stay.hotel_name, address: stay.address, map_url: stay.map_url }} />
          </InfoRow>
        )}
        {stay.check_in_at && <InfoRow label="Nhận phòng">{formatFullDateTime(stay.check_in_at)}</InfoRow>}
        {stay.check_out_at && <InfoRow label="Trả phòng">{formatFullDateTime(stay.check_out_at)}</InfoRow>}
        {stay.phone && (
          <InfoRow label="Lễ tân">
            <PhoneLink phone={stay.phone} />
          </InfoRow>
        )}
      </dl>

      <div className="mt-3 border-t border-slate-100 pt-3">
        <p className="text-xs tracking-wide text-slate-400 uppercase">Ở cùng phòng</p>
        {stay.roommates.length === 0 ? (
          <p className="mt-1 text-sm text-slate-500">Chưa có ai khác trong phòng.</p>
        ) : (
          <ul className="mt-2 flex flex-col gap-2">
            {stay.roommates.map((mate) => (
              <li key={mate.full_name} className="flex flex-wrap items-center justify-between gap-2">
                <span className="min-w-0">
                  <span className="block truncate text-sm font-medium text-slate-900">{mate.full_name}</span>
                  <span className="block text-xs text-slate-500">
                    {mate.team_name ?? '—'}
                    {mate.is_room_captain ? ' · Trưởng phòng' : ''}
                  </span>
                </span>
                <PhoneLink phone={mate.phone} label="Gọi" />
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  )
}
