import { useState } from 'react'
import { Check, Crown, Lock, Play, RotateCcw } from 'lucide-react'
import { useActiveEvent } from '../../../hooks/useEvent'
import { useAllocateRooms } from '../../../hooks/useRooms'
import { useToast } from '../../../context/ToastContext'
import {
  ROOM_LABELS,
  ALLOCATION_FLAG_META,
  GENDER_LABELS,
  ROOM_POLICY_META,
} from '../../../utils/constants'
import { formatPercent } from '../../../utils/format'
import Alert from '../../../components/common/Alert'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import FlagList from '../../../components/admin/FlagList'
import Modal from '../../../components/common/Modal'
import Spinner from '../../../components/common/Spinner'

/**
 * Xếp phòng tự động: luôn xem trước, chỉ ghi khi BTC bấm "Áp dụng" — giống chuyến bay và xe.
 *
 * Nam vào phòng nam, nữ vào phòng nữ; ưu tiên cùng team, rồi cùng chuyến bay chiều đi, rồi cùng
 * phòng ban. Nơi gọi dựng component mỗi lần mở nên state luôn sạch.
 */
export default function RoomAllocationModal({ onClose }) {
  const toast = useToast()
  const { data: event, error: eventError } = useActiveEvent()
  const [applied, setApplied] = useState(false)
  const [preview, setPreview] = useState(null)
  const [error, setError] = useState(null)
  const [onlyUsed, setOnlyUsed] = useState(true)
  const { mutateAsync: allocate, isPending } = useAllocateRooms()

  async function run(dryRun) {
    if (!dryRun && (!preview || applied || !canCommit)) return
    setError(null)
    if (dryRun) setPreview(null)
    try {
      const result = await allocate({
        dryRun,
        expectedAssignments: dryRun
          ? undefined
          : preview.rooms.flatMap((room) =>
              room.guests.map((guest) => ({
                registration_id: guest.registration_id,
                room_id: room.room_id,
                is_room_captain: guest.is_room_captain,
                pinned: guest.pinned,
              })),
            ),
      })
      if (dryRun) {
        setPreview(result)
        return
      }
      toast.success(
        `Đã ghi xếp phòng: ${result.summary.assigned} người vào ${result.summary.rooms_used} phòng.` +
          (result.removed_stale
            ? ` Dọn ${result.removed_stale} chỗ của người không còn tham gia.`
            : ''),
      )
      setPreview(result)
      setApplied(true)
    } catch (requestError) {
      setError(requestError)
      if (!dryRun) setPreview(null)
    }
  }

  const canCommit =
    [
      'registration_closed',
      'allocation_processing',
      'information_published',
      'event_started',
      'completed',
    ].includes(event?.status) && !eventError
  const preserved =
    preview?.rooms.reduce(
      (sum, room) => sum + room.guests.filter((guest) => guest.pinned).length,
      0,
    ) ?? 0
  const blocking = (preview?.flags ?? []).filter(
    (flag) => ALLOCATION_FLAG_META[flag.type]?.blocking,
  )
  const visibleRooms = (preview?.rooms ?? []).filter((room) => !onlyUsed || room.assigned > 0)
  const hotels = groupByHotel(visibleRooms)

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={ROOM_LABELS.allocationTitle}
      description={applied ? 'Đã ghi vào hệ thống' : 'Xem trước không ghi gì vào hệ thống'}
      footer={
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-ink-muted">
            {preview ? 'Ghi thật cần kỳ đã đóng đăng ký.' : 'Bấm "Xem trước" để chạy thử.'}
          </p>
          {applied ? (
            <Button onClick={onClose}>{ROOM_LABELS.close}</Button>
          ) : (
            <div className="flex gap-2">
              <Button
                variant="secondary"
                size="md"
                icon={preview ? RotateCcw : Play}
                loading={isPending && !preview}
                disabled={isPending}
                onClick={() => run(true)}
              >
                {preview ? 'Chạy lại' : 'Xem trước'}
              </Button>
              <Button
                size="md"
                icon={Check}
                disabled={!preview || !canCommit || isPending}
                loading={isPending && Boolean(preview)}
                onClick={() => run(false)}
              >
                Áp dụng vào hệ thống
              </Button>
            </div>
          )}
        </div>
      }
    >
      <div className="flex flex-col gap-4">
        <ul className="grid gap-2 text-sm text-ink-muted sm:grid-cols-2">
          <li className="rounded-lg bg-canvas-soft p-3">
            <span className="block font-medium text-ink">Bắt buộc</span>
            Nam vào phòng nam, nữ vào phòng nữ, không vượt sức chứa. Phòng không giới hạn cũng không
            xếp lẫn nam nữ. Người chưa khai giới tính chỉ vào phòng không giới hạn.
          </li>
          <li className="rounded-lg bg-canvas-soft p-3">
            <span className="block font-medium text-ink">Ưu tiên</span>
            Cùng team → cùng chuyến bay chiều đi → cùng phòng ban. Lấp đầy phòng trước khi mở phòng
            mới.
          </li>
        </ul>

        {!canCommit && !applied && (
          <Alert tone="info">
            {eventError
              ? 'Không tải được trạng thái kỳ. Có thể xem trước; tải lại trang trước khi ghi.'
              : 'Có thể xem trước lúc này. Đóng đăng ký trước khi áp dụng xếp phòng.'}
          </Alert>
        )}
        {preview && (
          <Alert
            tone={applied ? 'success' : 'info'}
            title={applied ? 'Đã ghi xếp phòng' : 'Xem trước · chưa ghi'}
          >
            Giữ nguyên {preserved} bản ghi BTC chỉnh tay hoặc import.
          </Alert>
        )}

        {error && (
          <Alert tone="error" title="Không chạy được">
            {error.message}
          </Alert>
        )}

        {isPending && !preview && <Spinner label="Đang tính phương án…" />}

        {preview && (
          <>
            <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
              <Stat label={ROOM_LABELS.needRoom} value={preview.summary.total_guests} />
              <Stat label={ROOM_LABELS.hasRoom} value={preview.summary.assigned} tone="emerald" />
              <Stat
                label="Chưa có phòng"
                value={preview.summary.unassigned}
                tone={preview.summary.unassigned ? 'rose' : 'slate'}
              />
              <Stat
                label={ROOM_LABELS.roomsUsed}
                value={`${preview.summary.rooms_used}/${preview.summary.rooms_total}`}
                hint={`${preview.summary.empty_beds} giường trống trong phòng đã dùng`}
              />
              <Stat
                label={ROOM_LABELS.sameTeam}
                value={formatPercent(preview.summary.same_team_rate)}
              />
              <Stat
                label={ROOM_LABELS.sameFlight}
                value={formatPercent(preview.summary.same_flight_rate)}
              />
            </div>

            {blocking.length > 0 ? (
              <Alert tone="warning" title="Có trường hợp chưa xếp được phòng">
                {blocking.length} người hết giường đúng giới tính hoặc chưa khai giới tính. Vẫn áp
                dụng được, rồi thêm phòng / đổi giới tính một phòng trống và chạy lại — người đã có
                phòng được giữ nguyên nếu BTC chuyển họ sang xếp tay.
              </Alert>
            ) : (
              <Alert tone="success">
                Không có trường hợp thiếu giường hoặc thiếu giới tính. Kiểm tra cảnh báo bên dưới
                trước khi công bố.
              </Alert>
            )}

            {preview.unassigned.length > 0 && (
              <section>
                <h3 className="mb-2 text-sm font-semibold text-ink">
                  Chưa có phòng ({preview.unassigned.length})
                </h3>
                <ul className="flex flex-wrap gap-1.5">
                  {preview.unassigned.map((guest) => (
                    <li key={guest.registration_id}>
                      <Badge tone="rose">
                        {guest.full_name} · {GENDER_LABELS[guest.gender] ?? 'chưa khai giới tính'}
                      </Badge>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            <section>
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-sm font-semibold text-ink">{ROOM_LABELS.eachRoom}</h3>
                <label className="inline-flex items-center gap-2 text-xs text-ink-muted">
                  <input
                    type="checkbox"
                    className="size-4 accent-primary"
                    checked={onlyUsed}
                    onChange={(changeEvent) => setOnlyUsed(changeEvent.target.checked)}
                  />
                  {ROOM_LABELS.usedOnly}
                </label>
              </div>
              {hotels.length === 0 ? (
                <p className="text-sm text-ink-muted">Không có phòng nào để hiển thị.</p>
              ) : (
                <div className="flex flex-col gap-3">
                  {hotels.map((hotel) => (
                    <div key={hotel.id}>
                      {hotels.length > 1 && (
                        <p className="mb-1.5 text-xs font-semibold tracking-wide text-ink-muted uppercase">
                          {hotel.name}
                        </p>
                      )}
                      <ul className="grid gap-2 sm:grid-cols-2">
                        {hotel.rooms.map((room) => (
                          <RoomPreview key={room.room_id} room={room} />
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section>
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-ink">{ROOM_LABELS.warnings}</h3>
                <Badge tone="slate">{preview.flags.length}</Badge>
              </div>
              <FlagList flags={preview.flags} />
            </section>

            <p className="text-xs leading-relaxed text-ink-muted">
              Trọng số đang dùng: cùng team {preview.params.team_weight} · cùng chuyến bay{' '}
              {preview.params.flight_weight} · cùng phòng ban {preview.params.department_weight}.
              Đổi trong cấu hình kỳ, không cần sửa code.
            </p>
          </>
        )}
      </div>
    </Modal>
  )
}

function RoomPreview({ room }) {
  const policy = ROOM_POLICY_META[room.gender_policy] ?? ROOM_POLICY_META.any

  return (
    <li className="rounded-lg border border-hairline p-2.5">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-semibold text-ink tabular-nums">
          {room.room_number}
          {room.floor && (
            <span className="ml-1 text-xs font-normal text-ink-muted">tầng {room.floor}</span>
          )}
        </p>
        <span className="flex items-center gap-1.5">
          <Badge tone={policy.tone}>{policy.label}</Badge>
          <span className="text-xs text-ink-muted tabular-nums">
            {room.assigned}/{room.capacity}
          </span>
        </span>
      </div>
      {room.guests.length === 0 ? (
        <p className="mt-1 text-xs text-ink-faint">{ROOM_LABELS.roomEmpty}</p>
      ) : (
        <ul className="mt-1.5 flex flex-col gap-1">
          {room.guests.map((guest) => (
            <li key={guest.registration_id} className="flex items-center gap-1.5 text-xs">
              <span className="min-w-0 flex-1 truncate text-ink-secondary">
                {guest.full_name}
                <span className="text-ink-faint"> · {guest.team_name}</span>
                {guest.flight_code && (
                  <span className="text-ink-faint"> · {guest.flight_code}</span>
                )}
              </span>
              {guest.is_room_captain && (
                <Crown className="size-3 shrink-0 text-primary" aria-label={ROOM_LABELS.captain} />
              )}
              {guest.pinned && (
                <Lock
                  className="size-3 shrink-0 text-ink-faint"
                  aria-label="BTC xếp tay, giữ nguyên"
                />
              )}
            </li>
          ))}
        </ul>
      )}
    </li>
  )
}

function groupByHotel(rooms) {
  const hotels = new Map()
  for (const room of rooms) {
    const group = hotels.get(room.hotel_id)
    if (group) group.rooms.push(room)
    else hotels.set(room.hotel_id, { id: room.hotel_id, name: room.hotel_name, rooms: [room] })
  }
  return [...hotels.values()]
}

const TONES = {
  slate: 'text-ink',
  emerald: 'text-accent-green',
  rose: 'text-rose-700',
}

function Stat({ label, value, hint, tone = 'slate' }) {
  return (
    <div className="rounded-lg border border-hairline px-3 py-2">
      <p className="text-xs text-ink-muted">{label}</p>
      <p className={`mt-0.5 text-lg font-bold tabular-nums ${TONES[tone]}`}>{value}</p>
      {hint && <p className="text-xs text-ink-faint">{hint}</p>}
    </div>
  )
}
