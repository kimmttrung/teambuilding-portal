import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowDown,
  ArrowUp,
  CalendarDays,
  MapPin,
  Pencil,
  Plus,
  Trash2,
} from 'lucide-react'
import { useActiveEvent } from '../../hooks/useEvent'
import {
  useDeleteItineraryItem,
  useItinerary,
  useReorderItineraryDay,
} from '../../hooks/useItinerary'
import { useRegistrationFormOptions } from '../../hooks/useRegistration'
import { useToast } from '../../context/ToastContext'
import { EVENT_STATUS, EVENT_STATUS_META, NOTIFY_HINTS } from '../../utils/constants'
import { formatDateWithWeekday } from '../../utils/format'
import Alert from '../../components/common/Alert'
import Badge from '../../components/common/Badge'
import Button from '../../components/common/Button'
import Card from '../../components/common/Card'
import EmptyState from '../../components/common/EmptyState'
import Modal from '../../components/common/Modal'
import NotifyToggle from '../../components/admin/NotifyToggle'
import PageHeader from '../../components/common/PageHeader'
import Spinner from '../../components/common/Spinner'
import ItineraryFormModal from './itinerary/ItineraryFormModal'

const STATUS_ORDER = Object.values(EVENT_STATUS)

/**
 * BTC quản lý lịch trình chương trình — nguồn của timeline My Journey.
 *
 * Sửa ở đây là CBNV thấy ngay (không cần chạy lại phân bổ): giờ bay/xe thật vẫn lấy
 * từ phân bổ, còn "làm gì, ở đâu, dành cho ai" lấy từ các mốc này.
 */
export default function ItineraryPage() {
  const toast = useToast()
  const { data: event } = useActiveEvent()
  const { data: options } = useRegistrationFormOptions()
  const { data: items, isLoading, error } = useItinerary()
  const { mutateAsync: removeItem, isPending: isDeleting } = useDeleteItineraryItem()
  const { mutateAsync: reorderDay, isPending: isReordering } = useReorderItineraryDay()

  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [defaultDay, setDefaultDay] = useState(null)
  const [deleting, setDeleting] = useState(null)

  const shifts = options?.shifts ?? []
  const teams = (options?.teams ?? []).filter((team) => team.is_active)
  const audiences = [
    { value: 'all', label: 'Tất cả mọi người' },
    ...shifts.map((shift) => ({ value: shift.code, label: `${shift.code} — ${shift.name}` })),
    ...teams.map((team) => ({ value: team.code, label: `Team ${team.code} — ${team.name}` })),
  ]
  const audienceLabel = Object.fromEntries(audiences.map((entry) => [entry.value, entry.label]))
  const tripLegs = [...(options?.trip_legs ?? [])].sort(
    (left, right) => left.display_order - right.display_order,
  )

  if (isLoading) return <Spinner label="Đang tải lịch trình…" />
  if (error) {
    return (
      <Alert tone="error" title="Không tải được lịch trình">
        {error.message}
      </Alert>
    )
  }

  const statusMeta = event ? EVENT_STATUS_META[event.status] : null
  // Trước công bố CBNV chưa thấy lịch theo ca được xếp — chưa có gì để báo "đổi".
  const published = event ? STATUS_ORDER.indexOf(event.status) >= STATUS_ORDER.indexOf(EVENT_STATUS.INFORMATION_PUBLISHED) : false
  const days = groupByDay(items ?? [])

  function openCreate(day) {
    setEditing(null)
    setDefaultDay(day)
    setFormOpen(true)
  }

  async function confirmDelete() {
    try {
      await removeItem(deleting.id)
      toast.success('Đã xoá mốc lịch trình.')
      setDeleting(null)
    } catch (deleteError) {
      toast.error(deleteError.message)
    }
  }

  /** Đổi chỗ 2 mốc kề nhau rồi gửi toàn bộ thứ tự của ngày lên server. */
  async function move(day, index, delta) {
    const ordered = day.items.map((item) => item.id)
    const other = index + delta
    if (other < 0 || other >= ordered.length) return
    const swapped = [...ordered]
    const [moved] = swapped.splice(index, 1)
    swapped.splice(other, 0, moved)
    try {
      await reorderDay({ dayDate: day.date, orderedIds: swapped })
    } catch (reorderError) {
      toast.error(reorderError.message)
    }
  }

  return (
    <>
      <PageHeader
        title="Lịch trình chương trình"
        description={event ? `${event.name} · ${statusMeta?.label ?? event.status}` : undefined}
        action={
          <div className="flex flex-wrap gap-2">
            {published && <NotifyToggle hint={NOTIFY_HINTS.itinerary} />}
            <Link to="/schedule" target="_blank" rel="noreferrer">
              <Button variant="secondary">Xem như CBNV</Button>
            </Link>
            <Button icon={Plus} onClick={() => openCreate(days[0]?.date)}>
              Thêm mốc
            </Button>
          </div>
        }
      />

      <Alert tone="info" className="mb-4" title="CBNV thấy gì từ các mốc này?">
        Mỗi người chỉ thấy mốc chung và mốc của ca được xếp của mình. Giờ bay/xe thật lấy từ
        kết quả phân bổ, không lấy giờ chữ ở đây — sửa mốc không làm lệch vé của ai.
      </Alert>

      {days.length === 0 && (
        <Card>
          <EmptyState
            icon={CalendarDays}
            title="Chưa có mốc lịch trình nào"
            description="Thêm mốc đầu tiên cho ngày đầu của kỳ — ví dụ giờ tập trung tại điểm đón."
            action={<Button size="sm" icon={Plus} onClick={() => openCreate(event?.start_date)}>Thêm mốc đầu tiên</Button>}
          />
        </Card>
      )}

      <div className="grid gap-4 xl:grid-cols-12">
        {days.map((day) => (
          <div key={day.date} className="xl:col-span-6">
            <Card
              title={formatDateWithWeekday(day.date)}
              description={`${day.items.length} mốc`}
              action={
                <Button variant="secondary" size="sm" icon={Plus} onClick={() => openCreate(day.date)}>
                  Thêm mốc
                </Button>
              }
            >
              <ol className="flex flex-col divide-y divide-slate-100">
                {day.items.map((item, index) => (
                  <li key={item.id} className="flex items-start gap-3 py-2.5">
                    <span className="w-24 shrink-0 text-sm font-bold text-slate-900 tabular-nums">
                      {item.start_time ?? '—'}
                      {item.end_time && (
                        <span className="block text-xs font-normal text-slate-500">
                          → {item.end_time}
                        </span>
                      )}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-medium text-slate-900">{item.title}</span>
                      {item.location && (
                        <span className="mt-0.5 flex items-center gap-1 text-xs text-slate-500">
                          <MapPin className="size-3 shrink-0" aria-hidden="true" />
                          <span className="truncate">{item.location}</span>
                        </span>
                      )}
                      <span className="mt-1 flex flex-wrap gap-1">
                        <Badge tone={item.audience === 'all' ? 'slate' : 'brand'}>
                          {audienceLabel[item.audience] ?? item.audience}
                        </Badge>
                        {item.trip_leg_id && (
                          <Badge tone="amber">
                            Chỉ người đi xe: {item.trip_leg_name ?? `chặng #${item.trip_leg_id}`}
                          </Badge>
                        )}
                      </span>
                    </span>
                    <span className="flex shrink-0 items-center gap-0.5">
                      <IconButton label="Lên trên" disabled={index === 0 || isReordering} onClick={() => move(day, index, -1)}>
                        <ArrowUp className="size-4" aria-hidden="true" />
                      </IconButton>
                      <IconButton label="Xuống dưới" disabled={index === day.items.length - 1 || isReordering} onClick={() => move(day, index, 1)}>
                        <ArrowDown className="size-4" aria-hidden="true" />
                      </IconButton>
                      <IconButton label="Sửa" onClick={() => {
                        setEditing(item)
                        setFormOpen(true)
                      }}>
                        <Pencil className="size-4" aria-hidden="true" />
                      </IconButton>
                      <IconButton label="Xoá" tone="danger" onClick={() => setDeleting(item)}>
                        <Trash2 className="size-4" aria-hidden="true" />
                      </IconButton>
                    </span>
                  </li>
                ))}
              </ol>
            </Card>
          </div>
        ))}
      </div>

      {formOpen && (
        <ItineraryFormModal
          open
          item={editing}
          defaultDay={defaultDay}
          event={event}
          audiences={audiences}
          tripLegs={tripLegs}
          onClose={() => {
            setFormOpen(false)
            setEditing(null)
          }}
        />
      )}

      <Modal
        open={Boolean(deleting)}
        onClose={() => setDeleting(null)}
        title="Xoá mốc lịch trình?"
        description={deleting ? `"${deleting.title}" — CBNV sẽ không còn thấy mốc này.` : undefined}
        footer={
          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" size="sm" onClick={() => setDeleting(null)}>
              Giữ lại
            </Button>
            <Button size="sm" variant="danger" loading={isDeleting} onClick={confirmDelete}>
              Xoá mốc
            </Button>
          </div>
        }
      />
    </>
  )
}

function IconButton({ label, tone, ...props }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      {...props}
      className={`rounded-lg p-1.5 transition disabled:cursor-not-allowed disabled:opacity-30 ${
        tone === 'danger'
          ? 'text-slate-400 hover:bg-rose-50 hover:text-rose-600'
          : 'text-slate-400 hover:bg-slate-100 hover:text-slate-700'
      }`}
    />
  )
}

function groupByDay(items) {
  const byDay = new Map()
  for (const item of items) {
    const list = byDay.get(item.day_date)
    if (list) list.push(item)
    else byDay.set(item.day_date, [item])
  }
  return [...byDay.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([date, list]) => ({ date, items: list }))
}
