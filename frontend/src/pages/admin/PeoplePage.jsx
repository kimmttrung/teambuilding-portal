import { Link } from 'react-router-dom'
import { BedDouble, Bus, PartyPopper, Phone, Plane, Search, UserRound } from 'lucide-react'
import { usePersonLocation } from '../../hooks/usePeople'
import { FLIGHT_DIRECTION_LABELS, REGISTRATION_STATUS_META } from '../../utils/constants'
import { formatFullDateTime, formatPhone } from '../../utils/format'
import Alert from '../../components/common/Alert'
import Avatar from '../../components/common/Avatar'
import Badge from '../../components/common/Badge'
import Card from '../../components/common/Card'
import EmptyState from '../../components/common/EmptyState'
import PageHeader from '../../components/common/PageHeader'
import PersonLocator from '../../components/admin/PersonLocator'
import Spinner from '../../components/common/Spinner'

/**
 * Tra cứu trọn lộ trình của một người trong một màn hình (docs/13 task 7).
 *
 * Dùng khi CBNV gọi hỏi "tôi đi chuyến nào, ở phòng nào" — BTC không phải mở 4 tab rồi ghép lại.
 * Mỗi mục có đường dẫn sang màn hình tương ứng, mang theo `?person=` để tới nơi là thấy chỗ của họ
 * đã được tô đỏ sẵn.
 */
export default function PeoplePage() {
  const { userId, location, isLoading, error } = usePersonLocation()

  return (
    <>
      <PageHeader
        title="Tra cứu lộ trình"
        description="Một người đang ở chuyến bay nào, xe nào, phòng nào, ghế Gala nào"
      />

      <div className="mb-6">
        <PersonLocator autoFocus />
      </div>

      {!userId ? (
        <Card>
          <EmptyState
            icon={Search}
            title="Chưa chọn ai"
            description="Gõ tên, email hoặc mã nhân viên ở ô trên. Gõ không dấu cũng tìm được."
          />
        </Card>
      ) : isLoading ? (
        <Spinner label="Đang tra cứu…" />
      ) : error ? (
        <Alert tone="error" title="Không tra cứu được">
          {error.message}
        </Alert>
      ) : (
        <PersonJourney location={location} />
      )}
    </>
  )
}

function PersonJourney({ location }) {
  const joining = location.registration_status === 'submitted' && location.is_participating
  const flights = location.flights ?? {}
  const legs = location.buses ?? []
  const ridingLegs = legs.filter((leg) => leg.bus_id).length
  const statusLabel = REGISTRATION_STATUS_META[location.registration_status]?.label ?? 'Chưa đăng ký'

  return (
    <div className="grid gap-x-10 gap-y-6 xl:grid-cols-12">
      {/* Figma v2 · B3: ai đây, đang ở trạng thái nào — rồi mới tới từng chỗ được xếp. */}
      <div className="min-w-0 xl:col-span-5">
        <div className="flex items-center gap-3.5">
          <Avatar user={location} size="md" />
          <div className="min-w-0">
            <h2 className="truncate text-heading-3 text-ink">{location.full_name}</h2>
            <p className="truncate text-body-sm text-ink-muted">
              {[location.team_name && `Team ${location.team_name}`, location.employee_code, location.email]
                .filter(Boolean)
                .join(' · ')}
            </p>
          </div>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          <Chip tone={joining ? 'green' : 'neutral'}>
            {joining && location.shift ? `${statusLabel} · ${location.shift.name}` : statusLabel}
          </Chip>
          {joining && legs.length > 0 && (
            <Chip tone={ridingLegs === legs.length ? 'neutral' : 'warning'}>
              Xe {ridingLegs}/{legs.length} chặng
            </Chip>
          )}
        </div>

        <div className="mt-5 flex flex-wrap gap-2.5">
          {location.phone && (
            <a href={`tel:${location.phone}`} className={UTILITY_LINK}>
              <Phone className="size-3.5" aria-hidden="true" />
              {formatPhone(location.phone)}
            </a>
          )}
          <Link to="/admin/users" className={UTILITY_LINK}>
            <UserRound className="size-3.5" aria-hidden="true" />
            Hồ sơ đầy đủ
          </Link>
        </div>
        <p className="mt-3 text-eyebrow font-normal text-ink-faint">
          Màn hình này chỉ hiện chỗ được xếp, không hiện CCCD hay ngày sinh.
        </p>
      </div>

      <div className="min-w-0 xl:col-span-7">
        <p className="text-eyebrow text-ink-muted">Đang được xếp</p>
        {!joining ? (
          <Alert tone="warning" title="Người này không tham gia kỳ đang xem" className="mt-2">
            {statusLabel} — nên không có chuyến bay, xe, phòng hay ghế Gala nào được xếp.
          </Alert>
        ) : (
          <ul className="mt-2 divide-y divide-hairline rounded-lg border border-hairline bg-surface">
            <Row
              icon={Plane}
              sticker="bg-accent-sky"
              label={`Chuyến bay ${FLIGHT_DIRECTION_LABELS.outbound.toLowerCase()}`}
              to="/admin/flights"
              person={location.user_id}
              value={flightLabel(flights.outbound)}
              hint={flights.outbound && formatFullDateTime(flights.outbound.departure_time)}
              mode={flights.outbound?.assignment_mode}
            />
            <Row
              icon={Plane}
              sticker="bg-accent-sky"
              label={`Chuyến bay ${FLIGHT_DIRECTION_LABELS.return.toLowerCase()}`}
              to="/admin/flights"
              person={location.user_id}
              value={flightLabel(flights.return)}
              hint={flights.return && formatFullDateTime(flights.return.departure_time)}
              mode={flights.return?.assignment_mode}
            />

            {legs.map((leg) => (
              <Row
                key={leg.trip_leg_id}
                icon={Bus}
                sticker="bg-accent-green"
                label={leg.leg_name}
                to="/admin/buses"
                person={location.user_id}
                value={leg.bus_code ? `Xe ${leg.bus_code}` : null}
                hint={leg.pickup_name}
                mode={leg.assignment_mode}
              />
            ))}

            <Row
              icon={BedDouble}
              sticker="bg-accent-purple-deep"
              label="Phòng"
              to="/admin/rooms"
              person={location.user_id}
              value={location.room ? `Phòng ${location.room.room_number}` : null}
              hint={
                location.room &&
                [
                  location.room.hotel_name,
                  location.room.floor && `tầng ${location.room.floor}`,
                  location.room.is_room_captain && 'trưởng phòng',
                ]
                  .filter(Boolean)
                  .join(' · ')
              }
              mode={location.room?.assignment_mode}
            />

            <Row
              icon={PartyPopper}
              sticker="bg-accent-pink"
              label="Gala"
              to="/admin/gala"
              person={location.user_id}
              value={
                location.gala ? `Bàn ${location.gala.table_code} · Ghế ${location.gala.seat_number}` : null
              }
              hint={location.gala?.table_name}
            />
          </ul>
        )}
      </div>
    </div>
  )
}

// design-notion › button-utility dùng cho liên kết: nền surface, viền hairline, bo 8px.
const UTILITY_LINK =
  'inline-flex min-h-11 items-center gap-1.5 rounded-md border border-hairline bg-surface px-3 text-caption font-medium text-ink hover:bg-canvas-soft sm:min-h-8'

// Màu trạng thái của ứng dụng — cùng bộ với Badge, bo 5px như chip của Figma v2.
const CHIP_TONES = {
  green: 'bg-emerald-50 text-emerald-700',
  warning: 'bg-amber-50 text-amber-800',
  neutral: 'bg-canvas-soft text-ink-muted',
}

function Chip({ tone, children }) {
  return (
    <span
      className={`inline-flex h-5.5 items-center rounded-sm px-2 text-eyebrow whitespace-nowrap ${CHIP_TONES[tone]}`}
    >
      {children}
    </span>
  )
}

function Row({ icon: Icon, sticker, label, value, hint, mode, to, person }) {
  return (
    <li className="flex items-center gap-3 px-4 py-3.5">
      {/* Sticker màu chỉ để phân loại bay / xe / phòng / Gala; chưa xếp thì để xám. */}
      <span
        className={`grid size-7 shrink-0 place-items-center rounded-md text-on-primary ${value ? sticker : 'bg-ink-faint'}`}
      >
        <Icon className="size-4" aria-hidden="true" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-eyebrow font-normal text-ink-faint">{label}</p>
        {value ? (
          <p className="flex flex-wrap items-center gap-2 text-body-sm font-semibold text-ink tabular-nums">
            {value}
            {mode === 'manual' && <Badge tone="blue">BTC xếp tay</Badge>}
          </p>
        ) : (
          <p className="text-body-sm font-semibold text-amber-800">Chưa được xếp</p>
        )}
        {hint && <p className="truncate text-caption text-ink-muted">{hint}</p>}
      </div>
      <Link to={`${to}?person=${person}`} className={`${UTILITY_LINK} shrink-0`}>
        {value ? 'Đổi' : 'Xếp'}
      </Link>
    </li>
  )
}

function flightLabel(flight) {
  if (!flight) return null
  const seat = flight.seat_number ? ` · ghế ${flight.seat_number}` : ''
  return `${flight.flight_code} ${flight.departure_airport}→${flight.arrival_airport}${seat}`
}
