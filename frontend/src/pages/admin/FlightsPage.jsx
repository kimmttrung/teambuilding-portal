import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  LayoutGrid,
  Pencil,
  Plane,
  Plus,
  Trash2,
  Users,
  Wand2,
} from 'lucide-react'
import { useActiveEvent } from '../../hooks/useEvent'
import { useDeleteFlight, useFlights, useFlightSummary } from '../../hooks/useFlights'
import { useRegistrationFormOptions } from '../../hooks/useRegistration'
import { useToast } from '../../context/ToastContext'
import { EVENT_STATUS_META, FLIGHT_DIRECTION_LABELS } from '../../utils/constants'
import { formatShortDateTime } from '../../utils/format'
import Alert from '../../components/common/Alert'
import Badge from '../../components/common/Badge'
import Button from '../../components/common/Button'
import Card from '../../components/common/Card'
import EmptyState from '../../components/common/EmptyState'
import ExportButton from '../../components/common/ExportButton'
import Modal from '../../components/common/Modal'
import PageHeader from '../../components/common/PageHeader'
import SlotBar from '../../components/admin/SlotBar'
import Spinner from '../../components/common/Spinner'
import AllocationPreviewModal from './flights/AllocationPreviewModal'
import CapacityPanel from './flights/CapacityPanel'
import FlightFormModal from './flights/FlightFormModal'
import PassengersModal from './flights/PassengersModal'

/**
 * Quản lý chuyến bay: bảng slot, thêm/sửa/xoá, và cửa vào phân bổ tự động.
 *
 * Giờ hiển thị theo giờ Việt Nam (backend lưu UTC). Số liệu slot lấy từ API, không tự
 * tính lại ở client — chỉ có một nơi biết cách đếm ghế còn trống.
 */
export default function FlightsPage() {
  const toast = useToast()
  const { data: event } = useActiveEvent()
  const { data: options } = useRegistrationFormOptions()
  const { data: flights, isLoading, error } = useFlights()
  const { data: summary } = useFlightSummary()
  const { mutateAsync: removeFlight, isPending: isDeleting } = useDeleteFlight()

  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [allocating, setAllocating] = useState(false)
  const [viewingPassengers, setViewingPassengers] = useState(null)
  const [deleting, setDeleting] = useState(null)

  const shifts = options?.shifts ?? []
  const shiftCodes = Object.fromEntries(shifts.map((shift) => [shift.id, shift.name]))

  if (isLoading) return <Spinner label="Đang tải chuyến bay…" />
  if (error) {
    return (
      <Alert tone="error" title="Không tải được danh sách chuyến bay">
        {error.message}
      </Alert>
    )
  }

  const statusMeta = event ? EVENT_STATUS_META[event.status] : null
  const byDirection = Object.keys(FLIGHT_DIRECTION_LABELS).map((direction) => ({
    direction,
    rows: flights.filter((flight) => flight.direction === direction),
  }))

  async function confirmDelete() {
    try {
      await removeFlight(deleting.id)
      toast.success(`Đã xoá chuyến ${deleting.flight_code}.`)
      setDeleting(null)
    } catch (deleteError) {
      toast.error(deleteError.message)
    }
  }

  return (
    <>
      <PageHeader
        title="Quản lý chuyến bay"
        description={event ? `${event.name} · ${statusMeta?.label ?? event.status}` : undefined}
        action={
          <div className="flex flex-wrap gap-2">
            <Link to="/admin/flights/board">
              <Button variant="secondary" icon={LayoutGrid}>
                Bảng điều chỉnh
              </Button>
            </Link>
            <ExportButton
              url="/flights/export"
              fallbackName="danh-sach-bay.xlsx"
              title="Danh sách hành khách theo chuyến, có ngày sinh và số giấy tờ — mỗi lần tải được ghi nhật ký"
            >
              Xuất danh sách bay
            </ExportButton>
            <Button variant="secondary" icon={Plus} onClick={() => {
              setEditing(null)
              setFormOpen(true)
            }}>
              Thêm chuyến
            </Button>
            <Button icon={Wand2} onClick={() => setAllocating(true)}>
              Phân bổ tự động
            </Button>
          </div>
        }
      />

      <div className="flex flex-col gap-4">
        <div className="grid gap-4 xl:grid-cols-12">
          <div className="flex flex-col gap-4 xl:col-span-8">
            {flights.length === 0 && (
              <Card>
                <EmptyState
                  icon={Plane}
                  title="Chưa có chuyến bay nào"
                  description="Thêm các chuyến BTC đã mua slot, rồi chạy phân bổ tự động."
                  action={
                    <Button icon={Plus} onClick={() => setFormOpen(true)}>
                      Thêm chuyến bay
                    </Button>
                  }
                />
              </Card>
            )}

            {byDirection.map(({ direction, rows }) =>
              rows.length ? (
                <FlightGroup
                  key={direction}
                  direction={direction}
                  rows={rows}
                  shiftCodes={shiftCodes}
                  onEdit={(flight) => {
                    setEditing(flight)
                    setFormOpen(true)
                  }}
                  onDelete={setDeleting}
                  onViewPassengers={setViewingPassengers}
                />
              ) : null,
            )}
          </div>

          <aside className="flex flex-col gap-4 xl:col-span-4">
            <CapacityPanel summary={summary} shiftCodes={shiftCodes} />

            <Card title="Thứ tự làm việc">
              <ol className="flex flex-col gap-2 text-sm text-slate-600">
                <li>1. Khai đủ chuyến bay hai chiều, đúng ca.</li>
                <li>2. Kiểm phần slot bên trên: thiếu ghế thì mua thêm hoặc mở chuyến.</li>
                <li>3. Bấm <strong>Phân bổ tự động</strong> → xem trước → áp dụng.</li>
                <li>
                  4. Sửa các trường hợp đặc biệt ở{' '}
                  <Link to="/admin/flights/board" className="font-medium text-brand-700 hover:underline">
                    bảng điều chỉnh
                  </Link>
                  .
                </li>
                <li>5. Đổi trạng thái kỳ sang "đã công bố" để CBNV xem được.</li>
              </ol>
            </Card>
          </aside>
        </div>
      </div>

      <FlightFormModal
        open={formOpen}
        flight={editing}
        shifts={shifts}
        onClose={() => {
          setFormOpen(false)
          setEditing(null)
        }}
      />

      {allocating && (
        <AllocationPreviewModal
          open
          shiftCodes={shiftCodes}
          onClose={() => setAllocating(false)}
        />
      )}

      {viewingPassengers && (
        <PassengersModal
          flight={viewingPassengers}
          onClose={() => setViewingPassengers(null)}
        />
      )}

      <Modal
        open={Boolean(deleting)}
        onClose={() => setDeleting(null)}
        title={`Xoá chuyến ${deleting?.flight_code ?? ''}?`}
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" size="sm" onClick={() => setDeleting(null)}>
              Không xoá
            </Button>
            <Button
              variant="danger"
              size="sm"
              icon={Trash2}
              loading={isDeleting}
              onClick={confirmDelete}
            >
              Xoá chuyến
            </Button>
          </div>
        }
      >
        <p className="text-sm text-slate-600">
          Chuyến {deleting?.flight_code} ({deleting?.departure_airport} →{' '}
          {deleting?.arrival_airport}) sẽ bị xoá khỏi kỳ này.
        </p>
        {deleting?.assigned_count > 0 && (
          <Alert tone="warning" className="mt-3">
            Chuyến còn {deleting.assigned_count} hành khách nên hệ thống sẽ chặn. Chuyển họ sang
            chuyến khác ở bảng điều chỉnh trước.
          </Alert>
        )}
      </Modal>
    </>
  )
}

/* --- Một chiều bay: bảng trên màn hình rộng, danh sách thẻ trên điện thoại --- */
function FlightGroup({ direction, rows, shiftCodes, onEdit, onDelete, onViewPassengers }) {
  const totals = rows.reduce(
    (accumulator, flight) => ({
      usable: accumulator.usable + flight.usable_capacity,
      assigned: accumulator.assigned + flight.assigned_count,
    }),
    { usable: 0, assigned: 0 },
  )

  return (
    <Card
      title={FLIGHT_DIRECTION_LABELS[direction]}
      description={`${rows.length} chuyến · đã xếp ${totals.assigned}/${totals.usable} ghế dùng được`}
      bodyClassName="p-0"
    >
      {/* Bảng: chỉ từ lg trở lên, dưới đó chuyển sang thẻ (docs/07-frontend.md §5) */}
      <div className="hidden overflow-x-auto lg:block">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs tracking-wide text-slate-500 uppercase">
              <th className="px-4 py-2 font-medium">Chuyến</th>
              <th className="px-4 py-2 font-medium">Ca</th>
              <th className="px-4 py-2 font-medium">Hành trình</th>
              <th className="px-4 py-2 font-medium">Giờ (VN)</th>
              <th className="w-44 px-4 py-2 font-medium">Ghế</th>
              <th className="px-4 py-2 font-medium" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((flight) => (
              <tr key={flight.id} className={flight.is_active ? '' : 'bg-slate-50/70'}>
                <td className="px-4 py-2.5">
                  <p className="font-semibold text-slate-900">{flight.flight_code}</p>
                  <p className="text-xs text-slate-500">{flight.airline ?? '—'}</p>
                </td>
                <td className="px-4 py-2.5 text-slate-600">
                  {shiftCodes[flight.shift_id] ?? '—'}
                </td>
                <td className="px-4 py-2.5 text-slate-600 tabular-nums">
                  {flight.departure_airport} → {flight.arrival_airport}
                </td>
                <td className="px-4 py-2.5 text-slate-600 tabular-nums">
                  {formatShortDateTime(flight.departure_time)}
                  <span className="text-slate-400"> → </span>
                  {formatShortDateTime(flight.arrival_time)}
                </td>
                <td className="px-4 py-2.5">
                  <SlotBar assigned={flight.assigned_count} usable={flight.usable_capacity} />
                  {!flight.is_active && (
                    <Badge tone="slate" className="mt-1.5">
                      Đã tắt
                    </Badge>
                  )}
                </td>
                <td className="px-4 py-2.5">
                  <RowActions
                    flight={flight}
                    onEdit={onEdit}
                    onDelete={onDelete}
                    onViewPassengers={onViewPassengers}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ul className="divide-y divide-slate-100 lg:hidden">
        {rows.map((flight) => (
          <li key={flight.id} className="px-4 py-3">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="font-semibold text-slate-900">
                  {flight.flight_code}
                  <span className="ml-2 text-xs font-normal text-slate-500">
                    {shiftCodes[flight.shift_id] ?? 'chưa gán ca'}
                  </span>
                </p>
                <p className="mt-0.5 text-xs text-slate-500 tabular-nums">
                  {flight.departure_airport} → {flight.arrival_airport} ·{' '}
                  {formatShortDateTime(flight.departure_time)}
                </p>
              </div>
              {!flight.is_active && <Badge tone="slate">Đã tắt</Badge>}
            </div>
            <SlotBar
              assigned={flight.assigned_count}
              usable={flight.usable_capacity}
              className="mt-2"
            />
            <div className="mt-2.5">
              <RowActions
                flight={flight}
                onEdit={onEdit}
                onDelete={onDelete}
                onViewPassengers={onViewPassengers}
              />
            </div>
          </li>
        ))}
      </ul>
    </Card>
  )
}

function RowActions({ flight, onEdit, onDelete, onViewPassengers }) {
  return (
    <div className="flex flex-wrap gap-1">
      <Button
        variant="ghost"
        size="sm"
        icon={Users}
        onClick={() => onViewPassengers(flight)}
        title="Xem hành khách"
      >
        {flight.assigned_count}
      </Button>
      <Button variant="ghost" size="sm" icon={Pencil} onClick={() => onEdit(flight)}>
        Sửa
      </Button>
      <Button
        variant="ghost"
        size="sm"
        icon={Trash2}
        className="text-rose-600 hover:bg-rose-50"
        onClick={() => onDelete(flight)}
      >
        Xoá
      </Button>
    </div>
  )
}
