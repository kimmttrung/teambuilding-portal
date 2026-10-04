import { Link } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import { useConfigImpact } from '../../hooks/useEvent'
import { CONFIG_IMPACT_ACTIONS } from '../../utils/constants'
import Alert from '../common/Alert'

const SHOWN_DETAILS = 3

/**
 * "Cần rà lại phân bổ" — những thứ đã xếp không còn khớp cấu hình kỳ (chuyến bay / xe / lịch trình
 * nằm ngoài ngày của kỳ, xe lệch giờ bay sau khi đổi số phút đệm…).
 *
 * Backend tính lại mỗi lần hỏi nên hộp này còn hiện chừng nào dữ liệu còn lệch, không chỉ ngay sau
 * khi bấm Lưu. Không có gì lệch thì không vẽ gì.
 */
export default function ConfigImpactAlert({ eventId, className = '' }) {
  const { data } = useConfigImpact(eventId)
  if (!data?.needs_review) return null

  return (
    <Alert tone="warning" title="Cần rà lại phân bổ" className={className}>
      <p>Cấu hình kỳ đã đổi nên một số thứ đã xếp không còn khớp. Sửa ở màn hình tương ứng:</p>
      <ul className="mt-2 grid gap-2">
        {data.items.map((item) => (
          <li key={item.kind}>
            <p className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
              <span className="font-medium text-ink">
                {item.title} · {item.count}
              </span>
              <Link to={item.link} className="inline-flex items-center gap-1 font-medium underline">
                {CONFIG_IMPACT_ACTIONS[item.kind] ?? 'Mở màn hình'}
                <ArrowRight className="size-3.5" aria-hidden="true" />
              </Link>
            </p>
            <ul className="mt-0.5 list-disc pl-5 text-ink-muted">
              {item.details.slice(0, SHOWN_DETAILS).map((line) => (
                <li key={line}>{line}</li>
              ))}
              {item.count > SHOWN_DETAILS && <li>… và {item.count - SHOWN_DETAILS} mục khác</li>}
            </ul>
          </li>
        ))}
      </ul>
    </Alert>
  )
}
