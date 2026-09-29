import { useState } from 'react'
import { CalendarRange, Plus } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { useActiveEvent, useSelectEvent, useSelectableEvents } from '../../hooks/useEvent'
import { EVENT_STATUS, EVENT_STATUS_META } from '../../utils/constants'
import EventCreateModal from './EventCreateModal'

/**
 * Chọn kỳ Team Building đang xem (docs/13 task 6).
 *
 * CBNV chỉ thấy khi thực sự có từ 2 kỳ trở lên — một ô chọn có đúng một lựa chọn chỉ làm rối thanh
 * bên. BTC thì luôn thấy, kể cả khi mới có một kỳ, vì đây cũng là chỗ mở kỳ cho mùa sau.
 */
export default function EventSwitcher({ compact = false }) {
  const { isAdmin } = useAuth()
  const { data: events } = useSelectableEvents()
  const { data: current } = useActiveEvent()
  const selectEvent = useSelectEvent()
  const [creating, setCreating] = useState(false)
  // Giữ lựa chọn vừa bấm: `useActiveEvent` bị reset khi đổi kỳ nên `current` rỗng vài trăm ms, để
  // `<select>` đọc thẳng nó thì ô chọn nhảy về kỳ đầu danh sách rồi mới nhảy lại — nhìn như bấm hụt.
  const [pendingId, setPendingId] = useState(null)

  if (!events) return null
  if (!isAdmin && events.length < 2) return null

  const meta = EVENT_STATUS_META[current?.status]
  const isDraft = current?.status === EVENT_STATUS.DRAFT
  const switching = pendingId !== null && String(current?.id ?? '') !== String(pendingId)

  function choose(eventId) {
    setPendingId(eventId)
    selectEvent(eventId)
  }

  return (
    <div className={compact ? 'px-2 py-1.5' : 'border-b border-hairline px-3 py-3'}>
      <label
        className="mb-1.5 flex items-center gap-1.5 text-eyebrow text-ink-faint"
        htmlFor="event-switcher"
      >
        <CalendarRange className="size-3.5 shrink-0" aria-hidden="true" />
        Kỳ Team Building
      </label>

      <select
        id="event-switcher"
        value={current?.id ?? pendingId ?? ''}
        onChange={(changeEvent) => choose(changeEvent.target.value)}
        className="min-h-9 w-full rounded-xs border border-input-border bg-surface px-2 py-1.5 text-body-sm font-medium text-ink focus:border-primary focus:shadow-soft focus:outline-none"
      >
        {events.map((item) => (
          <option key={item.id} value={item.id}>
            {item.name}
            {item.status === EVENT_STATUS.DRAFT ? ' (nháp)' : ''}
          </option>
        ))}
      </select>

      {switching ? (
        <p className="mt-1 text-caption text-ink-muted">Đang tải dữ liệu kỳ…</p>
      ) : (
        meta && (
          <p className={`mt-1 text-caption ${isDraft ? 'text-amber-700' : 'text-ink-muted'}`}>
            {isDraft ? 'Bản nháp — CBNV chưa nhìn thấy kỳ này' : meta.label}
          </p>
        )
      )}

      {isAdmin && (
        <>
          <button
            type="button"
            onClick={() => setCreating(true)}
            className="mt-2 flex items-center gap-1 text-caption font-medium text-primary hover:text-primary-active"
          >
            <Plus className="size-3.5 shrink-0" aria-hidden="true" />
            Thêm kỳ cho mùa sau
          </button>
          {creating && <EventCreateModal open onClose={() => setCreating(false)} />}
        </>
      )}
    </div>
  )
}
