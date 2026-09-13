import { Link } from 'react-router-dom'
import { CheckCircle2, Circle, CircleDashed } from 'lucide-react'
import Badge from '../../../components/common/Badge'
import Card from '../../../components/common/Card'

/**
 * Việc cần xong trước khi công bố. Chỉ nhắc, không chặn: BTC có thể cố ý công bố từng phần.
 * Icon khác nhau cho "bắt buộc" và "nên làm" — không dựa vào màu (docs/07 §6).
 */
export default function PublishChecklist({ items, ready, published }) {
  const pending = items.filter((item) => item.required && !item.done).length

  return (
    <Card
      title="Trước khi công bố"
      description={published ? 'Đã công bố — dùng để rà lại' : undefined}
      action={
        <Badge tone={ready ? 'emerald' : 'amber'}>{ready ? 'Sẵn sàng' : `Còn ${pending} việc`}</Badge>
      }
    >
      <ul className="flex flex-col gap-2.5">
        {items.map((item) => {
          const Icon = item.done ? CheckCircle2 : item.required ? Circle : CircleDashed
          return (
            <li key={item.key} className="flex gap-2.5">
              <Icon
                className={`mt-0.5 size-4 shrink-0 ${
                  item.done ? 'text-emerald-600' : item.required ? 'text-amber-600' : 'text-slate-400'
                }`}
                aria-hidden="true"
              />
              <div className="min-w-0 flex-1">
                <p className={`text-sm ${item.done ? 'text-slate-500' : 'font-medium text-slate-900'}`}>
                  {item.label}
                  {!item.required && <span className="ml-1 text-xs font-normal text-slate-400">(nên làm)</span>}
                  <span className="sr-only">{item.done ? ' — đã xong' : ' — chưa xong'}</span>
                </p>
                {item.detail && <p className="mt-0.5 text-xs text-slate-500">{item.detail}</p>}
              </div>
              {!item.done && item.link && (
                <Link
                  to={item.link}
                  className="shrink-0 self-start text-xs font-medium text-brand-700 hover:underline"
                >
                  Xử lý
                </Link>
              )}
            </li>
          )
        })}
      </ul>
    </Card>
  )
}
