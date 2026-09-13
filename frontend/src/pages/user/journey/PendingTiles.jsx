import { BedDouble, Bus, Hourglass, PartyPopper, Plane } from 'lucide-react'
import { JOURNEY_PARTS, PENDING_REASON_LABELS } from '../../../utils/constants'
import Card from '../../../components/common/Card'

const ICONS = { flights: Plane, buses: Bus, accommodation: BedDouble, gala: PartyPopper }

/**
 * Các phần hành trình chưa có dữ liệu. Hiện dạng ô chờ (skeleton), KHÔNG hiện lỗi
 * (docs/07 §3.2): "chưa công bố" là trạng thái bình thường, không phải sự cố.
 */
export default function PendingTiles({ parts = [], reasons = {} }) {
  if (parts.length === 0) return null
  const waitingForPublish = parts.every((part) => reasons[part] === 'not_published')

  return (
    <Card
      title={waitingForPublish ? 'Thông tin hành trình' : 'Còn đang chờ'}
      description={
        waitingForPublish ? 'Sẽ hiển thị ngay khi BTC công bố kết quả phân bổ' : undefined
      }
      bodyClassName="grid grid-cols-2 gap-2.5 lg:grid-cols-4"
    >
      {parts.map((part) => {
        const Icon = ICONS[part] ?? Hourglass
        const meta = JOURNEY_PARTS[part] ?? { label: part, hint: '' }
        const reason = reasons[part]

        return (
          <div
            key={part}
            className="rounded-lg border border-dashed border-slate-300 bg-slate-50/60 p-3"
          >
            <span className="grid size-8 place-items-center rounded-lg bg-white text-slate-400 ring-1 ring-slate-200">
              <Icon className="size-4" aria-hidden="true" />
            </span>
            <p className="mt-2 text-sm font-semibold text-slate-900">{meta.label}</p>
            <p className="mt-0.5 text-xs leading-snug text-slate-500">{meta.hint}</p>
            {reason === 'not_published' && (
              <div className="mt-2 space-y-1.5" aria-hidden="true">
                <div className="h-2 w-3/4 animate-pulse rounded bg-slate-200" />
                <div className="h-2 w-1/2 animate-pulse rounded bg-slate-200" />
              </div>
            )}
            <p
              className={`mt-2 text-xs font-medium ${
                reason === 'not_participating' ? 'text-slate-500' : 'text-amber-700'
              }`}
            >
              {PENDING_REASON_LABELS[reason] ?? 'Đang cập nhật'}
            </p>
          </div>
        )
      })}
    </Card>
  )
}
