import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Eraser, LayoutGrid, Pencil, Plane, Plus, Trash2, Users, Play } from 'lucide-react'
import { useActiveEvent } from '../../hooks/useEvent'
import { useDeleteFlight, useFlights, useFlightSummary } from '../../hooks/useFlights'
import { useRegistrationFormOptions } from '../../hooks/useRegistration'
import { useToast } from '../../context/ToastContext'
import { FLIGHT_DIRECTION_LABELS } from '../../utils/constants'
import { formatShortDateTime } from '../../utils/format'
import Alert from '../../components/common/Alert'
import Badge from '../../components/common/Badge'
import Button from '../../components/common/Button'
import Card from '../../components/common/Card'
import EmptyState from '../../components/common/EmptyState'
import ExportButton from '../../components/common/ExportButton'
import Modal from '../../components/common/Modal'
import PersonLocator from '../../components/admin/PersonLocator'
import { rowClass, scrollIntoView } from '../../utils/highlight'
import { highlightTargets, usePersonLocation } from '../../hooks/usePeople'
import SlotBar from '../../components/admin/SlotBar'
import Spinner from '../../components/common/Spinner'
import AllocationPreviewModal from './flights/AllocationPreviewModal'
import CapacityPanel from './flights/CapacityPanel'
import DirectionTabs from './flights/DirectionTabs'
import FlightFormModal from './flights/FlightFormModal'
import ResetAllocationModal from './flights/ResetAllocationModal'
import PassengersModal from './flights/PassengersModal'

export default function FlightsPage() {
  const event = useActiveEvent()
  if (event.isLoading) return <Spinner label="Đang tải kỳ…" />
  if (event.error) return <Alert tone="error">{event.error.message}</Alert>
  return <FlightResources key={event.data?.id} event={event.data} />
}

function FlightResources({ event }) {
  const toast = useToast()
  const [searchParams, setSearchParams] = useSearchParams()
  const direction = searchParams.get('direction') === 'return' ? 'return' : 'outbound'
  const options = useRegistrationFormOptions()
  const { data: flights = [], isLoading, error, refetch } = useFlights()
  const summary = useFlightSummary()
  const deletion = useDeleteFlight()
  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [allocating, setAllocating] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [viewingPassengers, setViewingPassengers] = useState(null)
  const [deleting, setDeleting] = useState(null)
  const [deleteError, setDeleteError] = useState(null)
  const shifts = options.data?.shifts ?? []
  const shiftCodes = Object.fromEntries(shifts.map((s) => [s.id, s.name]))
  const rows = flights.filter((f) => f.direction === direction)
  const pending = deletion.isPending
  const closeForm = () => {
    setFormOpen(false)
    setEditing(null)
  }
  function addFlight() {
    setEditing(null)
    setFormOpen(true)
  }
  async function confirmDelete() {
    setDeleteError(null)
    try {
      await deletion.mutateAsync(deleting.id)
      toast.success(`Đã xoá chuyến ${deleting.flight_code}.`)
      setDeleting(null)
    } catch (e) {
      setDeleteError(e.message)
    }
  }
  if (allocating)
    return (
      <AllocationPreviewModal open direction={direction} onClose={() => setAllocating(false)} />
    )
  return (
    <div className="space-y-6 text-ink">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-hairline pb-4">
        <div className="flex flex-wrap items-center gap-4">
          <h1 className="text-page-title text-ink">Chuyến bay · Nguồn lực</h1>
          <DirectionTabs
            value={direction}
            event={event}
            onChange={(value) => {
              const next = new URLSearchParams(searchParams)
              next.set('direction', value)
              setSearchParams(next)
            }}
          />
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            to={`/admin/flights/board?direction=${direction}`}
            className="inline-flex min-h-11 items-center gap-2 rounded-md border border-hairline bg-surface px-4 text-caption hover:bg-canvas-soft"
          >
            <LayoutGrid className="size-4" />
            Bảng điều chỉnh
          </Link>
          <Button
            shape="pill"
            icon={Play}
            disabled={
              isLoading ||
              Boolean(error) ||
              !flights.some((f) => f.direction === direction && f.is_active)
            }
            onClick={() => setAllocating(true)}
          >
            Chạy phân bổ thử
          </Button>
        </div>
      </header>
      <div className="flex flex-wrap items-center gap-2">
        <div className="min-w-0 basis-full lg:flex-1 lg:basis-auto">
          <PersonLocator />
        </div>
        <div className="flex flex-wrap gap-2">
          <ExportButton url="/flights/export" fallbackName="danh-sach-bay.xlsx">
            Xuất danh sách bay
          </ExportButton>
          <Button variant="secondary" icon={Eraser} onClick={() => setResetting(true)}>
            Bỏ phân bổ
          </Button>
          <Button
            variant="secondary"
            icon={Plus}
            disabled={options.isLoading || Boolean(options.error)}
            onClick={addFlight}
          >
            Thêm chuyến
          </Button>
        </div>
      </div>
      {options.error && (
        <Alert tone="error" title="Không tải được danh sách ca">
          {options.error.message}
          <Button variant="ghost" onClick={() => options.refetch()}>
            Thử lại
          </Button>
        </Alert>
      )}
      {isLoading ? (
        <Spinner label="Đang tải chuyến bay…" />
      ) : error ? (
        <Alert tone="error" title="Không tải được danh sách chuyến bay">
          {error.message}
          <Button variant="ghost" onClick={() => refetch()}>
            Thử lại
          </Button>
        </Alert>
      ) : rows.length ? (
        <FlightGroup
          direction={direction}
          rows={rows}
          shiftCodes={shiftCodes}
          onEdit={(f) => {
            setEditing(f)
            setFormOpen(true)
          }}
          onDelete={(f) => {
            setDeleting(f)
            setDeleteError(null)
          }}
          onViewPassengers={setViewingPassengers}
        />
      ) : (
        <Card>
          <EmptyState
            icon={Plane}
            title="Chưa có chuyến bay cho chiều này"
            description="Thêm chuyến và số ghế để bắt đầu phân bổ."
            action={
              <Button
                variant="secondary"
                icon={Plus}
                disabled={options.isLoading || Boolean(options.error)}
                onClick={addFlight}
              >
                Thêm chuyến bay
              </Button>
            }
          />
        </Card>
      )}
      {summary.error && (
        <Alert tone="error" title="Chưa tải được tổng quan slot">
          {summary.error.message}
        </Alert>
      )}
      <CapacityPanel summary={summary.data} shiftCodes={shiftCodes} />
      <FlightFormModal
        open={formOpen}
        flight={editing}
        direction={direction}
        shifts={shifts}
        onClose={closeForm}
      />
      {resetting && (
        <ResetAllocationModal direction={direction} onClose={() => setResetting(false)} />
      )}
      {viewingPassengers && (
        <PassengersModal flight={viewingPassengers} onClose={() => setViewingPassengers(null)} />
      )}
      <Modal
        open={Boolean(deleting)}
        onClose={() => {
          if (!pending) setDeleting(null)
        }}
        title={`Xoá chuyến ${deleting?.flight_code ?? ''}?`}
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" disabled={pending} onClick={() => setDeleting(null)}>
              Không xoá
            </Button>
            <Button variant="danger" loading={pending} onClick={confirmDelete}>
              Xoá chuyến
            </Button>
          </div>
        }
      >
        <p className="text-body-sm text-ink-muted">
          Chỉ xoá được chuyến không còn hành khách và không liên kết với xe sân bay.
        </p>
        {deleteError && (
          <Alert tone="error" className="mt-4">
            {deleteError}
          </Alert>
        )}
      </Modal>
    </div>
  )
}

function FlightGroup({ direction, rows, shiftCodes, onEdit, onDelete, onViewPassengers }) {
  // Hook đọc từ URL nên gọi thẳng ở đây được, không phải luồn prop qua nhiều tầng.
  // TanStack Query gộp chung một request dù nhiều component cùng hỏi.
  const { location: locatedPerson } = usePersonLocation()
  const locatedFlights = highlightTargets(locatedPerson).flights
  const ordered = [...rows].sort((left, right) => {
    const city = cityAirport(left, direction).localeCompare(cityAirport(right, direction))
    if (city !== 0) return city
    return String(left.departure_time).localeCompare(String(right.departure_time))
  })
  const groups = groupByCity(ordered, direction)
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
        <table className="w-full text-body-sm">
          <thead>
            <tr className="border-b border-hairline text-left text-caption tracking-wide text-ink-muted uppercase">
              <th className="px-4 py-2 font-medium">Chuyến</th>
              <th className="min-w-36 px-4 py-2 font-medium">Ca</th>
              <th className="px-4 py-2 font-medium">Hành trình</th>
              <th className="px-4 py-2 font-medium">Giờ (VN)</th>
              <th className="w-44 px-4 py-2 font-medium">Ghế</th>
              <th className="px-4 py-2 font-medium" />
            </tr>
          </thead>
          <tbody className="divide-y divide-hairline">
            {groups.flatMap((group) => [
              <tr key={`city-${group.code}`} className="bg-canvas-soft">
                <td colSpan={6} className="px-4 py-2 text-eyebrow text-ink-muted">
                  {cityLabel(group.code)}
                  <span className="ml-2 font-normal normal-case tracking-normal">
                    {group.rows.length} chuyến
                  </span>
                </td>
              </tr>,
              ...group.rows.map((flight) => (
              <tr
                key={flight.id}
                ref={locatedFlights.has(flight.id) ? scrollIntoView : undefined}
                className={rowClass(flight, locatedFlights.has(flight.id))}
              >
                <td className="px-4 py-2.5">
                  <p className="font-semibold text-ink">{flight.flight_code}</p>
                  <p className="text-caption text-ink-muted">{flight.airline ?? '—'}</p>
                </td>
                <td className="px-4 py-2.5 text-ink-secondary">
                  {shiftCodes[flight.shift_id] ?? '—'}
                </td>
                <td className="px-4 py-2.5 whitespace-nowrap text-ink-secondary tabular-nums">
                  {flight.departure_airport} → {flight.arrival_airport}
                </td>
                <td className="px-4 py-2.5 whitespace-nowrap text-ink-secondary tabular-nums">
                  {formatShortDateTime(flight.departure_time)}
                  <span className="block text-caption text-ink-faint">
                    đến {formatShortDateTime(flight.arrival_time)}
                  </span>
                </td>
                <td className="px-4 py-2.5">
                  <SlotBar assigned={flight.assigned_count} usable={flight.usable_capacity} />
                  {!flight.is_active && (
                    <Badge tone="slate" className="mt-1.5">
                      Đã tắt
                    </Badge>
                  )}
                </td>
                <td className="px-2 py-2.5">
                  <RowActions
                    compact
                    flight={flight}
                    onEdit={onEdit}
                    onDelete={onDelete}
                    onViewPassengers={onViewPassengers}
                  />
                </td>
              </tr>
              )),
            ])}
          </tbody>
        </table>
      </div>

      <ul className="divide-y divide-hairline lg:hidden">
        {groups.flatMap((group) => [
          <li key={`city-${group.code}`} className="bg-canvas-soft px-4 py-2 text-eyebrow text-ink-muted">
            {cityLabel(group.code)}
          </li>,
          ...group.rows.map((flight) => (
          <li
            key={flight.id}
            ref={locatedFlights.has(flight.id) ? scrollIntoView : undefined}
            className={
              locatedFlights.has(flight.id)
                ? 'border-l-4 border-primary bg-primary/5 px-4 py-3'
                : 'px-4 py-3'
            }
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="font-semibold text-ink">
                  {flight.flight_code}
                  <span className="ml-2 text-caption font-normal text-ink-muted">
                    {shiftCodes[flight.shift_id] ?? 'chưa gán ca'}
                  </span>
                </p>
                <p className="mt-0.5 text-caption text-ink-muted tabular-nums">
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
          )),
        ])}
      </ul>
    </Card>
  )
}

const CITY_LABELS = {
  HAN: 'Hà Nội',
  SGN: 'TP. Hồ Chí Minh',
  PQC: 'Phú Quốc',
  DAD: 'Đà Nẵng',
}

function cityAirport(flight, direction) {
  return (direction === 'outbound' ? flight.departure_airport : flight.arrival_airport) || '—'
}

function cityLabel(code) {
  return CITY_LABELS[code] ? `${CITY_LABELS[code]} (${code})` : code
}

function groupByCity(rows, direction) {
  const groups = []
  for (const flight of rows) {
    const code = cityAirport(flight, direction)
    const last = groups.at(-1)
    if (!last || last.code !== code) groups.push({ code, rows: [flight] })
    else last.rows.push(flight)
  }
  return groups
}

/** `compact`: trong bảng chỉ còn icon (có nhãn cho trình đọc màn hình) để cả hàng nằm trên một dòng. */
function RowActions({ flight, onEdit, onDelete, onViewPassengers, compact = false }) {
  return (
    <div className={`flex gap-1 ${compact ? 'flex-nowrap justify-end' : 'flex-wrap'}`}>
      <Button
        variant="ghost"
        size="sm"
        icon={Users}
        onClick={() => onViewPassengers(flight)}
        title="Xem hành khách"
        aria-label={`Xem hành khách chuyến ${flight.flight_code}`}
      >
        {flight.assigned_count}
      </Button>
      <Button
        variant="ghost"
        size="sm"
        icon={Pencil}
        onClick={() => onEdit(flight)}
        title="Sửa chuyến"
        aria-label={`Sửa chuyến ${flight.flight_code}`}
      >
        {!compact && 'Sửa'}
      </Button>
      <Button
        variant="ghost"
        size="sm"
        icon={Trash2}
        className="text-accent-orange hover:bg-primary/5"
        onClick={() => onDelete(flight)}
        title="Xoá chuyến"
        aria-label={`Xoá chuyến ${flight.flight_code}`}
      >
        {!compact && 'Xoá'}
      </Button>
    </div>
  )
}
