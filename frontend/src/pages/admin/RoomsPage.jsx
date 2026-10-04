import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { BedDouble, MapPin, Pencil, Plus, Trash2 } from 'lucide-react'
import {
  useAssignRoom,
  useDeleteHotel,
  useHotels,
  useRoomBoardAssignments,
  useRooms,
  useRoomSummary,
  useUnassignedRooms,
} from '../../hooks/useRooms'
import { useToast } from '../../context/ToastContext'
import { ROOM_LABELS, ROOM_POLICY_META } from '../../utils/constants'
import { formatFullDateTime, formatNumber } from '../../utils/format'
import { canStay, groupByFloor } from '../../utils/rooms'
import { mapsUrl, telHref } from '../../utils/travel'
import Alert from '../../components/common/Alert'
import Badge from '../../components/common/Badge'
import Button from '../../components/common/Button'
import Card from '../../components/common/Card'
import EmptyState from '../../components/common/EmptyState'
import ExportButton from '../../components/common/ExportButton'
import Input from '../../components/common/Input'
import Select from '../../components/common/Select'
import Modal from '../../components/common/Modal'
import PersonLocator from '../../components/admin/PersonLocator'
import { usePersonLocation } from '../../hooks/usePeople'
import Spinner from '../../components/common/Spinner'
import HotelFormModal from './rooms/HotelFormModal'
import RoomDetailModal from './rooms/RoomDetailModal'
import RoomFormModal from './rooms/RoomFormModal'
import RoomImportModal from './rooms/RoomImportModal'
import RoomPickerDialog from './rooms/RoomPickerDialog'
import RoomAllocationModal from './rooms/RoomAllocationModal'
import { RoomPolicyBadge, RoomTile, UnassignedPanel } from './rooms/RoomBoard'
import importIcon from '../../assets/rooms/import.svg'
import playIcon from '../../assets/rooms/play.svg'
import lockIcon from '../../assets/rooms/lock.svg'

const POLICY_FILTERS = ['all', 'male', 'female', 'any']

/** Figma B8/L4. Bộ lọc hotel/floor/policy/available giữ trên URL; mọi hook trước return sớm. */
export default function RoomsPage() {
  const toast = useToast()
  const [searchParams, setSearchParams] = useSearchParams()
  const hotelsQuery = useHotels()
  const roomsQuery = useRooms()
  const summaryQuery = useRoomSummary()
  const assignmentQuery = useRoomBoardAssignments()
  const { mutateAsync: removeHotel, isPending: deletingHotel } = useDeleteHotel()
  const { mutateAsync: assignRoom, isPending: assigning } = useAssignRoom()
  const [hotelForm, setHotelForm] = useState(null)
  const [roomForm, setRoomForm] = useState(null)
  const [importing, setImporting] = useState(false)
  const [allocating, setAllocating] = useState(false)
  const [openRoomId, setOpenRoomId] = useState(null)
  const [placing, setPlacing] = useState(null)
  const [dragging, setDragging] = useState(null)
  const [dropError, setDropError] = useState(null)
  const [deletingHotelRow, setDeletingHotelRow] = useState(null)
  const [deleteError, setDeleteError] = useState(null)
  const [unassignedSearch, setUnassignedSearch] = useState('')
  const [showTools, setShowTools] = useState(false)
  const [showFilters, setShowFilters] = useState(false)
  const unassignedPanelRef = useRef(null)
  const unassignedQuery = useUnassignedRooms({
    q: unassignedSearch.trim() || undefined,
  })
  const hotelList = hotelsQuery.data ?? []
  const hotelId =
    hotelList.find((item) => item.id === Number(searchParams.get('hotel')))?.id ??
    hotelList[0]?.id ??
    null
  const { location: locatedPerson } = usePersonLocation()
  const autoSwitchedFor = useRef(null)
  useEffect(() => {
    if (!locatedPerson) {
      autoSwitchedFor.current = null
      return
    }
    if (!hotelsQuery.data || autoSwitchedFor.current === locatedPerson.user_id) return
    autoSwitchedFor.current = locatedPerson.user_id
    const target = hotelsQuery.data.find((item) => item.id === locatedPerson.room?.hotel_id)
    if (!target) return
    const next = new URLSearchParams(searchParams)
    next.set('hotel', String(target.id))
    next.delete('floor')
    setSearchParams(next, { replace: true })
  }, [locatedPerson, hotelsQuery.data, searchParams, setSearchParams])

  if (hotelsQuery.isLoading || roomsQuery.isLoading)
    return <Spinner label="Đang tải khách sạn và phòng…" />
  const loadError = hotelsQuery.error ?? roomsQuery.error
  if (loadError)
    return (
      <Alert tone="error" title="Không tải được khách sạn và phòng">
        {loadError.message}
        <Button
          variant="ghost"
          onClick={() => {
            hotelsQuery.refetch()
            roomsQuery.refetch()
          }}
        >
          {ROOM_LABELS.tryAgain}
        </Button>
      </Alert>
    )
  const rooms = roomsQuery.data ?? []
  const hotel = hotelList.find((item) => item.id === hotelId)
  const policyFilter = POLICY_FILTERS.includes(searchParams.get('policy'))
    ? searchParams.get('policy')
    : 'all'
  const availableOnly = searchParams.get('available') === '1'
  const hotelRooms = rooms.filter((room) => room.hotel_id === hotelId)
  const allFloors = groupByFloor(hotelRooms)
  const requestedFloor = searchParams.get('floor')
  const floorFilter = allFloors.some((group) => (group.floor || '__none__') === requestedFloor)
    ? requestedFloor
    : null
  const visibleRooms = hotelRooms.filter(
    (room) =>
      (policyFilter === 'all' || room.gender_policy === policyFilter) &&
      (!availableOnly || room.remaining > 0) &&
      (!floorFilter || (room.floor || '__none__') === floorFilter),
  )
  const floors = groupByFloor(visibleRooms)
  const openRoom = rooms.find((room) => room.id === openRoomId)
  const guests = new Map()
  for (const person of assignmentQuery.error ? [] : (assignmentQuery.data ?? [])) {
    if (!guests.has(person.room_id)) guests.set(person.room_id, [])
    guests.get(person.room_id).push(person)
  }

  function updateParams(changes) {
    const next = new URLSearchParams(searchParams)
    for (const [key, value] of Object.entries(changes)) {
      if (value == null || value === '') next.delete(key)
      else next.set(key, String(value))
    }
    setSearchParams(next)
  }
  async function confirmDeleteHotel() {
    setDeleteError(null)
    try {
      await removeHotel(deletingHotelRow.id)
      toast.success(`Đã xoá ${deletingHotelRow.name}.`)
      setDeletingHotelRow(null)
      updateParams({ hotel: null, floor: null })
    } catch (error) {
      setDeleteError(error)
    }
  }
  async function confirmPlace({ roomId, isRoomCaptain, reason }) {
    const result = await assignRoom({
      registrationId: placing.person.registration_id,
      roomId,
      isRoomCaptain,
      reason,
    })
    toast.success(`Đã xếp ${placing.person.full_name} vào phòng ${result.assignment.room_number}.`)
    setPlacing(null)
  }
  function dropPerson(event, room) {
    const id = Number(event.dataTransfer.getData('application/x-teambuilding-room'))
    const person = unassignedQuery.data?.pages
      .flatMap((page) => page.items)
      .find((item) => item.registration_id === id)
    setDragging(null)
    if (!person || unassignedQuery.error) return
    if (!canStay(room.gender_policy, person.gender)) {
      setDropError(
        `Không thể xếp ${person.full_name} vào phòng ${room.room_number} — phòng dành cho ${ROOM_POLICY_META[room.gender_policy].label}.`,
      )
      return
    }
    if (room.remaining <= 0) {
      setDropError(`Phòng ${room.room_number} đã đủ người. Chọn phòng còn chỗ.`)
      return
    }
    setDropError(null)
    setPlacing({ person, roomId: room.id })
  }

  return (
    <>
      <header className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-hairline pb-4">
        <div>
          <h1 className="text-page-title text-ink">
            Phòng{hotel ? ` · ${hotel.name}` : ''}
          </h1>
          {summaryQuery.data && !summaryQuery.error && (
            <p className="mt-1 text-caption text-ink-muted sm:hidden">
              <span className="text-heading-2 font-bold text-ink">
                {summaryQuery.data.assigned}
                <span className="text-ink-faint">/{summaryQuery.data.participants}</span>
              </span>{' '}
              đã có phòng
            </p>
          )}
        </div>
        <Button
          variant="secondary"
          size="sm"
          className="min-h-11 sm:hidden"
          aria-expanded={showTools}
          onClick={() => setShowTools(!showTools)}
        >
          {ROOM_LABELS.tools}
        </Button>
        <div className="hidden flex-wrap gap-2 sm:flex">
          <Button
            variant="secondary"
            size="sm"
            className="max-sm:min-h-11"
            disabled={!hotelList.length}
            onClick={() => setImporting(true)}
          >
            <img src={importIcon} className="size-[15px]" alt="" />
            {ROOM_LABELS.import}
          </Button>
          <Button
            shape="pill"
            size="sm"
            className="max-sm:min-h-11"
            disabled={!rooms.length}
            onClick={() => setAllocating(true)}
          >
            <img src={playIcon} className="size-[15px]" alt="" />
            {ROOM_LABELS.auto}
          </Button>
        </div>
      </header>
      <div className={`mb-4 flex-wrap items-center gap-2 ${showTools ? 'flex' : 'hidden sm:flex'}`}>
        <div className="flex gap-2 sm:hidden">
          <Button
            variant="secondary"
            disabled={!hotelList.length}
            onClick={() => setImporting(true)}
          >
            <img src={importIcon} className="size-[15px]" alt="" />
            {ROOM_LABELS.import}
          </Button>
          <Button shape="pill" disabled={!rooms.length} onClick={() => setAllocating(true)}>
            <img src={playIcon} className="size-[15px]" alt="" />
            {ROOM_LABELS.auto}
          </Button>
        </div>
        <div className="min-w-0 basis-full lg:flex-1 lg:basis-auto">
          <PersonLocator />
        </div>
        <ExportButton
          url="/rooms/export"
          fallbackName="phan-phong.xlsx"
          disabled={!hotelList.length}
        >
          {ROOM_LABELS.export}
        </ExportButton>
        <Button
          variant="secondary"
          size="sm"
          className="max-sm:min-h-11"
          icon={Plus}
          disabled={!hotelList.length}
          onClick={() => setRoomForm({ room: null })}
        >
          {ROOM_LABELS.addRoom}
        </Button>
        <Button
          variant="secondary"
          size="sm"
          className="max-sm:min-h-11"
          icon={Plus}
          onClick={() => setHotelForm({ hotel: null })}
        >
          {ROOM_LABELS.addHotel}
        </Button>
      </div>
      {!hotelList.length ? (
        <Card>
          <EmptyState
            icon={BedDouble}
            title="Chưa có khách sạn nào"
            description="Thêm khách sạn và khai phòng theo giới tính trước khi phân phòng."
            action={
              <Button icon={Plus} onClick={() => setHotelForm({ hotel: null })}>
                {ROOM_LABELS.addHotel}
              </Button>
            }
          />
        </Card>
      ) : (
        <div className="flex flex-col gap-4">
          {summaryQuery.error ? (
            <Alert tone="error" title="Không tải được bảng giường">
              {summaryQuery.error.message}
            </Alert>
          ) : summaryQuery.data ? (
            <details className="order-1 rounded-lg border border-hairline bg-surface p-4 sm:order-none">
              <summary className="cursor-pointer text-sm font-semibold text-ink">
                {ROOM_LABELS.beds} · {summaryQuery.data.assigned}/{summaryQuery.data.participants}{' '}
                người đã có phòng
              </summary>
              <div className="mt-4">
                <BedBalance summary={summaryQuery.data} />
              </div>
            </details>
          ) : (
            <Spinner label="Đang tải bảng giường…" />
          )}
          <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_300px]">
            <section aria-label="Sơ đồ phòng" className="min-w-0">
              <Button
                variant="secondary"
                size="sm"
                className="mb-3 min-h-11 sm:hidden"
                aria-expanded={showFilters}
                onClick={() => setShowFilters(!showFilters)}
              >
                {ROOM_LABELS.filters}
                {policyFilter !== 'all' || availableOnly ? ' · Đang lọc' : ''}
              </Button>
              <div
                className={`mb-4 flex-wrap items-end gap-3 ${showFilters ? 'flex' : 'hidden sm:flex'}`}
              >
                <div className="min-w-40 flex-1">
                  <Select
                    label={ROOM_LABELS.hotel}
                    value={String(hotelId)}
                    onChange={(event) => updateParams({ hotel: event.target.value, floor: null })}
                    options={hotelList.map((item) => ({
                      value: String(item.id),
                      label: item.name,
                    }))}
                  />
                </div>
                <Select
                  label={ROOM_LABELS.roomGender}
                  value={policyFilter}
                  onChange={(event) =>
                    updateParams({
                      policy: event.target.value === 'all' ? null : event.target.value,
                    })
                  }
                  options={POLICY_FILTERS.map((value) => ({
                    value,
                    label: value === 'all' ? 'Tất cả' : ROOM_POLICY_META[value].label,
                  }))}
                />
                <label className="flex min-h-11 items-center gap-2 text-caption text-ink-secondary">
                  <input
                    type="checkbox"
                    className="size-4 accent-primary"
                    checked={availableOnly}
                    onChange={(event) =>
                      updateParams({
                        available: event.target.checked ? '1' : null,
                      })
                    }
                  />
                  {ROOM_LABELS.available}
                </label>
              </div>
              {hotel && (
                <div className="mb-4">
                  <HotelCard
                    hotel={hotel}
                    onEdit={() => setHotelForm({ hotel })}
                    onDelete={() => {
                      setDeleteError(null)
                      setDeletingHotelRow(hotel)
                    }}
                  />
                </div>
              )}
              <nav aria-label={ROOM_LABELS.floor} className="mb-4 flex gap-2 overflow-x-auto pb-1">
                {[
                  { floor: null, label: ROOM_LABELS.allFloors },
                  ...allFloors.map((group) => ({
                    floor: group.floor || '__none__',
                    label: group.floor ? `Tầng ${group.floor}` : ROOM_LABELS.unknownFloor,
                  })),
                ].map((item) => (
                  <button
                    key={item.floor ?? 'all'}
                    type="button"
                    aria-pressed={floorFilter === item.floor}
                    onClick={() => updateParams({ floor: item.floor })}
                    className={`min-h-11 shrink-0 rounded-md border px-3 text-caption transition ${floorFilter === item.floor ? 'border-primary bg-primary text-on-primary' : 'border-hairline bg-surface text-ink-muted hover:text-ink'}`}
                  >
                    {item.label}
                  </button>
                ))}
                <button
                  type="button"
                  className="min-h-11 shrink-0 rounded-md border border-hairline bg-surface px-3 text-caption text-ink-muted sm:hidden"
                  onClick={() =>
                    unassignedPanelRef.current?.scrollIntoView({
                      behavior: 'smooth',
                      block: 'start',
                    })
                  }
                >
                  Chưa xếp ·{' '}
                  {unassignedQuery.data?.pages[0]?.total ?? summaryQuery.data?.unassigned ?? '—'}
                </button>
              </nav>
              <div className="mb-4 flex flex-wrap items-center gap-3 text-xs text-ink-muted">
                <RoomPolicyBadge policy="male" />
                <RoomPolicyBadge policy="female" />
                <span>{ROOM_LABELS.teamDots}</span>
                <span className="flex items-center gap-1">
                  <img src={lockIcon} className="size-3.5" alt="" />
                  {ROOM_LABELS.manual}
                </span>
              </div>
              {assignmentQuery.error && (
                <Alert tone="warning" className="mb-4">
                  Không tải được nhãn team và bản ghi chỉnh tay. Số giường vẫn lấy từ dữ liệu phòng.
                  <Button variant="ghost" onClick={() => assignmentQuery.refetch()}>
                    {ROOM_LABELS.tryAgain}
                  </Button>
                </Alert>
              )}
              <LocatedRoomNotice
                locatedPerson={locatedPerson}
                hotelRooms={hotelRooms}
                visibleRooms={visibleRooms}
                onClearFilters={() => updateParams({ policy: null, available: null, floor: null })}
              />
              {!hotelRooms.length ? (
                <EmptyState
                  icon={BedDouble}
                  title="Khách sạn này chưa có phòng"
                  action={
                    <Button onClick={() => setRoomForm({ room: null })}>
                      {ROOM_LABELS.addRoom}
                    </Button>
                  }
                />
              ) : !floors.length ? (
                <p className="py-6 text-caption text-ink-muted">Không có phòng nào khớp bộ lọc.</p>
              ) : (
                <div className="flex flex-col gap-5">
                  {floors.map((group) => (
                    <section key={group.floor || '__none__'}>
                      <h2 className="mb-2 text-xs font-semibold text-ink-muted">
                        {group.floor ? `Tầng ${group.floor}` : ROOM_LABELS.unknownFloor} ·{' '}
                        {group.rooms.length} phòng
                      </h2>
                      <div className="grid grid-cols-2 gap-2 sm:grid-cols-[repeat(auto-fill,minmax(124px,1fr))]">
                        {group.rooms.map((room) => (
                          <RoomTile
                            key={room.id}
                            room={room}
                            guests={guests.get(room.id)}
                            ready={!!assignmentQuery.data && !assignmentQuery.error}
                            dragging={dragging}
                            onDrop={dropPerson}
                            onOpen={() => setOpenRoomId(room.id)}
                          />
                        ))}
                      </div>
                    </section>
                  ))}
                </div>
              )}
              {dropError && (
                <Alert tone="error" className="mt-4">
                  {dropError}
                </Alert>
              )}
            </section>
            <UnassignedPanel
              query={unassignedQuery}
              panelRef={unassignedPanelRef}
              filtered={Boolean(unassignedSearch.trim())}
              onPlace={(person) => setPlacing({ person })}
              onDrag={(person) => {
                setDropError(null)
                setDragging(person)
              }}
              onDragEnd={() => setDragging(null)}
            >
              <div className="mt-3">
                <Input
                  label={ROOM_LABELS.search}
                  type="search"
                  value={unassignedSearch}
                  onChange={(event) => setUnassignedSearch(event.target.value)}
                />
              </div>
            </UnassignedPanel>
          </div>
        </div>
      )}
      {hotelForm && <HotelFormModal hotel={hotelForm.hotel} onClose={() => setHotelForm(null)} />}
      {roomForm && (
        <RoomFormModal
          room={roomForm.room}
          hotels={hotelList}
          defaultHotelId={hotelId}
          onClose={() => setRoomForm(null)}
        />
      )}
      {importing && <RoomImportModal onClose={() => setImporting(false)} />}
      {allocating && <RoomAllocationModal onClose={() => setAllocating(false)} />}
      {openRoom && !roomForm && (
        <RoomDetailModal
          key={openRoom.id}
          room={openRoom}
          rooms={rooms}
          onEdit={() => setRoomForm({ room: openRoom })}
          onClose={() => setOpenRoomId(null)}
        />
      )}
      {placing && (
        <RoomPickerDialog
          title={ROOM_LABELS.place}
          person={placing.person}
          rooms={rooms}
          defaultRoomId={placing.roomId}
          pending={assigning}
          onConfirm={confirmPlace}
          onClose={() => setPlacing(null)}
        />
      )}
      <Modal
        open={!!deletingHotelRow}
        onClose={() => setDeletingHotelRow(null)}
        title={`Xoá ${deletingHotelRow?.name ?? 'khách sạn'}?`}
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setDeletingHotelRow(null)}>
              {ROOM_LABELS.noDelete}
            </Button>
            <Button
              variant="danger"
              icon={Trash2}
              loading={deletingHotel}
              onClick={confirmDeleteHotel}
            >
              {ROOM_LABELS.deleteHotel}
            </Button>
          </div>
        }
      >
        {deleteError && (
          <Alert tone="error" className="mb-3">
            {deleteError.message}
          </Alert>
        )}
        <p className="text-caption text-ink-secondary">
          Chỉ xoá được khi khách sạn không còn ai ở. Các phòng trống được xoá theo; thao tác lưu vào
          nhật ký thay đổi.
        </p>
      </Modal>
    </>
  )
}

/** Giường theo giới tính so với người cần: tổng đủ chưa chắc đủ, vì phòng nam không nhận nữ. */
function BedBalance({ summary }) {
  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label={ROOM_LABELS.guestCount} value={summary.participants} />
        <Stat label={ROOM_LABELS.assigned} value={summary.assigned} tone="emerald" />
        <Stat
          label="Chưa có phòng"
          value={summary.unassigned}
          tone={summary.unassigned ? 'amber' : 'slate'}
        />
        <Stat label={ROOM_LABELS.bedCount} value={summary.total_beds} />
      </div>

      {summary.uncovered > 0 && (
        <Alert tone="warning" title={`${summary.uncovered} người không còn giường hợp giới tính`}>
          Tổng giường có thể vẫn đủ, nhưng thiếu ở giới tính dưới đây. Đổi một phòng trống sang giới
          tính còn thiếu, hoặc thêm phòng.
        </Alert>
      )}

      <Card bodyClassName="p-0">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-sm">
            <thead>
              <tr className="border-b border-hairline text-left text-xs tracking-wide text-ink-faint uppercase">
                <th className="px-4 py-2 font-medium">{ROOM_LABELS.forGender}</th>
                <th className="px-3 py-2 text-right font-medium">{ROOM_LABELS.rooms}</th>
                <th className="px-3 py-2 text-right font-medium">{ROOM_LABELS.bedCount}</th>
                <th className="px-3 py-2 text-right font-medium">{ROOM_LABELS.occupied}</th>
                <th className="px-3 py-2 text-right font-medium">{ROOM_LABELS.remaining}</th>
                <th className="px-3 py-2 text-right font-medium">{ROOM_LABELS.needed}</th>
                <th className="px-4 py-2 text-right font-medium">{ROOM_LABELS.shortfall}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-hairline">
              {summary.by_policy.map((row) => {
                const meta = ROOM_POLICY_META[row.gender_policy] ?? {
                  label: row.gender_policy,
                  tone: 'slate',
                }
                return (
                  <tr key={row.gender_policy}>
                    <td className="px-4 py-2">
                      <Badge tone={meta.tone}>{meta.label}</Badge>
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">{row.rooms}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{row.beds}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{row.occupied}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{row.remaining}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{row.participants}</td>
                    <td
                      className={`px-4 py-2 text-right tabular-nums ${
                        row.shortfall ? 'font-semibold text-rose-700' : 'text-ink-faint'
                      }`}
                    >
                      {row.shortfall}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <p className="border-t border-hairline px-4 py-2 text-xs text-ink-muted">
          "Người cần" ở dòng không giới hạn là người chưa khai giới tính nam/nữ — họ chỉ ở được
          phòng loại này.
        </p>
      </Card>
    </div>
  )
}

function HotelCard({ hotel, onEdit, onDelete }) {
  const directions = mapsUrl({
    name: hotel.name,
    address: hotel.address,
    map_url: hotel.map_url,
  })

  return (
    <Card
      title={hotel.name}
      description={`${hotel.room_count} phòng · ${hotel.assigned_count}/${hotel.bed_count} giường có người`}
      action={
        <div className="flex gap-1">
          <Button variant="ghost" size="sm" icon={Pencil} onClick={onEdit}>
            {ROOM_LABELS.edit}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            icon={Trash2}
            disabled={hotel.assigned_count > 0}
            title={hotel.assigned_count > 0 ? 'Khách sạn còn người ở' : undefined}
            onClick={onDelete}
            aria-label={`Xoá ${hotel.name}`}
          />
        </div>
      }
    >
      <dl className="grid gap-x-4 gap-y-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
        <div className="min-w-0 sm:col-span-2">
          <dt className="text-xs text-ink-muted">{ROOM_LABELS.address}</dt>
          <dd className="truncate text-ink">
            {directions ? (
              <a
                href={directions}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-primary-active hover:underline"
              >
                <MapPin className="size-3.5 shrink-0" aria-hidden="true" />
                <span className="truncate">{hotel.address || 'Mở bản đồ'}</span>
              </a>
            ) : (
              '—'
            )}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-ink-muted">{ROOM_LABELS.checkIn}</dt>
          <dd className="text-ink">
            {hotel.check_in_at ? formatFullDateTime(hotel.check_in_at) : '—'}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-ink-muted">{ROOM_LABELS.checkOut}</dt>
          <dd className="text-ink">
            {hotel.check_out_at ? formatFullDateTime(hotel.check_out_at) : '—'}
          </dd>
        </div>
        {hotel.phone && (
          <div>
            <dt className="text-xs text-ink-muted">{ROOM_LABELS.reception}</dt>
            <dd>
              <a
                href={telHref(hotel.phone)}
                className="text-primary-active tabular-nums hover:underline"
              >
                {hotel.phone}
              </a>
            </dd>
          </div>
        )}
      </dl>
    </Card>
  )
}

/**
 * Phòng của người đang tra cứu tồn tại nhưng bị bộ lọc (giới tính / còn chỗ) ẩn mất:
 * nói rõ phòng nào và cho một nút bỏ lọc — không thì BTC tưởng họ chưa có phòng.
 */
function LocatedRoomNotice({ locatedPerson, hotelRooms, visibleRooms, onClearFilters }) {
  const room = locatedPerson?.room
  if (!room) return null
  // Phòng ở khách sạn khác thì effect bên trên đã tự chuyển tab — tới đây chỉ còn ca bị lọc ẩn.
  if (!hotelRooms.some((item) => item.id === room.room_id)) return null
  if (visibleRooms.some((item) => item.id === room.room_id)) return null
  return (
    <Alert tone="warning" className="mt-3" title={`Phòng ${room.room_number} đang bị bộ lọc ẩn`}>
      {locatedPerson.full_name} ở phòng này nhưng bộ lọc hiện tại không hiện nó.{' '}
      <button
        type="button"
        onClick={onClearFilters}
        className="font-medium underline underline-offset-2"
      >
        Bỏ bộ lọc để xem
      </button>
    </Alert>
  )
}

const STAT_TONES = {
  slate: 'text-ink',
  emerald: 'text-emerald-700',
  amber: 'text-amber-700',
}

function Stat({ label, value, tone = 'slate' }) {
  return (
    <div className="rounded-xl border border-hairline bg-surface px-4 py-3">
      <p className="text-xs text-ink-muted">{label}</p>
      <p className={`text-xl leading-tight font-bold tabular-nums ${STAT_TONES[tone]}`}>
        {formatNumber(value)}
      </p>
    </div>
  )
}
