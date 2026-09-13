import { useState } from 'react'
import { ArrowRight } from 'lucide-react'
import Alert from '../../../components/common/Alert'
import Button from '../../../components/common/Button'
import Modal from '../../../components/common/Modal'
import Select from '../../../components/common/Select'
import Textarea from '../../../components/common/Textarea'

/**
 * Chọn xe cho một người — dùng chung cho "xếp xe" (người chưa có xe) và "chuyển xe".
 *
 * Chỉ liệt kê xe cùng chặng còn chỗ. Xe đón ở điểm khác vẫn chọn được (BTC có quyền quyết
 * ngoại lệ) nhưng cảnh báo ngay tại chỗ. Lý do bắt buộc vì được ghi vào nhật ký thay đổi.
 */
export default function BusPickerDialog({
  title,
  person,
  buses = [],
  currentBusId = null,
  pending = false,
  onConfirm,
  onClose,
}) {
  const [busId, setBusId] = useState('')
  const [reason, setReason] = useState('')

  const options = buses.filter((bus) => bus.id !== currentBusId && bus.remaining_seats > 0)
  const chosen = options.find((bus) => String(bus.id) === busId) ?? null
  const pickupMismatch = Boolean(
    chosen &&
      person.pickup_point_id &&
      chosen.pickup_point_id &&
      chosen.pickup_point_id !== person.pickup_point_id,
  )
  const canSubmit = Boolean(chosen) && reason.trim().length >= 3 && !pending

  return (
    <Modal
      open
      onClose={onClose}
      title={title}
      description={[person.full_name, person.team_name].filter(Boolean).join(' · ')}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="sm" onClick={onClose}>
            Huỷ
          </Button>
          <Button
            size="sm"
            icon={ArrowRight}
            loading={pending}
            disabled={!canSubmit}
            onClick={() => onConfirm({ busId: Number(chosen.id), reason: reason.trim() })}
          >
            Xác nhận
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-3.5">
        {options.length === 0 ? (
          <Alert tone="warning" title="Không còn xe trống">
            Mọi xe khác của chặng này đã đủ chỗ. Thêm xe hoặc tăng số chỗ trước.
          </Alert>
        ) : (
          <Select
            label="Xe"
            required
            placeholder="— Chọn xe —"
            value={busId}
            onChange={(changeEvent) => setBusId(changeEvent.target.value)}
            options={options.map((bus) => ({
              value: String(bus.id),
              label: `${bus.bus_code} — còn ${bus.remaining_seats} chỗ${
                bus.pickup_point_name ? ` · đón ${bus.pickup_point_name}` : ''
              }`,
            }))}
          />
        )}

        {person.pickup_point_name && (
          <p className="text-sm text-slate-600">
            Điểm đón người này chọn: <strong className="text-slate-900">{person.pickup_point_name}</strong>
          </p>
        )}

        {pickupMismatch && (
          <Alert tone="warning">
            Xe {chosen.bus_code} đón ở {chosen.pickup_point_name}, khác điểm đón người này chọn. Vẫn xếp
            được — nhớ báo lại cho họ.
          </Alert>
        )}

        <Textarea
          label="Lý do"
          required
          rows={2}
          maxLength={500}
          value={reason}
          counterValue={reason}
          onChange={(changeEvent) => setReason(changeEvent.target.value)}
          placeholder="Ví dụ: đi cùng người nhà, đổi điểm đón theo yêu cầu…"
          hint="Lưu vào nhật ký thay đổi, tối thiểu 3 ký tự"
        />
      </div>
    </Modal>
  )
}
