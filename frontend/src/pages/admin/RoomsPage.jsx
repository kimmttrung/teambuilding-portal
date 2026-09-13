import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { BedDouble, Crown, MapPin, Pencil, Plus, Trash2, Upload, UserPlus, Wand2 } from 'lucide-react'
import {
  useAssignRoom,
  useDeleteHotel,
  useHotels,
  useRoomAssignments,
  useRooms,
  useRoomSummary,
} from '../../hooks/useRooms'
import { useParticipants } from '../../hooks/useRegistration'
import { useToast } from '../../context/ToastContext'
import { GENDER_LABELS, ROOM_POLICY_META, ROOM_TYPE_LABELS } from '../../utils/constants'
import { formatFullDateTime, formatNumber } from '../../utils/format'
import { groupByFloor } from '../../utils/rooms'
import { mapsUrl, telHref } from '../../utils/travel'
import Alert from '../../components/common/Alert'
import Badge from '../../components/common/Badge'
import Button from '../../components/common/Button'
import Card from '../../components/common/Card'
import EmptyState from '../../components/common/EmptyState'
import ExportButton from '../../components/common/ExportButton'
import Modal from '../../components/common/Modal'
import PageHeader from '../../components/common/PageHeader'
import Spinner from '../../components/common/Spinner'
import HotelFormModal from './rooms/HotelFormModal'
import RoomDetailModal from './rooms/RoomDetailModal'
import RoomFormModal from './rooms/RoomFormModal'
import RoomImportModal from './rooms/RoomImportModal'
import RoomPickerDialog from './rooms/RoomPickerDialog'
import RoomAllocationModal from './rooms/RoomAllocationModal'

const POLICY_FILTERS = ['all', 'male', 'female', 'any']
const GENDER_GROUPS = [
  { key: 'male', label: 'Nam' },
  { key: 'female', label: 'Nữ' },
  { key: 'unknown', label: 'Chưa khai nam/nữ' },
]

/**
 * Khách sạn & phòng: giường theo giới tính, sơ đồ phòng theo tầng, người chưa có phòng,
 * xếp tay và import Excel.
 *
 * Khách sạn và bộ lọc nằm trên URL (`?hotel=&policy=&available=1`) để F5 không mất chỗ đang làm.
 * Toàn bộ phòng tải một lần rồi lọc tại chỗ: vài chục tới vài trăm phòng, bấm lọc phải tức thì.
 */
export default function RoomsPage() {
  const toast = useToast()
  const [searchParams, setSearchParams] = useSearchParams()

  const { data: hotels, isLoading: loadingHotels, error: hotelsError } = useHotels()
  const { data: allRooms, isLoading: loadingRooms } = useRooms()
  const { data: summary } = useRoomSummary()
  const { data: assignmentPage } = useRoomAssignments({ page_size: 200 })
  const { data: participantPage } = useParticipants()
  const { mutateAsync: removeHotel, isPending: deletingHotel } = useDeleteHotel()
  const { mutateAsync: assignRoom, isPending: assigning } = useAssignRoom()

  const [hotelForm, setHotelForm] = useState(null) // { hotel: null } = thêm mới
  const [roomForm, setRoomForm] = useState(null) // { room: null } = thêm mới
  const [importing, setImporting] = useState(false)
  const [allocating, setAllocating] = useState(false)
  const [openRoomId, setOpenRoomId] = useState(null)
  const [placing, setPlacing] = useState(null)
  const [deletingHotelRow, setDeletingHotelRow] = useState(null)

  if (loadingHotels || loadingRooms) return <Spinner label="Đang tải khách sạn và phòng…" />
  if (hotelsError) {
    return (
      <Alert tone="error" title="Không tải được danh sách khách sạn">
        {hotelsError.message}
      </Alert>
    )
  }

  const hotelList = hotels ?? []
  const rooms = allRooms ?? []
  const hotelId = Number(searchParams.get('hotel')) || hotelList[0]?.id || null
  const hotel = hotelList.find((item) => item.id === hotelId) ?? null
  const policyFilter = POLICY_FILTERS.includes(searchParams.get('policy')) ? searchParams.get('policy') : 'all'
  const availableOnly = searchParams.get('available') === '1'

  const hotelRooms = rooms.filter((room) => room.hotel_id === hotelId)
  const visibleRooms = hotelRooms.filter(
    (room) =>
      (policyFilter === 'all' || room.gender_policy === policyFilter) && (!availableOnly || room.remaining > 0),
  )
  const floors = groupByFloor(visibleRooms)
  const openRoom = rooms.find((room) => room.id === openRoomId) ?? null

  const listsReady = Boolean(assignmentPage && participantPage)
  const assignedIds = new Set((assignmentPage?.items ?? []).map((row) => row.registration_id))
  const unassigned = (participantPage?.items ?? [])
    .filter((registration) => !assignedIds.has(registration.id))
    .map((registration) => ({
      registration_id: registration.id,
      full_name: registration.user.full_name,
      team_name: registration.user.team_name,
      gender: registration.user.gender,
    }))

  function updateParams(changes) {
    const next = new URLSearchParams(searchParams)
    for (const [key, value] of Object.entries(changes)) {
      if (value === null || value === undefined || value === '') next.delete(key)
      else next.set(key, String(value))
    }
    setSearchParams(next, { replace: true })
  }

  async function confirmDeleteHotel() {
    try {
      await removeHotel(deletingHotelRow.id)
      toast.success(`Đã xoá ${deletingHotelRow.name}.`)
      setDeletingHotelRow(null)
      updateParams({ hotel: null })
    } catch (deleteError) {
      toast.error(deleteError.message)
    }
  }

  async function confirmPlace({ roomId, isRoomCaptain, reason }) {
    try {
      const result = await assignRoom({ registrationId: placing.registration_id, roomId, isRoomCaptain, reason })
      toast.success(`Đã xếp ${placing.full_name} vào phòng ${result.assignment.room_number}.`)
      setPlacing(null)
    } catch (placeError) {
      toast.error(placeError.message)
    }
  }

  return (
    <>
      <PageHeader
        title="Khách sạn & phòng"
        description="Xếp phòng theo giới tính — phòng nam không nhận nữ và ngược lại"
        action={
          <div className="flex flex-wrap gap-2">
            <Button icon={Wand2} disabled={!rooms.length} onClick={() => setAllocating(true)}>
              Xếp phòng tự động
            </Button>
            <Button variant="secondary" icon={Upload} disabled={!hotelList.length} onClick={() => setImporting(true)}>
              Import Excel
            </Button>
            <ExportButton
              url="/rooms/export"
              fallbackName="phan-phong.xlsx"
              disabled={!hotelList.length}
              title="Sheet đầu cùng cột với Import — tải về, sửa rồi import lại được"
            >
              Xuất Excel
            </ExportButton>
            <Button variant="secondary" icon={Plus} disabled={!hotelList.length} onClick={() => setRoomForm({ room: null })}>
              Thêm phòng
            </Button>
            <Button icon={Plus} onClick={() => setHotelForm({ hotel: null })}>
              Thêm khách sạn
            </Button>
          </div>
        }
      />

      {hotelList.length === 0 ? (
        <Card>
          <EmptyState
            icon={BedDouble}
            title="Chưa có khách sạn nào"
            description="Thêm khách sạn, khai phòng theo giới tính, rồi xếp tay hoặc import danh sách từ Excel."
            action={
              <Button icon={Plus} onClick={() => setHotelForm({ hotel: null })}>
                Thêm khách sạn
              </Button>
            }
          />
        </Card>
      ) : (
        <div className="flex flex-col gap-4">
          {summary && <BedBalance summary={summary} />}

          {hotelList.length > 1 && (
            <nav aria-label="Khách sạn" className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
              <div className="flex min-w-max gap-2">
                {hotelList.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => updateParams({ hotel: item.id })}
                    aria-current={item.id === hotelId ? 'page' : undefined}
                    className={`rounded-lg border px-3 py-2 text-left text-sm transition ${
                      item.id === hotelId
                        ? 'border-brand-600 bg-brand-600 text-white'
                        : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
                    }`}
                  >
                    <span className="block font-medium">{item.name}</span>
                    <span className={`block text-xs ${item.id === hotelId ? 'text-brand-100' : 'text-slate-500'}`}>
                      {item.room_count} phòng · {item.assigned_count}/{item.bed_count} giường
                    </span>
                  </button>
                ))}
              </div>
            </nav>
          )}

          <div className="grid gap-4 xl:grid-cols-12">
            <div className="flex min-w-0 flex-col gap-4 xl:col-span-8">
              {hotel && (
                <HotelCard
                  hotel={hotel}
                  onEdit={() => setHotelForm({ hotel })}
                  onDelete={() => setDeletingHotelRow(hotel)}
                />
              )}

              <Card
                title="Sơ đồ phòng"
                description={`${visibleRooms.length}/${hotelRooms.length} phòng · bấm vào phòng để xếp người`}
              >
                <div className="mb-3 flex flex-wrap items-center gap-2">
                  {POLICY_FILTERS.map((value) => {
                    const count =
                      value === 'all'
                        ? hotelRooms.length
                        : hotelRooms.filter((room) => room.gender_policy === value).length
                    return (
                      <button
                        key={value}
                        type="button"
                        aria-pressed={policyFilter === value}
                        onClick={() => updateParams({ policy: value === 'all' ? null : value })}
                        className={`rounded-full px-3 py-1 text-xs font-medium ring-1 transition ring-inset ${
                          policyFilter === value
                            ? 'bg-brand-600 text-white ring-brand-600'
                            : 'bg-white text-slate-700 ring-slate-300 hover:bg-slate-50'
                        }`}
                      >
                        {value === 'all' ? 'Tất cả' : ROOM_POLICY_META[value].label} ({count})
                      </button>
                    )
                  })}
                  <label className="ml-auto inline-flex items-center gap-2 text-sm text-slate-700">
                    <input
                      type="checkbox"
                      className="size-4 accent-brand-600"
                      checked={availableOnly}
                      onChange={(changeEvent) => updateParams({ available: changeEvent.target.checked ? '1' : null })}
                    />
                    Chỉ phòng còn chỗ
                  </label>
                </div>

                {hotelRooms.length === 0 ? (
                  <EmptyState
                    icon={BedDouble}
                    title="Khách sạn này chưa có phòng"
                    description="Thêm từng phòng, ghi rõ sức chứa và phòng dành cho nam, nữ hay không giới hạn."
                    action={
                      <Button icon={Plus} onClick={() => setRoomForm({ room: null })}>
                        Thêm phòng
                      </Button>
                    }
                  />
                ) : floors.length === 0 ? (
                  <p className="text-sm text-slate-500">Không có phòng nào khớp bộ lọc.</p>
                ) : (
                  <div className="flex flex-col gap-4">
                    {floors.map((group) => (
                      <section key={group.floor || 'none'}>
                        <h3 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">
                          {group.floor ? `Tầng ${group.floor}` : 'Chưa ghi tầng'} · {group.rooms.length} phòng
                        </h3>
                        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-6">
                          {group.rooms.map((room) => (
                            <RoomTile key={room.id} room={room} onOpen={() => setOpenRoomId(room.id)} />
                          ))}
                        </div>
                      </section>
                    ))}
                  </div>
                )}
              </Card>
            </div>

            <aside className="flex min-w-0 flex-col gap-4 xl:col-span-4">
              <UnassignedPanel
                ready={listsReady}
                people={unassigned}
                onPlace={setPlacing}
                truncated={(assignmentPage?.total ?? 0) > (assignmentPage?.items?.length ?? 0)}
              />
              <Card title="Thứ tự làm việc">
                <ol className="flex flex-col gap-2 text-sm text-slate-600">
                  <li>1. Khai khách sạn và đủ phòng; ghi rõ phòng nam, nữ hay không giới hạn.</li>
                  <li>2. Xem bảng giường ở trên: thiếu giường giới nào thì đổi một phòng trống hoặc thêm phòng.</li>
                  <li>
                    3. Bấm <strong>Xếp phòng tự động</strong> → xem trước → áp dụng (kỳ phải đã đóng đăng ký), hoặc{' '}
                    <strong>Import Excel</strong> nếu đã có danh sách.
                  </li>
                  <li>4. Sửa trường hợp đặc biệt: bấm vào phòng để chuyển người; người xếp tay được giữ nguyên khi chạy lại.</li>
                  <li>5. Trưởng phòng được chọn tự động (ưu tiên trưởng nhóm); đổi trong chi tiết phòng nếu cần.</li>
                </ol>
              </Card>
            </aside>
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
          room={openRoom}
          rooms={rooms}
          unassigned={unassigned}
          onEdit={() => setRoomForm({ room: openRoom })}
          onClose={() => setOpenRoomId(null)}
        />
      )}
      {placing && (
        <RoomPickerDialog
          title="Xếp phòng"
          person={placing}
          rooms={rooms}
          pending={assigning}
          onConfirm={confirmPlace}
          onClose={() => setPlacing(null)}
        />
      )}

      <Modal
        open={Boolean(deletingHotelRow)}
        onClose={() => setDeletingHotelRow(null)}
        title={`Xoá ${deletingHotelRow?.name ?? 'khách sạn'}?`}
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" size="sm" onClick={() => setDeletingHotelRow(null)}>
              Không xoá
            </Button>
            <Button variant="danger" size="sm" icon={Trash2} loading={deletingHotel} onClick={confirmDeleteHotel}>
              Xoá khách sạn
            </Button>
          </div>
        }
      >
        <p className="text-sm text-slate-700">
          Chỉ xoá được khi khách sạn không còn ai ở. Các phòng trống của khách sạn bị xoá theo. Thao tác được ghi
          vào nhật ký thay đổi.
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
        <Stat label="Người tham gia" value={summary.participants} />
        <Stat label="Đã có phòng" value={summary.assigned} tone="emerald" />
        <Stat label="Chưa có phòng" value={summary.unassigned} tone={summary.unassigned ? 'amber' : 'slate'} />
        <Stat label="Giường" value={summary.total_beds} />
      </div>

      {summary.uncovered > 0 && (
        <Alert tone="warning" title={`${summary.uncovered} người không còn giường hợp giới tính`}>
          Tổng giường có thể vẫn đủ, nhưng thiếu ở giới tính dưới đây. Đổi một phòng trống sang giới tính còn thiếu,
          hoặc thêm phòng.
        </Alert>
      )}

      <Card bodyClassName="p-0">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left text-xs tracking-wide text-slate-400 uppercase">
                <th className="px-4 py-2 font-medium">Phòng dành cho</th>
                <th className="px-3 py-2 text-right font-medium">Phòng</th>
                <th className="px-3 py-2 text-right font-medium">Giường</th>
                <th className="px-3 py-2 text-right font-medium">Đã ở</th>
                <th className="px-3 py-2 text-right font-medium">Còn trống</th>
                <th className="px-3 py-2 text-right font-medium">Người cần</th>
                <th className="px-4 py-2 text-right font-medium">Thiếu</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {summary.by_policy.map((row) => {
                const meta = ROOM_POLICY_META[row.gender_policy] ?? { label: row.gender_policy, tone: 'slate' }
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
                        row.shortfall ? 'font-semibold text-rose-700' : 'text-slate-400'
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
        <p className="border-t border-slate-100 px-4 py-2 text-xs text-slate-500">
          "Người cần" ở dòng không giới hạn là người chưa khai giới tính nam/nữ — họ chỉ ở được phòng loại này.
        </p>
      </Card>
    </div>
  )
}

function HotelCard({ hotel, onEdit, onDelete }) {
  const directions = mapsUrl({ name: hotel.name, address: hotel.address, map_url: hotel.map_url })

  return (
    <Card
      title={hotel.name}
      description={`${hotel.room_count} phòng · ${hotel.assigned_count}/${hotel.bed_count} giường có người`}
      action={
        <div className="flex gap-1">
          <Button variant="ghost" size="sm" icon={Pencil} onClick={onEdit}>
            Sửa
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
          <dt className="text-xs text-slate-500">Địa chỉ</dt>
          <dd className="truncate text-slate-900">
            {directions ? (
              <a href={directions} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-brand-700 hover:underline">
                <MapPin className="size-3.5 shrink-0" aria-hidden="true" />
                <span className="truncate">{hotel.address || 'Mở bản đồ'}</span>
              </a>
            ) : (
              '—'
            )}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Nhận phòng</dt>
          <dd className="text-slate-900">{hotel.check_in_at ? formatFullDateTime(hotel.check_in_at) : '—'}</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Trả phòng</dt>
          <dd className="text-slate-900">{hotel.check_out_at ? formatFullDateTime(hotel.check_out_at) : '—'}</dd>
        </div>
        {hotel.phone && (
          <div>
            <dt className="text-xs text-slate-500">Lễ tân</dt>
            <dd>
              <a href={telHref(hotel.phone)} className="text-brand-700 tabular-nums hover:underline">
                {hotel.phone}
              </a>
            </dd>
          </div>
        )}
      </dl>
    </Card>
  )
}

/** Ô phòng: số chấm = sức chứa, chấm đậm = đã có người. Luôn kèm số, không chỉ dựa vào màu. */
function RoomTile({ room, onOpen }) {
  const policy = ROOM_POLICY_META[room.gender_policy] ?? ROOM_POLICY_META.any
  const full = room.remaining <= 0

  return (
    <button
      type="button"
      onClick={onOpen}
      className={`rounded-lg border p-2.5 text-left transition hover:border-brand-400 focus-visible:ring-2 focus-visible:ring-brand-300 focus-visible:outline-none ${
        full ? 'border-slate-200 bg-slate-50' : 'border-slate-200 bg-white'
      }`}
      aria-label={`Phòng ${room.room_number}, ${policy.label}, ${room.occupied} trên ${room.capacity} người`}
    >
      <span className="flex items-center justify-between gap-1.5">
        <span className="flex items-center gap-1 font-semibold text-slate-900 tabular-nums">
          {room.room_number}
          {room.has_captain && <Crown className="size-3 text-brand-600" aria-hidden="true" />}
        </span>
        <Badge tone={policy.tone}>{policy.label}</Badge>
      </span>
      <span className="mt-0.5 block truncate text-xs text-slate-500">
        {ROOM_TYPE_LABELS[room.room_type] ?? 'Chưa ghi loại'}
      </span>
      <span className="mt-2 flex items-center justify-between gap-2">
        <span className="flex flex-wrap gap-1" aria-hidden="true">
          {Array.from({ length: room.capacity }, (_, index) => (
            <span
              key={index}
              className={`size-2.5 rounded-full ${index < room.occupied ? 'bg-brand-600' : 'bg-slate-200'}`}
            />
          ))}
        </span>
        <span className={`text-xs tabular-nums ${full ? 'font-medium text-slate-500' : 'text-slate-600'}`}>
          {room.occupied}/{room.capacity}
        </span>
      </span>
    </button>
  )
}

function UnassignedPanel({ ready, people, onPlace, truncated }) {
  const groups = GENDER_GROUPS.map((group) => ({
    ...group,
    people: people.filter((person) =>
      group.key === 'unknown' ? !['male', 'female'].includes(person.gender) : person.gender === group.key,
    ),
  })).filter((group) => group.people.length)

  return (
    <Card
      title="Chưa có phòng"
      description={ready && people.length ? 'Gom theo giới tính' : undefined}
      action={ready ? <Badge tone={people.length ? 'amber' : 'emerald'}>{people.length}</Badge> : null}
      bodyClassName="p-0"
    >
      {!ready ? (
        <Spinner label="Đang tải danh sách…" />
      ) : people.length === 0 ? (
        <p className="px-4 py-3.5 text-sm text-emerald-700">Mọi người tham gia đều đã có phòng.</p>
      ) : (
        <div className="max-h-[32rem] divide-y divide-slate-100 overflow-y-auto">
          {truncated && (
            <p className="px-4 py-2 text-xs text-amber-700">
              Danh sách phân phòng quá dài để tải hết — số người chưa có phòng có thể chưa chính xác.
            </p>
          )}
          {groups.map((group) => (
            <section key={group.key}>
              <h3 className="bg-slate-50 px-4 py-1.5 text-xs font-semibold tracking-wide text-slate-500 uppercase">
                {group.label} · {group.people.length}
              </h3>
              <ul className="divide-y divide-slate-100">
                {group.people.map((person) => (
                  <li key={person.registration_id} className="flex items-center gap-2 px-4 py-2">
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm text-slate-900">{person.full_name}</span>
                      <span className="block truncate text-xs text-slate-500">
                        {person.team_name ?? 'Chưa có team'}
                        {group.key === 'unknown' && person.gender ? ` · ${GENDER_LABELS[person.gender] ?? person.gender}` : ''}
                      </span>
                    </span>
                    <Button variant="ghost" size="sm" icon={UserPlus} onClick={() => onPlace(person)}>
                      Xếp phòng
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
}

function Stat({ label, value, tone = 'slate' }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3">
      <p className="text-xs text-slate-500">{label}</p>
      <p className={`text-xl leading-tight font-bold tabular-nums ${STAT_TONES[tone]}`}>{formatNumber(value)}</p>
    </div>
  )
}
