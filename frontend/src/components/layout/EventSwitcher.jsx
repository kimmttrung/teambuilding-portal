import { Link } from 'react-router-dom'
import { CalendarRange } from 'lucide-react'
import { eventStore } from '../../api/client'
import { useAuth } from '../../context/AuthContext'
import { useActiveEvent, useSelectEvent, useSelectableEvents } from '../../hooks/useEvent'
import { EVENT_STATUS, EVENT_STATUS_META } from '../../utils/constants'

function sameId(left, right) {
  return String(left ?? '') === String(right ?? '')
}

/**
 * Chọn kỳ Team Building đang xem (docs/13 task 6).
 *
 * CBNV chỉ thấy khi thực sự có từ 2 kỳ trở lên — một ô chọn có đúng một lựa chọn chỉ làm rối thanh
 * bên. BTC thì luôn thấy, kể cả khi mới có một kỳ. Thêm và xoá kỳ nằm ở trang Quản lý kỳ.
 */
export default function EventSwitcher({ compact = false }) {
  const { isAdmin } = useAuth()
  const { data: events } = useSelectableEvents()
  const { data: current } = useActiveEvent()
  const selectEvent = useSelectEvent()

  if (!events) return null
  if (!isAdmin && events.length < 2) return null

  // `useActiveEvent` bị reset khi đổi kỳ nên `current` rỗng vài trăm ms. `<select>` đọc thẳng nó
  // thì value rỗng, không khớp option nào, trình duyệt vẽ kỳ đầu danh sách — nhìn như vẫn ở kỳ cũ.
  // `eventStore` đổi ngay lúc bấm hoặc lúc tạo kỳ.
  const storedId = eventStore.get()
  const selectedId = storedId ?? current?.id ?? ''
  const known = events.find((item) => sameId(item.id, selectedId))
  const selected = known
    ?? (current && sameId(current.id, selectedId) ? current : null)
    ?? (selectedId !== '' ? { id: selectedId, name: 'Đang mở kỳ…', status: null } : null)
  const options = selected && !known ? [selected, ...events] : events

  const meta = EVENT_STATUS_META[current?.status]
  const isDraft = current?.status === EVENT_STATUS.DRAFT
  const switching = selectedId !== '' && !sameId(current?.id, selectedId)

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
        value={selectedId === '' ? '' : String(selectedId)}
        onChange={(changeEvent) => selectEvent(changeEvent.target.value)}
        className="min-h-9 w-full rounded-xs border border-input-border bg-surface px-2 py-1.5 text-body-sm font-medium text-ink focus:border-primary focus:shadow-soft focus:outline-none"
      >
        {options.map((item) => (
          <option key={item.id} value={String(item.id)}>
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
        <Link
          to="/admin/events"
          className="mt-2 inline-flex items-center text-caption font-medium text-primary hover:text-primary-active"
        >
          Quản lý kỳ
        </Link>
      )}
    </div>
  )
}
