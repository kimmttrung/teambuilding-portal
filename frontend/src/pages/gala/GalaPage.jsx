import { useState } from 'react'
import { PartyPopper } from 'lucide-react'
import {
  useGalaLive,
  useGalaView,
  useHoldGalaSeats,
  useReleaseGalaSeats,
  useAssignGalaMember,
} from '../../hooks/useGala'
import { useToast } from '../../context/ToastContext'
import { formatFullDateTime } from '../../utils/format'
import { availablePicks, serverOffset } from '../../utils/gala'
import Alert from '../../components/common/Alert'
import Button from '../../components/common/Button'
import Card from '../../components/common/Card'
import EmptyState from '../../components/common/EmptyState'
import PageHeader from '../../components/common/PageHeader'
import Spinner from '../../components/common/Spinner'
import DrawOrderPanel from '../../components/gala/DrawOrderPanel'
import LiveBadge from '../../components/gala/LiveBadge'
import SeatLegend from '../../components/gala/SeatLegend'
import SeatMap from '../../components/gala/SeatMap'
import MemberSeatingCard from './MemberSeatingCard'
import MemberSeatModal from './MemberSeatModal'
import TeamTurnCard from './TeamTurnCard'

const EMPTY_CODES = new Set(['GALA_NOT_CONFIGURED', 'NO_ACTIVE_EVENT'])

export default function GalaPage() {
  const toast = useToast()
  const { data: view, isLoading, error, dataUpdatedAt, refetch } = useGalaView()
  const live = useGalaLive({ enabled: Boolean(view) })
  const { mutateAsync: hold, isPending: holding } = useHoldGalaSeats()
  const { mutateAsync: release, isPending: releasing } = useReleaseGalaSeats()
  const { mutateAsync: assign, isPending: assigning } = useAssignGalaMember()
  const [selection, setSelection] = useState({ scope: null, ids: [] })
  const [actionError, setActionError] = useState(null)
  const [seatEdit, setSeatEdit] = useState(null)
  if (isLoading) return <Spinner label="Đang tải sơ đồ Gala…" />
  if (!view)
    return (
      <>
        <PageHeader title="Gala Dinner" />
        {EMPTY_CODES.has(error?.code) ? (
          <Card>
            <EmptyState
              icon={PartyPopper}
              title="Sơ đồ Gala chưa sẵn sàng"
              description="Ban tổ chức chưa tạo sơ đồ bàn tiệc. Quay lại sau nhé."
            />
          </Card>
        ) : (
          <Alert tone="error" title="Không tải được sơ đồ">
            {error?.message}
            <Button variant="ghost" onClick={() => refetch()}>
              Thử lại
            </Button>
          </Alert>
        )}
      </>
    )
  const offsetMs = serverOffset(view.server_time, dataUpdatedAt)
  const team = view.my_team
  const canPick = Boolean(team?.is_leader && team.is_my_turn)
  const picked = availablePicks(view, selection)
  const scope = `${view.layout.id}:${team?.team_id}:${team?.turn_ends_at}`
  const busy = holding || releasing || assigning
  const offline = live === 'offline' || Boolean(error)
  async function run(action, message) {
    setActionError(null)
    try {
      const result = await action()
      if (message) toast.success(message)
      return result
    } catch (err) {
      setActionError(err.message)
      return null
    }
  }
  function handleSeat(seat, table) {
    if (team?.is_leader && seat.state === 'taken' && seat.team_id === team.team_id) {
      setSeatEdit({ seatId: seat.id, tableId: table.id })
      return
    }
    if (!canPick || busy || offline) return
    if (seat.state === 'held_by_me') {
      run(() => release([seat.id]), 'Đã nhả ghế.')
      return
    }
    if (seat.state !== 'available') return
    if (picked.includes(seat.id))
      setSelection({ scope, ids: picked.filter((id) => id !== seat.id) })
    else if (picked.length >= Math.min(team.remaining, 30))
      setActionError(`Team chỉ còn chọn được ${team.remaining} ghế; mỗi lần giữ tối đa 30 ghế.`)
    else {
      setActionError(null)
      setSelection({ scope, ids: [...picked, seat.id] })
    }
  }
  async function holdPicked() {
    const result = await run(() => hold(picked), 'Đã giữ ghế. Hãy xác nhận trước khi hết giờ.')
    if (result) setSelection({ scope: null, ids: [] })
  }
  return (
    <>
      <PageHeader
        title={view.layout.name}
        description={[
          view.layout.venue,
          view.layout.starts_at && formatFullDateTime(view.layout.starts_at),
        ]
          .filter(Boolean)
          .join(' · ')}
        action={<LiveBadge status={live} />}
      />
      {offline && (
        <div className="mb-4">
          <Alert tone="warning" title="Đang cập nhật lại sơ đồ">
            {error?.message ??
              'Mất kết nối trực tiếp. Thao tác chọn ghế tạm khoá trong lúc kết nối lại.'}
            <Button variant="ghost" onClick={() => refetch()}>
              Thử lại
            </Button>
          </Alert>
        </div>
      )}
      {actionError && (
        <div role="alert" className="mb-4">
          <Alert tone="error">{actionError}</Alert>
        </div>
      )}
      {team?.is_my_turn && (
        <div className="mb-6">
          <TeamTurnCard
            view={view}
            offsetMs={offsetMs}
            picked={picked}
            onHold={holdPicked}
            onClearPicked={() => setSelection({ scope: null, ids: [] })}
            onReleaseAll={() => run(() => release(null), 'Đã nhả các ghế đang giữ.')}
            holding={holding}
            releasing={releasing}
            offline={offline}
          />
        </div>
      )}
      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0 space-y-4">
          <Card>
            {view.tables.length ? (
              <div className="space-y-5">
                <SeatMap
                  key={view.layout.id}
                  view={view}
                  selectedIds={picked}
                  myTeamId={team?.team_id}
                  onSeatClick={handleSeat}
                  disabled={busy || offline}
                  isSeatClickable={(seat) =>
                    Boolean(
                      (canPick && ['available', 'held_by_me'].includes(seat.state)) ||
                      (team?.is_leader && seat.state === 'taken' && seat.team_id === team.team_id),
                    )
                  }
                  onMemberDrop={
                    team?.is_leader
                      ? (registrationId, seat) =>
                          run(
                            () => assign({ seatId: seat.id, registrationId }),
                            'Đã xếp thành viên vào ghế.',
                          )
                      : undefined
                  }
                />
                <SeatLegend showSelected={canPick} />
                <p className="text-xs text-ink-faint">
                  Bấm vào bàn để xem ghế lớn hơn. Chuyển sang Danh sách để chọn ghế trên điện thoại.
                </p>
              </div>
            ) : (
              <EmptyState
                icon={PartyPopper}
                title="Chưa có bàn tiệc"
                description="Ban tổ chức đang chuẩn bị sơ đồ."
              />
            )}
          </Card>
          {canPick && (
            <p className="text-caption text-ink-muted">
              Chọn tối đa {team.remaining} ghế còn lại → Giữ ghế → Xác nhận. Ghế đang giữ chưa phải
              ghế đã chốt.
            </p>
          )}
        </div>
        <aside className="min-w-0 space-y-5">
          {!team?.is_my_turn && <TeamTurnCard view={view} offsetMs={offsetMs} picked={[]} />}
          {team?.is_leader && (
            <MemberSeatingCard
              key={`${view.layout.id}:${team.team_id}`}
              view={view}
              teamId={team.team_id}
            />
          )}
          {team && !team.is_leader && (
            <Card title="Ghế của team">
              <ul className="space-y-3">
                {view.tables.flatMap((table) =>
                  table.seats
                    .filter(
                      (seat) =>
                        seat.state === 'taken' &&
                        seat.team_id === team.team_id &&
                        seat.occupant_name,
                    )
                    .map((seat) => (
                      <li key={seat.id} className="flex justify-between gap-3 text-caption">
                        <span className="font-medium text-ink">{seat.occupant_name}</span>
                        <span className="text-ink-muted">
                          {table.table_code} · ghế {seat.seat_number}
                        </span>
                      </li>
                    )),
                )}
              </ul>
              <p className="mt-3 text-caption text-ink-muted">
                Trưởng nhóm xếp từng thành viên vào ghế đã xác nhận.
              </p>
            </Card>
          )}
          <DrawOrderPanel draw={view.draw} myTeamId={team?.team_id} offsetMs={offsetMs} />
        </aside>
      </div>
      {seatEdit && (
        <MemberSeatModal
          key={`${seatEdit.seatId}:${team?.team_id}`}
          {...seatEdit}
          teamId={team?.team_id}
          view={view}
          onClose={() => setSeatEdit(null)}
        />
      )}
    </>
  )
}
