import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Eye, PartyPopper, Pencil, Plus } from 'lucide-react'
import { useGalaLive, useGalaView } from '../../hooks/useGala'
import { useActiveEvent } from '../../hooks/useEvent'
import { formatFullDateTime, formatNumber } from '../../utils/format'
import { serverOffset } from '../../utils/gala'
import Alert from '../../components/common/Alert'
import Button from '../../components/common/Button'
import Card from '../../components/common/Card'
import EmptyState from '../../components/common/EmptyState'
import PageHeader from '../../components/common/PageHeader'
import Select from '../../components/common/Select'
import Spinner from '../../components/common/Spinner'
import DrawOrderPanel from '../../components/gala/DrawOrderPanel'
import LiveBadge from '../../components/gala/LiveBadge'
import SeatLegend from '../../components/gala/SeatLegend'
import SeatMap from '../../components/gala/SeatMap'
import MemberSeatingCard from '../gala/MemberSeatingCard'
import GalaControlPanel from './gala/GalaControlPanel'
import LayoutFormModal from './gala/LayoutFormModal'
import SeatAdminModal from './gala/SeatAdminModal'
import TableFormModal from './gala/TableFormModal'

/**
 * BTC điều hành Gala: sơ đồ bàn, bốc thăm, mở và chuyển lượt, ép gán / khoá ghế, xếp người.
 * Bấm bàn để sửa bàn, bấm ghế để sửa ghế. Hộp thoại mount khi mở nên không cần reset state.
 */
export default function GalaAdminPage() {
  const { data: view, isLoading, error, dataUpdatedAt } = useGalaView()
  const { data: event } = useActiveEvent()
  const live = useGalaLive({ enabled: Boolean(view) })

  const [layoutForm, setLayoutForm] = useState(false)
  const [tableForm, setTableForm] = useState(null)
  const [seatEdit, setSeatEdit] = useState(null)
  const [seatingTeamId, setSeatingTeamId] = useState('')

  if (isLoading) return <Spinner label="Đang tải sơ đồ Gala…" />

  if (error?.code === 'GALA_NOT_CONFIGURED') {
    return (
      <>
        <PageHeader title="Gala Dinner" description="Sơ đồ bàn tiệc và chọn ghế theo lượt" />
        <Card>
          <EmptyState
            icon={PartyPopper}
            title="Chưa có sơ đồ Gala"
            description="Tạo sơ đồ (lưới toạ độ, vị trí sân khấu, thời gian mỗi lượt) rồi thêm bàn."
            action={
              <Button icon={Plus} onClick={() => setLayoutForm(true)}>
                Tạo sơ đồ
              </Button>
            }
          />
        </Card>
        {layoutForm && <LayoutFormModal layout={null} onClose={() => setLayoutForm(false)} />}
      </>
    )
  }

  if (error) {
    return (
      <>
        <PageHeader title="Gala Dinner" />
        <Alert tone="error" title="Không tải được sơ đồ">
          {error.message}
        </Alert>
      </>
    )
  }

  const offsetMs = serverOffset(view.server_time, dataUpdatedAt)
  const { draw, layout, totals } = view
  const teamOptions = draw.orders.map((order) => ({ value: order.team_id, label: order.team_name }))
  const seatingTeam = Number(seatingTeamId) || null

  return (
    <>
      <PageHeader
        title={layout.name}
        description={[layout.venue, layout.starts_at && formatFullDateTime(layout.starts_at)].filter(Boolean).join(' · ')}
        action={
          <div className="flex flex-wrap items-center gap-2">
            <LiveBadge status={live} />
            <Link to="/gala">
              <Button variant="ghost" icon={Eye}>
                Xem như CBNV
              </Button>
            </Link>
            <Button variant="secondary" icon={Pencil} onClick={() => setLayoutForm(true)}>
              Sửa sơ đồ
            </Button>
            <Button icon={Plus} onClick={() => setTableForm({ table: null })}>
              Thêm bàn
            </Button>
          </div>
        }
      />

      <div className="grid gap-4 xl:grid-cols-12">
        <div className="flex min-w-0 flex-col gap-4 xl:col-span-8">
          {draw.total_quota > draw.total_seats && (
            <Alert tone="warning" title="Không đủ ghế">
              Tổng quota {formatNumber(draw.total_quota)} ghế nhưng chỉ còn {formatNumber(draw.total_seats)} ghế khả dụng.
              Thêm bàn hoặc mở khoá ghế trước khi mở chọn.
            </Alert>
          )}
          {draw.unteamed_participants > 0 && (
            <Alert tone="info">
              {draw.unteamed_participants} người tham gia chưa thuộc team nên không có quota — gán team trong{' '}
              <Link to="/admin/users" className="font-medium underline">
                Quản lý CBNV
              </Link>{' '}
              hoặc ép gán ghế cho họ.
            </Alert>
          )}

          <Card
            title="Sơ đồ bàn tiệc"
            description={`${view.tables.length} bàn · ${formatNumber(totals.seats)} ghế · ${formatNumber(totals.taken)} đã có team · ${formatNumber(totals.held)} đang giữ · ${formatNumber(totals.unavailable)} khoá`}
          >
            {view.tables.length === 0 ? (
              <EmptyState
                icon={PartyPopper}
                title="Sơ đồ chưa có bàn"
                action={
                  <Button size="sm" icon={Plus} onClick={() => setTableForm({ table: null })}>
                    Thêm bàn đầu tiên
                  </Button>
                }
              />
            ) : (
              <div className="flex flex-col gap-3">
                <SeatMap
                  view={view}
                  onTableClick={(table) => setTableForm({ table })}
                  onSeatClick={(seat, table) => setSeatEdit({ seatId: seat.id, tableId: table.id })}
                />
                <SeatLegend showSelected={false} />
              </div>
            )}
          </Card>
        </div>

        <div className="flex min-w-0 flex-col gap-4 xl:col-span-4">
          <GalaControlPanel view={view} event={event} offsetMs={offsetMs} />
          <DrawOrderPanel draw={draw} offsetMs={offsetMs} showLeaders />
          {teamOptions.length > 0 && (
            <>
              <Select
                label="Xếp người cho team"
                placeholder="Chọn team"
                value={seatingTeamId}
                onChange={(changeEvent) => setSeatingTeamId(changeEvent.target.value)}
                options={teamOptions}
              />
              {seatingTeam && <MemberSeatingCard key={seatingTeam} view={view} teamId={seatingTeam} forTeam />}
            </>
          )}
        </div>
      </div>

      {layoutForm && <LayoutFormModal layout={layout} onClose={() => setLayoutForm(false)} />}
      {tableForm && <TableFormModal table={tableForm.table} view={view} onClose={() => setTableForm(null)} />}
      {seatEdit && <SeatAdminModal seatId={seatEdit.seatId} tableId={seatEdit.tableId} view={view} onClose={() => setSeatEdit(null)} />}
    </>
  )
}
