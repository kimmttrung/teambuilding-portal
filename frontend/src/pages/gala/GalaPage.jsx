import { useState } from 'react'
import { MapPin, PartyPopper } from 'lucide-react'
import { useGalaLive, useGalaView, useHoldGalaSeats, useReleaseGalaSeats } from '../../hooks/useGala'
import { useToast } from '../../context/ToastContext'
import { formatFullDateTime, formatNumber } from '../../utils/format'
import { serverOffset } from '../../utils/gala'
import Alert from '../../components/common/Alert'
import Card from '../../components/common/Card'
import EmptyState from '../../components/common/EmptyState'
import PageHeader from '../../components/common/PageHeader'
import Spinner from '../../components/common/Spinner'
import DrawOrderPanel from '../../components/gala/DrawOrderPanel'
import LiveBadge from '../../components/gala/LiveBadge'
import SeatLegend from '../../components/gala/SeatLegend'
import SeatMap from '../../components/gala/SeatMap'
import MemberSeatingCard from './MemberSeatingCard'
import TeamTurnCard from './TeamTurnCard'

const EMPTY_CODES = new Set(['GALA_NOT_CONFIGURED', 'NO_ACTIVE_EVENT'])

/**
 * Sơ đồ Gala cho mọi người. Trưởng nhóm của team đang tới lượt chọn ghế ngay trên sơ đồ:
 * bấm ghế trống → Giữ ghế → Xác nhận. Sau đó xếp từng thành viên vào ghế của team.
 *
 * Sơ đồ tự cập nhật qua SSE — hai team không nhìn thấy hai trạng thái khác nhau của cùng một ghế.
 */
export default function GalaPage() {
  const toast = useToast()
  const { data: view, isLoading, error, dataUpdatedAt } = useGalaView()
  const live = useGalaLive({ enabled: Boolean(view) })
  const { mutateAsync: hold, isPending: holding } = useHoldGalaSeats()
  const { mutateAsync: release, isPending: releasing } = useReleaseGalaSeats()
  const [selected, setSelected] = useState([])

  if (isLoading) return <Spinner label="Đang tải sơ đồ Gala…" />
  if (error) {
    return (
      <>
        <PageHeader title="Gala Dinner" />
        {EMPTY_CODES.has(error.code) ? (
          <Card>
            <EmptyState
              icon={PartyPopper}
              title="Sơ đồ Gala chưa sẵn sàng"
              description="Ban tổ chức chưa công bố sơ đồ bàn tiệc. Quay lại sau nhé."
            />
          </Card>
        ) : (
          <Alert tone="error" title="Không tải được sơ đồ">
            {error.message}
          </Alert>
        )}
      </>
    )
  }

  const offsetMs = serverOffset(view.server_time, dataUpdatedAt)
  const team = view.my_team
  const canPick = Boolean(team?.is_leader && team.is_my_turn)
  const seats = new Map(view.tables.flatMap((table) => table.seats.map((seat) => [seat.id, seat])))
  // Ghế vừa bị team khác giữ, hoặc hết lượt: tự rơi khỏi danh sách đang chọn.
  const picked = canPick ? selected.filter((seatId) => seats.get(seatId)?.state === 'available') : []

  async function handleSeat(seat) {
    if (!canPick) return
    if (seat.state === 'held_by_me') {
      try {
        await release([seat.id])
      } catch (releaseError) {
        toast.error(releaseError.message)
      }
      return
    }
    if (seat.state !== 'available') return
    if (picked.includes(seat.id)) {
      setSelected(picked.filter((seatId) => seatId !== seat.id))
    } else if (picked.length >= team.remaining) {
      toast.error(`Team chỉ còn chọn được ${team.remaining} ghế.`)
    } else {
      setSelected([...picked, seat.id])
    }
  }

  async function holdPicked() {
    try {
      const result = await hold(picked)
      setSelected([])
      toast.success(`Đã giữ ${result.seat_ids.length} ghế. Bấm "Xác nhận" trước khi hết giờ giữ.`)
    } catch (holdError) {
      toast.error(holdError.message)
    }
  }

  return (
    <>
      <PageHeader
        title={view.layout.name}
        description={[view.layout.venue, view.layout.starts_at && formatFullDateTime(view.layout.starts_at)]
          .filter(Boolean)
          .join(' · ')}
        action={<LiveBadge status={live} />}
      />

      <div className="grid gap-4 xl:grid-cols-12">
        <div className="flex min-w-0 flex-col gap-4 xl:col-span-8">
          <Card
            title="Sơ đồ bàn tiệc"
            description={`${formatNumber(view.totals.available)} ghế trống / ${formatNumber(view.totals.seats)} ghế`}
            action={
              view.layout.venue ? (
                <span className="hidden items-center gap-1 text-xs text-slate-500 sm:inline-flex">
                  <MapPin className="size-3.5" aria-hidden="true" />
                  {view.layout.venue}
                </span>
              ) : undefined
            }
          >
            <div className="flex flex-col gap-3">
              {canPick && (
                <Alert tone="info">
                  Bấm ghế trống để chọn (tối đa {team.remaining} ghế), bấm ghế team đang giữ để nhả.
                </Alert>
              )}
              <SeatMap
                view={view}
                selectedIds={picked}
                myTeamId={team?.team_id}
                onSeatClick={canPick ? handleSeat : undefined}
                isSeatClickable={(seat) => canPick && (seat.state === 'available' || seat.state === 'held_by_me')}
              />
              <SeatLegend showSelected={canPick} />
            </div>
          </Card>
        </div>

        <div className="flex min-w-0 flex-col gap-4 xl:col-span-4">
          <TeamTurnCard
            view={view}
            offsetMs={offsetMs}
            picked={picked}
            onHold={holdPicked}
            onClearPicked={() => setSelected([])}
            onReleaseAll={async () => {
              try {
                const result = await release(null)
                toast.success(`Đã nhả ${result.released} ghế.`)
              } catch (releaseError) {
                toast.error(releaseError.message)
              }
            }}
            holding={holding}
            releasing={releasing}
          />
          {team?.is_leader && <MemberSeatingCard view={view} teamId={team.team_id} />}
          <DrawOrderPanel draw={view.draw} myTeamId={team?.team_id} offsetMs={offsetMs} />
        </div>
      </div>
    </>
  )
}
