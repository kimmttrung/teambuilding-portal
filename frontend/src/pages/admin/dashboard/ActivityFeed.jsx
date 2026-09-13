import { History } from 'lucide-react'
import { AUDIT_ACTION_LABELS } from '../../../utils/constants'
import { formatDateTime, formatRelative } from '../../../utils/format'
import Card from '../../../components/common/Card'

/** Những thay đổi mới nhất trong kỳ, lấy từ audit log. */
export default function ActivityFeed({ items }) {
  return (
    <Card
      title="Hoạt động gần đây"
      action={<History className="size-4 text-slate-400" aria-hidden="true" />}
      bodyClassName="p-0"
    >
      {items.length === 0 ? (
        <p className="px-4 py-3.5 text-sm text-slate-500">Chưa có thay đổi nào.</p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {items.map((item) => (
            <li key={item.id} className="px-4 py-2.5">
              <p className="text-sm text-slate-900">{AUDIT_ACTION_LABELS[item.action] ?? item.action}</p>
              <p className="text-xs text-slate-500">
                {item.actor_name ?? 'Hệ thống'} ·{' '}
                <time dateTime={item.created_at} title={formatDateTime(item.created_at)}>
                  {formatRelative(item.created_at)}
                </time>
              </p>
              {item.reason && <p className="mt-0.5 text-xs text-slate-600 italic">“{item.reason}”</p>}
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
