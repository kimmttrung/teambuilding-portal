import { useState } from 'react'
import { useAuditLogs } from '../../hooks/useDashboard'
import { useActiveEvent } from '../../hooks/useEvent'
import { AUDIT_ACTION_LABELS } from '../../utils/constants'
import { formatDateTime, formatRelative, initials } from '../../utils/format'
import Alert from '../../components/common/Alert'
import Button from '../../components/common/Button'
import PageHeader from '../../components/common/PageHeader'
import Spinner from '../../components/common/Spinner'

/**
 * Lịch sử ai đã thao tác trên kỳ đang xem. Đọc `GET /admin/audit-logs`, không nhét vào Tổng quan.
 */
export default function ActivityLogPage() {
  const [page, setPage] = useState(1)
  const { data: event, isLoading: eventLoading } = useActiveEvent()
  const { data, isLoading, error } = useAuditLogs(event?.id, page)

  if (eventLoading || (event && isLoading)) return <Spinner label="Đang tải nhật ký…" />

  const items = data?.items ?? []
  const total = data?.total ?? 0
  const pageSize = data?.page_size ?? 30
  const pages = Math.max(1, Math.ceil(total / pageSize))

  return (
    <>
      <PageHeader
        title="Nhật ký thao tác"
        description={event ? `${event.name} · ai làm gì, lúc nào` : 'Chưa chọn kỳ'}
      />

      {!event ? (
        <Alert tone="warning" title="Chưa có kỳ">
          Tạo hoặc chọn một kỳ rồi quay lại đây.
        </Alert>
      ) : error ? (
        <Alert tone="error" title="Không tải được nhật ký">
          {error.message}
        </Alert>
      ) : items.length === 0 ? (
        <Alert tone="info" title="Chưa có thao tác nào">
          Khi BTC đổi trạng thái, phân bổ hoặc sửa cấu hình, dòng lịch sử sẽ hiện ở đây.
        </Alert>
      ) : (
        <>
          <ul className="flex flex-col gap-2">
            {items.map((item) => {
              const actor = item.actor_name ?? 'Hệ thống'
              return (
                <li
                  key={item.id}
                  className="flex items-start gap-3 rounded-lg border border-hairline bg-surface px-4 py-3"
                >
                  <span
                    className="grid size-8 shrink-0 place-items-center rounded-full bg-canvas-soft text-caption font-bold text-ink-secondary"
                    aria-hidden="true"
                  >
                    {item.actor_name ? initials(item.actor_name) : 'HT'}
                  </span>
                  <p className="min-w-0 flex-1 text-body-sm">
                    <b className="font-semibold text-ink">{actor}</b>{' '}
                    <span className="text-ink-secondary">
                      {(AUDIT_ACTION_LABELS[item.action] ?? item.action).toLowerCase()}
                      {item.reason && <span className="italic"> · “{item.reason}”</span>}
                    </span>
                  </p>
                  <time
                    dateTime={item.created_at}
                    title={formatDateTime(item.created_at)}
                    className="shrink-0 text-caption whitespace-nowrap text-ink-muted"
                  >
                    {formatRelative(item.created_at)}
                  </time>
                </li>
              )
            })}
          </ul>
          {pages > 1 && (
            <div className="mt-4 flex items-center justify-between gap-3">
              <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>
                Trang trước
              </Button>
              <span className="text-caption text-ink-muted">
                Trang {page}/{pages}
              </span>
              <Button
                variant="secondary"
                size="sm"
                disabled={page >= pages}
                onClick={() => setPage((value) => value + 1)}
              >
                Trang sau
              </Button>
            </div>
          )}
        </>
      )}
    </>
  )
}
