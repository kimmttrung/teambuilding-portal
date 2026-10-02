import { formatShortDateTime } from '../../utils/format'

/**
 * Ngữ cảnh kỳ đang xem — dùng chung cho toàn bộ màn hình trong AppLayout.
 * EventPublic là nguồn duy nhất cho tiêu đề, trạng thái và thời điểm cập nhật.
 */
export default function EventContextBar({ event, className = '' }) {
  if (!event) return null

  const published = Boolean(
    event.is_published ||
      ['information_published', 'event_started', 'completed'].includes(event.status),
  )
  const statusLabel = getStatusLabel(event, published)
  const updatedLabel = event.updated_at
    ? `Cập nhật ${formatShortDateTime(event.updated_at)} · tự động từ BTC`
    : 'Cập nhật tự động từ BTC'

  return (
    <div
      className={`hidden min-h-10 items-center justify-between gap-3 border-b border-hairline bg-canvas px-4 py-2 md:flex sm:px-6 lg:px-8 ${className}`}
      aria-label="Thông tin kỳ Team Building"
    >
      <div className="flex min-w-0 items-center gap-2">
        <span className="truncate text-caption font-semibold text-ink">
          {event.code} · {event.destination || event.name}
        </span>
        <span
          className={`shrink-0 rounded-md px-2 py-0.5 text-[10px] font-semibold leading-4 ${
            published ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-800'
          }`}
        >
          {statusLabel}
        </span>
      </div>
      <span className="shrink-0 text-[10px] text-ink-faint">{updatedLabel}</span>
    </div>
  )
}

function getStatusLabel(event, published) {
  if (published) return 'Đã công bố'
  if (event.status === 'draft') return 'Đang chuẩn bị'
  return event.status_label || 'Đang chuẩn bị'
}
