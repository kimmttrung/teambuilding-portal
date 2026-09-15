import { useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, CheckCircle2, ChevronDown, CircleAlert, Info } from 'lucide-react'
import { EVENT_STATUS } from '../../../utils/constants'
import { formatNumber } from '../../../utils/format'
import Badge from '../../../components/common/Badge'
import Card from '../../../components/common/Card'

/**
 * "Việc cần làm": mọi thứ BTC phải xử lý trong một danh sách, mỗi dòng dẫn thẳng tới chỗ xử lý.
 * Thay cho 4 thẻ cũ (checklist, nhắc email, cảnh báo thiếu giấy tờ, email lỗi) vốn lặp lại cùng con số.
 * Việc đã xong thu gọn thành một dòng — mở ra khi cần rà trước khi công bố.
 */
export default function ActionCenter({ data, onRemind }) {
  const [showDone, setShowDone] = useState(false)
  const { event, checklist } = data
  const tasks = buildTasks(data, onRemind)
  const done = checklist.filter((item) => item.done)
  const pendingRequired = checklist.filter((item) => item.required && !item.done).length

  const badge = event.is_published ? (
    <Badge tone="brand">Đã công bố</Badge>
  ) : data.ready_to_publish ? (
    <Badge tone="emerald">Sẵn sàng công bố</Badge>
  ) : (
    <Badge tone="amber">Còn {pendingRequired} việc trước công bố</Badge>
  )

  return (
    <Card title="Việc cần làm" action={badge} bodyClassName="p-0">
      {tasks.length === 0 ? (
        <div className="flex items-center gap-3 px-4 py-4">
          <span className="grid size-9 shrink-0 place-items-center rounded-full bg-emerald-50 text-emerald-600">
            <CheckCircle2 className="size-5" aria-hidden="true" />
          </span>
          <div>
            <p className="text-sm font-medium text-slate-900">Không có việc tồn đọng</p>
            <p className="text-xs text-slate-500">Số liệu tự làm mới khi quay lại tab này.</p>
          </div>
        </div>
      ) : (
        <ul className="divide-y divide-slate-100">
          {tasks.map((task) => (
            <TaskRow key={task.key} task={task} />
          ))}
        </ul>
      )}

      {done.length > 0 && (
        <div className="border-t border-slate-100">
          <button
            type="button"
            onClick={() => setShowDone((open) => !open)}
            aria-expanded={showDone}
            className="flex w-full items-center justify-between gap-3 px-4 py-2.5 text-xs font-medium text-slate-500 transition hover:bg-slate-50"
          >
            <span>
              Đã xong {done.length}/{checklist.length} mục trước công bố
            </span>
            <ChevronDown className={`size-4 transition ${showDone ? 'rotate-180' : ''}`} aria-hidden="true" />
          </button>
          {showDone && (
            <ul className="flex flex-col gap-1.5 px-4 pb-3">
              {done.map((item) => (
                <li key={item.key} className="flex items-center gap-2 text-sm text-slate-500">
                  <CheckCircle2 className="size-4 shrink-0 text-emerald-600" aria-hidden="true" />
                  {item.label}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </Card>
  )
}

const TONES = {
  danger: { icon: CircleAlert, cls: 'text-rose-600', label: 'Khẩn' },
  warning: { icon: AlertTriangle, cls: 'text-amber-600', label: 'Cần xử lý' },
  info: { icon: Info, cls: 'text-blue-600', label: 'Nên làm' },
}

const STATUS_ORDER = Object.values(EVENT_STATUS)
const atLeast = (status, target) => STATUS_ORDER.indexOf(status) >= STATUS_ORDER.indexOf(target)

// Nhãn checklist là đích cần đạt ("Email gửi không lỗi"); khi còn dang dở thì đọc như một việc phải làm.
const PENDING_TITLES = {
  flight_documents: 'Bổ sung giấy tờ để xuất vé',
  flight_capacity: 'Bổ sung ghế máy bay',
  flights_assigned: 'Xếp chuyến bay còn thiếu',
  buses_assigned: 'Xếp xe còn thiếu',
  rooms_assigned: 'Xếp phòng còn thiếu',
  emails_ok: 'Gửi lại email bị lỗi',
}

// Hai mục này làm được ngay từ lúc mở đăng ký; các mục phân bổ chỉ thành "việc" khi đã đóng đăng ký.
const ALWAYS_ACTIONABLE = new Set(['flight_documents', 'emails_ok'])

/** Hàm thuần: dựng danh sách việc từ số liệu dashboard (backend đã đếm, ở đây chỉ chọn và sắp). */
export function buildTasks(data, onRemind) {
  const { event, registrations: stats, checklist, gala } = data
  const status = event.status
  const tasks = []

  if (status === EVENT_STATUS.REGISTRATION_OPEN && stats.not_submitted > 0) {
    tasks.push({
      key: 'not_registered',
      tone: 'info',
      title: `${formatNumber(stats.not_submitted)} CBNV chưa phản hồi đăng ký`,
      detail: 'Nhắc sớm để chốt số lượng trước khi mua vé.',
      actions: [
        { label: 'Xem danh sách', to: '/admin/users?registration=none' },
        { label: 'Gửi email nhắc', onClick: () => onRemind('not_registered') },
      ],
    })
  }

  for (const item of checklist) {
    if (item.done) continue
    if (!ALWAYS_ACTIONABLE.has(item.key) && !atLeast(status, EVENT_STATUS.REGISTRATION_CLOSED)) continue
    // Đóng đăng ký là nút ở đầu trang, không cần nhắc lại ở đây.
    if (item.key === 'registration_closed') continue

    const actions = []
    if (item.link) {
      actions.push({ label: item.key === 'emails_ok' ? 'Xem thư lỗi' : 'Xử lý', to: item.link })
    }
    if (item.key === 'flight_documents' && !atLeast(status, EVENT_STATUS.EVENT_STARTED)) {
      actions.push({ label: 'Gửi email nhắc', onClick: () => onRemind('missing_documents') })
    }
    tasks.push({
      key: item.key,
      // Đã công bố mà còn thiếu thì CBNV đang thấy "đang chờ" — nặng hơn lúc chuẩn bị.
      tone: !item.required ? 'info' : event.is_published ? 'danger' : 'warning',
      title: PENDING_TITLES[item.key] ?? item.label,
      detail: item.detail,
      actions,
    })
  }

  if (event.is_published && gala?.configured) {
    const gaps = [
      gala.selection_status === 'open' && 'các team đang chọn ghế',
      gala.teams_missing > 0 && `${gala.teams_missing} team chưa đủ ghế`,
      gala.unseated > 0 && `${gala.unseated} người chưa có ghế`,
    ].filter(Boolean)
    if (gala.teams_missing > 0 || gala.unseated > 0) {
      tasks.push({
        key: 'gala_seating',
        tone: 'warning',
        title: 'Xếp xong chỗ ngồi Gala',
        detail: `${gaps.join(', ')}. Chưa xong thì không chuyển sang "Đang diễn ra" được.`,
        actions: [{ label: 'Mở Gala', to: '/admin/gala' }],
      })
    }
  }

  const rank = { danger: 0, warning: 1, info: 2 }
  return tasks.sort((a, b) => rank[a.tone] - rank[b.tone])
}

const ACTION_CLASS = 'text-xs font-semibold text-brand-700 hover:underline'

function TaskRow({ task }) {
  const { icon: Icon, cls, label } = TONES[task.tone]
  return (
    <li className="flex gap-3 px-4 py-3">
      <Icon className={`mt-0.5 size-4 shrink-0 ${cls}`} aria-label={label} />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-slate-900">{task.title}</p>
        {task.detail && <p className="mt-0.5 text-xs leading-relaxed text-slate-500">{task.detail}</p>}
        {task.actions.length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1">
            {task.actions.map((action) =>
              action.to ? (
                <Link key={action.label} to={action.to} className={ACTION_CLASS}>
                  {action.label}
                </Link>
              ) : (
                <button key={action.label} type="button" onClick={action.onClick} className={ACTION_CLASS}>
                  {action.label}
                </button>
              ),
            )}
          </div>
        )}
      </div>
    </li>
  )
}
