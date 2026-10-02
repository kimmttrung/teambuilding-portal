import { useId, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { roomPersonSchema } from '../../../utils/schemas'
import { ArrowRightLeft, Crown, HeartPulse, Pencil, Trash2, UserPlus } from 'lucide-react'
import {
  useAssignRoom,
  useDeleteRoom,
  useOccupants,
  useRemoveRoomAssignment,
  useUnassignedRooms,
} from '../../../hooks/useRooms'
import { usePersonLocation } from '../../../hooks/usePeople'
import { scrollIntoView } from '../../../utils/highlight'
import { useToast } from '../../../context/ToastContext'
import {
  ROOM_LABELS,
  GENDER_LABELS,
  ROOM_POLICY_META,
  ROOM_TYPE_LABELS,
} from '../../../utils/constants'
import { canStay } from '../../../utils/rooms'
import Alert from '../../../components/common/Alert'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Modal from '../../../components/common/Modal'
import Select from '../../../components/common/Select'
import Spinner from '../../../components/common/Spinner'
import ReasonDialog from '../../../components/common/ReasonDialog'
import Input from '../../../components/common/Input'
import RoomPickerDialog from './RoomPickerDialog'

/**
 * Một phòng: ai đang ở, trưởng phòng, thêm người, chuyển, bỏ xếp, sửa/xoá phòng.
 * Hộp thoại con thay chỗ hộp thoại này thay vì chồng lên — Esc chỉ đóng một lớp.
 */
export default function RoomDetailModal({ room, rooms = [], onEdit, onClose }) {
  const toast = useToast()
  const { data: occupants, isLoading, error } = useOccupants(room.id)
  const { mutateAsync: assign, isPending: assigning } = useAssignRoom()
  const { mutateAsync: remove, isPending: removing } = useRemoveRoomAssignment()
  const { mutateAsync: deleteRoom, isPending: deleting } = useDeleteRoom()

  const [view, setView] = useState({ name: 'detail' })
  const [operationError, setOperationError] = useState(null)
  // Người BTC đang tra cứu ở phòng này thì tô đỏ dòng tên họ — mở phòng từ ô phòng
  // được tô đỏ mà không thấy tên họ thì tra cứu mất nửa tác dụng.
  const { location: locatedPerson } = usePersonLocation()
  const locatedUserId = locatedPerson?.user_id ?? null

  const policy = ROOM_POLICY_META[room.gender_policy] ?? ROOM_POLICY_META.any
  const backToDetail = () => {
    setOperationError(null)
    setView({ name: 'detail' })
  }

  async function makeCaptain(person) {
    setOperationError(null)
    try {
      await assign({
        registrationId: person.registration_id,
        roomId: room.id,
        isRoomCaptain: true,
      })
      toast.success(`${person.full_name} là trưởng phòng ${room.room_number}.`)
    } catch (captainError) {
      setOperationError(captainError)
    }
  }

  if (view.name === 'move') {
    return (
      <RoomPickerDialog
        title={ROOM_LABELS.changeRoom}
        person={view.person}
        rooms={rooms}
        currentRoomId={room.id}
        pending={assigning}
        onClose={backToDetail}
        onConfirm={async ({ roomId, isRoomCaptain, reason: why }) => {
          const result = await assign({
            registrationId: view.person.registration_id,
            roomId,
            isRoomCaptain,
            replaceExisting: true,
            reason: why,
          })
          toast.success(
            `Đã chuyển ${view.person.full_name} sang phòng ${result.assignment.room_number}.`,
          )
          backToDetail()
        }}
      />
    )
  }

  if (view.name === 'remove') {
    return (
      <ReasonDialog
        title={`Bỏ xếp phòng của ${view.person.full_name}?`}
        description={`Phòng ${room.room_number} · ${room.hotel_name}`}
        confirmLabel="Bỏ xếp phòng"
        pending={removing}
        onClose={backToDetail}
        onConfirm={async (reason) => {
          await remove({ assignmentId: view.person.assignment_id, reason })
          toast.success(`Đã bỏ xếp phòng của ${view.person.full_name}.`)
          backToDetail()
        }}
      />
    )
  }

  if (view.name === 'delete') {
    return (
      <Modal
        open
        onClose={backToDetail}
        title={`Xoá phòng ${room.room_number}?`}
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" size="md" onClick={backToDetail}>
              {ROOM_LABELS.noDelete}
            </Button>
            <Button
              variant="danger"
              size="md"
              icon={Trash2}
              loading={deleting}
              onClick={async () => {
                try {
                  await deleteRoom(room.id)
                  toast.success(`Đã xoá phòng ${room.room_number}.`)
                  onClose()
                } catch (deleteError) {
                  setOperationError(deleteError)
                }
              }}
            >
              {ROOM_LABELS.deleteRoom}
            </Button>
          </div>
        }
      >
        {operationError && (
          <Alert tone="error" className="mb-3">
            {operationError.message}
          </Alert>
        )}
        <p className="text-sm text-ink-secondary">
          Phòng chưa có ai ở. Thao tác được ghi vào nhật ký thay đổi.
        </p>
      </Modal>
    )
  }

  const rows = error ? [] : (occupants ?? [])

  return (
    <Modal
      open
      size="lg"
      onClose={onClose}
      title={`Phòng ${room.room_number}`}
      description={[
        room.hotel_name,
        room.floor ? `tầng ${room.floor}` : null,
        ROOM_TYPE_LABELS[room.room_type] ?? null,
      ]
        .filter(Boolean)
        .join(' · ')}
      footer={
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Button
            variant="ghost"
            size="md"
            icon={Trash2}
            disabled={room.occupied > 0 || !!error || isLoading}
            title={room.occupied > 0 ? 'Chuyển hết người sang phòng khác trước khi xoá' : undefined}
            onClick={() => setView({ name: 'delete' })}
          >
            {ROOM_LABELS.deleteRoom}
          </Button>
          <div className="flex gap-2">
            <Button variant="secondary" size="md" icon={Pencil} onClick={onEdit}>
              {ROOM_LABELS.editRoom}
            </Button>
            <Button variant="secondary" size="md" onClick={onClose}>
              {ROOM_LABELS.close}
            </Button>
          </div>
        </div>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={policy.tone}>{policy.label}</Badge>
          <span className="text-sm text-ink-secondary tabular-nums">
            {room.occupied}/{room.capacity} người
          </span>
          {room.occupied > 0 && !room.has_captain && (
            <Badge tone="amber">{ROOM_LABELS.unassignedCaptain}</Badge>
          )}
        </div>
        {room.note && <p className="text-sm text-ink-muted">{room.note}</p>}

        {isLoading && <Spinner label="Đang tải người ở…" />}
        {error && <Alert tone="error">{error.message}</Alert>}
        {operationError && <Alert tone="error">{operationError.message}</Alert>}

        {!error && occupants && rows.length === 0 && (
          <p className="text-sm text-ink-muted">{ROOM_LABELS.emptyRoom}</p>
        )}

        {rows.length > 0 && (
          <ul className="divide-y divide-hairline rounded-lg border border-hairline">
            {rows.map((person) => (
              <li
                key={person.assignment_id}
                ref={person.user_id === locatedUserId ? scrollIntoView : undefined}
                className={`flex flex-wrap items-center gap-x-3 gap-y-1.5 px-3 py-2.5 ${
                  person.user_id === locatedUserId ? 'border-l-4 border-rose-500 bg-rose-50' : ''
                }`}
              >
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center gap-1.5 text-sm font-medium text-ink">
                    {person.full_name}
                    {person.is_room_captain && (
                      <Badge tone="brand">
                        <Crown className="mr-1 size-3" aria-hidden="true" />
                        {ROOM_LABELS.captain}
                      </Badge>
                    )}
                  </p>
                  <p className="text-xs text-ink-muted">
                    {[person.team_name, GENDER_LABELS[person.gender], person.employee_code]
                      .filter(Boolean)
                      .join(' · ')}
                  </p>
                  {(person.dietary_restriction || person.has_health_note) && (
                    <p className="mt-1 flex flex-wrap gap-1">
                      {person.dietary_restriction && (
                        <Badge tone="slate">Ăn kiêng: {person.dietary_restriction}</Badge>
                      )}
                      {person.has_health_note && (
                        <Badge tone="amber">
                          <HeartPulse className="mr-1 size-3" aria-hidden="true" />
                          Có ghi chú sức khoẻ
                        </Badge>
                      )}
                    </p>
                  )}
                </div>
                <div className="flex gap-1">
                  {!person.is_room_captain && (
                    <Button
                      variant="ghost"
                      size="md"
                      icon={Crown}
                      disabled={assigning}
                      onClick={() => makeCaptain(person)}
                    >
                      {ROOM_LABELS.captain}
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="md"
                    icon={ArrowRightLeft}
                    onClick={() => setView({ name: 'move', person })}
                  >
                    Chuyển
                  </Button>
                  <Button
                    variant="ghost"
                    size="md"
                    icon={Trash2}
                    aria-label={`Bỏ xếp phòng của ${person.full_name}`}
                    onClick={() => {
                      setView({ name: 'remove', person })
                    }}
                  />
                </div>
              </li>
            ))}
          </ul>
        )}

        {!error && !isLoading && room.remaining > 0 && (
          <AddRoomPerson
            room={room}
            pending={assigning}
            onConfirm={async (values) => {
              await assign({
                ...values,
                registrationId: Number(values.registrationId),
                roomId: room.id,
              })
              toast.success(`Đã thêm người vào phòng ${room.room_number}.`)
            }}
          />
        )}
      </div>
    </Modal>
  )
}

function AddRoomPerson({ room, onConfirm, pending }) {
  const formId = useId()
  const [search, setSearch] = useState('')
  const query = useUnassignedRooms({
    gender: room.gender_policy === 'any' ? undefined : room.gender_policy,
    q: search.trim() || undefined,
  })
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: zodResolver(roomPersonSchema),
    defaultValues: { registrationId: '', isRoomCaptain: false },
    mode: 'onTouched',
  })
  const candidates = query.error
    ? []
    : (query.data?.pages.flatMap((page) => page.items) ?? []).filter((person) =>
        canStay(room.gender_policy, person.gender),
      )
  async function submit(values) {
    const person = candidates.find((item) => item.registration_id === Number(values.registrationId))
    if (!person) {
      setError('registrationId', {
        message: 'Người đã chọn không còn trong danh sách. Chọn lại.',
      })
      return
    }
    try {
      await onConfirm(values)
      reset()
    } catch (error) {
      setError('root', { message: error.message })
    }
  }
  return (
    <section className="rounded-lg bg-canvas-soft p-3">
      <h3 className="mb-3 text-sm font-semibold text-ink">{ROOM_LABELS.addPerson}</h3>
      <Input
        type="search"
        label={ROOM_LABELS.searchPerson}
        value={search}
        onChange={(event) => {
          setSearch(event.target.value)
          reset()
        }}
      />
      {query.isLoading ? (
        <Spinner label="Đang tìm người…" />
      ) : query.error ? (
        <Alert tone="error" className="mt-3">
          {query.error.message}
        </Alert>
      ) : (
        <form
          id={formId}
          noValidate
          onSubmit={handleSubmit(submit)}
          className="mt-3 flex flex-col gap-3"
        >
          {errors.root && <Alert tone="error">{errors.root.message}</Alert>}
          {!candidates.length ? (
            <p className="text-caption text-ink-muted">
              Không có người chưa xếp hợp giới tính với phòng này trong kết quả tìm kiếm.
            </p>
          ) : (
            <Select
              label={ROOM_LABELS.person}
              required
              placeholder="— Chọn người —"
              error={errors.registrationId?.message}
              options={candidates.map((person) => ({
                value: String(person.registration_id),
                label: `${person.full_name} · ${person.team_name ?? 'Chưa có team'}`,
              }))}
              {...register('registrationId')}
            />
          )}
          {query.hasNextPage && (
            <Button
              variant="secondary"
              loading={query.isFetchingNextPage}
              onClick={() => query.fetchNextPage()}
            >
              {ROOM_LABELS.loadMore}
            </Button>
          )}
          <div className="flex flex-wrap items-center justify-between gap-2">
            <label className="flex min-h-11 items-center gap-2 text-caption text-ink-secondary">
              <input
                type="checkbox"
                className="size-4 accent-primary"
                {...register('isRoomCaptain')}
              />
              Làm trưởng phòng
              {room.has_captain ? ' (thay trưởng phòng hiện tại)' : ''}
            </label>
            <Button
              type="submit"
              icon={UserPlus}
              disabled={!candidates.length}
              loading={pending || isSubmitting}
            >
              {ROOM_LABELS.placeHere}
            </Button>
          </div>
        </form>
      )}
    </section>
  )
}
