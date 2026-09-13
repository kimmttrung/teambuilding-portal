import { useState } from 'react'
import { AlertTriangle, ArrowRightLeft, Trash2 } from 'lucide-react'
import { useBusAssignments, useMoveBusAssignment, useRemoveBusAssignment } from '../../../hooks/useBuses'
import { useToast } from '../../../context/ToastContext'
import { ASSIGNMENT_MODE_LABELS } from '../../../utils/constants'
import { telHref } from '../../../utils/travel'
import Alert from '../../../components/common/Alert'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import EmptyState from '../../../components/common/EmptyState'
import Modal from '../../../components/common/Modal'
import Spinner from '../../../components/common/Spinner'
import Textarea from '../../../components/common/Textarea'
import BusPickerDialog from './BusPickerDialog'

/**
 * Hành khách một xe, kèm chuyển xe và bỏ xếp.
 *
 * Hộp thoại con thay chỗ hộp thoại này (không chồng hai modal): Esc đóng đúng một lớp, và
 * trên điện thoại không có hai tấm phủ đè nhau.
 */
export default function BusPassengersModal({ bus, buses = [], onClose }) {
  const toast = useToast()
  const { data, isLoading, error } = useBusAssignments({ bus_id: bus.id, page_size: 200 })
  const { mutateAsync: move, isPending: moving } = useMoveBusAssignment()
  const { mutateAsync: remove, isPending: removing } = useRemoveBusAssignment()

  const [movingRow, setMovingRow] = useState(null)
  const [removingRow, setRemovingRow] = useState(null)
  const [removeReason, setRemoveReason] = useState('')

  if (movingRow) {
    return (
      <BusPickerDialog
        title="Chuyển sang xe khác"
        person={movingRow}
        buses={buses}
        currentBusId={bus.id}
        pending={moving}
        onClose={() => setMovingRow(null)}
        onConfirm={async ({ busId, reason }) => {
          try {
            const result = await move({ assignmentId: movingRow.id, busId, reason })
            toast.success(`Đã chuyển ${movingRow.full_name} sang xe ${result.assignment.bus_code}.`)
            result.warnings.forEach((warning) => toast.warning(warning.message))
            setMovingRow(null)
          } catch (moveError) {
            toast.error(moveError.message)
          }
        }}
      />
    )
  }

  if (removingRow) {
    const closeRemove = () => setRemovingRow(null)
    return (
      <Modal
        open
        onClose={closeRemove}
        title={`Bỏ xếp xe của ${removingRow.full_name}?`}
        description={`Xe ${bus.bus_code} · ${bus.trip_leg_name}`}
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" size="sm" onClick={closeRemove}>
              Không bỏ
            </Button>
            <Button
              variant="danger"
              size="sm"
              icon={Trash2}
              loading={removing}
              disabled={removeReason.trim().length < 3 || removing}
              onClick={async () => {
                try {
                  await remove({ assignmentId: removingRow.id, reason: removeReason.trim() })
                  toast.success(`Đã bỏ xếp xe của ${removingRow.full_name}.`)
                  closeRemove()
                } catch (removeError) {
                  toast.error(removeError.message)
                }
              }}
            >
              Bỏ xếp xe
            </Button>
          </div>
        }
      >
        <div className="flex flex-col gap-3">
          <p className="text-sm text-slate-700">
            Người này vẫn đăng ký cần xe, nên lần chạy phân xe tự động sau sẽ xếp lại. Muốn họ không đi
            xe hẳn thì CBNV cần bỏ nhu cầu xe trong đăng ký.
          </p>
          <Textarea
            label="Lý do"
            required
            rows={2}
            maxLength={500}
            value={removeReason}
            counterValue={removeReason}
            onChange={(changeEvent) => setRemoveReason(changeEvent.target.value)}
            hint="Lưu vào nhật ký thay đổi, tối thiểu 3 ký tự"
          />
        </div>
      </Modal>
    )
  }

  const rows = data?.items ?? []
  const mismatches = rows.filter((row) => row.pickup_mismatch || row.flight_mismatch).length

  return (
    <Modal
      open
      size="lg"
      onClose={onClose}
      title={`Hành khách xe ${bus.bus_code}`}
      description={`${bus.assigned_count}/${bus.capacity} chỗ · ${bus.trip_leg_name} · sắp theo xe rồi tên`}
    >
      {isLoading && <Spinner label="Đang tải danh sách…" />}
      {error && <Alert tone="error">{error.message}</Alert>}

      {data && rows.length === 0 && (
        <EmptyState
          title="Chưa có ai trên xe này"
          description="Chạy phân xe tự động hoặc xếp tay từ danh sách Chưa có xe."
        />
      )}

      {mismatches > 0 && (
        <Alert tone="warning" className="mb-3" title={`${mismatches} người lệch điểm đón hoặc chuyến bay`}>
          Xe này đón ở điểm khác, hoặc chờ chuyến bay khác với những người được đánh dấu. Chuyển xe hoặc
          báo lại giờ tập trung cho họ.
        </Alert>
      )}

      {rows.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs tracking-wide text-slate-500 uppercase">
                <th className="py-2 pr-3 font-medium">Họ tên</th>
                <th className="py-2 pr-3 font-medium">Team</th>
                <th className="py-2 pr-3 font-medium">Điện thoại</th>
                <th className="py-2 pr-3 font-medium">Điểm đón</th>
                <th className="py-2 pr-3 font-medium">Chuyến bay</th>
                <th className="py-2 pr-3 font-medium">Nguồn</th>
                <th className="py-2 text-right font-medium">
                  <span className="sr-only">Thao tác</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((row) => (
                <tr key={row.id} className="align-top">
                  <td className="py-2 pr-3">
                    <p className="font-medium text-slate-900">{row.full_name}</p>
                    {row.employee_code && <p className="text-xs text-slate-500 tabular-nums">{row.employee_code}</p>}
                  </td>
                  <td className="py-2 pr-3 text-slate-600">{row.team_name ?? '—'}</td>
                  <td className="py-2 pr-3 tabular-nums">
                    {row.phone ? (
                      <a href={telHref(row.phone)} className="text-brand-700 hover:underline">
                        {row.phone}
                      </a>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td className="py-2 pr-3 text-slate-600">
                    {row.pickup_point_name ?? '—'}
                    {row.pickup_mismatch && <MismatchIcon label="Xe đón ở điểm khác" />}
                  </td>
                  <td className="py-2 pr-3 text-slate-600">
                    {row.flight_code ?? '—'}
                    {row.flight_mismatch && <MismatchIcon label="Xe chờ chuyến bay khác" />}
                  </td>
                  <td className="py-2 pr-3">
                    <Badge tone={row.assignment_mode === 'manual' ? 'brand' : 'slate'}>
                      {ASSIGNMENT_MODE_LABELS[row.assignment_mode] ?? row.assignment_mode}
                    </Badge>
                  </td>
                  <td className="py-2">
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" size="sm" icon={ArrowRightLeft} onClick={() => setMovingRow(row)}>
                        Chuyển
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        icon={Trash2}
                        aria-label={`Bỏ xếp xe của ${row.full_name}`}
                        onClick={() => {
                          setRemoveReason('')
                          setRemovingRow(row)
                        }}
                      />
                    </div>
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

function MismatchIcon({ label }) {
  return (
    <AlertTriangle className="ml-1 inline size-3.5 text-amber-600" aria-label={label}>
      <title>{label}</title>
    </AlertTriangle>
  )
}
