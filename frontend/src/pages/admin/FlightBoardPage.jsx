import { useCallback, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { AlertTriangle, ArrowRight, Plane, Play } from 'lucide-react'
import { useBulkMove, useFlightBoard, useRemoveAssignment } from '../../hooks/useFlights'
import { useActiveEvent } from '../../hooks/useEvent'
import { useToast } from '../../context/ToastContext'
import { usePersonLocation } from '../../hooks/usePeople'
import Alert from '../../components/common/Alert'
import Button from '../../components/common/Button'
import Card from '../../components/common/Card'
import EmptyState from '../../components/common/EmptyState'
import Modal from '../../components/common/Modal'
import Select from '../../components/common/Select'
import Spinner from '../../components/common/Spinner'
import Textarea from '../../components/common/Textarea'
import PersonLocator from '../../components/admin/PersonLocator'
import AllocationPreviewModal from './flights/AllocationPreviewModal'
import DirectionTabs from './flights/DirectionTabs'
import MoveDialog from './flights/MoveDialog'
import PassengersModal from './flights/PassengersModal'
import FlightBoardRow from './flights/FlightBoardRow'
import './flights/flights.css'
import { boardPeople, boardStats, groupTeams } from './flights/boardData'

export default function FlightBoardPage() {
  const event = useActiveEvent()
  const [search, setSearch] = useSearchParams()
  const direction = search.get('direction') === 'return' ? 'return' : 'outbound'
  if (event.isLoading) return <Spinner label="Đang tải kỳ…" />
  if (event.error) return <Alert tone="error">{event.error.message}</Alert>
  return (
    <Board
      key={`${event.data?.id}-${direction}`}
      event={event.data}
      direction={direction}
      onDirection={(value) => {
        const next = new URLSearchParams(search)
        next.set('direction', value)
        setSearch(next)
      }}
    />
  )
}

function Board({ event, direction, onDirection }) {
  const query = useFlightBoard(direction)
  const toast = useToast()
  const { location } = usePersonLocation()
  const [previewOpen, setPreviewOpen] = useState(false)
  const [selection, setSelection] = useState(null)
  const [targetId, setTargetId] = useState('')
  const [dragging, setDragging] = useState(null)
  const [hover, setHover] = useState(null)
  const [move, setMove] = useState(null)
  const [passengers, setPassengers] = useState(null)
  const [removing, setRemoving] = useState(null)
  const [reason, setReason] = useState('')
  const [moveError, setMoveError] = useState(null)
  const [showAll, setShowAll] = useState(false)
  const bulk = useBulkMove()
  const remove = useRemoveAssignment()
  const closeRemoval = useCallback(() => {
    if (!remove.isPending) setRemoving(null)
  }, [remove.isPending])
  const people = boardPeople(query.data)
  const flights = query.data?.flights ?? []
  const active = flights.filter((f) => f.is_active)
  const stats = boardStats(people, flights)
  const unassigned = people.filter((p) => !p.flight_id)
  const issues = [
    ...groupTeams(unassigned).map((team) => ({
      title: `${team.name} · ${team.people.length} người chưa xếp`,
      description: 'Chọn chuyến còn đủ chỗ để xếp cùng team hoặc đúng ca đăng ký.',
      people: team.people,
    })),
    ...people
      .filter((p) => p.shift_mismatch)
      .map((p) => ({
        title: `${p.full_name} muốn ${p.requested_shift_code ?? 'ca khác'}`,
        description: `Đang ở ${p.flight_code}${p.assignment_mode === 'manual' ? ' · BTC chỉnh tay' : ' · kiểm tra nguyện vọng ca'}`,
        people: [p],
      })),
  ]
  const transferFlights = (group) =>
    active.filter(
      (f) => group.every((p) => p.flight_id !== f.id) && f.remaining_slots >= group.length,
    )
  const target = active.find((f) => String(f.id) === targetId)
  const selectedPeople = selection
    ? selection.people
        .map((p) => people.find((live) => live.registration_id === p.registration_id))
        .filter(Boolean)
    : []
  const differentShift =
    target &&
    selectedPeople.some(
      (p) => p.requested_shift_id != null && p.requested_shift_id !== target.shift_id,
    )
  const pending = bulk.isPending || remove.isPending

  function requestMove(group, flight = null) {
    setMoveError(null)
    setMove({
      people: group,
      targetFlight: flight,
      sourceLabel: [...new Set(group.map((p) => p.flight_code ?? 'Chưa có chuyến'))].join(', '),
    })
  }
  async function confirmMove(payload) {
    try {
      setMoveError(null)
      const result = await bulk.mutateAsync(payload)
      toast.success(
        `Đã chuyển ${result.moved + result.created} người. Các phân bổ này được giữ khi chạy tự động.`,
      )
      result.warnings.forEach((warning) => toast.warning(warning.message))
      setMove(null)
      setSelection(null)
      setTargetId('')
    } catch (error) {
      setMoveError(error.message)
    }
  }
  function drop(flight) {
    if (!dragging || !transferFlights(dragging.people).some((f) => f.id === flight.id)) return
    requestMove(dragging.people, flight)
    setDragging(null)
    setHover(null)
  }

  if (previewOpen)
    return (
      <AllocationPreviewModal open direction={direction} onClose={() => setPreviewOpen(false)} />
    )
  return (
    <div className="space-y-6 text-ink">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-hairline pb-4">
        <div className="flex flex-wrap items-center gap-4">
          <h1 className="text-page-title text-ink">Chuyến bay</h1>
          <DirectionTabs
            value={direction}
            event={event}
            onChange={onDirection}
            disabled={pending}
          />
        </div>
        <div className="flex gap-2">
          <Link
            to={`/admin/flights?direction=${direction}`}
            className="inline-flex min-h-11 items-center gap-2 rounded-md border border-hairline bg-surface px-4 text-caption hover:bg-canvas-soft"
          >
            <Plane className="size-4" />
            Nguồn lực ({active.length} chuyến)
          </Link>
          <Button
            shape="pill"
            icon={Play}
            disabled={query.isLoading || Boolean(query.error) || pending || !active.length}
            onClick={() => setPreviewOpen(true)}
          >
            Chạy phân bổ thử
          </Button>
        </div>
      </header>
      <PersonLocator />
      {query.isLoading ? (
        <Spinner label="Đang tải toàn bộ bảng phân bổ…" />
      ) : query.error ? (
        <Alert tone="error" title="Không tải được board">
          {query.error.message}
          <div className="mt-3">
            <Button variant="secondary" onClick={() => query.refetch()}>
              Thử lại
            </Button>
          </div>
        </Alert>
      ) : (
        <>
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="mb-2 text-caption text-ink-muted">
                {active.length} chuyến · {active.reduce((n, f) => n + f.usable_capacity, 0)} ghế
                dùng được
              </p>
              <h2 className="text-heading-2 sm:text-heading-1">
                {stats.assigned}
                <span className="text-ink-faint">/{stats.total}</span> người đã có chuyến
              </h2>
            </div>
            <div className="flex flex-wrap gap-4 text-caption text-ink-muted">
              <span>
                <span className="mr-2 inline-block size-2 rounded-full bg-accent-orange" />
                {issues.length} cần xử lý
              </span>
              <span>{stats.split} team bị tách</span>
              <span>{stats.overloaded} chuyến quá tải</span>
            </div>
          </div>
          <section className="space-y-3">
            <h2 className="flex items-center gap-2 text-title">
              <Step>1</Step>
              {issues.length
                ? `Xử lý ${issues.length} trường hợp cần quyết định`
                : 'Không có trường hợp cần điều chỉnh'}
            </h2>
            {issues.length > 0 ? (
              <Card bodyClassName="p-0">
                <ul className="divide-y divide-hairline">
                  {(showAll ? issues : issues.slice(0, 6)).map((issue, index) => {
                    const choices = transferFlights(issue.people)
                    const preferred =
                      choices.find((f) =>
                        issue.people.every(
                          (p) =>
                            p.requested_shift_id == null || p.requested_shift_id === f.shift_id,
                        ),
                      ) ?? choices[0]
                    return (
                      <li
                        key={`${issue.people[0].registration_id}-${index}`}
                        className="flex flex-wrap items-center justify-between gap-3 px-4 py-4"
                      >
                        <div className="flex min-w-0 items-start gap-3">
                          <span className="mt-2 size-2 shrink-0 rounded-full bg-accent-orange" />
                          <div>
                            <p className="text-body-sm font-semibold">{issue.title}</p>
                            <p className="mt-1 text-caption text-ink-muted">{issue.description}</p>
                          </div>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Button
                            variant="ghost"
                            disabled={!choices.length || pending}
                            onClick={() => requestMove(issue.people)}
                          >
                            Chọn chuyến khác
                          </Button>
                          {preferred && (
                            <Button
                              shape="pill"
                              disabled={pending}
                              onClick={() => requestMove(issue.people, preferred)}
                            >
                              Xếp vào {preferred.flight_code} · còn {preferred.remaining_slots} chỗ
                            </Button>
                          )}
                          {!choices.length && (
                            <span className="text-caption text-ink-muted">
                              Chưa có chuyến đủ chỗ cho nhóm
                            </span>
                          )}
                        </div>
                      </li>
                    )
                  })}
                </ul>
                {issues.length > 6 && (
                  <div className="border-t border-hairline px-4 py-2">
                    <Button variant="ghost" onClick={() => setShowAll(!showAll)}>
                      {showAll ? 'Thu gọn' : `Xem tất cả ${issues.length} trường hợp`}
                    </Button>
                  </div>
                )}
              </Card>
            ) : (
              <p className="text-caption text-ink-muted">
                Mọi người đã được xếp và đúng ca đăng ký. Kiểm tra từng chuyến bên dưới trước khi
                công bố.
              </p>
            )}
          </section>
          <section className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="flex items-center gap-2 text-title">
                <Step>2</Step>Xem lại từng chuyến
              </h2>
              <p className="text-caption text-ink-muted">
                Chọn team rồi chọn chuyến đích · hoặc kéo thả
              </p>
            </div>

            {!flights.length && (
              <Card>
                <EmptyState
                  icon={Plane}
                  title="Chưa có chuyến bay cho chiều này"
                  description="Thêm chuyến bay và số ghế trước khi phân bổ."
                  action={
                    <Link to="/admin/flights" className="text-primary hover:underline">
                      Thêm chuyến bay
                    </Link>
                  }
                />
              </Card>
            )}
            {flights.map((flight, index) => {
              const assigned = people.filter((p) => p.flight_id === flight.id)
              const accepts =
                dragging && transferFlights(dragging.people).some((f) => f.id === flight.id)
              return (
                <FlightBoardRow
                  key={flight.id}
                  flight={flight}
                  people={assigned}
                  first={index === 0}
                  selection={selection}
                  target={target?.id === flight.id}
                  locatedId={location?.registration_id}
                  disabled={pending}
                  accepts={accepts}
                  hovered={hover === flight.id}
                  onHover={() => setHover(flight.id)}
                  onDragOver={(e) => {
                    if (accepts) e.preventDefault()
                  }}
                  onDrop={(e) => {
                    e.preventDefault()
                    drop(flight)
                  }}
                  onDrag={(group, e) => {
                    e.stopPropagation()
                    e.dataTransfer.setData(
                      'text/plain',
                      group.map((p) => p.registration_id).join(','),
                    )
                    e.dataTransfer.effectAllowed = 'move'
                    setDragging({ people: group })
                  }}
                  onDragEnd={() => {
                    setDragging(null)
                    setHover(null)
                  }}
                  onSelect={(group) => {
                    setSelection(
                      selection?.people[0]?.registration_id === group[0]?.registration_id &&
                        selection?.people.length === group.length
                        ? null
                        : { people: group },
                    )
                    setTargetId('')
                  }}
                  onTarget={() => {
                    if (
                      selectedPeople.length &&
                      transferFlights(selectedPeople).some((f) => f.id === flight.id)
                    )
                      setTargetId(String(flight.id))
                  }}
                  onMove={requestMove}
                  onPassengers={() => setPassengers(flight)}
                  onRemove={(person) => {
                    setRemoving(person)
                    setReason('')
                    setMoveError(null)
                  }}
                />
              )
            })}
          </section>
          {selection && (
            <div className="sticky bottom-20 z-[45] flex flex-wrap items-center justify-between gap-3 rounded-xl bg-primary p-4 text-on-primary shadow-soft md:bottom-4">
              <p className="text-caption">
                <strong>{selectedPeople.length} người</strong> từ{' '}
                {[...new Set(selectedPeople.map((p) => p.flight_code ?? 'Chưa có chuyến'))].join(
                  ', ',
                )}{' '}
                <ArrowRight className="mx-2 inline size-4" />
              </p>
              <div className="min-w-44">
                <Select
                  aria-label="Chuyến đích"
                  value={targetId}
                  onChange={(e) => setTargetId(e.target.value)}
                  placeholder="Chọn chuyến đích"
                  options={transferFlights(selectedPeople).map((f) => ({
                    value: String(f.id),
                    label: `${f.flight_code} · còn ${f.remaining_slots} chỗ`,
                  }))}
                />
              </div>
              {differentShift && (
                <span className="text-caption">
                  <AlertTriangle className="mr-1 inline size-4" />
                  Khác ca đăng ký
                </span>
              )}
              <div className="flex gap-2">
                <button
                  type="button"
                  className="min-h-11 px-3 text-caption"
                  onClick={() => {
                    setSelection(null)
                    setTargetId('')
                  }}
                >
                  Bỏ chọn
                </button>
                <Button
                  variant="secondary"
                  shape="pill"
                  disabled={!target || pending || !selectedPeople.length}
                  onClick={() => requestMove(selectedPeople, target)}
                >
                  Chuyển {selectedPeople.length} người
                </Button>
              </div>
            </div>
          )}
        </>
      )}
      <MoveDialog
        open={Boolean(move)}
        people={move?.people}
        sourceLabel={move?.sourceLabel}
        targetFlight={move?.targetFlight}
        flightOptions={move ? transferFlights(move.people) : []}
        pending={bulk.isPending}
        error={moveError}
        onClose={() => {
          if (!bulk.isPending) setMove(null)
        }}
        onConfirm={confirmMove}
      />
      {passengers && <PassengersModal flight={passengers} onClose={() => setPassengers(null)} />}
      <Modal
        open={Boolean(removing)}
        onClose={closeRemoval}
        title="Bỏ phân bổ hành khách"
        description={removing?.full_name}
        footer={
          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              disabled={remove.isPending}
              onClick={() => setRemoving(null)}
            >
              Huỷ
            </Button>
            <Button
              loading={remove.isPending}
              disabled={reason.trim().length < 3}
              onClick={async () => {
                try {
                  await remove.mutateAsync({
                    assignmentId: removing.assignment_id,
                    reason: reason.trim(),
                  })
                  setRemoving(null)
                  setSelection(null)
                  toast.success('Đã bỏ phân bổ.')
                } catch (e) {
                  setMoveError(e.message)
                }
              }}
            >
              Bỏ phân bổ
            </Button>
          </div>
        }
      >
        <p className="mb-4 text-body-sm text-ink-muted">
          Người này sẽ trở lại danh sách chưa có chuyến. Lần chạy tự động sau có thể xếp lại.
        </p>
        {moveError && (
          <Alert tone="error" className="mb-4">
            {moveError}
          </Alert>
        )}
        <Textarea
          label="Lý do"
          required
          value={reason}
          maxLength={500}
          onChange={(e) => setReason(e.target.value)}
          hint="Tối thiểu 3 ký tự"
        />
      </Modal>
    </div>
  )
}

function Step({ children }) {
  return (
    <span className="inline-flex size-6 shrink-0 items-center justify-center rounded-full bg-ink text-caption text-on-primary">
      {children}
    </span>
  )
}
