import { Megaphone } from 'lucide-react'
import { ANNOUNCEMENT_SEVERITY_META } from '../../../utils/constants'
import { formatRelative } from '../../../utils/format'
import Badge from '../../../components/common/Badge'
import Card from '../../../components/common/Card'
import MarkdownText from '../../../components/common/MarkdownText'

/** Thông báo BTC gửi cho người này: chung, theo team, theo chuyến/xe, hoặc riêng. */
export default function AnnouncementsPanel({ announcements = [] }) {
  return (
    <Card
      title="Thông báo từ BTC"
      action={<Megaphone className="size-4 text-slate-400" aria-hidden="true" />}
      bodyClassName="p-0"
    >
      {announcements.length === 0 ? (
        <p className="px-4 py-3.5 text-sm text-slate-500">Chưa có thông báo nào.</p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {announcements.map((item, index) => {
            const meta = ANNOUNCEMENT_SEVERITY_META[item.severity] ?? ANNOUNCEMENT_SEVERITY_META.info
            return (
              <li key={item.id}>
                {/* <details> gốc: mở/đóng bằng bàn phím sẵn, không cần JS. Tin khẩn mới nhất mở sẵn. */}
                <details className="px-4 py-3" open={index === 0 && item.severity === 'urgent'}>
                  <summary className="flex cursor-pointer list-none items-start gap-2">
                    <Badge tone={meta.tone}>{meta.label}</Badge>
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-medium text-slate-900">{item.title}</span>
                      <span className="block text-xs text-slate-500">{formatRelative(item.published_at)}</span>
                    </span>
                  </summary>
                  <MarkdownText content={item.content} className="mt-2" />
                </details>
              </li>
            )
          })}
        </ul>
      )}
    </Card>
  )
}
