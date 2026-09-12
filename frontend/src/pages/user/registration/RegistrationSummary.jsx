import { Bus } from 'lucide-react'
import Badge from '../../../components/common/Badge'
import Card from '../../../components/common/Card'
import { REGISTRATION_STATUS_META } from '../../../utils/constants'
import { formatDateTime } from '../../../utils/format'

/** Tóm tắt một đăng ký đã gửi. Dùng ở trang thành công và khi đăng ký đã chốt, không sửa được. */
export default function RegistrationSummary({ registration, title = 'Đăng ký của bạn', action }) {
  const meta = REGISTRATION_STATUS_META[registration.status] ?? {
    label: registration.status,
    tone: 'slate',
  }
  const busLegs = (registration.bus_needs ?? []).filter((need) => need.needs_bus)

  return (
    <Card
      title={title}
      action={
        <div className="flex shrink-0 items-center gap-2">
          <Badge tone={meta.tone}>{meta.label}</Badge>
          {action}
        </div>
      }
    >
      <dl className="grid grid-cols-2 gap-x-5 gap-y-3 sm:grid-cols-4">
        <Field label="Tham gia">{registration.is_participating ? 'Có' : 'Không'}</Field>
        <Field label="Ca đăng ký">{registration.shift?.name ?? '—'}</Field>
        <Field label="Đi xe BTC">
          {busLegs.length ? `${busLegs.length} chặng` : 'Không'}
        </Field>
        <Field label="Gửi lúc">{formatDateTime(registration.submitted_at)}</Field>
      </dl>

      {busLegs.length > 0 && (
        <ul className="mt-3 flex flex-wrap gap-1.5 border-t border-slate-100 pt-3">
          {busLegs.map((leg) => (
            <li
              key={leg.trip_leg_id}
              className="inline-flex items-center gap-1.5 rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-700"
            >
              <Bus className="size-3.5 text-slate-400" aria-hidden="true" />
              {leg.trip_leg_name}
              {leg.pickup_point_name && <span className="text-slate-500">· {leg.pickup_point_name}</span>}
            </li>
          ))}
        </ul>
      )}

      {registration.wish_note && (
        <p className="mt-3 border-t border-slate-100 pt-3 text-sm text-slate-600">
          <span className="text-xs tracking-wide text-slate-400 uppercase">Mong muốn: </span>
          {registration.wish_note}
        </p>
      )}

      {!registration.is_participating && registration.not_participating_reason && (
        <p className="mt-3 text-sm text-slate-500">
          Lý do không tham gia: {registration.not_participating_reason}
        </p>
      )}

      {registration.agreed_terms_version && (
        <p className="mt-3 text-xs text-slate-400">
          Đã đồng ý quy định bản {registration.agreed_terms_version}
        </p>
      )}
    </Card>
  )
}

function Field({ label, children }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs tracking-wide text-slate-400 uppercase">{label}</dt>
      <dd className="mt-0.5 truncate text-sm font-medium text-slate-900">{children}</dd>
    </div>
  )
}
