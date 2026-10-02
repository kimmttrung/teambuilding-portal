import { useState } from 'react'
import { ArrowRightLeft, Trash2 } from 'lucide-react'
import {
  useBusAssignments,
  useMoveBusAssignment,
  useRemoveBusAssignment,
} from '../../../hooks/useBuses'
import { usePersonLocation } from '../../../hooks/usePeople'
import { scrollIntoView } from '../../../utils/highlight'
import { useToast } from '../../../context/ToastContext'
import { ASSIGNMENT_MODE_LABELS, BUS_LABELS } from '../../../utils/constants'
import { telHref } from '../../../utils/travel'
import Alert from '../../../components/common/Alert'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import EmptyState from '../../../components/common/EmptyState'
import Modal from '../../../components/common/Modal'
import ReasonDialog from '../../../components/common/ReasonDialog'
import SearchBox from '../../../components/common/SearchBox'
import Spinner from '../../../components/common/Spinner'
import BusPickerDialog from './BusPickerDialog'

/** Danh sách BTC: mobile dùng thẻ, chuyển/bỏ xếp thay modal cha để tránh chồng hộp thoại. */
export default function BusPassengersModal({ bus, buses = [], onClose }) {
  const toast = useToast()
  const query = useBusAssignments({ bus_id: bus.id, page_size: 200 })
  const move = useMoveBusAssignment()
  const remove = useRemoveBusAssignment()
  const [movingRow, setMovingRow] = useState(null)
  const [removingRow, setRemovingRow] = useState(null)
  const [search, setSearch] = useState('')
  const { location } = usePersonLocation()
  const locatedUserId = location?.user_id
  const rows = (query.data?.items ?? []).filter((row) =>
    `${row.full_name} ${row.employee_code ?? ''} ${row.team_name ?? ''}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  )

  if (movingRow)
    return (
      <BusPickerDialog
        title="Chuyển sang xe khác"
        person={movingRow}
        buses={buses}
        currentBusId={bus.id}
        pending={move.isPending}
        onClose={() => setMovingRow(null)}
        onConfirm={async ({ busId, reason }) => {
          const result = await move.mutateAsync({
            assignmentId: movingRow.id,
            busId,
            reason,
          })
          toast.success(
            `Đã chuyển ${movingRow.full_name} sang xe ${result.assignment.bus_code}.`,
          )
          result.warnings.forEach((warning) => toast.warning(warning.message))
          setMovingRow(null)
        }}
      />
    )
  if (removingRow)
    return (
      <ReasonDialog
        title={`Bỏ xếp xe của ${removingRow.full_name}?`}
        description={`Xe ${bus.bus_code} · ${bus.trip_leg_name}`}
        confirmLabel={BUS_LABELS.remove}
        pending={remove.isPending}
        onClose={() => setRemovingRow(null)}
        onConfirm={async (reason) => {
          await remove.mutateAsync({ assignmentId: removingRow.id, reason })
          toast.success(`Đã bỏ xếp xe của ${removingRow.full_name}.`)
          setRemovingRow(null)
        }}
      >
        <p className="text-caption text-ink-muted">
          Nhu cầu xe và điểm đón vẫn được giữ. Lần phân xe tự động sau có thể
          xếp lại người này.
        </p>
      </ReasonDialog>
    )

  function actions(row) {
    return (
      <div className="flex flex-wrap gap-1">
        <Button
          variant="secondary"
          size="sm"
          className="min-h-11"
          icon={ArrowRightLeft}
          onClick={() => setMovingRow(row)}
        >
          {BUS_LABELS.move}
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="min-h-11 min-w-11"
          icon={Trash2}
          aria-label={`Bỏ xếp xe của ${row.full_name}`}
          onClick={() => setRemovingRow(row)}
        />
      </div>
    )
  }
  function details(row) {
    return (
      <>
        <p className="text-caption text-ink-muted">
          {[row.pickup_point_name, row.flight_code]
            .filter(Boolean)
            .join(' · ') || 'Chưa có điểm đón'}
        </p>
        {row.phone && (
          <a
            href={telHref(row.phone)}
            className="inline-flex min-h-11 items-center text-caption text-primary"
          >
            {row.phone}
          </a>
        )}
        <Badge tone={row.assignment_mode === 'manual' ? 'brand' : 'slate'}>
          {ASSIGNMENT_MODE_LABELS[row.assignment_mode]}
        </Badge>
        {(row.pickup_mismatch || row.flight_mismatch) && (
          <p className="mt-1 text-caption text-accent-orange">
            {row.pickup_mismatch ? 'Lệch điểm đón' : ''}
            {row.pickup_mismatch && row.flight_mismatch ? ' · ' : ''}
            {row.flight_mismatch ? 'Lệch chuyến bay' : ''}
          </p>
        )}
      </>
    )
  }
  return (
    <Modal
      open
      size="lg"
      onClose={onClose}
      title={`Hành khách xe ${bus.bus_code}`}
      description={`${bus.assigned_count}/${bus.capacity} chỗ · ${bus.trip_leg_name}`}
    >
      <div className="flex flex-col gap-4">
        <SearchBox
          label={BUS_LABELS.search}
          placeholder="Tên, mã nhân viên, team"
          onSearch={setSearch}
        />
        {query.isLoading && <Spinner label="Đang tải danh sách…" />}
        {query.error && (
          <Alert tone="error">
            {query.error.message}
            <Button variant="secondary" onClick={() => query.refetch()}>
              {BUS_LABELS.retry}
            </Button>
          </Alert>
        )}
        {query.data && !rows.length && (
          <EmptyState
            title={
              search ? 'Không tìm thấy hành khách' : 'Chưa có ai trên xe này'
            }
            description={
              search
                ? 'Thử tên hoặc team khác.'
                : 'Xếp tự động hoặc xếp tay từ danh sách Chưa có xe.'
            }
          />
        )}
        <ul className="divide-y divide-hairline sm:hidden">
          {rows.map((row) => (
            <li key={row.id} className="py-4">
              <p className="text-body-sm font-semibold">{row.full_name}</p>
              <p className="mt-1 text-caption text-ink-muted">
                {row.team_name ?? 'Chưa có team'}
              </p>
              <div className="mt-2 flex flex-col items-start gap-1">
                {details(row)}
              </div>
              <div className="mt-3">{actions(row)}</div>
            </li>
          ))}
        </ul>
        {rows.length > 0 && (
          <table className="hidden w-full text-left text-body-sm sm:table">
            <thead className="border-b border-hairline text-caption text-ink-muted">
              <tr>
                <th className="pb-3 pr-3 font-medium">Người / Team</th>
                <th className="pb-3 pr-3 font-medium">Điểm đón / Chuyến bay</th>
                <th className="pb-3 font-medium">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-hairline">
              {rows.map((row) => (
                <tr
                  key={row.id}
                  ref={
                    row.user_id === locatedUserId ? scrollIntoView : undefined
                  }
                  className={
                    row.user_id === locatedUserId
                      ? 'bg-primary/5 align-top'
                      : 'align-top'
                  }
                >
                  <td className="py-3 pr-3">
                    <p className="font-semibold">{row.full_name}</p>
                    <p className="mt-1 text-caption text-ink-muted">
                      {row.team_name ?? 'Chưa có team'}
                    </p>
                    {row.employee_code && (
                      <p className="text-caption text-ink-faint">
                        {row.employee_code}
                      </p>
                    )}
                  </td>
                  <td className="py-3 pr-3">
                    <div className="flex flex-col items-start gap-1">
                      {details(row)}
                    </div>
                  </td>
                  <td className="py-3">{actions(row)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </Modal>
  )
}
