import { AlertTriangle } from 'lucide-react'
import { usePassengers } from '../../../hooks/useFlights'
import { usePersonLocation } from '../../../hooks/usePeople'
import { scrollIntoView } from '../../../utils/highlight'
import { ASSIGNMENT_MODE_LABELS } from '../../../utils/constants'
import Alert from '../../../components/common/Alert'
import Badge from '../../../components/common/Badge'
import EmptyState from '../../../components/common/EmptyState'
import Modal from '../../../components/common/Modal'
import Spinner from '../../../components/common/Spinner'

/** Danh sách hành khách của một chuyến — BTC in ra để điểm danh ở sân bay. */
export default function PassengersModal({ flight, onClose }) {
  const { data: passengers, isLoading, error } = usePassengers(flight?.id, {
    enabled: Boolean(flight),
  })
  // Người đang tra cứu ngồi chuyến này thì tô đỏ dòng tên họ. Hook phải đứng TRƯỚC `return null` bên
  // dưới — đặt sau thì lúc `flight` đổi từ null sang có, React thấy thêm một hook và gỡ cả trang.
  const { location: locatedPerson } = usePersonLocation()
  const locatedUserId = locatedPerson?.user_id ?? null

  if (!flight) return null

  const missingDocuments = (passengers ?? []).filter((row) => !row.has_flight_documents)

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={`Hành khách chuyến ${flight.flight_code}`}
      description={`${flight.assigned_count}/${flight.usable_capacity} ghế dùng được · sắp theo team`}
    >
      {isLoading && <Spinner label="Đang tải danh sách…" />}
      {error && <Alert tone="error">{error.message}</Alert>}

      {passengers && passengers.length === 0 && (
        <EmptyState
          title="Chưa có ai trên chuyến này"
          description="Chạy phân bổ tự động hoặc xếp tay ở bảng điều chỉnh."
        />
      )}

      {missingDocuments.length > 0 && (
        <Alert tone="warning" className="mb-3" title="Có người chưa xuất được vé">
          {missingDocuments.length} người thiếu CCCD hoặc ngày sinh. Nhắc họ bổ sung trước khi
          đặt vé.
        </Alert>
      )}

      {passengers && passengers.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[520px] text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs tracking-wide text-slate-500 uppercase">
                <th className="py-2 pr-3 font-medium">Họ tên</th>
                <th className="py-2 pr-3 font-medium">Mã NV</th>
                <th className="py-2 pr-3 font-medium">Team</th>
                <th className="py-2 pr-3 font-medium">Ca xin</th>
                <th className="py-2 font-medium">Nguồn</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {passengers.map((row) => (
                <tr
                  key={row.assignment_id}
                  ref={row.user_id === locatedUserId ? scrollIntoView : undefined}
                  className={row.user_id === locatedUserId ? 'bg-rose-50 outline outline-2 -outline-offset-2 outline-rose-500' : undefined}
                >
                  <td className="py-2 pr-3">
                    <span className="inline-flex items-center gap-1.5 font-medium text-slate-900">
                      {row.full_name}
                      {!row.has_flight_documents && (
                        <AlertTriangle
                          className="size-3.5 text-amber-600"
                          aria-label="Thiếu giấy tờ bay"
                        />
                      )}
                    </span>
                  </td>
                  <td className="py-2 pr-3 text-slate-500 tabular-nums">
                    {row.employee_code ?? '—'}
                  </td>
                  <td className="py-2 pr-3 text-slate-600">{row.team_name ?? '—'}</td>
                  <td className="py-2 pr-3 text-slate-500">{row.requested_shift_code ?? '—'}</td>
                  <td className="py-2">
                    <Badge tone={row.assignment_mode === 'manual' ? 'brand' : 'slate'}>
                      {ASSIGNMENT_MODE_LABELS[row.assignment_mode] ?? row.assignment_mode}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Modal>
  )
}
