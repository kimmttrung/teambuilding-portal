import { useState } from 'react'
import { ArrowRight } from 'lucide-react'
import Alert from '../../../components/common/Alert'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Modal from '../../../components/common/Modal'
import Select from '../../../components/common/Select'
import Textarea from '../../../components/common/Textarea'

/**
 * Hộp thoại xác nhận chuyển người sang chuyến khác.
 *
 * Lý do là bắt buộc (backend đòi tối thiểu 3 ký tự): sáu tháng sau, khi CBNV hỏi "vì sao
 * tôi bị đổi chuyến", audit log phải trả lời được. Đây cũng là đường dùng được trên điện
 * thoại — kéo-thả HTML5 không hoạt động trên cảm ứng.
 */
export default function MoveDialog(props) {
  // Chỉ dựng nội dung khi mở: mỗi lần mở là một form mới tinh, không cần effect để xoá
  // lý do và chuyến đã chọn của lần trước.
  if (!props.open) return null
  return <MoveDialogBody {...props} />
}

function MoveDialogBody({
  onClose,
  onConfirm,
  people = [],
  sourceLabel,
  targetFlight,
  flightOptions = [],
  pending = false,
  warnings = [],
}) {
  const [reason, setReason] = useState('')
  const [flightId, setFlightId] = useState(targetFlight?.id ? String(targetFlight.id) : '')

  const chosen =
    targetFlight ?? flightOptions.find((flight) => String(flight.id) === flightId) ?? null
  const remaining = chosen ? chosen.remaining_slots : null
  const tooMany = remaining !== null && people.length > remaining
  const canSubmit = reason.trim().length >= 3 && chosen && !tooMany

  return (
    <Modal
      open
      onClose={onClose}
      title={people.length > 1 ? `Chuyển ${people.length} người` : 'Chuyển hành khách'}
      description={sourceLabel ? `Đang ở: ${sourceLabel}` : undefined}
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
            onClick={() =>
              onConfirm({
                flightId: Number(chosen.id),
                reason: reason.trim(),
                registrationIds: people.map((person) => person.registration_id),
              })
            }
          >
            Chuyển
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-3.5">
        {!targetFlight && (
          <Select
            label="Chuyển sang chuyến"
            required
            placeholder="— Chọn chuyến —"
            value={flightId}
            onChange={(event) => setFlightId(event.target.value)}
            options={flightOptions.map((flight) => ({
              value: String(flight.id),
              label: `${flight.flight_code} — còn ${flight.remaining_slots} chỗ`,
            }))}
          />
        )}

        {targetFlight && (
          <p className="text-sm text-slate-600">
            Chuyển sang <strong className="text-slate-900">{targetFlight.flight_code}</strong>{' '}
            <span className="text-slate-500">(còn {targetFlight.remaining_slots} chỗ)</span>
          </p>
        )}

        <div>
          <p className="mb-1.5 text-sm font-medium text-slate-700">
            Người được chuyển ({people.length})
          </p>
          <ul className="flex max-h-40 flex-wrap gap-1.5 overflow-y-auto">
            {people.map((person) => (
              <li key={person.registration_id}>
                <Badge tone="slate">{person.full_name}</Badge>
              </li>
            ))}
          </ul>
        </div>

        {tooMany && (
          <Alert tone="error" title="Không đủ chỗ">
            Chuyến {chosen.flight_code} còn {remaining} chỗ nhưng bạn đang chuyển {people.length}{' '}
            người. Giảm số người hoặc chọn chuyến khác.
          </Alert>
        )}

        {warnings.length > 0 && (
          <Alert tone="warning" title="Lưu ý">
            <ul className="mt-1 list-disc space-y-1 pl-4">
              {warnings.map((warning, index) => (
                <li key={index}>{warning}</li>
              ))}
            </ul>
          </Alert>
        )}

        <Textarea
          label="Lý do"
          required
          rows={3}
          maxLength={500}
          counterValue={reason}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          placeholder="Ví dụ: vợ chồng muốn bay cùng chuyến, người này nối chuyến công tác…"
          hint="Lưu vào nhật ký thay đổi, tối thiểu 3 ký tự"
        />
      </div>
    </Modal>
  )
}
