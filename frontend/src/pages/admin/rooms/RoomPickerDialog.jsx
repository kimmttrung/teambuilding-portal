import { useState } from 'react'
import { ArrowRight } from 'lucide-react'
import { GENDER_LABELS, ROOM_POLICY_META, ROOM_TYPE_LABELS } from '../../../utils/constants'
import { canStay } from '../../../utils/rooms'
import Alert from '../../../components/common/Alert'
import Button from '../../../components/common/Button'
import Modal from '../../../components/common/Modal'
import Select from '../../../components/common/Select'
import Textarea from '../../../components/common/Textarea'

/**
 * Chọn phòng cho một người — dùng cho "xếp phòng" và "chuyển phòng".
 *
 * Chỉ liệt kê phòng còn chỗ và HỢP GIỚI TÍNH: backend chặn cứng sai giới, nên cho chọn rồi mới
 * báo lỗi chỉ làm BTC mất công.
 */
export default function RoomPickerDialog({
  title,
  person,
  rooms = [],
  currentRoomId = null,
  pending = false,
  onConfirm,
  onClose,
}) {
  const [roomId, setRoomId] = useState('')
  const [captain, setCaptain] = useState(false)
  const [reason, setReason] = useState('')

  const options = rooms.filter(
    (room) => room.id !== currentRoomId && room.remaining > 0 && canStay(room.gender_policy, person.gender),
  )
  const byHotel = new Map()
  for (const room of options) {
    const list = byHotel.get(room.hotel_name)
    if (list) list.push(room)
    else byHotel.set(room.hotel_name, [room])
  }
  const chosen = options.find((room) => String(room.id) === roomId) ?? null
  const genderKnown = person.gender === 'male' || person.gender === 'female'

  return (
    <Modal
      open
      onClose={onClose}
      title={title}
      description={[person.full_name, person.team_name, GENDER_LABELS[person.gender] ?? 'chưa khai giới tính']
        .filter(Boolean)
        .join(' · ')}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="sm" onClick={onClose}>
            Huỷ
          </Button>
          <Button
            size="sm"
            icon={ArrowRight}
            loading={pending}
            disabled={!chosen || pending}
            onClick={() => onConfirm({ roomId: chosen.id, isRoomCaptain: captain, reason: reason.trim() })}
          >
            Xác nhận
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-3.5">
        {options.length === 0 ? (
          <Alert tone="warning" title="Không còn phòng phù hợp">
            {genderKnown
              ? `Mọi phòng dành cho ${GENDER_LABELS[person.gender].toLowerCase()} và phòng không giới hạn đã đủ người. Thêm phòng hoặc đổi một phòng trống sang giới tính này.`
              : 'Người này chưa khai giới tính nam/nữ nên chỉ vào được phòng không giới hạn, và kỳ này không còn phòng như vậy. Bổ sung hồ sơ hoặc tạo phòng không giới hạn.'}
          </Alert>
        ) : (
          <Select
            label="Phòng"
            required
            placeholder="— Chọn phòng —"
            value={roomId}
            onChange={(changeEvent) => setRoomId(changeEvent.target.value)}
          >
            {[...byHotel.entries()].map(([hotelName, list]) => (
              <optgroup key={hotelName} label={hotelName}>
                {list.map((room) => (
                  <option key={room.id} value={room.id}>
                    {room.room_number}
                    {room.floor ? ` · tầng ${room.floor}` : ''} · {ROOM_TYPE_LABELS[room.room_type] ?? 'phòng'} ·{' '}
                    {ROOM_POLICY_META[room.gender_policy]?.label ?? room.gender_policy} · còn {room.remaining} chỗ
                  </option>
                ))}
              </optgroup>
            ))}
          </Select>
        )}

        {chosen && (
          <label className="flex items-center gap-2.5 text-sm text-slate-700">
            <input
              type="checkbox"
              className="size-4 accent-brand-600"
              checked={captain}
              onChange={(changeEvent) => setCaptain(changeEvent.target.checked)}
            />
            Làm trưởng phòng {chosen.room_number}
            {chosen.has_captain && <span className="text-xs text-amber-700">(thay trưởng phòng hiện tại)</span>}
          </label>
        )}

        <Textarea
          label="Ghi chú lý do"
          rows={2}
          maxLength={500}
          value={reason}
          counterValue={reason}
          onChange={(changeEvent) => setReason(changeEvent.target.value)}
          placeholder="Ví dụ: ở cùng đồng nghiệp cùng team, cần phòng gần thang máy…"
          hint="Không bắt buộc, lưu vào nhật ký thay đổi"
        />
      </div>
    </Modal>
  )
}
