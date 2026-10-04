import { NavLink } from 'react-router-dom'
import { formatShortDateTime } from '../../utils/format'

/**
 * Ngữ cảnh kỳ đang xem — dùng chung cho toàn bộ màn hình trong AppLayout.
 * EventPublic là nguồn duy nhất cho tiêu đề, trạng thái và thời điểm cập nhật.
 *
 * `tabs` là các màn hình cùng nhóm (BTC: 5 màn hình phân bổ) để chuyển thẳng qua lại mà không phải
 * quay về trang gom. Trên điện thoại chỉ còn hàng tab: tên kỳ đã có ở thanh trên cùng.
 */
export default function EventContextBar({ event, tabs = [], className = '' }) {
  if (!event) return null

  const published = Boolean(
    event.is_published ||
      ['information_published', 'event_started', 'completed'].includes(event.status),
  )
  const statusLabel = getStatusLabel(event, published)
  const updatedLabel = event.updated_at
    ? `Cập nhật ${formatShortDateTime(event.updated_at)} · tự động từ BTC`
    : 'Cập nhật tự động từ BTC'
  const hasTabs = tabs.length > 0

  return (
    <div
      className={`${hasTabs ? 'flex' : 'hidden md:flex'} min-h-14 items-center gap-x-6 border-b border-hairline bg-canvas px-4 sm:px-6 lg:px-8 ${className}`}
      aria-label="Thông tin kỳ Team Building"
    >
      <div className="hidden min-w-0 shrink-0 items-center gap-2.5 py-2 md:flex">
        <span className="truncate text-title text-ink">
          {event.code} · {event.destination || event.name}
        </span>
        <span
          className={`shrink-0 rounded-md px-2 py-0.5 text-eyebrow ${
            published ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-800'
          }`}
        >
          {statusLabel}
        </span>
      </div>

      {hasTabs && (
        <nav aria-label="Phân bổ" className="flex min-w-0 flex-1 gap-1 self-stretch overflow-x-auto overflow-y-hidden [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {tabs.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `inline-flex shrink-0 items-center gap-2 border-b-2 px-3 text-body-sm whitespace-nowrap transition ${
                  isActive
                    ? 'border-primary font-medium text-primary'
                    : 'border-transparent text-ink-muted hover:text-ink'
                }`
              }
            >
              <Icon className="size-4" aria-hidden="true" />
              {label}
            </NavLink>
          ))}
        </nav>
      )}

      <span className="ml-auto hidden shrink-0 text-caption text-ink-faint xl:block">{updatedLabel}</span>
    </div>
  )
}

function getStatusLabel(event, published) {
  if (published) return 'Đã công bố'
  if (event.status === 'draft') return 'Đang chuẩn bị'
  return event.status_label || 'Đang chuẩn bị'
}
