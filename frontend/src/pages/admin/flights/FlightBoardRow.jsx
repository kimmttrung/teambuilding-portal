import { useState } from 'react'
import { ChevronDown, ChevronRight, GripVertical, Lock, UserMinus, Users } from 'lucide-react'
import { formatTime } from '../../../utils/format'
import Button from '../../../components/common/Button'
import { groupTeams, teamColor } from './boardData'

export default function FlightBoardRow({
  flight,
  people,
  first,
  selection,
  target,
  locatedId,
  disabled,
  accepts,
  hovered,
  onHover,
  onDragOver,
  onDrop,
  onDrag,
  onDragEnd,
  onSelect,
  onTarget,
  onMove,
  onPassengers,
  onRemove,
}) {
  const [expanded, setExpanded] = useState(first)
  const [openTeams, setOpenTeams] = useState({})
  const teams = groupTeams(people)
  const containsLocated = people.some((p) => p.registration_id === locatedId)
  const visible = expanded || containsLocated
  const selectedIds = new Set(selection?.people.map((p) => p.registration_id) ?? [])
  return (
    <article
      onDragEnter={onHover}
      onDragOver={onDragOver}
      onDrop={onDrop}
      className={`rounded-lg border bg-surface p-4 transition ${target || (hovered && accepts) || containsLocated ? 'border-primary ring-2 ring-primary/10' : 'border-hairline'} ${!flight.is_active ? 'opacity-70' : ''}`}
    >
      <div className="flex flex-wrap items-center gap-4">
        <button
          type="button"
          className="min-h-11 min-w-36 text-left"
          onClick={onTarget}
          disabled={!selection || disabled}
          aria-label={`Chọn chuyến đích ${flight.flight_code}`}
        >
          <span className="text-body-md font-bold">{flight.flight_code}</span>
          <span className="ml-2 rounded-xs bg-black/5 px-2 py-1 text-eyebrow text-ink-muted">
            {flight.shift_code ?? 'Chưa gán ca'}
          </span>
          <span className="mt-1 block text-caption text-ink-muted">
            {formatTime(flight.departure_time)} · {flight.departure_airport} →{' '}
            {flight.arrival_airport}
          </span>
          {!flight.is_active && <span className="text-caption text-ink-muted">Ngừng dùng</span>}
        </button>
        <div
          className="flex h-8 min-w-40 flex-1 overflow-hidden rounded-sm bg-canvas-soft"
          aria-label={`${flight.assigned_count}/${flight.usable_capacity} ghế đã xếp`}
        >
          {teams.map((team) => (
            <div
              key={team.key}
              className="flex min-w-0 items-center border-r border-surface px-2 text-eyebrow text-on-primary"
              title={`${team.name}: ${team.people.length} người`}
              style={{
                width: `${Math.min(100, (team.people.length / Math.max(flight.usable_capacity, 1)) * 100)}%`,
                backgroundColor: teamColor(team.color),
              }}
            >
              <span className="truncate">
                {team.name} {team.people.length}
              </span>
            </div>
          ))}
          {target && selection && (
            <div
              className="flex items-center justify-center border border-dashed border-primary bg-primary/5 text-caption font-semibold text-primary"
              style={{
                width: `${(selection.people.length / Math.max(flight.usable_capacity, 1)) * 100}%`,
              }}
            >
              +{selection.people.length}
            </div>
          )}
          <div className="flight-empty-seats flex-1" />
        </div>
        <div className="text-right">
          <p className="text-title tabular-nums">
            {flight.assigned_count}
            <span className="text-ink-faint">/{flight.usable_capacity}</span>
          </p>
          <p className="text-caption text-ink-muted">còn {flight.remaining_slots} chỗ</p>
        </div>
        <button
          type="button"
          className="flex size-11 items-center justify-center rounded-md hover:bg-canvas-soft"
          aria-label={`${visible ? 'Thu gọn' : 'Mở'} chuyến ${flight.flight_code}`}
          aria-expanded={visible}
          onClick={() => setExpanded(!visible)}
        >
          {visible ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
        </button>
      </div>
      {hovered && !accepts && selection && (
        <p className="mt-2 text-caption text-ink-muted">Kiểm tra chuyến đích và số ghế còn lại.</p>
      )}
      {visible && (
        <div className="mt-4 border-t border-hairline pt-4">
          {!people.length ? (
            <p className="text-caption text-ink-muted">Chưa có ai trên chuyến này.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {teams.map((team) => {
                const manual = team.people.filter((p) => p.assignment_mode === 'manual').length
                const teamOpen =
                  openTeams[team.key] || team.people.some((p) => p.registration_id === locatedId)
                return (
                  <div key={team.key} className="max-w-full rounded-md border border-hairline">
                    <div
                      draggable={!disabled}
                      onDragStart={(e) => onDrag(team.people, e)}
                      onDragEnd={onDragEnd}
                      className={`flex items-center gap-2 p-2 ${team.people.every((p) => selectedIds.has(p.registration_id)) ? 'bg-primary/5 ring-1 ring-primary' : ''}`}
                    >
                      <label className="flex min-h-11 sm:min-h-6 cursor-pointer items-center gap-2">
                        <input
                          type="checkbox"
                          className="size-4 accent-primary"
                          disabled={disabled}
                          checked={team.people.every((p) => selectedIds.has(p.registration_id))}
                          onChange={() => onSelect(team.people)}
                          aria-label={`Chọn team ${team.name} trên ${flight.flight_code}`}
                        />
                        <span
                          className="size-2 rounded-full"
                          style={{ backgroundColor: teamColor(team.color) }}
                        />
                      </label>
                      <button
                        type="button"
                        aria-expanded={Boolean(teamOpen)}
                        className="min-h-11 sm:min-h-6 min-w-0 text-left text-caption font-medium"
                        onClick={() => setOpenTeams({ ...openTeams, [team.key]: !teamOpen })}
                      >
                        {team.name} <span className="text-ink-faint">{team.people.length}</span>
                        {manual > 0 && (
                          <Lock
                            className="ml-1 inline size-3 text-ink-faint"
                            aria-label={`${manual} người chỉnh tay`}
                          />
                        )}
                      </button>
                      <GripVertical className="size-3 text-ink-faint" aria-hidden="true" />
                      <Button
                        variant="ghost"
                        size="sm"
                        className="min-h-11 sm:min-h-6 sm:px-2"
                        disabled={disabled}
                        onClick={() => onMove(team.people)}
                      >
                        Chuyển
                      </Button>
                    </div>
                    {teamOpen && (
                      <ul className="border-t border-hairline p-2">
                        {team.people.map((p) => (
                          <li
                            key={p.registration_id}
                            draggable={!disabled}
                            onDragStart={(e) => onDrag([p], e)}
                            onDragEnd={onDragEnd}
                            className={`flex items-center gap-2 rounded-sm p-1 ${p.registration_id === locatedId ? 'bg-primary/5 ring-1 ring-primary' : ''}`}
                          >
                            <span className="flex-1 text-caption">
                              {p.full_name}
                              {p.shift_mismatch && (
                                <span className="ml-1 text-ink-muted">· lệch ca</span>
                              )}
                              {p.assignment_mode === 'manual' && (
                                <Lock className="ml-1 inline size-3" aria-label="BTC chỉnh tay" />
                              )}
                            </span>
                            <Button
                              variant="ghost"
                              className="min-h-11"
                              disabled={disabled}
                              onClick={() => onMove([p])}
                            >
                              Chuyển
                            </Button>
                            <button
                              type="button"
                              className="flex size-11 items-center justify-center rounded-md text-ink-muted hover:bg-canvas-soft"
                              disabled={disabled}
                              aria-label={`Bỏ phân bổ của ${p.full_name}`}
                              onClick={() => onRemove(p)}
                            >
                              <UserMinus className="size-4" />
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )
              })}
            </div>
          )}
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
            <p className="text-caption text-ink-muted">
              <Lock className="mr-1 inline size-3" />
              BTC chỉnh tay, xếp lại không bị ghi đè
            </p>
            <Button variant="ghost" icon={Users} onClick={onPassengers}>
              Danh sách hành khách
            </Button>
          </div>
        </div>
      )}
    </article>
  )
}
