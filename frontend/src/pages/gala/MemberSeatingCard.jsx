import { Shuffle, Wand2 } from 'lucide-react'
import { useAssignGalaMember, useAutoAssignGalaMembers, useGalaTeamMembers } from '../../hooks/useGala'
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
  const { data: members, isLoading, error } = useGalaTeamMembers(forTeam ? teamId : null, { enabled: Boolean(teamId) })
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
      toast.error(assignError.message)
    }
  }

  async function runAuto(reshuffle) {
    try {
      const result = await autoAssign({ teamId: forTeam ? teamId : null, reshuffle })
      toast.success(
        `Đã xếp ${result.placed} người vào ghế${result.unseated ? `, còn ${result.unseated} người chưa có ghế vì team thiếu ghế` : ''}.`,
      )
    } catch (autoError) {
      toast.error(autoError.message)
    }
  }

  return (
    <Card
      title="Xếp thành viên vào ghế"
      description={members ? `${seated}/${members.length} người có ghế · ${teamSeats.length} ghế của team` : undefined}
      bodyClassName="p-0"
    >
      {isLoading ? (
        <Spinner />
      ) : error ? (
        <div className="p-4">
          <Alert tone="error">{error.message}</Alert>
        </div>
      ) : teamSeats.length === 0 ? (
        <p className="px-4 py-3.5 text-sm text-slate-500">Team chưa chốt ghế nào. Chọn và xác nhận ghế trước.</p>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 px-4 py-2.5">
            <Button
              size="sm"
              icon={Wand2}
              disabled={!unseated || !freeSeats || busy}
              loading={autoAssigning}
              onClick={() => runAuto(false)}
            >
              {unseated ? `Xếp ngẫu nhiên ${Math.min(unseated, freeSeats)} người chưa có ghế` : 'Mọi người đã có ghế'}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              icon={Shuffle}
              disabled={!seated || busy}
              onClick={() => {
                if (window.confirm('Xáo lại chỗ của TẤT CẢ thành viên? Các chỗ đã đổi tay sẽ mất.')) runAuto(true)
              }}
            >
              Xáo lại tất cả
            </Button>
            <p className="w-full text-xs text-slate-500">
              Xếp xong, thành viên nào muốn đổi chỗ thì chọn lại ghế cho người đó ở danh sách dưới.
            </p>
          </div>
          <ul className="max-h-[28rem] divide-y divide-slate-100 overflow-y-auto">
            {members.map((member) => (
              <li key={member.registration_id} className="flex items-center gap-2.5 px-4 py-2">
                <Avatar user={member} size="sm" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-slate-900">{member.full_name}</p>
                  {member.employee_code && <p className="text-xs text-slate-500">{member.employee_code}</p>}
                </div>
                <label className="sr-only" htmlFor={`gala-seat-${member.registration_id}`}>
                  Ghế của {member.full_name}
                </label>
                <select
                  id={`gala-seat-${member.registration_id}`}
                  value={member.seat_id ?? ''}
                  disabled={busy}
                  onChange={(changeEvent) => choose(member, changeEvent.target.value)}
                  className="w-40 rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-900"
                >
                  <option value="">Chưa có ghế</option>
                  {teamSeats.map((seat) => (
                    <option key={seat.id} value={seat.id}>
                      {seat.table_code} – ghế {seat.seat_number}
                      {seat.occupant_name && seat.registration_id !== member.registration_id ? ` (${seat.occupant_name})` : ''}
                    </option>
                  ))}
                </select>
              </li>
            ))}
          </ul>
        </>
      )}
    </Card>
  )
}
