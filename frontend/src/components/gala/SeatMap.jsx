import { useEffect, useRef, useState } from 'react'
import { Crown, Minus } from 'lucide-react'
import { GALA_UI, GALA_SEAT_STATE_LABELS } from '../../utils/constants'
import { galaFloorGeometry, seatVisual } from '../../utils/gala'
import { highlightTargets, usePersonLocation } from '../../hooks/usePeople'
import { scrollIntoView } from '../../utils/highlight'
import Button from '../common/Button'
import Modal from '../common/Modal'
import mapIcon from '../../assets/gala/map.svg'
import listIcon from '../../assets/gala/list.svg'
import addIcon from '../../assets/gala/add.svg'
import checkIcon from '../../assets/gala/check.svg'
import lockIcon from '../../assets/gala/lock.svg'

const CELL = 64
const TABLE_SIZE = 60
const SEAT_SIZE = 24
const STAGE_SPACE = 52
const MAX_FLOOR_RATIO = 0.7
const MIN_FLOOR_HEIGHT = 360
const MIN_FIT_SCALE = 0.6
// Khung có padding 12px mỗi cạnh (p-3).
const FLOOR_PADDING = 24

/** Cùng một sơ đồ ở mọi kích thước; danh sách giữ vùng bấm 44px cho điện thoại. */
export default function SeatMap({
  view,
  selectedIds = [],
  myTeamId,
  onSeatClick,
  onTableClick,
  isSeatClickable,
  onMemberDrop,
  disabled = false,
}) {
  const [mode, setMode] = useState('map')
  const [zoom, setZoom] = useState(1)
  const [tableId, setTableId] = useState(null)
  const [filter, setFilter] = useState('all')
  const { location } = usePersonLocation()
  const locatedSeats = highlightTargets(location).seats
  const selected = new Set(selectedIds)
  const geometry = galaFloorGeometry(view.tables)
  const shared = {
    selected,
    myTeamId,
    onSeatClick: (seat, table) => {
      if (view.can_manage || seat.state === 'taken') setTableId(null)
      onSeatClick?.(seat, table)
    },
    isSeatClickable,
    locatedSeats,
    onMemberDrop,
    disabled,
  }
  const detail = view.tables.find((table) => table.id === tableId)
  const tables = view.tables.filter(
    (table) => filter === 'all' || (filter === 'vip' ? table.is_vip : table.available_seats > 0),
  )

  return (
    <div className="min-w-0 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div
          className="inline-flex rounded-full bg-ink/5 p-1"
          role="group"
          aria-label="Cách xem ghế"
        >
          {[
            ['map', GALA_UI.map, mapIcon],
            ['list', GALA_UI.list, listIcon],
          ].map(([value, label, icon]) => (
            <button
              key={value}
              type="button"
              aria-pressed={mode === value}
              onClick={() => setMode(value)}
              className={`inline-flex min-h-11 items-center justify-center gap-2 rounded-full px-5 text-caption ${mode === value ? 'bg-surface font-semibold text-ink shadow-soft' : 'text-ink-muted'}`}
            >
              <img src={icon} alt="" />
              {label}
            </button>
          ))}
        </div>
        {mode === 'map' && (
          <div className="flex items-center gap-1.5" role="group" aria-label="Thu phóng sơ đồ">
            <Button
              variant="secondary"
              aria-label="Phóng to sơ đồ"
              disabled={zoom >= 2}
              onClick={() => setZoom(Math.min(2, zoom + 0.25))}
            >
              <img src={addIcon} alt="" />
            </Button>
            <Button variant="secondary" onClick={() => setZoom(1)} title="Thu vừa khung">
              {Math.round(zoom * 100)}%
            </Button>
            <Button
              variant="secondary"
              icon={Minus}
              aria-label="Thu nhỏ sơ đồ"
              disabled={zoom <= 1}
              onClick={() => setZoom(Math.max(1, zoom - 0.25))}
            />
          </div>
        )}
      </div>
      {mode === 'map' ? (
        <Floor layout={view.layout} geometry={geometry} zoom={zoom}>
          {view.tables.map((table) => (
            <RoundTable
              key={table.id}
              table={table}
              geometry={geometry}
              openTable={() => setTableId(table.id)}
              {...shared}
            />
          ))}
        </Floor>
      ) : (
        <>
          <div className="flex flex-wrap gap-2" role="group" aria-label="Lọc bàn">
            {[
              ['all', GALA_UI.all],
              ['available', GALA_UI.available],
              ['vip', GALA_UI.vip],
            ].map(([value, label]) => (
              <button
                type="button"
                key={value}
                aria-pressed={filter === value}
                onClick={() => setFilter(value)}
                className={`min-h-11 rounded-md border px-3 text-caption ${filter === value ? 'border-primary bg-primary text-on-primary' : 'border-hairline bg-surface text-ink-secondary'}`}
              >
                {label}
              </button>
            ))}
          </div>
          {tables.length ? (
            tables.map((table) => (
              <TableCard key={table.id} table={table} onTableClick={onTableClick} {...shared} />
            ))
          ) : (
            <p className="py-6 text-center text-caption text-ink-muted">
              Không có bàn phù hợp bộ lọc.
            </p>
          )}
        </>
      )}
      {detail && (
        <Modal
          open
          title={`Bàn ${detail.table_code}`}
          description="Chọn ghế để xem chi tiết hoặc thao tác"
          onClose={() => setTableId(null)}
        >
          <TableCard table={detail} onTableClick={onTableClick} {...shared} />
        </Modal>
      )}
    </div>
  )
}

function Floor({ layout, geometry, zoom, children }) {
  const frameRef = useRef(null)
  const [available, setAvailable] = useState({ width: 0, height: 0 })
  const { width, height } = geometry
  const vertical = ['left', 'right'].includes(layout.stage_position)
  const first = ['top', 'left'].includes(layout.stage_position)
  const naturalWidth = width + (vertical ? STAGE_SPACE : 0)
  const naturalHeight = height + (vertical ? 0 : STAGE_SPACE)
  useEffect(() => {
    const frame = frameRef.current
    if (!frame) return undefined
    // Khung cao tối đa 70% màn hình (khớp class max-h bên dưới): sơ đồ nhiều hàng bàn hay đang phóng to
    // thì cuộn trong khung, không đẩy cả trang dài ra.
    const measure = () =>
      setAvailable({
        width: frame.clientWidth - FLOOR_PADDING,
        height: Math.max(MIN_FLOOR_HEIGHT, window.innerHeight * MAX_FLOOR_RATIO) - FLOOR_PADDING,
      })
    measure()
    window.addEventListener('resize', measure)
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(measure)
    observer?.observe(frame)
    return () => {
      window.removeEventListener('resize', measure)
      observer?.disconnect()
    }
  }, [])
  // Thu vừa cả hai chiều, nhưng chiều cao không ép nhỏ hơn MIN_FIT_SCALE: ghế bé quá thì không bấm được,
  // lúc đó để cuộn dọc trong khung.
  const fit = available.width
    ? Math.min(
        1,
        available.width / naturalWidth,
        Math.max(MIN_FIT_SCALE, available.height / naturalHeight),
      )
    : 1
  const scale = fit * zoom
  const stage = (
    <div
      className={`grid shrink-0 place-items-center rounded-md bg-ink-secondary text-xs font-semibold tracking-[2px] text-on-primary ${vertical ? 'w-10 [writing-mode:vertical-rl]' : 'h-10 w-full'}`}
    >
      SÂN KHẤU
    </div>
  )
  return (
    <div
      ref={frameRef}
      data-gala-floor
      className="max-h-[max(70vh,360px)] max-w-full overflow-auto overscroll-contain rounded-lg border border-hairline bg-surface p-3"
    >
      <div
        className="mx-auto"
        style={{ width: naturalWidth * scale, height: naturalHeight * scale }}
      >
        <div
          className={`flex origin-top-left gap-3 ${vertical ? 'flex-row' : 'flex-col'}`}
          style={{ width: naturalWidth, height: naturalHeight, transform: `scale(${scale})` }}
        >
          {first && stage}
          <div className="relative shrink-0" style={{ width, height }}>
            {children}
          </div>
          {!first && stage}
        </div>
      </div>
    </div>
  )
}

function RoundTable({ table, geometry, openTable, ...shared }) {
  const radius = Math.max(62, (table.seat_count * 30) / (2 * Math.PI))
  const box = radius * 2 + SEAT_SIZE
  return (
    <div
      className="absolute"
      style={{
        left: (table.pos_x + 0.5) * CELL - geometry.left - box / 2,
        top: (table.pos_y + 0.5) * CELL - geometry.top - box / 2,
        width: box,
        height: box,
      }}
    >
      <button
        type="button"
        onClick={openTable}
        aria-label={`Xem bàn ${table.table_code}`}
        className={`absolute top-1/2 left-1/2 flex -translate-x-1/2 -translate-y-1/2 flex-col items-center justify-center rounded-full border border-hairline text-ink ${table.is_available ? 'bg-canvas-soft' : 'bg-hairline'} hover:border-primary`}
        style={{ width: TABLE_SIZE, height: TABLE_SIZE }}
      >
        <span className="flex items-center gap-1 text-xs font-semibold">
          {table.is_vip && <Crown className="size-3 text-accent-orange" />}
          {table.table_code}
        </span>
        <span className="text-[10px] text-ink-muted">{table.available_seats} trống</span>
      </button>
      {table.seats.map((seat, index) => {
        const angle = -Math.PI / 2 + (index * 2 * Math.PI) / table.seats.length
        return (
          <Seat
            key={seat.id}
            seat={seat}
            table={table}
            {...shared}
            compact
            style={{
              left: box / 2 + radius * Math.cos(angle) - SEAT_SIZE / 2,
              top: box / 2 + radius * Math.sin(angle) - SEAT_SIZE / 2,
              width: SEAT_SIZE,
              height: SEAT_SIZE,
            }}
          />
        )
      })}
    </div>
  )
}

function TableCard({ table, onTableClick, ...shared }) {
  const held = table.seats.filter((seat) => seat.state === 'held_by_me').length
  return (
    <section className="rounded-lg border border-hairline bg-surface p-4">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="grid size-11 shrink-0 place-items-center rounded-full bg-ink-secondary text-caption font-semibold text-on-primary">
            {table.table_code.replace(/^B/, '')}
          </span>
          <div>
            <h3 className="text-body-md font-semibold text-ink">
              Bàn {table.table_code}
              {table.table_name ? ` · ${table.table_name}` : ''}
              {table.is_vip ? ' · VIP' : ''}
            </h3>
            <p className="text-caption text-ink-muted">
              {table.available_seats} ghế trống{held > 0 ? ` · team bạn giữ ${held}` : ''}
              {!table.is_available ? ' · bàn không dùng' : ''}
            </p>
          </div>
        </div>
        {onTableClick && (
          <Button variant="ghost" onClick={() => onTableClick(table)}>
            Sửa bàn
          </Button>
        )}
      </div>
      <div className="grid grid-cols-5 gap-2 sm:grid-cols-8">
        {table.seats.map((seat) => (
          <Seat key={seat.id} seat={seat} table={table} {...shared} />
        ))}
      </div>
    </section>
  )
}

function Seat({
  seat,
  table,
  selected,
  myTeamId,
  locatedSeats,
  onSeatClick,
  isSeatClickable,
  onMemberDrop,
  disabled,
  compact = false,
  style,
}) {
  const chosen = selected.has(seat.id)
  const mine = myTeamId != null && seat.team_id === myTeamId
  const located = locatedSeats.has(seat.id)
  const visual = seatVisual(seat.state, { selected: chosen, mine, teamId: seat.team_id })
  const clickable =
    !disabled && (isSeatClickable ? isSeatClickable(seat, table) : Boolean(onSeatClick))
  const droppable = !disabled && onMemberDrop && seat.state === 'taken' && mine
  const label = [
    `Bàn ${table.table_code}, ghế ${seat.seat_number}`,
    GALA_SEAT_STATE_LABELS[chosen ? 'selected' : seat.state],
    mine ? `${seat.team_name} (team bạn)` : seat.team_name,
    seat.occupant_name,
    located && 'ĐANG TRA CỨU',
  ]
    .filter(Boolean)
    .join(' · ')
  return (
    <button
      type="button"
      ref={located ? scrollIntoView : undefined}
      aria-label={label}
      aria-pressed={seat.state === 'available' ? chosen : undefined}
      title={label}
      disabled={!clickable && !droppable}
      onClick={() => onSeatClick?.(seat, table)}
      onDragOver={
        droppable
          ? (event) => {
              event.preventDefault()
              event.dataTransfer.dropEffect = 'move'
            }
          : undefined
      }
      onDrop={
        droppable
          ? (event) => {
              event.preventDefault()
              const id = Number(event.dataTransfer.getData('application/x-gala-member'))
              if (Number.isInteger(id) && id > 0) onMemberDrop(id, seat)
            }
          : undefined
      }
      className={`grid place-items-center font-semibold tabular-nums transition disabled:cursor-default ${compact ? 'absolute rounded-full text-[9px]' : 'min-h-11 rounded-md text-caption'} ${clickable ? 'cursor-pointer hover:ring-2 hover:ring-primary/40' : ''} ${visual.className} ${located ? 'ring-4 ring-rose-500 ring-offset-2' : ''}`}
      style={style}
    >
      {seat.state === 'held_by_me' || chosen ? (
        <img src={checkIcon} alt="" />
      ) : seat.state === 'held_by_other' ? (
        <img src={lockIcon} alt="" />
      ) : compact ? (
        <span className="sr-only">{seat.seat_number}</span>
      ) : (
        seat.seat_number
      )}
    </button>
  )
}
