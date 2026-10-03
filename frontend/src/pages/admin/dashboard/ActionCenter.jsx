import { useState } from 'react'
import { Link } from 'react-router-dom'
import { CheckCircle2, ChevronDown } from 'lucide-react'
import { EVENT_STATUS } from '../../../utils/constants'
import { formatNumber } from '../../../utils/format'

/**
 * "Việc cần làm" (Figma v2 · B1): mọi thứ BTC phải xử lý trong một danh sách, mỗi dòng dẫn thẳng tới
 * chỗ xử lý. Nhãn bên trái cho biết loại việc, hành động nằm bên phải.
 * Việc đã xong thu gọn thành một dòng — mở ra khi cần rà trước khi công bố.
 */
export default function ActionCenter({ data, onRemind, onAssignLeader }) {
  const [showDone, setShowDone] = useState(false)
  const { event, checklist } = data
  const tasks = buildTasks(data, onRemind, onAssignLeader)
  const done = checklist.filter((item) => item.done)
  const pendingRequired = checklist.filter((item) => item.required && !item.done).length

  const summary = event.is_published
    ? 'Đã công bố'
    : data.ready_to_publish
      ? 'Sẵn sàng công bố'
      : `${pendingRequired} việc trước khi công bố`

  return (
    <section aria-labelledby="dashboard-tasks">
      <div className="flex items-baseline justify-between gap-3">
        <h2 id="dashboard-tasks" className="text-heading-3 text-ink">
          Việc cần làm
        </h2>
        <span className="text-caption text-ink-muted">{summary}</span>
      </div>

      <div className="mt-3.5 overflow-hidden rounded-lg border border-hairline bg-surface">
        {tasks.length === 0 ? (
          <div className="flex items-center gap-3 px-4 py-4 sm:px-5">
            <CheckCircle2 className="size-5 shrink-0 text-accent-green" aria-hidden="true" />
            <div>
              <p className="text-body-sm font-semibold text-ink">Không có việc tồn đọng</p>
              <p className="text-caption text-ink-muted">Số liệu tự làm mới khi quay lại tab này.</p>
            </div>
          </div>
        ) : (
          <ul className="divide-y divide-hairline">
            {tasks.map((task) => (
              <TaskRow key={task.key} task={task} />
            ))}
          </ul>
        )}

        {done.length > 0 && (
          <div className="border-t border-hairline">
            <button
              type="button"
              onClick={() => setShowDone((open) => !open)}
              aria-expanded={showDone}
              className="flex min-h-11 w-full items-center justify-between gap-3 px-4 text-caption text-ink-muted transition hover:bg-canvas-soft sm:px-5"
            >
              <span>
                Đã xong {done.length}/{checklist.length} mục trước công bố
              </span>
              <ChevronDown className={`size-4 transition ${showDone ? 'rotate-180' : ''}`} aria-hidden="true" />
            </button>
            {showDone && (
              <ul className="flex flex-col gap-2 px-4 pb-4 sm:px-5">
                {done.map((item) => (
                  <li key={item.key} className="flex items-center gap-2 text-caption text-ink-muted">
                    <CheckCircle2 className="size-4 shrink-0 text-accent-green" aria-hidden="true" />
                    {item.label}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </section>
  )
}

// Màu trạng thái của ứng dụng (skill không có bảng màu lỗi/cảnh báo) — cùng bộ với `Badge`.
const TAG_TONES = {
  danger: 'bg-rose-50 text-rose-700',
  warning: 'bg-amber-50 text-amber-800',
  info: 'bg-brand-50 text-primary-active',
  neutral: 'bg-canvas-soft text-ink-muted',
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
export function buildTasks(data, onRemind, onAssignLeader) {
  const { event, registrations: stats, checklist, gala } = data
  const status = event.status
  const tasks = []
  const cancellations = data.cancellations ?? { pending: 0, self_recent: 0 }

  if (cancellations.pending > 0) {
    tasks.push({
      key: 'cancellation_requests',
      tone: 'danger',
      tag: 'Chờ duyệt',
      title: `${formatNumber(cancellations.pending)} yêu cầu huỷ đăng ký chờ duyệt`,
      detail: 'CBNV xin huỷ sau công bố — vé, xe, phòng vẫn đang giữ cho tới khi BTC duyệt hoặc từ chối.',
      actions: [{ label: 'Xem & duyệt', to: '/admin/cancellations?status=pending' }],
    })
  }
  if (cancellations.self_recent > 0) {
    tasks.push({
      key: 'self_cancellations',
      tone: 'info',
      tag: 'Đã huỷ',
      title: `${formatNumber(cancellations.self_recent)} CBNV tự huỷ trong 7 ngày qua`,
      detail: 'Hệ thống đã giải phóng chỗ của họ — xếp lại hoặc chạy lại phân bổ nếu cần.',
      actions: [{ label: 'Xem danh sách', to: '/admin/cancellations?status=approved&mode=self' }],
    })
  }
  if (cancellations.reregistered_recent > 0 && atLeast(status, EVENT_STATUS.REGISTRATION_CLOSED)) {
    tasks.push({
      key: 'reregistered',
      tone: 'warning',
      tag: 'Xếp lại',
      title: `${formatNumber(cancellations.reregistered_recent)} CBNV đăng ký lại sau khi huỷ`,
      detail: 'Chỗ cũ đã được giải phóng khi huỷ — cần xếp lại chuyến bay, xe, phòng, ghế Gala.',
      actions: [{ label: 'Xem danh sách', to: '/admin/cancellations?status=approved' }],
    })
  }

  // Trưởng nhóm là người chọn ghế Gala cho team — Trưởng nhóm huỷ thì phải có người thay.
  for (const team of data.teams ?? []) {
    if (!team.needs_leader) continue
    tasks.push({
      key: `team_leader_${team.team_id}`,
      tone: event.is_published ? 'danger' : 'warning',
      tag: 'Trưởng nhóm',
      title: `Team ${team.name} chưa có Trưởng nhóm đang tham gia`,
      detail: team.leader_name
        ? `${team.leader_name} không còn tham gia — không ai chọn ghế Gala cho team.`
        : 'Không ai chọn ghế Gala cho team.',
      actions: onAssignLeader ? [{ label: 'Chỉ định Trưởng nhóm', onClick: () => onAssignLeader(team) }] : [],
    })
  }

  if (status === EVENT_STATUS.REGISTRATION_OPEN && stats.not_submitted > 0) {
    tasks.push({
      key: 'not_registered',
      tone: 'info',
      tag: 'Nhắc',
      title: `${formatNumber(stats.not_submitted)} nhân sự chưa phản hồi đăng ký`,
      detail: 'Nhắc sớm để chốt số lượng trước khi mua vé.',
      actions: [
        { label: 'Xem danh sách', to: '/admin/users?registration=none' },
        { label: 'Gửi nhắc', onClick: () => onRemind('not_registered') },
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
      tag: item.key === 'emails_ok' ? 'Email' : item.required ? 'Chặn công bố' : 'Nên làm',
      // Việc không bắt buộc đứng cuối danh sách nên nhãn cũng để xám, đúng dòng "Email" của Figma.
      tagTone: item.required ? undefined : 'neutral',
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
        tag: 'Gala',
        title: 'Xếp xong chỗ ngồi Gala',
        detail: `${gaps.join(', ')}. Chưa xong thì không chuyển sang "Đang diễn ra" được.`,
        actions: [{ label: 'Mở Gala', to: '/admin/gala' }],
      })
    }
  }

  const rank = { danger: 0, warning: 1, info: 2 }
  return tasks.sort((a, b) => rank[a.tone] - rank[b.tone])
}

const ACTION_CLASS =
  'inline-flex min-h-11 items-center text-caption font-semibold whitespace-nowrap text-primary hover:underline sm:min-h-0'

function TaskRow({ task }) {
  return (
    <li className="flex flex-wrap items-center gap-x-3.5 gap-y-1 px-4 py-3.5 sm:flex-nowrap sm:px-5">
      <span
        className={`inline-flex h-5.5 w-24 shrink-0 items-center justify-center rounded-sm px-2 text-eyebrow whitespace-nowrap ${
          TAG_TONES[task.tagTone ?? task.tone]
        }`}
      >
        {task.tag}
      </span>
      <div className="min-w-0 flex-1 basis-48">
        <p className="text-body-sm font-semibold text-ink">{task.title}</p>
        {task.detail && <p className="mt-0.5 text-caption text-ink-muted">{task.detail}</p>}
      </div>
      {task.actions.length > 0 && (
        <div className="flex shrink-0 flex-wrap items-center gap-x-4 sm:justify-end">
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
    </li>
  )
}
