import { useBusPassengers } from '../../../hooks/useBuses'
import Alert from '../../../components/common/Alert'
import EmptyState from '../../../components/common/EmptyState'
import Modal from '../../../components/common/Modal'
import Spinner from '../../../components/common/Spinner'
import { PhoneLink } from './TravelLinks'

/**
 * Danh sách hành khách cho **Trưởng xe**, mở từ My Journey.
 *
 * Khác bản của BTC (`pages/admin/buses/BusPassengersModal`): chỉ đọc, không có chuyển xe hay
 * bỏ xếp — đó là quyền của BTC. Chỉ tên, SĐT bấm gọi, điểm đón, team: đủ để điểm danh và gọi
 * người đến muộn, không hiện CCCD hay ngày sinh (docs/09 §4).
 *
 * Trên điện thoại (nơi màn hình này thực sự được dùng, lúc 4 giờ sáng ở điểm đón) hiện dạng
 * danh sách; từ sm trở lên mới là bảng.
 */
export default function BusPassengersModal({ bus, onClose }) {
  const { data: passengers, isLoading, error } = useBusPassengers(bus?.bus_id)

  if (!bus) return null

  const rows = passengers ?? []
  const withoutPhone = rows.filter((row) => !row.phone).length

  return (
    <Modal
      open
      size="lg"
      onClose={onClose}
      title={`Hành khách xe ${bus.bus_code}`}
      description={`${bus.trip_leg.name} · ${rows.length}/${bus.capacity} chỗ · sắp theo team rồi tên`}
    >
      {isLoading && <Spinner label="Đang tải danh sách…" />}
      {error && <Alert tone="error">{error.message}</Alert>}

      {passengers && rows.length === 0 && (
        <EmptyState
          title="Chưa có ai trên xe này"
          description="Ban tổ chức chưa xếp hành khách vào xe bạn phụ trách."
        />
      )}

      {withoutPhone > 0 && (
        <Alert tone="warning" className="mb-3" title={`${withoutPhone} người chưa có số điện thoại`}>
          Không gọi được nếu họ đến muộn — báo Ban tổ chức bổ sung giúp.
        </Alert>
      )}

      {rows.length > 0 && (
        <ul className="flex flex-col divide-y divide-slate-100">
          {rows.map((row, index) => (
            <li
              key={row.assignment_id}
              className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2 py-2.5"
            >
              <div className="flex min-w-0 items-start gap-3">
                <span className="w-6 shrink-0 pt-0.5 text-right text-xs text-slate-400 tabular-nums">
                  {index + 1}
                </span>
                <div className="min-w-0">
                  <p className="truncate font-medium text-slate-900">{row.full_name}</p>
                  <p className="truncate text-xs text-slate-500">
                    {[row.team_name, row.pickup_point_name, row.flight_code]
                      .filter(Boolean)
                      .join(' · ') || '—'}
                  </p>
                </div>
              </div>
              {row.phone ? (
                <PhoneLink phone={row.phone} />
              ) : (
                <span className="text-xs text-slate-400">Chưa có SĐT</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </Modal>
  )
}
