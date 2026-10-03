import { useState } from 'react'
import { AUDIT_ACTION_LABELS } from '../../../utils/constants'
import { formatDateTime, formatRelative, initials } from '../../../utils/format'

const VISIBLE = 5

/** "Vừa xảy ra" (Figma v2 · B1): thay đổi mới nhất trong kỳ từ audit log — ai, làm gì, bao lâu trước. */
export default function ActivityFeed({ items }) {
  const [expanded, setExpanded] = useState(false)
  const shown = expanded ? items : items.slice(0, VISIBLE)
  const hidden = items.length - shown.length

  return (
    <section aria-labelledby="dashboard-activity">
      <h2 id="dashboard-activity" className="text-heading-3 text-ink">
        Vừa xảy ra
      </h2>

      {items.length === 0 ? (
        <p className="mt-3.5 text-caption text-ink-muted">Chưa có thay đổi nào.</p>
      ) : (
        <>
          <ul className="mt-3.5 flex flex-col gap-3">
            {shown.map((item) => {
              const actor = item.actor_name ?? 'Hệ thống'
              return (
                <li key={item.id} className="flex items-start gap-2.5 text-caption">
                  <span
                    className="grid size-6 shrink-0 place-items-center rounded-full bg-canvas-soft text-[10px] font-bold text-ink-secondary ring-1 ring-hairline"
                    aria-hidden="true"
                  >
                    {item.actor_name ? initials(item.actor_name) : 'HT'}
                  </span>
                  <p className="min-w-0 flex-1">
                    <b className="font-semibold text-ink">{actor}</b>{' '}
                    <span className="text-ink-muted">
                      {(AUDIT_ACTION_LABELS[item.action] ?? item.action).toLowerCase()}
                      {item.reason && <span className="italic"> · “{item.reason}”</span>}
                    </span>
                  </p>
                  <time
                    dateTime={item.created_at}
                    title={formatDateTime(item.created_at)}
                    className="shrink-0 text-eyebrow font-normal whitespace-nowrap text-ink-faint"
                  >
                    {formatRelative(item.created_at)}
                  </time>
                </li>
              )
            })}
          </ul>
          {(hidden > 0 || expanded) && items.length > VISIBLE && (
            <button
              type="button"
              onClick={() => setExpanded((open) => !open)}
              className="mt-2 inline-flex min-h-11 items-center text-caption font-semibold text-primary hover:underline sm:min-h-8"
            >
              {expanded ? 'Thu gọn' : `Xem thêm ${hidden} thay đổi`}
            </button>
          )}
        </>
      )}
    </section>
  )
}
