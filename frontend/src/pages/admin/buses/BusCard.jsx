import { AlertTriangle, Pencil, Trash2, UserCog, Users } from 'lucide-react'
import { formatShortDateTime } from '../../../utils/format'
import { telHref } from '../../../utils/travel'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import SlotBar from '../../../components/admin/SlotBar'
import { highlightTargets, usePersonLocation } from '../../../hooks/usePeople'
import { cardClass } from '../../../utils/highlight'

/** Câu lệch giờ từ backend viết thường ở đầu (nó vốn nằm giữa câu dài hơn). */
function upperFirst(text) {
  return text.charAt(0).toUpperCase() + text.slice(1)
}

/** Một xe: số chỗ, giờ tập trung, điểm đón, chuyến bay gắn kèm và Trưởng xe. */
export default function BusCard({ bus, mismatches = 0, onPassengers, onLeader, onEdit, onDelete }) {
  const full = bus.remaining_seats <= 0
  const timingIssues = bus.timing_issues ?? []
  const { location: locatedPerson } = usePersonLocation()
  const highlighted = highlightTargets(locatedPerson).buses.has(bus.id)

  return (
    <Card
      className={cardClass(highlighted)}
      title={bus.bus_code}
      description={bus.plate_number ?? 'Chưa có biển số'}
      action={
        <div className="flex flex-wrap items-center justify-end gap-1.5">
          {timingIssues.length > 0 && <Badge tone="amber">Lệch giờ</Badge>}
          {full ? (
            <Badge tone="rose">Đủ chỗ</Badge>
          ) : (
            <Badge tone="slate">Còn {bus.remaining_seats} chỗ</Badge>
          )}
        </div>
      }
    >
      <SlotBar assigned={bus.assigned_count} usable={bus.capacity} />

      {timingIssues.length > 0 && (
        <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-2.5 text-xs text-amber-900">
          <p className="flex items-center gap-1.5 font-semibold">
            <AlertTriangle className="size-3.5 shrink-0" aria-hidden="true" />
            Giờ xe không khớp giờ bay
          </p>
          <ul className="mt-1 list-disc space-y-0.5 pl-4">
            {timingIssues.map((issue) => (
              <li key={issue}>{upperFirst(issue)}</li>
            ))}
          </ul>
          <button
            type="button"
            onClick={onEdit}
            className="mt-1.5 font-medium underline underline-offset-2"
          >
            Sửa giờ xe này
          </button>
        </div>
      )}

      <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-2 text-sm">
        <Info label="Tập trung">{bus.gather_time ? formatShortDateTime(bus.gather_time) : '—'}</Info>
        <Info label="Xe chạy">{bus.departure_time ? formatShortDateTime(bus.departure_time) : '—'}</Info>
        <Info label="Điểm đón">{bus.pickup_point_name ?? 'Không cố định'}</Info>
        <Info label="Chuyến bay">{bus.linked_flight_code ?? '—'}</Info>
      </dl>

      <div className="mt-3 flex flex-col gap-1 border-t border-slate-100 pt-3 text-sm">
        {bus.leader_name ? (
          <p className="flex flex-wrap items-center gap-x-2">
            <span className="text-xs text-slate-500">Trưởng xe</span>
            <span className="font-medium text-slate-900">{bus.leader_name}</span>
            {bus.leader_phone && (
              <a href={telHref(bus.leader_phone)} className="text-brand-700 tabular-nums hover:underline">
                {bus.leader_phone}
              </a>
            )}
          </p>
        ) : (
          <p className="inline-flex items-center gap-1.5 font-medium text-amber-700">
            <AlertTriangle className="size-3.5" aria-hidden="true" />
            Chưa có Trưởng xe
          </p>
        )}
        {bus.driver_name && (
          <p className="text-xs text-slate-500">
            Tài xế {bus.driver_name}
            {bus.driver_phone ? ` · ${bus.driver_phone}` : ''}
          </p>
        )}
        {mismatches > 0 && (
          <p className="text-xs text-amber-700">{mismatches} người lệch điểm đón hoặc chuyến bay</p>
        )}
      </div>

      {/* Sửa/Xoá chỉ còn icon, dồn về phải: 4 nút chữ trên thẻ nửa cột bị rớt dòng. */}
      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        <Button variant="secondary" size="sm" icon={Users} onClick={onPassengers}>
          Hành khách
        </Button>
        <Button variant="ghost" size="sm" icon={UserCog} onClick={onLeader}>
          Trưởng xe
        </Button>
        <span className="ml-auto flex gap-0.5">
          <Button variant="ghost" size="sm" icon={Pencil} onClick={onEdit} title="Sửa xe" aria-label={`Sửa xe ${bus.bus_code}`} />
          <Button
            variant="ghost"
            size="sm"
            icon={Trash2}
            onClick={onDelete}
            disabled={bus.assigned_count > 0}
            className="text-rose-600 hover:bg-rose-50"
            title={bus.assigned_count > 0 ? 'Chuyển hết hành khách sang xe khác trước khi xoá' : 'Xoá xe'}
            aria-label={`Xoá xe ${bus.bus_code}`}
          />
        </span>
      </div>
    </Card>
  )
}

function Info({ label, children }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="truncate text-slate-900">{children}</dd>
    </div>
  )
}
