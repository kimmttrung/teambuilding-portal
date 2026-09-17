import { Link } from 'react-router-dom'
import { BedDouble, Bus, PartyPopper, Plane, Search } from 'lucide-react'
import { usePersonLocation } from '../../hooks/usePeople'
import { FLIGHT_DIRECTION_LABELS, REGISTRATION_STATUS_META } from '../../utils/constants'
import { formatFullDateTime } from '../../utils/format'
import Alert from '../../components/common/Alert'
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

      <div className="mb-4">
        <PersonLocator />
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

  return (
    <div className="grid gap-4 xl:grid-cols-12">
      <div className="min-w-0 xl:col-span-8">
        <Card title="Lộ trình trong kỳ này" bodyClassName="p-0">
          {!joining ? (
            <div className="p-4">
              <Alert tone="warning" title="Người này không tham gia kỳ đang xem">
                {REGISTRATION_STATUS_META[location.registration_status]?.label ?? 'Chưa đăng ký'} — nên
                không có chuyến bay, xe, phòng hay ghế Gala nào được xếp.
              </Alert>
            </div>
          ) : (
            <ul className="divide-y divide-slate-100">
              <Row
                icon={Plane}
                label={`Chuyến bay ${FLIGHT_DIRECTION_LABELS.outbound.toLowerCase()}`}
                to="/admin/flights"
                person={location.user_id}
                value={flightLabel(flights.outbound)}
                hint={flights.outbound && formatFullDateTime(flights.outbound.departure_time)}
                mode={flights.outbound?.assignment_mode}
              />
              <Row
                icon={Plane}
                label={`Chuyến bay ${FLIGHT_DIRECTION_LABELS.return.toLowerCase()}`}
                to="/admin/flights"
                person={location.user_id}
                value={flightLabel(flights.return)}
                hint={flights.return && formatFullDateTime(flights.return.departure_time)}
                mode={flights.return?.assignment_mode}
              />

              {(location.buses ?? []).map((leg) => (
                <Row
                  key={leg.trip_leg_id}
                  icon={Bus}
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
                label="Phòng khách sạn"
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
                label="Ghế Gala Dinner"
                to="/admin/gala"
                person={location.user_id}
                value={
                  location.gala
                    ? `Bàn ${location.gala.table_code} – ghế ${location.gala.seat_number}`
                    : null
                }
                hint={location.gala?.table_name}
              />
            </ul>
          )}
        </Card>
      </div>

      <div className="min-w-0 xl:col-span-4">
        <Card title="Người được tra cứu">
          <dl className="grid gap-2 text-sm">
            <Field label="Họ tên" value={location.full_name} />
            <Field label="Mã nhân viên" value={location.employee_code} />
            <Field label="Email" value={location.email} />
            <Field
              label="Điện thoại"
              value={
                location.phone ? (
                  <a href={`tel:${location.phone}`} className="text-brand-700 underline">
                    {location.phone}
                  </a>
                ) : null
              }
            />
            <Field label="Team" value={location.team_name} />
            <Field label="Ca nguyện vọng" value={location.shift?.name} />
            <Field
              label="Đăng ký"
              value={
                <Badge tone={location.registration_status === 'submitted' ? 'emerald' : 'slate'}>
                  {REGISTRATION_STATUS_META[location.registration_status]?.label ?? 'Chưa đăng ký'}
                </Badge>
              }
            />
          </dl>
          <p className="mt-3 text-xs text-slate-500">
            Màn hình này chỉ hiện chỗ ngồi. Xem hồ sơ đầy đủ ở{' '}
            <Link to="/admin/users" className="underline">
              Quản lý CBNV
            </Link>
            .
          </p>
        </Card>
      </div>
    </div>
  )
}

function Row({ icon: Icon, label, value, hint, mode, to, person }) {
  return (
    <li className="flex flex-wrap items-center gap-3 px-4 py-3">
      <Icon className={`size-5 shrink-0 ${value ? 'text-slate-500' : 'text-slate-300'}`} aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="text-xs text-slate-500">{label}</p>
        {value ? (
          <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-slate-900">
            {value}
            {mode === 'manual' && <Badge tone="blue">BTC xếp tay</Badge>}
          </p>
        ) : (
          <p className="text-sm text-amber-700">Chưa được xếp</p>
        )}
        {hint && <p className="text-xs text-slate-500">{hint}</p>}
      </div>
      <Link
        to={`${to}?person=${person}`}
        className="shrink-0 text-xs font-medium text-brand-700 underline-offset-2 hover:underline"
      >
        Mở màn hình
      </Link>
    </li>
  )
}

function Field({ label, value }) {
  return (
    <div className="flex gap-2">
      <dt className="w-32 shrink-0 text-slate-500">{label}</dt>
      <dd className="min-w-0 flex-1 text-slate-900">{value || '—'}</dd>
    </div>
  )
}

function flightLabel(flight) {
  if (!flight) return null
  const seat = flight.seat_number ? ` · ghế ${flight.seat_number}` : ''
  return `${flight.flight_code} ${flight.departure_airport}→${flight.arrival_airport}${seat}`
}
