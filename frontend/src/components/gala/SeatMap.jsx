import { Crown, Lock } from 'lucide-react'
import { GALA_SEAT_STATE_LABELS } from '../../utils/constants'
import { seatVisual } from '../../utils/gala'

const CELL = 64
const PAD = 48
const TABLE_SIZE = 60
const SEAT_SIZE = 24

/**
 * Sơ đồ bàn tròn trên lưới toạ độ của BTC (docs/07 §3.4) + danh sách dạng thẻ cho màn hình hẹp.
 *
 * Trạng thái ghế không chỉ phân biệt bằng màu: ghế đang giữ viền đứt, ghế đã có team tô kín,
 * ghế khoá có sọc và gạch ngang; mỗi ghế có `aria-label` đọc đủ bàn, số ghế, trạng thái.
 */
export default function SeatMap({ view, selectedIds = [], myTeamId, onSeatClick, onTableClick, isSeatClickable }) {
  const selected = new Set(selectedIds)
  const shared = { selected, myTeamId, onSeatClick, isSeatClickable }

  return (
    <>
      <div className="hidden sm:block">
        <Floor layout={view.layout}>
          {view.tables.map((table) => (
            <RoundTable key={table.id} table={table} onTableClick={onTableClick} {...shared} />
          ))}
        </Floor>
      </div>
      <div className="flex flex-col gap-2.5 sm:hidden">
        {view.tables.map((table) => (
          <TableCard key={table.id} table={table} onTableClick={onTableClick} {...shared} />
        ))}
      </div>
    </>
  )
}

function Floor({ layout, children }) {
  const width = layout.grid_width * CELL + PAD * 2
  const height = layout.grid_height * CELL + PAD * 2
  const vertical = layout.stage_position === 'left' || layout.stage_position === 'right'
  const stageFirst = layout.stage_position === 'top' || layout.stage_position === 'left'

  const stage = (
    <div
      className={`grid shrink-0 place-items-center rounded-lg bg-slate-800 text-xs font-semibold tracking-widest text-white uppercase ${
        vertical ? 'w-10 [writing-mode:vertical-rl]' : 'h-10'
      }`}
    >
      Sân khấu
    </div>
  )

  return (
    <div className="overflow-auto rounded-lg bg-slate-50 p-3 ring-1 ring-slate-200 ring-inset">
      <div className={`flex w-max gap-3 ${vertical ? 'flex-row' : 'flex-col'}`}>
        {stageFirst && stage}
        <div className="relative" style={{ width, height }}>
          {children}
        </div>
        {!stageFirst && stage}
      </div>
    </div>
  )
}

function RoundTable({ table, selected, myTeamId, onSeatClick, onTableClick, isSeatClickable }) {
  const radius = Math.max(TABLE_SIZE / 2 + SEAT_SIZE / 2 + 4, (table.seat_count * (SEAT_SIZE + 4)) / (2 * Math.PI))
  const box = radius * 2 + SEAT_SIZE
  const TableTag = onTableClick ? 'button' : 'div'

  return (
    <div
      className="absolute"
      style={{
        left: PAD + (table.pos_x + 0.5) * CELL - box / 2,
        top: PAD + (table.pos_y + 0.5) * CELL - box / 2,
        width: box,
        height: box,
      }}
    >
      <TableTag
        {...(onTableClick ? { type: 'button', onClick: () => onTableClick(table), title: `Sửa bàn ${table.table_code}` } : {})}
        className={`absolute top-1/2 left-1/2 flex -translate-x-1/2 -translate-y-1/2 flex-col items-center justify-center rounded-full text-center ring-1 ${
          table.is_available ? 'bg-white ring-slate-300' : 'bg-slate-200 ring-slate-300'
        } ${onTableClick ? 'transition hover:ring-2 hover:ring-brand-500' : ''}`}
        style={{ width: TABLE_SIZE, height: TABLE_SIZE }}
      >
        <span className="flex items-center gap-0.5 text-xs font-bold text-slate-900">
          {table.is_vip && <Crown className="size-3 text-amber-500" aria-label="Bàn VIP" />}
          {!table.is_available && <Lock className="size-3 text-slate-500" aria-label="Bàn đang khoá" />}
          {table.table_code}
        </span>
        <span className="text-[10px] text-slate-500 tabular-nums">
          {table.available_seats}/{table.seat_count} trống
        </span>
      </TableTag>

      {table.seats.map((seat, index) => {
        const angle = -Math.PI / 2 + (index * 2 * Math.PI) / table.seats.length
        return (
          <Seat
            key={seat.id}
            seat={seat}
            table={table}
            selected={selected.has(seat.id)}
            mine={myTeamId != null && seat.team_id === myTeamId}
            onSeatClick={onSeatClick}
            clickable={isSeatClickable ? isSeatClickable(seat, table) : Boolean(onSeatClick)}
            className="absolute size-6 text-[10px]"
            style={{
              left: box / 2 + radius * Math.cos(angle) - SEAT_SIZE / 2,
              top: box / 2 + radius * Math.sin(angle) - SEAT_SIZE / 2,
            }}
          />
        )
      })}
    </div>
  )
}

function TableCard({ table, selected, myTeamId, onSeatClick, onTableClick, isSeatClickable }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 text-sm font-semibold text-slate-900">
          {table.is_vip && <Crown className="size-3.5 text-amber-500" aria-label="Bàn VIP" />}
          {!table.is_available && <Lock className="size-3.5 text-slate-500" aria-label="Bàn đang khoá" />}
          {table.table_code}
          {table.table_name && <span className="font-normal text-slate-500">· {table.table_name}</span>}
        </p>
        {onTableClick ? (
          <button type="button" onClick={() => onTableClick(table)} className="text-xs font-medium text-brand-700">
            Sửa bàn
          </button>
        ) : (
          <span className="text-xs text-slate-500 tabular-nums">
            {table.available_seats}/{table.seat_count} trống
          </span>
        )}
      </div>
      <div className="flex flex-wrap gap-1.5">
        {table.seats.map((seat) => (
          <Seat
            key={seat.id}
            seat={seat}
            table={table}
            selected={selected.has(seat.id)}
            mine={myTeamId != null && seat.team_id === myTeamId}
            onSeatClick={onSeatClick}
            clickable={isSeatClickable ? isSeatClickable(seat, table) : Boolean(onSeatClick)}
            className="size-9 text-xs"
          />
        ))}
      </div>
    </div>
  )
}

function Seat({ seat, table, selected, mine, onSeatClick, clickable, className = '', style = {} }) {
  const visual = seatVisual(seat.state, { selected, teamColor: seat.team_color })
  const stateLabel = selected && seat.state === 'available' ? GALA_SEAT_STATE_LABELS.selected : GALA_SEAT_STATE_LABELS[seat.state]
  const label = [
    `Bàn ${table.table_code}, ghế ${seat.seat_number}`,
    stateLabel,
    seat.team_name,
    seat.occupant_name,
  ]
    .filter(Boolean)
    .join(' · ')

  return (
    <button
      type="button"
      aria-label={label}
      aria-pressed={seat.state === 'available' ? selected : undefined}
      title={label}
      disabled={!clickable}
      onClick={() => onSeatClick?.(seat, table)}
      className={`grid place-items-center rounded-full font-semibold tabular-nums transition disabled:cursor-default ${
        clickable ? 'cursor-pointer hover:scale-110 focus-visible:outline-2 focus-visible:outline-brand-600' : ''
      } ${mine && seat.state === 'taken' ? 'ring-2 ring-slate-900 ring-offset-1' : ''} ${visual.className} ${className}`}
      style={{ ...visual.style, ...style }}
    >
      {seat.seat_number}
    </button>
  )
}
