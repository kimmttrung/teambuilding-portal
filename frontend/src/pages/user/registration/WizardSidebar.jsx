import { useFormContext } from 'react-hook-form'
import { Ban, CalendarDays, Check, MapPin, X } from 'lucide-react'
import { PROFILE_REQUIRED_FIELDS } from '../../../utils/schemas'
import { daysUntil, formatDate, formatDateTime } from '../../../utils/format'

/** Cột phải cố định theo layout mới: lựa chọn hiện tại và thông tin kỳ. */
export default function WizardSidebar({ event, options, isEditing, onRequestCancel }) {
  const { watch } = useFormContext()
  const values = watch()
  const participating = values.is_participating === 'yes'
  const notParticipating = values.is_participating === 'no'
  const shift = options.shifts?.find((item) => String(item.id) === values.shift_id)
  const location = options.work_locations?.find((item) => String(item.id) === values.departure_location_id)
  const busLegs = (values.bus_needs ?? []).filter((need) => need.needs_bus)
  const remainingDays = daysUntil(event.registration_closes_at)
  const pickup = options.pickup_points?.find((item) => String(item.id) === String(busLegs[0]?.pickup_point_id))

  return (
    <div className="flex flex-col gap-4">
      <section className="rounded-xl border border-hairline bg-surface px-4 py-3.5 shadow-soft">
        <p className="text-body-sm font-semibold text-ink">Lựa chọn của bạn</p>
        <p className="mt-0.5 text-caption text-ink-muted">Cập nhật theo từng bước bạn điền</p>
        <dl className="mt-3 divide-y divide-hairline">
          <SummaryRow label="Tham gia">{participating ? 'Có' : notParticipating ? 'Không' : 'Chưa chọn'}</SummaryRow>
          {!notParticipating && (
            <>
              <SummaryRow label="Ca đi">{formatShift(shift?.name)}</SummaryRow>
              <SummaryRow label="Xe BTC">{busLegs.length ? `${busLegs.length}/${values.bus_needs?.length ?? 0} chặng` : 'Chưa chọn'}</SummaryRow>
              <SummaryRow label="Điểm đón">{pickup?.name || (location ? location.name : 'Chưa chọn')}</SummaryRow>
              <SummaryRow label="Quy định">{values.agreed_terms ? 'Đã đồng ý v1' : 'Chưa đồng ý'}</SummaryRow>
            </>
          )}
        </dl>
      </section>

      <section className="rounded-xl border border-hairline bg-surface px-4 py-3.5 shadow-soft">
        <p className="text-caption font-semibold text-ink-muted">Kỳ Team Building</p>
        <p className="mt-1.5 text-body-md font-semibold text-ink">{event.code} · {event.destination || event.name}</p>
        <p className="mt-0.5 text-caption text-ink-muted">
          {formatDate(event.start_date)}–{formatDate(event.end_date)}{event.hotel_name ? ` · ${event.hotel_name}` : ' · Sea Star Resort'}
        </p>
        {event.registration_closes_at && (
          <div className="mt-3 flex items-center gap-2 border-t border-hairline pt-2.5 text-caption text-ink-secondary">
            <CalendarDays className="size-4 text-ink-muted" aria-hidden="true" />
            Hạn đăng ký {formatDateTime(event.registration_closes_at)}
            {remainingDays !== null && remainingDays >= 0 && <span className="text-ink-faint">· còn {remainingDays} ngày</span>}
          </div>
        )}
        {event.destination && (
          <p className="mt-2 flex items-center gap-2 text-caption text-ink-muted">
            <MapPin className="size-4" aria-hidden="true" /> {event.destination}
          </p>
        )}
      </section>

      {participating && <FlightReadyCard profile={values.profile} />}

      {isEditing && (
        <section className="rounded-xl border border-hairline bg-surface px-4 py-3.5">
          <p className="text-body-sm font-semibold text-ink">Không đi được nữa?</p>
          <p className="mt-1 text-caption leading-relaxed text-ink-muted">Huỷ đăng ký để BTC không tính suất của bạn.</p>
          <button type="button" onClick={onRequestCancel} className="mt-3 inline-flex items-center gap-1.5 text-body-sm font-semibold text-rose-600 hover:underline">
            <Ban className="size-4" aria-hidden="true" /> Huỷ đăng ký tham gia
          </button>
        </section>
      )}
    </div>
  )
}

function SummaryRow({ label, children }) {
  return (
    <div className="flex items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
      <dt className="text-body-sm text-ink-muted">{label}</dt>
      <dd className="min-w-0 truncate text-right text-body-sm font-semibold text-ink">{children}</dd>
    </div>
  )
}

function formatShift(value) {
  if (!value) return 'Chưa chọn'
  return value.replace(' – bay sáng', ' · sáng').replace(' – bay chiều', ' · chiều')
}

function FlightReadyCard({ profile }) {
  const done = PROFILE_REQUIRED_FIELDS.filter(({ name }) => profile?.[name])
  return (
    <section className="rounded-xl border border-hairline bg-surface px-4 py-3.5">
      <p className="text-body-sm font-semibold text-ink">Điều kiện xuất vé</p>
      <p className="mt-0.5 text-caption text-ink-muted">{done.length}/{PROFILE_REQUIRED_FIELDS.length} thông tin bắt buộc</p>
      <ul className="mt-3 flex flex-col gap-2">
        {PROFILE_REQUIRED_FIELDS.map(({ name, label }) => {
          const filled = Boolean(profile?.[name])
          return (
            <li key={name} className="flex items-center gap-2.5 text-caption">
              <span className={`grid size-5 shrink-0 place-items-center rounded-full text-on-primary ${filled ? 'bg-accent-green' : 'bg-input-border'}`}>
                {filled ? <Check className="size-3" strokeWidth={3} aria-hidden="true" /> : <X className="size-3 text-white" aria-hidden="true" />}
              </span>
              <span className={filled ? 'text-ink-secondary' : 'font-medium text-ink'}>{label}</span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
