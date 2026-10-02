import { teamDotClass } from '../../../utils/rooms'
import { ROOM_LABELS, ROOM_POLICY_META, GENDER_LABELS } from '../../../utils/constants'
import { highlightTargets, usePersonLocation } from '../../../hooks/usePeople'
import { scrollIntoView } from '../../../utils/highlight'
import Alert from '../../../components/common/Alert'
import Button from '../../../components/common/Button'
import Spinner from '../../../components/common/Spinner'
import lockIcon from '../../../assets/rooms/lock-small.svg'
import dragIcon from '../../../assets/rooms/drag.svg'

export function RoomPolicyBadge({ policy, compact = false }) {
  return (
    <span
      title={ROOM_POLICY_META[policy]?.label}
      className={`shrink-0 rounded-sm px-2 py-1 text-eyebrow ${policy === 'male' ? 'bg-primary/10 text-primary-active' : policy === 'female' ? 'bg-accent-pink/10 text-accent-purple-deep' : 'bg-canvas-soft text-ink-muted'}`}
    >
      {compact && policy === 'any' ? '—' : (ROOM_POLICY_META[policy]?.label ?? policy)}
    </span>
  )
}

export function RoomTile({ room, onOpen, onDrop, dragging, guests = [], ready = true }) {
  const { location } = usePersonLocation()
  const highlighted = highlightTargets(location).rooms.has(room.id)
  const pinned = guests.some((person) => person.assignment_mode === 'manual')
  const teams = new Set(guests.map((person) => person.team_id).filter((id) => id != null))
  const compatible =
    dragging &&
    room.remaining > 0 &&
    (room.gender_policy === 'any' || room.gender_policy === dragging.gender)
  return (
    <button
      type="button"
      onClick={onOpen}
      onDragOver={(event) => {
        if (dragging) {
          event.preventDefault()
          event.dataTransfer.dropEffect = 'move'
        }
      }}
      onDrop={(event) => {
        event.preventDefault()
        onDrop?.(event, room)
      }}
      ref={highlighted ? scrollIntoView : undefined}
      className={`min-h-20 rounded-lg border bg-surface p-3 text-left transition hover:shadow-soft ${highlighted ? 'border-primary ring-2 ring-primary/30' : compatible ? 'border-dashed border-primary bg-primary/5' : 'border-hairline'}`}
      aria-label={`Phòng ${room.room_number}, ${ROOM_POLICY_META[room.gender_policy]?.label}, ${room.occupied} trên ${room.capacity} người`}
    >
      <span className="flex items-center justify-between gap-2">
        <span className="flex min-w-0 items-center gap-1 font-bold text-ink tabular-nums">
          <span className="truncate" title={room.room_number}>
            {room.room_number}
          </span>
          {pinned && <img src={lockIcon} className="size-[13px] shrink-0" alt={ROOM_LABELS.manual} />}
        </span>
        <RoomPolicyBadge policy={room.gender_policy} compact />
      </span>
      <span className="mt-3 flex items-center justify-between gap-2">
        <span className="flex flex-wrap gap-1" aria-hidden="true">
          {Array.from({ length: room.capacity }, (_, index) => (
            <span
              key={index}
              className={`size-5 rounded-full ${index < room.occupied ? (ready && guests[index] ? teamDotClass(guests[index].team_id) : 'bg-ink-faint') : 'border border-dashed border-input-border'}`}
            />
          ))}
        </span>
        <span className="shrink-0 text-xs text-ink-muted tabular-nums">
          {room.occupied}/{room.capacity}
        </span>
      </span>
      {teams.size > 1 && (
        <span className="mt-2 block text-xs text-ink-muted">{teams.size} team khác nhau</span>
      )}
      {compatible && (
        <span className="mt-2 block text-xs font-medium text-primary">
          Thả {dragging.full_name} vào đây
        </span>
      )}
    </button>
  )
}

export function UnassignedPanel({
  query,
  onPlace,
  onDrag,
  onDragEnd,
  children,
  draggable = true,
  filtered = false,
  panelRef,
}) {
  const people = query.error ? [] : (query.data?.pages.flatMap((page) => page.items) ?? [])
  const total = query.error ? null : query.data?.pages[0]?.total
  return (
    <aside ref={panelRef} className="rounded-lg border border-hairline bg-surface p-4 lg:p-6">
      <h2 className="text-lg font-bold text-ink">
        {ROOM_LABELS.unassigned}
        {total != null ? ` · ${total}` : ''}
      </h2>
      <p className="mt-1 text-xs text-ink-muted">Kéo vào ô phòng còn chỗ hoặc bấm Xếp phòng.</p>
      {children}
      {query.isLoading ? (
        <Spinner label="Đang tải danh sách…" />
      ) : query.error ? (
        <Alert tone="error" className="mt-3">
          {query.error.message}
          <Button variant="ghost" onClick={() => query.refetch()}>
            {ROOM_LABELS.tryAgain}
          </Button>
        </Alert>
      ) : total === 0 ? (
        <p className="mt-4 text-caption text-ink-muted">
          {filtered ? 'Không có người khớp tìm kiếm.' : ROOM_LABELS.empty}
        </p>
      ) : (
        <ul className="mt-4 flex max-h-[36rem] flex-col gap-2 overflow-y-auto">
          {people.map((person) => (
            <li
              key={person.registration_id}
              draggable={draggable}
              onDragStart={(event) => {
                event.dataTransfer.setData(
                  'application/x-teambuilding-room',
                  String(person.registration_id),
                )
                event.dataTransfer.effectAllowed = 'move'
                onDrag?.(person)
              }}
              onDragEnd={onDragEnd}
              className="flex flex-wrap items-center gap-2 rounded-lg border border-hairline bg-surface p-3"
            >
              {draggable && (
                <img src={dragIcon} className="size-[15px] shrink-0 cursor-grab" alt="" />
              )}
              <span
                aria-hidden="true"
                className={`size-6 shrink-0 rounded-full ${teamDotClass(person.team_id)}`}
              />
              <div className="min-w-0 flex-1 basis-[calc(100%-4rem)]">
                <p className="break-words text-sm font-semibold text-ink" title={person.full_name}>
                  {person.full_name}
                </p>
                <p className="truncate text-xs text-ink-muted">
                  {GENDER_LABELS[person.gender] ?? 'Chưa khai nam/nữ'} ·{' '}
                  {person.team_name ?? 'Chưa có team'}
                </p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="ml-auto max-sm:min-h-11"
                aria-label={`Xếp phòng cho ${person.full_name}`}
                onClick={() => onPlace(person)}
              >
                {ROOM_LABELS.place}
              </Button>
            </li>
          ))}
        </ul>
      )}
      {query.hasNextPage && !query.error && (
        <Button
          variant="secondary"
          className="mt-3 w-full"
          loading={query.isFetchingNextPage}
          onClick={() => query.fetchNextPage()}
        >
          {ROOM_LABELS.loadMore}
        </Button>
      )}
    </aside>
  )
}
