import { useState } from 'react'
import { CheckCircle2, Plus, Trash2 } from 'lucide-react'
import { eventStore } from '../../api/client'
import DeleteEventDialog from '../../components/layout/DeleteEventDialog'
import EventCreateModal from '../../components/layout/EventCreateModal'
import Alert from '../../components/common/Alert'
import Button from '../../components/common/Button'
import PageHeader from '../../components/common/PageHeader'
import Spinner from '../../components/common/Spinner'
import { useToast } from '../../context/ToastContext'
import { useActivateEvent, useActiveEvent, useEvents, useSelectEvent } from '../../hooks/useEvent'
import { formatDate } from '../../utils/format'

/**
 * Quản lý các kỳ: thêm, chuyển sang xem, đặt làm mặc định, xoá.
 * Kỳ mặc định xoá được — nếu còn kỳ khác, kỳ tạo sau cùng được đặt làm mặc định.
 */
export default function EventsPage() {
  const toast = useToast()
  const { data: events, isLoading, error } = useEvents()
  const { data: current } = useActiveEvent()
  const selectEvent = useSelectEvent()
  const { mutateAsync: activate, isPending: activating } = useActivateEvent()
  const [creating, setCreating] = useState(false)
  const [deleting, setDeleting] = useState(null)

  async function onActivate(event) {
    const message =
      `Đặt "${event.name}" làm kỳ mặc định?\n\n` +
      'Kỳ mặc định là thứ mọi người thấy khi chưa chọn kỳ nào — đổi là ảnh hưởng toàn bộ CBNV.'
    if (!window.confirm(message)) return
    try {
      await activate(event.id)
      toast.success(`${event.name} giờ là kỳ mặc định.`)
    } catch (activateError) {
      toast.error(activateError.message)
    }
  }

  if (isLoading) return <Spinner label="Đang tải danh sách kỳ…" />
  if (error) {
    return (
      <>
        <PageHeader title="Kỳ Team Building" />
        <Alert tone="error" title="Không tải được danh sách kỳ">
          {error.message}
        </Alert>
      </>
    )
  }

  return (
    <>
      <PageHeader
        title="Kỳ Team Building"
        description="Thêm kỳ cho mùa sau, chọn kỳ đang xem, hoặc xoá kỳ không còn dùng."
        action={
          <Button shape="pill" icon={Plus} onClick={() => setCreating(true)}>
            Thêm kỳ
          </Button>
        }
      />

      {events.length === 0 ? (
        <Alert tone="warning" title="Chưa có kỳ nào">
          Tạo kỳ mới để bắt đầu. Kỳ vừa tạo ở trạng thái nháp, CBNV chưa nhìn thấy.
        </Alert>
      ) : (
        <ul className="flex flex-col gap-3">
          {events.map((event) => {
            // Cùng nguồn với ô chọn kỳ: localStorage đổi ngay khi tạo, còn `useActiveEvent`
            // trống vài trăm ms lúc đang tải lại. So bằng `current` thì kỳ mới chưa kịp
            // hiện "Đang xem" hoặc hiện trong lúc thanh bên vẫn là kỳ cũ.
            const viewingId = eventStore.get() ?? current?.id
            const viewing = viewingId != null && String(viewingId) === String(event.id)
            return (
              <li key={event.id} className="rounded-lg border border-hairline bg-surface px-4 py-4 sm:px-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-body-md font-semibold text-ink">{event.name}</p>
                    <p className="mt-1 text-caption text-ink-muted">
                      {event.code}
                      {event.destination ? ` · ${event.destination}` : ''} · {formatDate(event.start_date)} –{' '}
                      {formatDate(event.end_date)}
                    </p>
                    <p className="mt-2 flex flex-wrap items-center gap-2 text-caption">
                      <span className="text-ink-secondary">{event.status_label}</span>
                      {event.is_active && (
                        <span className="rounded-full bg-canvas-soft px-2 py-0.5 font-medium text-ink">
                          Kỳ mặc định
                        </span>
                      )}
                      {viewing && <span className="font-medium text-primary">Đang xem</span>}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {!viewing && (
                      <Button variant="secondary" size="sm" onClick={() => selectEvent(event.id)}>
                        Xem kỳ này
                      </Button>
                    )}
                    {!event.is_active && (
                      <Button
                        variant="secondary"
                        size="sm"
                        icon={CheckCircle2}
                        loading={activating}
                        onClick={() => onActivate(event)}
                      >
                        Đặt làm mặc định
                      </Button>
                    )}
                    <Button variant="danger" size="sm" icon={Trash2} onClick={() => setDeleting(event)}>
                      Xoá
                    </Button>
                  </div>
                </div>
              </li>
            )
          })}
        </ul>
      )}

      {creating && <EventCreateModal open onClose={() => setCreating(false)} />}
      {deleting && <DeleteEventDialog event={deleting} onClose={() => setDeleting(null)} />}
    </>
  )
}
