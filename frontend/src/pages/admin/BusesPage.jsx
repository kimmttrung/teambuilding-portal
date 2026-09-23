import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { AlertTriangle, Bus, Plus, Trash2, UserPlus, Wand2 } from 'lucide-react'
import { useAssignRider, useBusAssignments, useBuses, useDeleteBus } from '../../hooks/useBuses'
import { highlightTargets, usePersonLocation } from '../../hooks/usePeople'
import { scrollIntoView } from '../../utils/highlight'
import { useParticipants, useRegistrationFormOptions } from '../../hooks/useRegistration'
import { useToast } from '../../context/ToastContext'
import { FLIGHT_DIRECTION_LABELS, NOTIFY_HINTS } from '../../utils/constants'
import { formatNumber } from '../../utils/format'
import Alert from '../../components/common/Alert'
import Badge from '../../components/common/Badge'
import Button from '../../components/common/Button'
import Card from '../../components/common/Card'
import EmptyState from '../../components/common/EmptyState'
import ExportButton from '../../components/common/ExportButton'
import Modal from '../../components/common/Modal'
import NotifyToggle from '../../components/admin/NotifyToggle'
import PageHeader from '../../components/common/PageHeader'
import PersonLocator from '../../components/admin/PersonLocator'
import Spinner from '../../components/common/Spinner'
import BusAllocationModal from './buses/BusAllocationModal'
import BusCard from './buses/BusCard'
import BusFormModal from './buses/BusFormModal'
import BusPassengersModal from './buses/BusPassengersModal'
import BusPickerDialog from './buses/BusPickerDialog'
import LeaderDialog from './buses/LeaderDialog'

/**
 * Xe đưa đón theo từng chặng: xe và chỗ trống, người chưa có xe, Trưởng xe, phân xe tự động.
 *
 * Chặng đang xem nằm trên URL (`?leg=`) để BTC gửi link cho nhau và F5 không mất chỗ đang làm.
 * Số chặng, điểm đón lấy từ master data của kỳ — không hard-code (CLAUDE.md #3).
 */
export default function BusesPage() {
  const toast = useToast()
  const [searchParams, setSearchParams] = useSearchParams()

  const { data: options, isLoading: loadingOptions } = useRegistrationFormOptions()
  const legs = [...(options?.trip_legs ?? [])].sort((left, right) => left.display_order - right.display_order)
  const legId = Number(searchParams.get('leg')) || legs[0]?.id || null
  const leg = legs.find((item) => item.id === legId) ?? null

  const { data: buses, isLoading: loadingBuses, error } = useBuses(
    { trip_leg_id: legId },
    { enabled: Boolean(legId) },
  )
  // Đếm xe lệch giờ ở MỌI chặng để tab nào có lỗi là thấy ngay, không phải bấm từng tab.
  const { data: everyBus } = useBuses({})
  const { data: assignmentPage } = useBusAssignments(
    { trip_leg_id: legId, page_size: 200 },
    { enabled: Boolean(legId) },
  )
  const { data: participantPage } = useParticipants()
  const { mutateAsync: removeBus, isPending: deleting } = useDeleteBus()
  const { mutateAsync: assign, isPending: assigning } = useAssignRider()

  const [form, setForm] = useState(null) // { bus: null } = thêm mới
  const [allocating, setAllocating] = useState(false)
  const [viewing, setViewing] = useState(null)
  const [leaderBus, setLeaderBus] = useState(null)
  const [assigningPerson, setAssigningPerson] = useState(null)
  const [deletingBus, setDeletingBus] = useState(null)

  // Người đang tra cứu có xe ở chặng khác thì tự chuyển tab sang đó — xe họ đi mới là
  // thứ BTC cần thấy, không phải chặng đang mở. Chỉ tự chuyển một lần cho mỗi người
  // (ghi nhớ theo user_id) để không đánh nhau với tay bấm tab của BTC.
  const { location: locatedPerson } = usePersonLocation()
  const locatedBusIds = highlightTargets(locatedPerson).buses
  const autoSwitchedFor = useRef(null)
  useEffect(() => {
    if (!locatedPerson) {
      autoSwitchedFor.current = null
      return
    }
    if (autoSwitchedFor.current === locatedPerson.user_id || legs.length === 0) return
    autoSwitchedFor.current = locatedPerson.user_id
    const legIds = new Set(
      (locatedPerson.buses ?? []).filter((leg) => leg.bus_id).map((leg) => leg.trip_leg_id),
    )
    if (legIds.size === 0 || legIds.has(legId)) return
    const target = legs.find((leg) => legIds.has(leg.id))
    if (!target) return
    const next = new URLSearchParams(searchParams)
    next.set('leg', String(target.id))
    setSearchParams(next, { replace: true })
    toast.info(`Đã chuyển sang ${target.name} — xe của ${locatedPerson.full_name} ở chặng này.`)
  }, [locatedPerson, legId, legs, searchParams, setSearchParams, toast])

  if (loadingOptions) return <Spinner label="Đang tải chặng xe…" />

  const participants = participantPage?.items ?? []
  const demandByLeg = countDemand(participants)
  const riders = ridersOf(participants, legId)
  const assignments = assignmentPage?.items ?? []
  const assignedIds = new Set(assignments.map((row) => row.registration_id))
  const unassigned = riders.filter((person) => !assignedIds.has(person.registration_id))

  const timingByLeg = {}
  for (const bus of everyBus ?? []) {
    if ((bus.timing_issues ?? []).length > 0) {
      timingByLeg[bus.trip_leg_id] = (timingByLeg[bus.trip_leg_id] ?? 0) + 1
    }
  }

  const busList = buses ?? []
  const offSchedule = busList.filter((bus) => (bus.timing_issues ?? []).length > 0)
  const seats = busList.reduce((total, bus) => total + bus.capacity, 0)
  const seated = busList.reduce((total, bus) => total + bus.assigned_count, 0)
  const shortfall = Math.max(riders.length - seats, 0)
  const withoutLeader = busList.filter((bus) => !bus.leader_name).length
  const mismatchesByBus = {}
  for (const row of assignments) {
    if (row.pickup_mismatch || row.flight_mismatch) {
      mismatchesByBus[row.bus_id] = (mismatchesByBus[row.bus_id] ?? 0) + 1
    }
  }

  function selectLeg(id) {
    // Giữ lại ?person=: chuyển tab mà mất người đang tra cứu thì tính năng vô dụng.
    const next = new URLSearchParams(searchParams)
    next.set('leg', String(id))
    setSearchParams(next, { replace: true })
  }

  async function confirmDelete() {
    try {
      await removeBus(deletingBus.id)
      toast.success(`Đã xoá xe ${deletingBus.bus_code}.`)
      setDeletingBus(null)
    } catch (deleteError) {
      toast.error(deleteError.message)
    }
  }

  async function confirmAssign({ busId, reason }) {
    try {
      const result = await assign({ registrationId: assigningPerson.registration_id, busId, reason })
      toast.success(`Đã xếp ${assigningPerson.full_name} lên xe ${result.assignment.bus_code}.`)
      result.warnings.forEach((warning) => toast.warning(warning.message))
      setAssigningPerson(null)
    } catch (assignError) {
      toast.error(assignError.message)
    }
  }

  const header = (
    <PageHeader
      title="Xe đưa đón"
      description="Mỗi chặng một nhóm xe — xếp theo điểm đón và chuyến bay"
      action={
        legs.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            <NotifyToggle hint={NOTIFY_HINTS.journey} />
            <ExportButton
              url="/buses/export"
              fallbackName="xe-dua-don.xlsx"
              title="Mỗi chặng một sheet: xe, Trưởng xe, hành khách và người chưa có xe"
            >
              Xuất Excel
            </ExportButton>
            <Button variant="secondary" icon={Plus} onClick={() => setForm({ bus: null })}>
              Thêm xe
            </Button>
            <Button icon={Wand2} onClick={() => setAllocating(true)}>
              Phân xe tự động
            </Button>
          </div>
        ) : undefined
      }
    />
  )

  if (legs.length === 0) {
    return (
      <>
        {header}
        <Card>
          <EmptyState
            icon={Bus}
            title="Kỳ này chưa có chặng xe nào"
            description="Khai các chặng (ví dụ Công ty → Sân bay) trong master data của kỳ trước khi thêm xe."
          />
        </Card>
      </>
    )
  }

  return (
    <>
      {header}

      <div className="mb-4">
        <PersonLocator />
      </div>

      <div className="flex flex-col gap-4">
        <nav aria-label="Chặng xe" className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
          <div className="flex min-w-max gap-2">
            {legs.map((item) => {
              const active = item.id === legId
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => selectLeg(item.id)}
                  aria-current={active ? 'page' : undefined}
                  className={`rounded-lg border px-3 py-2 text-left text-sm transition ${
                    active
                      ? 'border-brand-600 bg-brand-600 text-white'
                      : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
                  }`}
                >
                  <span className="block font-medium">{item.name}</span>
                  <span className={`block text-xs ${active ? 'text-brand-100' : 'text-slate-500'}`}>
                    {FLIGHT_DIRECTION_LABELS[item.direction] ?? item.direction} · {demandByLeg[item.id] ?? 0} người cần xe
                  </span>
                  {timingByLeg[item.id] > 0 && (
                    <span
                      className={`mt-0.5 flex items-center gap-1 text-xs font-medium ${
                        active ? 'text-amber-100' : 'text-amber-700'
                      }`}
                    >
                      <AlertTriangle className="size-3.5 shrink-0" aria-hidden="true" />
                      {timingByLeg[item.id]} xe lệch giờ
                    </span>
                  )}
                </button>
              )
            })}
          </div>
        </nav>

        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Stat label="Cần xe" value={riders.length} />
          <Stat label="Số chỗ" value={seats} hint={`${busList.length} xe`} tone={shortfall ? 'rose' : 'slate'} />
          <Stat label="Đã xếp" value={seated} tone="emerald" />
          <Stat label="Chưa có xe" value={unassigned.length} tone={unassigned.length ? 'amber' : 'slate'} />
        </div>

        {offSchedule.length > 0 && (
          <Alert
            tone="warning"
            title={`${offSchedule.length} xe ở chặng này lệch giờ bay: ${offSchedule
              .map((bus) => bus.bus_code)
              .join(', ')}`}
          >
            Chi tiết từng xe ở thẻ bên dưới (khối vàng). Còn lệch thì không công bố kỳ được, vì
            lịch trình CBNV nhìn thấy sẽ mâu thuẫn.
          </Alert>
        )}

        {shortfall > 0 && (
          <Alert tone="warning" title={`Thiếu ${shortfall} chỗ ở chặng này`}>
            {riders.length} người cần xe nhưng mới có {seats} chỗ. Thêm xe hoặc tăng số chỗ trước khi phân xe.
          </Alert>
        )}
        {leg?.is_airport_linked && (
          <Alert tone="info">
            Chặng gắn sân bay: xe nên gắn với chuyến bay, và cần phân bổ chuyến bay{' '}
            {FLIGHT_DIRECTION_LABELS[leg.direction]?.toLowerCase()} trước khi phân xe.
          </Alert>
        )}

        <div className="grid gap-4 xl:grid-cols-12">
          <div className="min-w-0 xl:col-span-8">
            {loadingBuses ? (
              <Spinner label="Đang tải xe…" />
            ) : error ? (
              <Alert tone="error" title="Không tải được danh sách xe">
                {error.message}
              </Alert>
            ) : busList.length === 0 ? (
              <Card>
                <EmptyState
                  icon={Bus}
                  title="Chưa có xe nào ở chặng này"
                  description="Thêm các xe BTC đã thuê, rồi chạy phân xe tự động."
                  action={
                    <Button icon={Plus} onClick={() => setForm({ bus: null })}>
                      Thêm xe
                    </Button>
                  }
                />
              </Card>
            ) : (
              <div className="grid gap-4 md:grid-cols-2">
                {busList.map((bus) => (
                  <div key={bus.id} ref={locatedBusIds.has(bus.id) ? scrollIntoView : undefined}>
                    <BusCard
                      bus={bus}
                      mismatches={mismatchesByBus[bus.id] ?? 0}
                      onPassengers={() => setViewing(bus)}
                      onLeader={() => setLeaderBus(bus)}
                      onEdit={() => setForm({ bus })}
                      onDelete={() => setDeletingBus(bus)}
                    />
                  </div>
                ))}
              </div>
            )}
          </div>

          <aside className="flex min-w-0 flex-col gap-4 xl:col-span-4">
            <UnassignedPanel
              people={unassigned}
              canAssign={busList.some((bus) => bus.remaining_seats > 0)}
              onAssign={setAssigningPerson}
            />

            {withoutLeader > 0 && (
              <Alert tone="warning">
                {withoutLeader} xe chưa có Trưởng xe. CBNV sẽ không biết gọi ai khi lỡ giờ tập trung.
              </Alert>
            )}

            <Card title="Thứ tự làm việc">
              <ol className="flex flex-col gap-2 text-sm text-slate-600">
                <li>1. Khai đủ xe cho từng chặng: số chỗ, điểm đón, giờ tập trung.</li>
                <li>2. Chặng gắn sân bay: phân bổ chuyến bay trước, rồi gắn chuyến cho xe.</li>
                <li>
                  3. Bấm <strong>Phân xe tự động</strong> → xem trước → áp dụng (kỳ phải đã đóng đăng ký).
                </li>
                <li>4. Xếp tay người còn ở “Chưa có xe”; chuyển xe trong danh sách hành khách.</li>
                <li>5. Gán Trưởng xe cho mọi xe.</li>
              </ol>
            </Card>
          </aside>
        </div>
      </div>

      {form && (
        <BusFormModal
          bus={form.bus}
          legs={legs}
          pickupPoints={options?.pickup_points ?? []}
          defaultLegId={legId}
          onClose={() => setForm(null)}
        />
      )}
      {allocating && (
        <BusAllocationModal legs={legs} defaultLegId={legId} onClose={() => setAllocating(false)} />
      )}
      {viewing && (
        <BusPassengersModal
          bus={busList.find((bus) => bus.id === viewing.id) ?? viewing}
          buses={busList}
          onClose={() => setViewing(null)}
        />
      )}
      {leaderBus && (
        <LeaderDialog bus={leaderBus} participants={participants} onClose={() => setLeaderBus(null)} />
      )}
      {assigningPerson && (
        <BusPickerDialog
          title="Xếp xe"
          person={assigningPerson}
          buses={busList}
          pending={assigning}
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
            <Button variant="secondary" size="sm" onClick={() => setDeletingBus(null)}>
              Không xoá
            </Button>
            <Button variant="danger" size="sm" icon={Trash2} loading={deleting} onClick={confirmDelete}>
              Xoá xe
            </Button>
          </div>
        }
      >
        <p className="text-sm text-slate-700">Xe chưa có hành khách nào. Thao tác được ghi vào nhật ký thay đổi.</p>
      </Modal>
    </>
  )
}

/** Người cần xe ở chặng này mà chưa được xếp, gom theo điểm đón họ đã chọn. */
function UnassignedPanel({ people, canAssign, onAssign }) {
  const groups = groupByPickup(people)

  return (
    <Card
      title="Chưa có xe"
      description={people.length ? 'Gom theo điểm đón CBNV đã chọn' : undefined}
      action={<Badge tone={people.length ? 'amber' : 'emerald'}>{people.length}</Badge>}
      bodyClassName="p-0"
    >
      {people.length === 0 ? (
        <p className="px-4 py-3.5 text-sm text-emerald-700">Mọi người cần xe ở chặng này đều đã có xe.</p>
      ) : (
        <div className="max-h-[32rem] divide-y divide-slate-100 overflow-y-auto">
          {groups.map((group) => (
            <section key={group.name}>
              <h3 className="bg-slate-50 px-4 py-1.5 text-xs font-semibold tracking-wide text-slate-500 uppercase">
                {group.name} · {group.people.length}
              </h3>
              <ul className="divide-y divide-slate-100">
                {group.people.map((person) => (
                  <li key={person.registration_id} className="flex items-center gap-2 px-4 py-2">
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm text-slate-900">{person.full_name}</span>
                      <span className="block truncate text-xs text-slate-500">{person.team_name ?? 'Chưa có team'}</span>
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      icon={UserPlus}
                      disabled={!canAssign}
                      title={canAssign ? undefined : 'Mọi xe đã đủ chỗ'}
                      onClick={() => onAssign(person)}
                    >
                      Xếp xe
                    </Button>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
    </Card>
  )
}

const STAT_TONES = {
  slate: 'text-slate-900',
  emerald: 'text-emerald-700',
  amber: 'text-amber-700',
  rose: 'text-rose-700',
}

function Stat({ label, value, hint, tone = 'slate' }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3">
      <p className="text-xs text-slate-500">{label}</p>
      <p className={`text-xl leading-tight font-bold tabular-nums ${STAT_TONES[tone]}`}>{formatNumber(value)}</p>
      {hint && <p className="text-xs text-slate-400">{hint}</p>}
    </div>
  )
}

function countDemand(participants) {
  const counts = {}
  for (const registration of participants) {
    for (const need of registration.bus_needs ?? []) {
      if (need.needs_bus) counts[need.trip_leg_id] = (counts[need.trip_leg_id] ?? 0) + 1
    }
  }
  return counts
}

function ridersOf(participants, legId) {
  return participants.flatMap((registration) => {
    const need = (registration.bus_needs ?? []).find((item) => item.trip_leg_id === legId && item.needs_bus)
    if (!need) return []
    return [
      {
        registration_id: registration.id,
        full_name: registration.user.full_name,
        team_name: registration.user.team_name,
        pickup_point_id: need.pickup_point_id,
        pickup_point_name: need.pickup_point_name,
      },
    ]
  })
}

function groupByPickup(people) {
  const groups = new Map()
  for (const person of people) {
    const name = person.pickup_point_name ?? 'Chưa chọn điểm đón'
    const group = groups.get(name)
    if (group) group.people.push(person)
    else groups.set(name, { name, people: [person] })
  }
  return [...groups.values()].sort((left, right) => right.people.length - left.people.length)
}
