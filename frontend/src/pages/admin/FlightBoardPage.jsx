import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertTriangle,
  ArrowLeft,
  ChevronDown,
  ChevronRight,
  GripVertical,
  Lock,
  UserMinus,
} from 'lucide-react'
import {
  useAssignments,
  useBulkMove,
  useFlights,
  useRemoveAssignment,
} from '../../hooks/useFlights'
import { useParticipants, useRegistrationFormOptions } from '../../hooks/useRegistration'
import { useToast } from '../../context/ToastContext'
import { FLIGHT_DIRECTION_LABELS, FLIGHT_DIRECTIONS } from '../../utils/constants'
import { formatShortDateTime } from '../../utils/format'
import Alert from '../../components/common/Alert'
import Badge from '../../components/common/Badge'
import Button from '../../components/common/Button'
import PageHeader from '../../components/common/PageHeader'
import SlotBar from '../../components/admin/SlotBar'
import Spinner from '../../components/common/Spinner'
import MoveDialog from './flights/MoveDialog'

const UNASSIGNED = 'unassigned'

/**
 * Bảng điều chỉnh phân bổ: mỗi cột là một chuyến, mỗi thẻ là một team.
 *
 * Kéo-thả dùng HTML5 drag & drop (không thêm thư viện), nhưng **mọi thẻ cũng có nút
 * "Chuyển"** — DnD của HTML5 không chạy trên cảm ứng, mà BTC hay ngồi sửa trên iPad.
 * Cột nào không đủ chỗ thì chuyển đỏ và không nhận thả; kèm số "đã xếp/ghế" vì màu không
 * được là dấu hiệu duy nhất.
 */
export default function FlightBoardPage() {
  const toast = useToast()
  const [direction, setDirection] = useState(FLIGHT_DIRECTIONS.OUTBOUND)
  const [dragging, setDragging] = useState(null)
  const [hoverColumn, setHoverColumn] = useState(null)
  const [pendingMove, setPendingMove] = useState(null)

  const { data: options } = useRegistrationFormOptions()
  const { data: flights, isLoading: loadingFlights } = useFlights({ direction, is_active: true })
  const { data: assignmentPage, isLoading: loadingAssignments } = useAssignments({
    direction,
    page_size: 200,
  })
  const { data: participantPage, isLoading: loadingParticipants } = useParticipants()

  const { mutateAsync: bulkMove, isPending: isMoving } = useBulkMove()
  const { mutateAsync: unassign } = useRemoveAssignment()

  const teamColors = useMemo(
    () => Object.fromEntries((options?.teams ?? []).map((team) => [team.id, team.color])),
    [options],
  )

  const columns = useMemo(
    () => buildColumns({ flights, assignmentPage, participantPage }),
    [flights, assignmentPage, participantPage],
  )

  if (loadingFlights || loadingAssignments || loadingParticipants) {
    return <Spinner label="Đang tải bảng phân bổ…" />
  }

  function startDrag(payload) {
    setDragging(payload)
  }

  function canAccept(column) {
    if (!dragging || column.id === dragging.columnId) return false
    if (column.id === UNASSIGNED) return false
    return column.flight.remaining_slots >= dragging.people.length
  }

  function handleDrop(column) {
    if (!canAccept(column)) return
    setPendingMove({
      people: dragging.people,
      sourceLabel: dragging.sourceLabel,
      targetFlight: column.flight,
    })
    setDragging(null)
    setHoverColumn(null)
  }

  async function confirmMove({ flightId, reason, registrationIds }) {
    try {
      const result = await bulkMove({ registrationIds, flightId, reason })
      const warnings = result.warnings ?? []
      toast.success(
        `Đã chuyển ${result.moved + result.created} người.` +
          (warnings.length ? ` ${warnings.length} cảnh báo.` : ''),
      )
      warnings.slice(0, 3).forEach((warning) => toast.warning(warning.message))
      setPendingMove(null)
    } catch (error) {
      toast.error(error.message)
    }
  }

  async function removeFromFlight(person) {
    try {
      await unassign({
        assignmentId: person.assignment_id,
        reason: 'BTC bỏ phân bổ từ bảng điều chỉnh',
      })
      toast.success(`Đã bỏ phân bổ của ${person.full_name}.`)
    } catch (error) {
      toast.error(error.message)
    }
  }

  const movableFlights = (flights ?? []).filter((flight) => flight.remaining_slots > 0)

  return (
    <>
      <PageHeader
        title="Bảng điều chỉnh chuyến bay"
        description="Kéo thẻ team sang chuyến khác, hoặc bấm Chuyển trên từng thẻ"
        action={
          <div className="flex flex-wrap gap-2">
            <Link to="/admin/flights">
              <Button variant="secondary" icon={ArrowLeft}>
                Về quản lý chuyến bay
              </Button>
            </Link>
            <div className="flex gap-1 rounded-lg border border-slate-200 bg-white p-1">
              {Object.entries(FLIGHT_DIRECTION_LABELS).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setDirection(value)}
                  className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
                    direction === value
                      ? 'bg-brand-600 text-white'
                      : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        }
      />

      {columns.length === 1 && (
        <Alert tone="warning" className="mb-4" title="Chưa có chuyến bay nào cho chiều này">
          Thêm chuyến ở trang quản lý chuyến bay trước khi điều chỉnh.
        </Alert>
      )}

      {/* Cuộn ngang: nhiều chuyến thì không nên co cột lại đến mức không đọc được */}
      <div className="-mx-4 overflow-x-auto px-4 pb-2 sm:mx-0 sm:px-0">
        <div className="flex min-w-max gap-3">
          {columns.map((column) => (
            <BoardColumn
              key={column.id}
              column={column}
              teamColors={teamColors}
              dragging={dragging}
              accepts={canAccept(column)}
              isHovered={hoverColumn === column.id}
              onDragEnter={() => setHoverColumn(column.id)}
              onDragLeaveColumn={() => setHoverColumn((current) => (current === column.id ? null : current))}
              onDrop={() => handleDrop(column)}
              onStartDrag={startDrag}
              onRequestMove={(people, sourceLabel) =>
                setPendingMove({ people, sourceLabel, targetFlight: null })
              }
              onRemove={removeFromFlight}
            />
          ))}
        </div>
      </div>

      <MoveDialog
        open={Boolean(pendingMove)}
        onClose={() => setPendingMove(null)}
        onConfirm={confirmMove}
        people={pendingMove?.people ?? []}
        sourceLabel={pendingMove?.sourceLabel}
        targetFlight={pendingMove?.targetFlight}
        flightOptions={movableFlights}
        pending={isMoving}
      />
    </>
  )
}

/* --- Một cột = một chuyến (hoặc nhóm chưa xếp) --- */
function BoardColumn({
  column,
  teamColors,
  dragging,
  accepts,
  isHovered,
  onDragEnter,
  onDragLeaveColumn,
  onDrop,
  onStartDrag,
  onRequestMove,
  onRemove,
}) {
  const isUnassigned = column.id === UNASSIGNED
  const blocked = Boolean(dragging) && !accepts && dragging.columnId !== column.id

  return (
    <section
      onDragEnter={onDragEnter}
      onDragOver={(event) => {
        // Chỉ preventDefault khi cột nhận được — nếu không, trình duyệt hiện con trỏ "cấm".
        if (accepts) event.preventDefault()
      }}
      onDragLeave={onDragLeaveColumn}
      onDrop={(event) => {
        event.preventDefault()
        onDrop()
      }}
      className={`flex w-72 shrink-0 flex-col rounded-xl border-2 bg-white transition ${
        isHovered && accepts
          ? 'border-brand-500 bg-brand-50/40'
          : isHovered && blocked
            ? 'border-rose-400 bg-rose-50/40'
            : 'border-slate-200'
      }`}
    >
      <header className="border-b border-slate-100 px-3 py-2.5">
        {isUnassigned ? (
          <p className="flex items-center gap-2 text-sm font-semibold text-slate-900">
            <AlertTriangle className="size-4 text-amber-600" aria-hidden="true" />
            Chưa có chỗ
            <Badge tone={column.people.length ? 'rose' : 'slate'}>{column.people.length}</Badge>
          </p>
        ) : (
          <>
            <div className="flex items-baseline justify-between gap-2">
              <p className="truncate text-sm font-semibold text-slate-900">
                {column.flight.flight_code}
              </p>
              <p className="shrink-0 text-xs text-slate-500">
                {column.flight.shift_code ?? 'chưa gán ca'}
              </p>
            </div>
            <p className="mt-0.5 text-xs text-slate-500 tabular-nums">
              {column.flight.departure_airport} → {column.flight.arrival_airport} ·{' '}
              {formatShortDateTime(column.flight.departure_time)}
            </p>
            <SlotBar
              assigned={column.flight.assigned_count}
              usable={column.flight.usable_capacity}
              className="mt-2"
            />
            {blocked && isHovered && (
              <p className="mt-1.5 text-xs font-medium text-rose-700">
                Không đủ chỗ cho {dragging.people.length} người
              </p>
            )}
          </>
        )}
      </header>

      <div className="flex flex-1 flex-col gap-2 p-2">
        {column.teams.length === 0 && (
          <p className="px-1 py-4 text-center text-xs text-slate-400">
            {isUnassigned ? 'Mọi người đều đã có chỗ' : 'Chưa có ai trên chuyến này'}
          </p>
        )}

        {column.teams.map((team) => (
          <TeamCard
            key={`${column.id}-${team.teamId ?? 'none'}`}
            column={column}
            team={team}
            color={teamColors[team.teamId]}
            onStartDrag={onStartDrag}
            onRequestMove={onRequestMove}
            onRemove={onRemove}
            allowRemove={!isUnassigned}
          />
        ))}
      </div>
    </section>
  )
}

/* --- Thẻ team: kéo được cả thẻ, mở ra kéo được từng người --- */
function TeamCard({ column, team, color, onStartDrag, onRequestMove, onRemove, allowRemove }) {
  const [open, setOpen] = useState(false)
  const Chevron = open ? ChevronDown : ChevronRight
  const sourceLabel = column.id === UNASSIGNED ? 'Chưa có chỗ' : column.flight.flight_code

  return (
    <article
      draggable
      onDragStart={() =>
        onStartDrag({ columnId: column.id, people: team.people, sourceLabel })
      }
      className="cursor-grab rounded-lg border border-slate-200 bg-white p-2.5 active:cursor-grabbing"
    >
      <div className="flex items-start gap-2">
        <GripVertical className="mt-0.5 size-4 shrink-0 text-slate-300" aria-hidden="true" />
        <span
          className="mt-1 size-2.5 shrink-0 rounded-full"
          style={{ backgroundColor: color || '#cbd5e1' }}
          aria-hidden="true"
        />
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          className="min-w-0 flex-1 text-left"
          aria-expanded={open}
        >
          <span className="flex items-center gap-1">
            <Chevron className="size-3.5 shrink-0 text-slate-400" aria-hidden="true" />
            <span className="truncate text-sm font-medium text-slate-900">{team.teamName}</span>
          </span>
          <span className="mt-0.5 block text-xs text-slate-500">
            {team.people.length} người
            {team.manualCount > 0 && ` · ${team.manualCount} xếp tay`}
            {team.mismatchCount > 0 && ` · ${team.mismatchCount} lệch ca`}
          </span>
        </button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onRequestMove(team.people, sourceLabel)}
        >
          Chuyển
        </Button>
      </div>

      {open && (
        <ul className="mt-2 flex flex-col gap-1 border-t border-slate-100 pt-2">
          {team.people.map((person) => (
            <li
              key={person.registration_id}
              draggable
              onDragStart={(event) => {
                event.stopPropagation()
                onStartDrag({ columnId: column.id, people: [person], sourceLabel })
              }}
              className="flex items-center gap-1.5 rounded-md px-1 py-1 text-xs hover:bg-slate-50"
            >
              <span className="min-w-0 flex-1 truncate text-slate-700">
                {person.full_name}
                {person.shift_locked && (
                  <Lock className="ml-1 inline size-3 text-slate-400" aria-label="Khoá ca" />
                )}
                {!person.has_flight_documents && (
                  <AlertTriangle
                    className="ml-1 inline size-3 text-amber-600"
                    aria-label="Thiếu giấy tờ"
                  />
                )}
              </span>
              {person.shift_mismatch && <Badge tone="amber">lệch ca</Badge>}
              <button
                type="button"
                onClick={() => onRequestMove([person], sourceLabel)}
                className="rounded px-1 text-brand-700 hover:underline"
              >
                chuyển
              </button>
              {allowRemove && (
                <button
                  type="button"
                  onClick={() => onRemove(person)}
                  className="rounded p-0.5 text-slate-400 hover:text-rose-600"
                  aria-label={`Bỏ phân bổ của ${person.full_name}`}
                  title="Bỏ phân bổ"
                >
                  <UserMinus className="size-3.5" />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </article>
  )
}

/**
 * Dựng cột từ 3 nguồn: chuyến bay, phân bổ hiện tại, và danh sách tham gia.
 *
 * Cột "Chưa có chỗ" = người tham gia trừ người đã có phân bổ ở chiều này. Thiếu cột này thì
 * những người bị flag UNASSIGNED không có cách nào xếp bằng tay.
 */
function buildColumns({ flights, assignmentPage, participantPage }) {
  const assignments = assignmentPage?.items ?? []
  const participants = participantPage?.items ?? []
  const assignedIds = new Set(assignments.map((row) => row.registration_id))

  const unassignedPeople = participants
    .filter((registration) => !assignedIds.has(registration.id))
    .map((registration) => ({
      registration_id: registration.id,
      assignment_id: null,
      full_name: registration.user.full_name,
      team_id: registration.user.team_id,
      team_name: registration.user.team_name ?? 'Chưa có team',
      shift_mismatch: false,
      shift_locked: false,
      has_flight_documents: registration.user.can_fly,
      assignment_mode: null,
    }))

  const columns = [
    {
      id: UNASSIGNED,
      flight: null,
      people: unassignedPeople,
      teams: groupByTeam(unassignedPeople),
    },
  ]

  for (const flight of flights ?? []) {
    const people = assignments
      .filter((row) => row.flight_id === flight.id)
      .map((row) => ({
        registration_id: row.registration_id,
        assignment_id: row.id,
        full_name: row.full_name,
        team_id: row.team_id,
        team_name: row.team_name ?? 'Chưa có team',
        shift_mismatch: row.shift_mismatch,
        shift_locked: row.shift_locked,
        has_flight_documents: row.has_flight_documents,
        assignment_mode: row.assignment_mode,
      }))

    columns.push({ id: `flight-${flight.id}`, flight, people, teams: groupByTeam(people) })
  }

  return columns
}

function groupByTeam(people) {
  const byTeam = new Map()
  for (const person of people) {
    const key = person.team_id ?? 'none'
    const group = byTeam.get(key)
    if (group) {
      group.people.push(person)
    } else {
      byTeam.set(key, {
        teamId: person.team_id,
        teamName: person.team_name,
        people: [person],
      })
    }
  }

  return [...byTeam.values()]
    .map((group) => ({
      ...group,
      manualCount: group.people.filter((person) => person.assignment_mode === 'manual').length,
      mismatchCount: group.people.filter((person) => person.shift_mismatch).length,
    }))
    .sort((left, right) => right.people.length - left.people.length)
}
