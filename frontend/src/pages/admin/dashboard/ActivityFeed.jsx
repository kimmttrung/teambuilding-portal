import { useState } from 'react'
import { History } from 'lucide-react'
import { AUDIT_ACTION_LABELS } from '../../../utils/constants'
import { formatDateTime, formatRelative } from '../../../utils/format'
import Card from '../../../components/common/Card'

const VISIBLE = 5

/** Những thay đổi mới nhất trong kỳ, lấy từ audit log. Mặc định 5 dòng để cột phụ không dài hơn cột chính. */
export default function ActivityFeed({ items }) {
  const [expanded, setExpanded] = useState(false)
  const shown = expanded ? items : items.slice(0, VISIBLE)
  const hidden = items.length - shown.length

  return (
    <Card
      title="Hoạt động gần đây"
      action={<History className="size-4 text-slate-400" aria-hidden="true" />}
      bodyClassName="p-0"
    >
      {items.length === 0 ? (
        <p className="px-4 py-3.5 text-sm text-slate-500">Chưa có thay đổi nào.</p>
      ) : (
        <>
          <ul className="divide-y divide-slate-100">
            {shown.map((item) => (
              <li key={item.id} className="px-4 py-2">
                <div className="flex items-baseline justify-between gap-3">
                  <p className="min-w-0 truncate text-sm text-slate-900">
                    {AUDIT_ACTION_LABELS[item.action] ?? item.action}
                  </p>
                  <time
                    dateTime={item.created_at}
                    title={formatDateTime(item.created_at)}
                    className="shrink-0 text-xs text-slate-400"
                  >
                    {formatRelative(item.created_at)}
                  </time>
                </div>
                <p className="truncate text-xs text-slate-500">
                  {item.actor_name ?? 'Hệ thống'}
                  {item.reason && <span className="italic"> · “{item.reason}”</span>}
                </p>
              </li>
            ))}
          </ul>
          {(hidden > 0 || expanded) && items.length > VISIBLE && (
            <button
              type="button"
              onClick={() => setExpanded((open) => !open)}
              className="w-full border-t border-slate-100 px-4 py-2 text-xs font-medium text-brand-700 transition hover:bg-slate-50"
            >
              {expanded ? 'Thu gọn' : `Xem thêm ${hidden} thay đổi`}
            </button>
          )}
        </>
      )}
    </Card>
  )
}
