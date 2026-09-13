import { useState } from 'react'
import { ArrowRightLeft, Crown, HeartPulse, Pencil, Trash2, UserPlus } from 'lucide-react'
import { useAssignRoom, useDeleteRoom, useOccupants, useRemoveRoomAssignment } from '../../../hooks/useRooms'
import { useToast } from '../../../context/ToastContext'
import { GENDER_LABELS, ROOM_POLICY_META, ROOM_TYPE_LABELS } from '../../../utils/constants'
import { canStay } from '../../../utils/rooms'
import Alert from '../../../components/common/Alert'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Modal from '../../../components/common/Modal'
import Select from '../../../components/common/Select'
import Spinner from '../../../components/common/Spinner'
import Textarea from '../../../components/common/Textarea'
import RoomPickerDialog from './RoomPickerDialog'

/**
 * Một phòng: ai đang ở, trưởng phòng, thêm người, chuyển, bỏ xếp, sửa/xoá phòng.
 * Hộp thoại con thay chỗ hộp thoại này thay vì chồng lên — Esc chỉ đóng một lớp.
 */
export default function RoomDetailModal({ room, rooms = [], unassigned = [], onEdit, onClose }) {
  const toast = useToast()
  const { data: occupants, isLoading, error } = useOccupants(room.id)
  const { mutateAsync: assign, isPending: assigning } = useAssignRoom()
  const { mutateAsync: remove, isPending: removing } = useRemoveRoomAssignment()
  const { mutateAsync: deleteRoom, isPending: deleting } = useDeleteRoom()

  const [view, setView] = useState({ name: 'detail' })
  const [reason, setReason] = useState('')
  const [addId, setAddId] = useState('')
  const [addCaptain, setAddCaptain] = useState(false)

  const policy = ROOM_POLICY_META[room.gender_policy] ?? ROOM_POLICY_META.any
  const candidates = unassigned.filter((person) => canStay(room.gender_policy, person.gender))
  const backToDetail = () => setView({ name: 'detail' })

  async function makeCaptain(person) {
    try {
      await assign({ registrationId: person.registration_id, roomId: room.id, isRoomCaptain: true })
      toast.success(`${person.full_name} là trưởng phòng ${room.room_number}.`)
    } catch (captainError) {
      toast.error(captainError.message)
    }
  }

  async function addPerson() {
    const person = candidates.find((item) => String(item.registration_id) === addId)
    if (!person) return
    try {
      await assign({ registrationId: person.registration_id, roomId: room.id, isRoomCaptain: addCaptain })
      toast.success(`Đã xếp ${person.full_name} vào phòng ${room.room_number}.`)
      setAddId('')
      setAddCaptain(false)
    } catch (addError) {
      toast.error(addError.message)
    }
  }

  if (view.name === 'move') {
    return (
      <RoomPickerDialog
        title="Chuyển sang phòng khác"
        person={view.person}
        rooms={rooms}
        currentRoomId={room.id}
        pending={assigning}
        onClose={backToDetail}
        onConfirm={async ({ roomId, isRoomCaptain, reason: why }) => {
          try {
            const result = await assign({
              registrationId: view.person.registration_id,
              roomId,
              isRoomCaptain,
              replaceExisting: true,
              reason: why,
            })
            toast.success(`Đã chuyển ${view.person.full_name} sang phòng ${result.assignment.room_number}.`)
            backToDetail()
          } catch (moveError) {
            toast.error(moveError.message)
          }
        }}
      />
    )
  }

  if (view.name === 'remove') {
    return (
      <Modal
        open
        onClose={backToDetail}
        title={`Bỏ xếp phòng của ${view.person.full_name}?`}
        description={`Phòng ${room.room_number} · ${room.hotel_name}`}
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" size="sm" onClick={backToDetail}>
              Không bỏ
            </Button>
            <Button
              variant="danger"
              size="sm"
              icon={Trash2}
              loading={removing}
              disabled={reason.trim().length < 3 || removing}
              onClick={async () => {
                try {
                  await remove({ assignmentId: view.person.assignment_id, reason: reason.trim() })
                  toast.success(`Đã bỏ xếp phòng của ${view.person.full_name}.`)
                  backToDetail()
                } catch (removeError) {
                  toast.error(removeError.message)
                }
              }}
            >
              Bỏ xếp phòng
            </Button>
          </div>
        }
      >
        <Textarea
          label="Lý do"
          required
          rows={2}
          maxLength={500}
          value={reason}
          counterValue={reason}
          onChange={(changeEvent) => setReason(changeEvent.target.value)}
          hint="Lưu vào nhật ký thay đổi, tối thiểu 3 ký tự"
        />
      </Modal>
    )
  }

  if (view.name === 'delete') {
    return (
      <Modal
        open
        onClose={backToDetail}
        title={`Xoá phòng ${room.room_number}?`}
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" size="sm" onClick={backToDetail}>
              Không xoá
            </Button>
            <Button
              variant="danger"
              size="sm"
              icon={Trash2}
              loading={deleting}
              onClick={async () => {
                try {
                  await deleteRoom(room.id)
                  toast.success(`Đã xoá phòng ${room.room_number}.`)
                  onClose()
                } catch (deleteError) {
                  toast.error(deleteError.message)
                }
              }}
            >
              Xoá phòng
            </Button>
          </div>
        }
      >
        <p className="text-sm text-slate-700">Phòng chưa có ai ở. Thao tác được ghi vào nhật ký thay đổi.</p>
      </Modal>
    )
  }

  const rows = occupants ?? []

  return (
    <Modal
      open
      size="lg"
      onClose={onClose}
      title={`Phòng ${room.room_number}`}
      description={[
        room.hotel_name,
        room.floor ? `tầng ${room.floor}` : null,
        ROOM_TYPE_LABELS[room.room_type] ?? null,
      ]
        .filter(Boolean)
        .join(' · ')}
      footer={
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Button
            variant="ghost"
            size="sm"
            icon={Trash2}
            disabled={room.occupied > 0}
            title={room.occupied > 0 ? 'Chuyển hết người sang phòng khác trước khi xoá' : undefined}
            onClick={() => setView({ name: 'delete' })}
          >
            Xoá phòng
          </Button>
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" icon={Pencil} onClick={onEdit}>
              Sửa phòng
            </Button>
            <Button size="sm" onClick={onClose}>
              Đóng
            </Button>
          </div>
        </div>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={policy.tone}>{policy.label}</Badge>
          <span className="text-sm text-slate-700 tabular-nums">
            {room.occupied}/{room.capacity} người
          </span>
          {room.occupied > 0 && !room.has_captain && <Badge tone="amber">Chưa có trưởng phòng</Badge>}
        </div>
        {room.note && <p className="text-sm text-slate-600">{room.note}</p>}

        {isLoading && <Spinner label="Đang tải người ở…" />}
        {error && <Alert tone="error">{error.message}</Alert>}

        {occupants && rows.length === 0 && <p className="text-sm text-slate-500">Phòng đang trống.</p>}

        {rows.length > 0 && (
          <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200">
            {rows.map((person) => (
              <li key={person.assignment_id} className="flex flex-wrap items-center gap-x-3 gap-y-1.5 px-3 py-2.5">
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center gap-1.5 text-sm font-medium text-slate-900">
                    {person.full_name}
                    {person.is_room_captain && (
                      <Badge tone="brand">
                        <Crown className="mr-1 size-3" aria-hidden="true" />
                        Trưởng phòng
                      </Badge>
                    )}
                  </p>
                  <p className="text-xs text-slate-500">
                    {[person.team_name, GENDER_LABELS[person.gender], person.employee_code].filter(Boolean).join(' · ')}
                  </p>
                  {(person.dietary_restriction || person.has_health_note) && (
                    <p className="mt-1 flex flex-wrap gap-1">
                      {person.dietary_restriction && <Badge tone="slate">Ăn kiêng: {person.dietary_restriction}</Badge>}
                      {person.has_health_note && (
                        <Badge tone="amber">
                          <HeartPulse className="mr-1 size-3" aria-hidden="true" />
                          Có ghi chú sức khoẻ
                        </Badge>
                      )}
                    </p>
                  )}
                </div>
                <div className="flex gap-1">
                  {!person.is_room_captain && (
                    <Button variant="ghost" size="sm" icon={Crown} disabled={assigning} onClick={() => makeCaptain(person)}>
                      Trưởng phòng
                    </Button>
                  )}
                  <Button variant="ghost" size="sm" icon={ArrowRightLeft} onClick={() => setView({ name: 'move', person })}>
                    Chuyển
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={Trash2}
                    aria-label={`Bỏ xếp phòng của ${person.full_name}`}
                    onClick={() => {
                      setReason('')
                      setView({ name: 'remove', person })
                    }}
                  />
                </div>
              </li>
            ))}
          </ul>
        )}

        {room.remaining > 0 && (
          <section className="rounded-lg bg-slate-50 p-3">
            <h3 className="mb-2 text-sm font-semibold text-slate-900">Thêm người chưa có phòng</h3>
            {candidates.length === 0 ? (
              <p className="text-sm text-slate-500">Không còn ai chưa có phòng hợp giới tính với phòng này.</p>
            ) : (
              <div className="flex flex-col gap-2.5">
                <Select
                  label="Người"
                  placeholder="— Chọn người —"
                  value={addId}
                  onChange={(changeEvent) => setAddId(changeEvent.target.value)}
                  options={candidates.map((person) => ({
                    value: String(person.registration_id),
                    label: `${person.full_name}${person.team_name ? ` — ${person.team_name}` : ''}`,
                  }))}
                />
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <label className="flex items-center gap-2 text-sm text-slate-700">
                    <input
                      type="checkbox"
                      className="size-4 accent-brand-600"
                      checked={addCaptain}
                      onChange={(changeEvent) => setAddCaptain(changeEvent.target.checked)}
                    />
                    Làm trưởng phòng
                  </label>
                  <Button size="sm" icon={UserPlus} disabled={!addId || assigning} loading={assigning} onClick={addPerson}>
                    Xếp vào phòng
                  </Button>
                </div>
              </div>
            )}
          </section>
        )}
      </div>
    </Modal>
  )
}
