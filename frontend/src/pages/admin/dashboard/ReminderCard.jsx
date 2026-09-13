import { Send } from 'lucide-react'
import { REMINDER_KINDS } from '../../../utils/constants'
import { formatNumber } from '../../../utils/format'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'

/** Lối vào gửi email nhắc cho các nhóm CBNV còn nợ việc. */
export default function ReminderCard({ stats, event, onRemind }) {
  const registrationOpen = event.status === 'registration_open'
  const rows = [
    {
      kind: 'missing_documents',
      count: stats.missing_flight_documents,
      hint: 'Đã xác nhận đi nhưng thiếu CCCD hoặc ngày sinh',
      disabled: false,
    },
    {
      kind: 'not_registered',
      count: stats.not_submitted,
      hint: registrationOpen ? 'Chưa gửi đăng ký' : 'Chỉ nhắc được khi đang mở đăng ký',
      disabled: !registrationOpen,
    },
  ]

  return (
    <Card title="Nhắc CBNV qua email" action={<Send className="size-4 text-slate-400" aria-hidden="true" />}>
      <ul className="flex flex-col gap-3">
        {rows.map((row) => (
          <li key={row.kind} className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="text-sm text-slate-900">
                {REMINDER_KINDS[row.kind].short}:{' '}
                <span className="font-semibold tabular-nums">{formatNumber(row.count)}</span> người
              </p>
              <p className="text-xs text-slate-500">{row.hint}</p>
            </div>
            <Button
              variant="secondary"
              size="sm"
              disabled={!row.count || row.disabled}
              onClick={() => onRemind(row.kind)}
            >
              Gửi nhắc
            </Button>
          </li>
        ))}
      </ul>
    </Card>
  )
}
