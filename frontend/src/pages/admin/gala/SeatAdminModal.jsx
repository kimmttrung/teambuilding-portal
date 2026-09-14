import { useState } from 'react'
import { Save } from 'lucide-react'
import { useGalaTeamMembers, useUpdateGalaSeat } from '../../../hooks/useGala'
import { useRegistrationFormOptions } from '../../../hooks/useRegistration'
import { useToast } from '../../../context/ToastContext'
import { GALA_SEAT_STATE_LABELS } from '../../../utils/constants'
import { formatTime } from '../../../utils/format'
import Alert from '../../../components/common/Alert'
import Button from '../../../components/common/Button'
import Modal from '../../../components/common/Modal'
import Select from '../../../components/common/Select'
import Textarea from '../../../components/common/Textarea'

/**
 * BTC ép gán ghế cho team / người, gỡ ghế, khoá ghế. Lý do bắt buộc (ghi audit).
 * Chỉ gửi trường thật sự đổi. Ghế lấy lại từ `view` theo id nên luôn là trạng thái mới nhất.
 */
export default function SeatAdminModal({ seatId, tableId, view, onClose }) {
  const toast = useToast()
  const table = view.tables.find((item) => item.id === tableId)
  const seat = table?.seats.find((item) => item.id === seatId)
  const { data: options } = useRegistrationFormOptions()
  const { mutateAsync: update, isPending } = useUpdateGalaSeat()

  const initialTeam = seat?.state === 'taken' ? String(seat.team_id) : ''
  const initialMember = seat?.registration_id ? String(seat.registration_id) : ''
  const initialLocked = seat?.state === 'unavailable' && Boolean(table?.is_available)

  const [teamId, setTeamState] = useState(initialTeam)
  const [memberId, setMemberId] = useState(initialMember)
  const [locked, setLocked] = useState(initialLocked)
  const [reason, setReason] = useState('')
  const { data: members } = useGalaTeamMembers(Number(teamId) || null, { enabled: Boolean(teamId) })

  if (!seat) return null

  function setTeamId(value) {
    setTeamState(value)
    setMemberId('')
  }

  const payload = {}
  if (teamId !== initialTeam) payload.team_id = teamId ? Number(teamId) : null
  if (teamId && memberId !== (teamId === initialTeam ? initialMember : '')) {
    payload.registration_id = memberId ? Number(memberId) : null
  }
  if (locked !== initialLocked) payload.is_available = !locked
  const changed = Object.keys(payload).length > 0
  const teams = (options?.teams ?? view.draw.orders.map((order) => ({ id: order.team_id, name: order.team_name }))).map(
    (team) => ({ value: team.id, label: team.name }),
  )

  async function submit() {
    try {
      await update({ seatId: seat.id, payload: { ...payload, reason: reason.trim() } })
      toast.success(`Đã cập nhật ${table.table_code} – ghế ${seat.seat_number}.`)
      onClose()
    } catch (updateError) {
      toast.error(updateError.message)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={`${table.table_code} – ghế ${seat.seat_number}`}
      description={`${GALA_SEAT_STATE_LABELS[seat.state]}${seat.team_name ? ` · ${seat.team_name}` : ''}`}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="sm" onClick={onClose}>
            Huỷ
          </Button>
          <Button size="sm" icon={Save} loading={isPending} disabled={!changed || reason.trim().length < 3} onClick={submit}>
            Lưu thay đổi
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-3.5">
        {seat.state.startsWith('held') && (
          <Alert tone="warning">
            {seat.team_name} đang giữ ghế này{seat.hold_expires_at ? ` tới ${formatTime(seat.hold_expires_at)}` : ''}. Gán team sẽ
            huỷ lượt giữ đó.
          </Alert>
        )}
        {!table.is_available && <Alert tone="info">Cả bàn {table.table_code} đang khoá — mở bàn trong phần Sửa bàn.</Alert>}

        <Select
          label="Team sở hữu ghế"
          placeholder="Không thuộc team nào"
          value={teamId}
          disabled={locked}
          onChange={(changeEvent) => setTeamId(changeEvent.target.value)}
          options={teams}
        />
        <Select
          label="Người ngồi"
          placeholder={teamId ? 'Chưa gán người' : 'Chọn team trước'}
          value={memberId}
          disabled={!teamId}
          onChange={(changeEvent) => setMemberId(changeEvent.target.value)}
          options={(members ?? []).map((member) => ({
            value: member.registration_id,
            label: member.seat_id && member.seat_id !== seat.id
              ? `${member.full_name} (đang ngồi ${member.table_code} – ${member.seat_number})`
              : member.full_name,
          }))}
        />
        <label className="inline-flex items-center gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            className="size-4 accent-brand-600"
            checked={locked}
            disabled={Boolean(teamId) || !table.is_available}
            onChange={(changeEvent) => setLocked(changeEvent.target.checked)}
          />
          Khoá ghế (cột che, lối đi, chỗ dành cho khách mời…)
        </label>
        {teamId && <p className="-mt-2 text-xs text-slate-500">Gỡ team khỏi ghế trước khi khoá.</p>}

        <Textarea
          label="Lý do"
          required
          rows={2}
          maxLength={500}
          counterValue={reason}
          value={reason}
          placeholder="Ví dụ: ghế gần lối đi cho người đau chân"
          onChange={(changeEvent) => setReason(changeEvent.target.value)}
        />
      </div>
    </Modal>
  )
}
