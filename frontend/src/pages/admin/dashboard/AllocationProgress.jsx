import { Link } from 'react-router-dom'
import { BedDouble, Bus, PartyPopper, Plane } from 'lucide-react'
import { EVENT_STATUS } from '../../../utils/constants'
import { formatNumber } from '../../../utils/format'

const STATUS_ORDER = Object.values(EVENT_STATUS)

/**
 * "Phân bổ" (Figma v2 · B1): bốn ô bay / xe / phòng / Gala, mỗi ô một con số "đã xếp / cần xếp" và
 * dẫn thẳng sang màn hình xếp. Chi tiết từng chuyến, từng chặng nằm ở màn hình đó, không lặp lại ở đây.
 */
export default function AllocationProgress({ status, participants, flights, buses, rooms, gala, shiftDemand }) {
  const shifts = Object.entries(shiftDemand ?? {})
  const opened = STATUS_ORDER.indexOf(status) >= STATUS_ORDER.indexOf(EVENT_STATUS.REGISTRATION_CLOSED)

  // Một người cần cả chiều đi lẫn chiều về: lấy chiều đang thiếu nhiều nhất để không báo "xong" sớm.
  const flightUnassigned = flights.length ? Math.max(...flights.map((item) => item.unassigned)) : participants
  const flightWarning = flights.find((item) => item.flights === 0)
    ? 'Có chiều chưa khai chuyến'
    : flights.some((item) => item.shortfall)
      ? `Thiếu ${Math.max(...flights.map((item) => item.shortfall))} ghế`
      : null

  const busDemand = buses.reduce((sum, leg) => sum + leg.demand, 0)
  const busAssigned = buses.reduce((sum, leg) => sum + leg.assigned, 0)
  const busWarning = buses.some((leg) => leg.demand && leg.buses === 0)
    ? 'Có chặng chưa có xe'
    : buses.some((leg) => leg.shortfall)
      ? `Thiếu ${buses.reduce((sum, leg) => sum + leg.shortfall, 0)} ghế`
      : null

  return (
    <section aria-labelledby="dashboard-allocation">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h2 id="dashboard-allocation" className="text-heading-3 text-ink">
          Phân bổ
        </h2>
        <span className="text-caption text-ink-muted">
          {!opened
            ? 'Mở khi đóng đăng ký'
            : shifts.length > 0
              ? `Nguyện vọng ca: ${shifts.map(([shift, count]) => `${shift} ${count}`).join(' · ')}`
              : 'Số người đã xếp so với số cần xếp'}
        </span>
      </div>

      <div className="mt-3.5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Tile
          to="/admin/flights/board"
          icon={Plane}
          sticker="bg-accent-sky"
          title="Chuyến bay"
          done={Math.max(participants - flightUnassigned, 0)}
          total={participants}
          note={flights
            .map((item) => `${item.direction === 'outbound' ? 'Đi' : 'Về'} ${item.flights} chuyến · ${item.usable_capacity} chỗ`)
            .join(' / ')}
          emptyNote="Chưa khai chuyến nào"
          warning={flightWarning}
        />
        <Tile
          to="/admin/buses"
          icon={Bus}
          sticker="bg-accent-green"
          title={buses.length ? `Xe · ${buses.length} chặng` : 'Xe'}
          done={busAssigned}
          total={busDemand}
          note={`${buses.reduce((sum, leg) => sum + leg.buses, 0)} xe · tính theo lượt đi xe`}
          emptyNote={buses.length ? 'Chưa ai cần xe' : 'Chưa khai chặng xe nào'}
          warning={busWarning}
        />
        <Tile
          to="/admin/rooms"
          icon={BedDouble}
          sticker="bg-accent-purple-deep"
          title="Phòng"
          done={rooms.assigned}
          total={rooms.participants}
          note={`${formatNumber(rooms.total_beds)} giường`}
          emptyNote={`${formatNumber(rooms.total_beds)} giường đã khai`}
          warning={rooms.uncovered ? `${rooms.uncovered} người không còn giường hợp lệ` : null}
        />
        <Tile
          to="/admin/gala"
          icon={PartyPopper}
          sticker="bg-accent-pink"
          title="Gala"
          done={gala.assigned}
          total={gala.configured ? gala.seats : 0}
          note={`${gala.tables} bàn${gala.selection_status ? '' : ' · chưa bốc thăm'}`}
          emptyNote="Chưa cấu hình sơ đồ bàn"
          warning={gala.configured && gala.unseated > 0 && opened ? `${gala.unseated} người chưa có ghế` : null}
        />
      </div>
    </section>
  )
}

function Tile({ to, icon: Icon, sticker, title, done, total, note, emptyNote, warning }) {
  return (
    <Link
      to={to}
      aria-label={`${title}: đã xếp ${done} trên ${total}`}
      className="block rounded-lg border border-hairline bg-surface p-4 transition hover:shadow-soft"
    >
      {/* Sticker màu chỉ để phân loại bốn mảng phân bổ (design-notion: bảng sticker là trang trí). */}
      <span className={`grid size-7 place-items-center rounded-md text-on-primary ${sticker}`}>
        <Icon className="size-4" aria-hidden="true" />
      </span>
      <p className="mt-3 text-body-sm font-semibold text-ink">{title}</p>
      <p className="mt-0.5 text-heading-2 text-ink tabular-nums">
        {total ? (
          <>
            {formatNumber(done)}
            <span className="text-ink-faint">/{formatNumber(total)}</span>
          </>
        ) : (
          <span className="text-ink-faint">—</span>
        )}
      </p>
      <p className="text-eyebrow font-normal text-ink-faint">{total ? note : emptyNote}</p>
      {warning && <p className="mt-1.5 text-eyebrow text-amber-800">{warning}</p>}
    </Link>
  )
}
