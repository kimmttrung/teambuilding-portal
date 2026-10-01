import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { AlertTriangle, Bus, Plus, Trash2, UserPlus, Wand2 } from 'lucide-react'
import {
  useAssignRider,
  useBuses,
  useDeleteBus,
  useUnassignedBusRiders,
} from '../../hooks/useBuses'
import { useActiveEvent } from '../../hooks/useEvent'
import { highlightTargets, usePersonLocation } from '../../hooks/usePeople'
import { scrollIntoView } from '../../utils/highlight'
import { useRegistrationFormOptions } from '../../hooks/useRegistration'
import { useToast } from '../../context/ToastContext'
import { BUS_LABELS } from '../../utils/constants'
import Alert from '../../components/common/Alert'
import Badge from '../../components/common/Badge'
import Button from '../../components/common/Button'
import Card from '../../components/common/Card'
import EmptyState from '../../components/common/EmptyState'
import ExportButton from '../../components/common/ExportButton'
import Modal from '../../components/common/Modal'
import PersonLocator from '../../components/admin/PersonLocator'
import Spinner from '../../components/common/Spinner'
import BusAllocationModal from './buses/BusAllocationModal'
import BusCard from './buses/BusCard'
import BusFormModal from './buses/BusFormModal'
import BusPassengersModal from './buses/BusPassengersModal'
import BusPickerDialog from './buses/BusPickerDialog'
import LeaderDialog from './buses/LeaderDialog'
import addIcon from '../../assets/buses/add.svg'

export default function BusesPage() {
  const event = useActiveEvent()
  if (event.isLoading) return <Spinner label="Đang tải kỳ…" />
  if (event.error) return <Alert tone="error">{event.error.message}</Alert>
  return <BusResources key={event.data.id} event={event.data} />
}

function BusResources({ event }) {
  const toast = useToast()
  const [searchParams, setSearchParams] = useSearchParams()
  const options = useRegistrationFormOptions()
  const legs = useMemo(
    () =>
      [...(options.data?.trip_legs ?? [])].sort(
        (a, b) => a.display_order - b.display_order,
      ),
    [options.data],
  )
  const requested = Number(searchParams.get('leg'))
  const legId = legs.some((item) => item.id === requested)
    ? requested
    : legs[0]?.id
  const buses = useBuses({ trip_leg_id: legId }, { enabled: Boolean(legId) })
  const unassigned = useUnassignedBusRiders({ trip_leg_id: legId })
  const deletion = useDeleteBus()
  const assignment = useAssignRider()
  const [form, setForm] = useState(null)
  const [allocating, setAllocating] = useState(false)
  const [viewing, setViewing] = useState(null)
  const [leaderBus, setLeaderBus] = useState(null)
  const [assigningPerson, setAssigningPerson] = useState(null)
  const [deletingBus, setDeletingBus] = useState(null)
  const [deleteError, setDeleteError] = useState(null)
  const { location: locatedPerson } = usePersonLocation()
  const locatedBusIds = highlightTargets(locatedPerson).buses
  const autoSwitchedFor = useRef(null)

  useEffect(() => {
    if (!legId || String(legId) === searchParams.get('leg')) return
    const next = new URLSearchParams(searchParams)
    next.set('leg', String(legId))
    setSearchParams(next, { replace: true })
  }, [legId, searchParams, setSearchParams])

  useEffect(() => {
    if (!locatedPerson) {
      autoSwitchedFor.current = null
      return
    }
    if (autoSwitchedFor.current === locatedPerson.user_id || !legs.length)
      return
    autoSwitchedFor.current = locatedPerson.user_id
    const targetIds = new Set(
      (locatedPerson.buses ?? [])
        .filter((item) => item.bus_id)
        .map((item) => item.trip_leg_id),
    )
    if (targetIds.has(legId)) return
    const target = legs.find((item) => targetIds.has(item.id))
    if (!target) return
    const next = new URLSearchParams(searchParams)
    next.set('leg', String(target.id))
    setSearchParams(next)
    toast.info(
      `Đã chuyển sang ${target.name} — xe của ${locatedPerson.full_name} ở chặng này.`,
    )
  }, [locatedPerson, legId, legs, searchParams, setSearchParams, toast])

  const busList = buses.data ?? []
  const people = unassigned.data?.pages.flatMap((page) => page.items) ?? []
  const totalUnassigned = unassigned.data?.pages[0]?.total
  const seated = busList.reduce((sum, bus) => sum + bus.assigned_count, 0)
  const seats = busList.reduce((sum, bus) => sum + bus.capacity, 0)
  const offSchedule = busList.filter((bus) => bus.timing_issues?.length).length
  const withoutLeader = busList.filter((bus) => !bus.leader_name).length
  const currentLeg = legs.find((item) => item.id === legId)

  function selectLeg(id) {
    const next = new URLSearchParams(searchParams)
    next.set('leg', String(id))
    setSearchParams(next)
  }
  async function confirmAssign({ busId, reason }) {
    const result = await assignment.mutateAsync({
      registrationId: assigningPerson.registration_id,
      busId,
      reason,
    })
    toast.success(
      `Đã xếp ${assigningPerson.full_name} lên xe ${result.assignment.bus_code}.`,
    )
    result.warnings.forEach((warning) => toast.warning(warning.message))
    setAssigningPerson(null)
  }
  async function confirmDelete() {
    setDeleteError(null)
    try {
      await deletion.mutateAsync(deletingBus.id)
      toast.success(`Đã xoá xe ${deletingBus.bus_code}.`)
      setDeletingBus(null)
    } catch (error) {
      setDeleteError(error.message)
    }
  }

  if (options.isLoading) return <Spinner label="Đang tải chặng xe…" />
  if (options.error)
    return (
      <Alert tone="error" title="Không tải được chặng xe">
        {options.error.message}
        <Button variant="secondary" onClick={() => options.refetch()}>
          {BUS_LABELS.retry}
        </Button>
      </Alert>
    )

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-center gap-4 border-b border-hairline pb-4">
        <h1 className="text-title font-semibold">{BUS_LABELS.title}</h1>
        <nav
          aria-label="Chặng xe"
          className="order-last w-full min-w-0 overflow-x-auto lg:order-none lg:w-auto lg:flex-1"
        >
          <div className="flex w-max gap-1 rounded-full bg-black/5 p-1">
            {legs.map((item, index) => (
              <button
                key={item.id}
                type="button"
                aria-current={item.id === legId ? 'page' : undefined}
                onClick={() => selectLeg(item.id)}
                className={`min-h-11 rounded-full px-3 py-2 text-caption transition sm:min-h-8 ${item.id === legId ? 'bg-surface font-medium text-ink shadow-soft' : 'text-ink-muted hover:text-ink'}`}
              >
                {index + 1} · {item.name}
              </button>
            ))}
          </div>
        </nav>
        {legs.length > 0 && (
          <div className="ml-auto flex flex-wrap gap-2">
            <Button
              variant="secondary"
              icon={Plus}
              onClick={() => setForm({ bus: null })}
            >
              {BUS_LABELS.add}
            </Button>
            <Button
              shape="pill"
              icon={Wand2}
              onClick={() => setAllocating(true)}
            >
              {BUS_LABELS.allocate}
            </Button>
          </div>
        )}
      </header>
      {!legs.length ? (
        <Card>
          <EmptyState
            icon={Bus}
            title="Kỳ này chưa có chặng xe nào"
            description="Khai các chặng trong cấu hình kỳ trước khi thêm xe."
          />
        </Card>
      ) : (
        <div className="flex flex-col gap-6 sm:px-4">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              {buses.data && totalUnassigned !== undefined ? (
                <p className="text-heading-1 font-bold tabular-nums">
                  {seated}
                  <span className="text-ink-faint">
                    /{seated + totalUnassigned}
                  </span>
                  <span className="ml-2 text-body-md font-semibold">
                    đã có xe
                  </span>
                </p>
              ) : (
                <p className="text-body-sm text-ink-muted">
                  Đang tải số người cần xe…
                </p>
              )}
              <p className="mt-2 text-caption text-ink-muted">
                {busList.length} xe · {seats} chỗ · {currentLeg?.name}
              </p>
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-2 text-caption">
              {offSchedule > 0 && (
                <span className="inline-flex items-center gap-1 text-rose-700">
                  <AlertTriangle className="size-4" />
                  {offSchedule} xe lệch giờ bay
                </span>
              )}
              {withoutLeader > 0 && (
                <span className="text-accent-orange">
                  {withoutLeader} xe chưa có Trưởng xe
                </span>
              )}
            </div>
          </div>
          {totalUnassigned !== undefined &&
            seated + totalUnassigned > seats && (
              <Alert tone="warning">
                Thiếu {seated + totalUnassigned - seats} chỗ. Thêm xe hoặc tăng
                số chỗ trước khi phân xe.
              </Alert>
            )}
          <div
            className={`grid items-start gap-4 ${totalUnassigned > 0 ? 'xl:grid-cols-[minmax(0,1fr)_20rem]' : ''}`}
          >
            <div className="min-w-0">
              {buses.isLoading ? (
                <Spinner label="Đang tải xe…" />
              ) : buses.error ? (
                <Alert tone="error" title="Không tải được danh sách xe">
                  {buses.error.message}
                  <Button variant="secondary" onClick={() => buses.refetch()}>
                    {BUS_LABELS.retry}
                  </Button>
                </Alert>
              ) : (
                <>
                  {!busList.length && (
                    <EmptyState
                      icon={Bus}
                      title="Chưa có xe nào ở chặng này"
                      description="Thêm xe đã thuê, sau đó xem trước phân xe tự động."
                    />
                  )}
                  <div
                    className={`grid gap-4 md:grid-cols-2 ${totalUnassigned > 0 ? '2xl:grid-cols-3' : 'xl:grid-cols-3'}`}
                  >
                    {busList.map((bus) => (
                      <div
                        key={bus.id}
                        ref={
                          locatedBusIds.has(bus.id) ? scrollIntoView : undefined
                        }
                      >
                        <BusCard
                          bus={bus}
                          onPassengers={() => setViewing(bus)}
                          onLeader={() => setLeaderBus(bus)}
                          onEdit={() => setForm({ bus })}
                          onDelete={() => {
                            setDeleteError(null)
                            setDeletingBus(bus)
                          }}
                        />
                      </div>
                    ))}
                    <button
                      type="button"
                      onClick={() => setForm({ bus: null })}
                      className="flex min-h-40 flex-col items-center justify-center gap-4 rounded-lg border border-dashed border-hairline p-6 text-caption text-ink-faint transition hover:bg-surface hover:text-ink focus-visible:outline-2 focus-visible:outline-primary"
                    >
                      <img src={addIcon} alt="" />
                      {BUS_LABELS.add} cho {currentLeg?.name}
                    </button>
                  </div>
                </>
              )}
            </div>
            <UnassignedPanel
              people={people}
              total={totalUnassigned}
              query={unassigned}
              canAssign={busList.some((bus) => bus.remaining_seats > 0)}
              onAssign={setAssigningPerson}
            />
          </div>
          <div className="flex flex-col items-stretch justify-between gap-4 border-t border-hairline pt-4 sm:flex-row sm:items-center">
            <div className="min-w-0 flex-1">
              <PersonLocator />
            </div>
            <ExportButton url="/buses/export" fallbackName="xe-dua-don.xlsx">
              Xuất Excel
            </ExportButton>
          </div>
        </div>
      )}
      {form && (
        <BusFormModal
          bus={form.bus}
          legs={legs}
          pickupPoints={options.data?.pickup_points ?? []}
          defaultLegId={legId}
          onClose={() => setForm(null)}
        />
      )}
      {allocating && (
        <BusAllocationModal
          legs={legs}
          defaultLegId={legId}
          event={event}
          onClose={() => setAllocating(false)}
        />
      )}
      {viewing && (
        <BusPassengersModal
          bus={busList.find((bus) => bus.id === viewing.id) ?? viewing}
          buses={busList}
          onClose={() => setViewing(null)}
        />
      )}
      {leaderBus && (
        <LeaderDialog
          bus={busList.find((bus) => bus.id === leaderBus.id) ?? leaderBus}
          onClose={() => setLeaderBus(null)}
        />
      )}
      {assigningPerson && (
        <BusPickerDialog
          title={BUS_LABELS.assign}
          person={assigningPerson}
          buses={busList}
          pending={assignment.isPending}
          onConfirm={confirmAssign}
          onClose={() => setAssigningPerson(null)}
        />
      )}
      <Modal
        open={Boolean(deletingBus)}
        onClose={() => setDeletingBus(null)}
        title={`Xoá xe ${deletingBus?.bus_code ?? ''}?`}
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setDeletingBus(null)}>
              Không xoá
            </Button>
            <Button
              variant="danger"
              icon={Trash2}
              loading={deletion.isPending}
              onClick={confirmDelete}
            >
              Xoá xe
            </Button>
          </div>
        }
      >
        {deleteError && (
          <Alert tone="error" className="mb-4">
            {deleteError}
          </Alert>
        )}
        <p className="text-body-sm text-ink-muted">
          Xe chưa có hành khách. Thao tác được ghi vào nhật ký thay đổi.
        </p>
      </Modal>
    </div>
  )
}

function UnassignedPanel({ people, total, query, canAssign, onAssign }) {
  const groups = new Map()
  for (const person of people) {
    const key = person.pickup_point_id ?? 'none'
    if (!groups.has(key))
      groups.set(key, {
        name: person.pickup_point_name ?? 'Chưa chọn điểm đón',
        people: [],
      })
    groups.get(key).people.push(person)
  }
  return (
    <Card
      title={BUS_LABELS.unassigned}
      action={
        total !== undefined && (
          <Badge tone={total ? 'amber' : 'emerald'}>{total}</Badge>
        )
      }
      bodyClassName="p-0"
    >
      {query.isLoading ? (
        <Spinner label="Đang tải người chưa có xe…" />
      ) : query.error ? (
        <div className="p-4">
          <Alert tone="error">{query.error.message}</Alert>
          <Button variant="secondary" onClick={() => query.refetch()}>
            {BUS_LABELS.retry}
          </Button>
        </div>
      ) : total === 0 ? (
        <p className="p-4 text-caption text-ink-muted">
          Mọi người cần xe ở chặng này đều đã có xe.
        </p>
      ) : (
        <>
          <div className="max-h-[32rem] overflow-y-auto">
            {[...groups].map(([key, group]) => (
              <section key={key}>
                <h2 className="bg-canvas-soft px-4 py-2 text-eyebrow text-ink-muted">
                  {group.name}
                </h2>
                <ul className="divide-y divide-hairline">
                  {group.people.map((person) => (
                    <li
                      key={person.id}
                      className="flex items-center gap-2 px-4 py-3"
                    >
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-body-sm font-medium">
                          {person.full_name}
                        </span>
                        <span className="block truncate text-caption text-ink-muted">
                          {person.team_name ?? 'Chưa có team'}
                        </span>
                      </span>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="min-h-11"
                        icon={UserPlus}
                        disabled={!canAssign}
                        title={canAssign ? undefined : 'Mọi xe đã đủ chỗ'}
                        onClick={() => onAssign(person)}
                      >
                        {BUS_LABELS.assign}
                      </Button>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2 border-t border-hairline p-4 text-caption text-ink-muted">
            <span>
              Đang xem {people.length}/{total} người
            </span>
            {query.hasNextPage && (
              <Button
                variant="secondary"
                size="sm"
                className="min-h-11"
                loading={query.isFetchingNextPage}
                onClick={() => query.fetchNextPage()}
              >
                {BUS_LABELS.loadMore}
              </Button>
            )}
          </div>
        </>
      )}
    </Card>
  )
}
