import { CalendarRange } from 'lucide-react'
import { useActiveEvent, useSelectEvent, useSelectableEvents } from '../../hooks/useEvent'
import { EVENT_STATUS_META } from '../../utils/constants'

/**
 * Chọn kỳ Team Building đang xem (docs/13 task 6).
 *
 * Chỉ hiện khi có từ 2 kỳ trở lên — công ty thường chỉ chạy một kỳ, hiện một ô chọn có đúng một
 * lựa chọn chỉ làm rối thanh bên. Đổi kỳ là xoá sạch cache TanStack Query (xem `useSelectEvent`).
 */
export default function EventSwitcher({ compact = false }) {
  const { data: events } = useSelectableEvents()
  const { data: current } = useActiveEvent()
  const selectEvent = useSelectEvent()

  if (!events || events.length < 2) return null

  const value = current?.id ?? ''
  const meta = EVENT_STATUS_META[current?.status]

  return (
    <div className={compact ? 'px-2 py-1.5' : 'border-b border-slate-200 px-2.5 py-2'}>
      <label
        className="mb-1 flex items-center gap-1.5 text-xs font-medium text-slate-500"
        htmlFor="event-switcher"
      >
        <CalendarRange className="size-3.5 shrink-0" aria-hidden="true" />
        Kỳ Team Building
      </label>
      <select
        id="event-switcher"
        value={value}
        onChange={(changeEvent) => selectEvent(changeEvent.target.value)}
        className="w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm font-medium text-slate-900"
      >
        {events.map((item) => (
          <option key={item.id} value={item.id}>
            {item.name}
          </option>
        ))}
      </select>
      {meta && <p className="mt-1 text-xs text-slate-500">{meta.label}</p>}
    </div>
  )
}
