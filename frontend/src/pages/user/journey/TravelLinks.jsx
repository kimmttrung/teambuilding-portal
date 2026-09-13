import { CalendarPlus, MapPin, Phone } from 'lucide-react'
import { downloadIcs, mapsUrl, telHref } from '../../../utils/travel'
import Button from '../../../components/common/Button'

/** Mở Google Maps ở tab mới. Không có địa chỉ lẫn link thì chỉ hiện tên. */
export function MapLink({ place, className = '' }) {
  if (!place) return null
  const href = mapsUrl(place)
  const label = place.name || place.address

  if (!href) return <span className={className}>{label}</span>
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={`inline-flex min-w-0 items-center gap-1.5 font-medium text-brand-700 hover:underline ${className}`}
    >
      <MapPin className="size-3.5 shrink-0" aria-hidden="true" />
      <span className="truncate">{label}</span>
    </a>
  )
}

/** Số điện thoại bấm gọi được trên điện thoại (docs/07-frontend.md §6). */
export function PhoneLink({ phone, label, className = '' }) {
  const href = telHref(phone)
  if (!href) return null
  return (
    <a
      href={href}
      className={`inline-flex items-center gap-1.5 rounded-lg bg-emerald-50 px-2.5 py-1.5 text-sm
        font-medium text-emerald-700 ring-1 ring-emerald-200 ring-inset transition hover:bg-emerald-100 ${className}`}
    >
      <Phone className="size-3.5" aria-hidden="true" />
      {label ?? phone}
    </a>
  )
}

export function AddToCalendarButton({ event, filename }) {
  return (
    <Button
      type="button"
      variant="secondary"
      size="sm"
      icon={CalendarPlus}
      onClick={() => downloadIcs(filename, event)}
    >
      Thêm vào lịch
    </Button>
  )
}

/** Một dòng "nhãn — giá trị" trong thẻ hành trình. */
export function InfoRow({ label, children }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <dt className="shrink-0 text-xs tracking-wide text-slate-400 uppercase">{label}</dt>
      <dd className="min-w-0 text-right text-sm text-slate-700">{children}</dd>
    </div>
  )
}
