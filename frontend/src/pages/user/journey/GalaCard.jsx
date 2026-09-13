import { PartyPopper } from 'lucide-react'
import { formatFullDateTime } from '../../../utils/format'
import Card from '../../../components/common/Card'

export default function GalaCard({ gala }) {
  return (
    <Card
      title={gala.name}
      description={gala.venue ?? undefined}
      action={<PartyPopper className="size-4 text-slate-400" aria-hidden="true" />}
    >
      <div className="flex items-end gap-8">
        <BigValue label="Bàn" value={gala.table_code} hint={gala.table_name} />
        <BigValue label="Ghế" value={gala.seat_number} />
      </div>
      {gala.starts_at && (
        <p className="mt-3 border-t border-slate-100 pt-3 text-sm text-slate-600">
          Bắt đầu {formatFullDateTime(gala.starts_at)}
        </p>
      )}
    </Card>
  )
}

function BigValue({ label, value, hint }) {
  return (
    <div>
      <p className="text-xs tracking-wide text-slate-400 uppercase">{label}</p>
      <p className="text-3xl leading-none font-bold text-slate-900 tabular-nums">{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  )
}
