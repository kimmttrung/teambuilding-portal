import { GALA_UI } from '../../utils/constants'
import { useState } from 'react'
import seatAddIcon from '../../assets/gala/seatAdd.svg'
import MemberSeatModal from './MemberSeatModal'
import gripIcon from '../../assets/gala/grip.svg'
import Modal from '../../components/common/Modal'
import { Shuffle, Wand2 } from 'lucide-react'
import {
  useAssignGalaMember,
  useAutoAssignGalaMembers,
  useGalaTeamMembers,
} from '../../hooks/useGala'
import { useToast } from '../../context/ToastContext'
import Alert from '../../components/common/Alert'
import Avatar from '../../components/common/Avatar'
import Button from '../../components/common/Button'
import Card from '../../components/common/Card'
import Spinner from '../../components/common/Spinner'

/**
 * Xếp thành viên vào các ghế team đã chốt: bấm "Xếp ngẫu nhiên" cho nhanh, rồi ai muốn đổi chỗ thì
 * chọn lại ghế cho người đó. Chọn ghế đang có người khác thì người đó bị bỏ ghế; chọn ghế cho người
 * đang ngồi chỗ khác thì họ được chuyển.
 *
 * `forTeam` chỉ truyền khi BTC xem team bất kỳ; Trưởng nhóm luôn là team mình.
 */
export default function MemberSeatingCard({ view, teamId, forTeam = false }) {
  const toast = useToast()
  const [reshuffleOpen, setReshuffleOpen] = useState(false)
  const [actionError, setActionError] = useState(null)
  const [seatEdit, setSeatEdit] = useState(null)
  const {
    data: members,
    isLoading,
    error,
  } = useGalaTeamMembers(forTeam ? teamId : null, { enabled: Boolean(teamId) })
  const { mutateAsync: assign, isPending } = useAssignGalaMember()
  const { mutateAsync: autoAssign, isPending: autoAssigning } = useAutoAssignGalaMembers()

  const teamSeats = view.tables.flatMap((table) =>
    table.seats
      .filter((seat) => seat.state === 'taken' && seat.team_id === teamId)
      .map((seat) => ({ ...seat, table_code: table.table_code })),
  )
  const seated = members?.filter((member) => member.seat_id).length ?? 0
  const unseated = members ? members.length - seated : 0
  const freeSeats = teamSeats.filter((seat) => !seat.registration_id).length
  const busy = isPending || autoAssigning

  async function choose(member, value) {
    const seatId = value ? Number(value) : null
    if (seatId === member.seat_id) return
    setActionError(null)
    try {
      if (seatId === null) {
        await assign({ seatId: member.seat_id, registrationId: null })
        toast.success(`Đã bỏ ghế của ${member.full_name}.`)
      } else {
        await assign({ seatId, registrationId: member.registration_id })
        const seat = teamSeats.find((item) => item.id === seatId)
        toast.success(`${member.full_name} ngồi ${seat?.table_code} – ghế ${seat?.seat_number}.`)
      }
    } catch (assignError) {
      setActionError(assignError.message)
    }
  }

  async function runAuto(reshuffle) {
    setActionError(null)
    try {
      const result = await autoAssign({ teamId: forTeam ? teamId : null, reshuffle })
      setReshuffleOpen(false)
      toast.success(
        `Đã xếp ${result.placed} người vào ghế${result.unseated ? `, còn ${result.unseated} người chưa có ghế vì team thiếu ghế` : ''}.`,
      )
    } catch (autoError) {
      setActionError(autoError.message)
    }
  }

  return (
    <Card
      title={GALA_UI.members}
      description={
        members
          ? `${seated}/${members.length} người có ghế · ${teamSeats.length} ghế của team`
          : undefined
      }
      bodyClassName="p-0"
    >
      {actionError && !reshuffleOpen && (
        <div className="p-4">
          <Alert tone="error">{actionError}</Alert>
        </div>
      )}
      {isLoading ? (
        <Spinner />
      ) : error ? (
        <div className="p-4">
          <Alert tone="error">{error.message}</Alert>
        </div>
      ) : teamSeats.length === 0 ? (
        <p className="px-4 py-3.5 text-sm text-ink-muted">
          Team chưa chốt ghế nào. Chọn và xác nhận ghế trước.
        </p>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2 border-b border-hairline px-4 py-2.5">
            <Button
              size="md"
              icon={Wand2}
              disabled={!unseated || !freeSeats || busy}
              loading={autoAssigning}
              onClick={() => runAuto(false)}
            >
              {unseated
                ? `Xếp ngẫu nhiên ${Math.min(unseated, freeSeats)} người chưa có ghế`
                : 'Mọi người đã có ghế'}
            </Button>
            <Button
              size="md"
              variant="ghost"
              icon={Shuffle}
              disabled={!seated || busy}
              onClick={() => setReshuffleOpen(true)}
            >
              Xáo lại tất cả
            </Button>
            <p className="w-full text-xs text-ink-muted">
              Xếp xong, thành viên nào muốn đổi chỗ thì chọn lại ghế cho người đó ở danh sách dưới.
            </p>
          </div>
          <div className="border-b border-hairline px-4 py-4">
            <p className="mb-3 text-caption text-ink-muted">
              Chọn ghế rồi chọn người, hoặc kéo tên vào ghế trên sơ đồ.
            </p>
            <div className="grid grid-cols-5 gap-2">
              {teamSeats.map((seat) => (
                <button
                  key={seat.id}
                  type="button"
                  disabled={busy}
                  aria-label={`Xếp người vào ${seat.table_code}, ghế ${seat.seat_number}`}
                  onClick={() => setSeatEdit(seat)}
                  className="flex min-h-16 flex-col items-center justify-center gap-1 rounded-md border border-hairline bg-canvas-soft text-ink-secondary"
                >
                  {seat.occupant_name ? (
                    <span className="font-semibold">
                      {seat.occupant_name.trim().split(/\s+/).at(-1).slice(0, 1)}
                    </span>
                  ) : (
                    <img src={seatAddIcon} alt="" />
                  )}
                  <span className="text-[10px] text-ink-muted">
                    {seat.table_code} · {seat.seat_number}
                  </span>
                </button>
              ))}
            </div>
          </div>
          <ul className="max-h-[28rem] divide-y divide-hairline overflow-y-auto">
            {(members ?? []).map((member) => (
              <li
                key={member.registration_id}
                draggable={!busy}
                onDragStart={(event) => {
                  event.dataTransfer.setData(
                    'application/x-gala-member',
                    String(member.registration_id),
                  )
                  event.dataTransfer.effectAllowed = 'move'
                }}
                className="flex items-center gap-2 px-4 py-3"
              >
                <img src={gripIcon} alt="" className="hidden shrink-0 sm:block" />
                <Avatar user={member} size="md" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-ink">{member.full_name}</p>
                  {member.employee_code && (
                    <p className="text-xs text-ink-muted">{member.employee_code}</p>
                  )}
                </div>
                <label className="sr-only" htmlFor={`gala-seat-${member.registration_id}`}>
                  Ghế của {member.full_name}
                </label>
                <select
                  id={`gala-seat-${member.registration_id}`}
                  value={member.seat_id ?? ''}
                  disabled={busy}
                  onChange={(changeEvent) => choose(member, changeEvent.target.value)}
                  className="min-h-11 w-32 shrink-0 rounded-md border border-input-border bg-surface px-2 text-caption text-ink"
                >
                  <option value="">Chưa có ghế</option>
                  {teamSeats.map((seat) => (
                    <option key={seat.id} value={seat.id}>
                      {seat.table_code} – ghế {seat.seat_number}
                      {seat.occupant_name && seat.registration_id !== member.registration_id
                        ? ` (${seat.occupant_name})`
                        : ''}
                    </option>
                  ))}
                </select>
              </li>
            ))}
          </ul>
        </>
      )}
      {seatEdit && (
        <MemberSeatModal
          key={seatEdit.id}
          seatId={seatEdit.id}
          tableId={
            view.tables.find((table) => table.seats.some((seat) => seat.id === seatEdit.id))?.id
          }
          teamId={teamId}
          forTeam={forTeam}
          view={view}
          onClose={() => setSeatEdit(null)}
        />
      )}
      {reshuffleOpen && (
        <Modal
          open
          title="Xáo lại chỗ của cả team?"
          description="Các chỗ đã đổi tay cũng sẽ được xếp lại."
          onClose={() => setReshuffleOpen(false)}
          footer={
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setReshuffleOpen(false)}>
                {GALA_UI.cancel}
              </Button>
              <Button loading={autoAssigning} onClick={() => runAuto(true)}>
                Xáo lại
              </Button>
            </div>
          }
        >
          {actionError && <Alert tone="error">{actionError}</Alert>}
        </Modal>
      )}
    </Card>
  )
}
