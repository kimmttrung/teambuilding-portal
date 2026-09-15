import { Link } from 'react-router-dom'
import {
  Bus,
  Calendar,
  Check,
  ChevronRight,
  ClipboardList,
  FileText,
  MapPin,
  UserRound,
} from 'lucide-react'
import { useActiveEvent, useMyRegistration } from '../../hooks/useEvent'
import { useMyJourney } from '../../hooks/useJourney'
import { useAuth } from '../../context/AuthContext'
import { EVENT_STATUS_META, REGISTRATION_STATUS_META } from '../../utils/constants'
import { daysUntil, formatDate } from '../../utils/format'
import Alert from '../../components/common/Alert'
import Badge from '../../components/common/Badge'
import Button from '../../components/common/Button'
import Card from '../../components/common/Card'
import Spinner from '../../components/common/Spinner'
import AnnouncementsPanel from './journey/AnnouncementsPanel'
import BusCard from './journey/BusCard'
import FlightCard from './journey/FlightCard'
import GalaCard from './journey/GalaCard'
import HotelCard from './journey/HotelCard'
import ItineraryPanel from './journey/ItineraryPanel'
import PendingTiles from './journey/PendingTiles'

export default function MyJourneyPage() {
  const { user } = useAuth()
  const { data: event, isLoading, error } = useActiveEvent()
  const { data: registration, isLoading: loadingRegistration } = useMyRegistration()
  const { data: journey, isLoading: loadingJourney, error: journeyError } = useMyJourney({
    enabled: Boolean(event),
  })

  if (isLoading || loadingRegistration || (event && loadingJourney)) return <Spinner />
  if (error) {
    return (
      <Alert tone="warning" title="Chưa có kỳ Team Building nào">
        {error.message}
      </Alert>
    )
  }

  const statusMeta = EVENT_STATUS_META[event.status] ?? { label: event.status, tone: 'slate' }
  const remaining = daysUntil(event.start_date)
  const buses = journey?.buses ?? []
  const outboundBuses = buses.filter((bus) => bus.trip_leg.direction !== 'return')
  const returnBuses = buses.filter((bus) => bus.trip_leg.direction === 'return')
  const urgent = journey?.announcements.find((item) => item.severity === 'urgent')

  return (
    <div className="flex flex-col gap-4">
      <EventBanner
        event={event}
        statusLabel={statusMeta.label}
        remaining={remaining}
        userName={user.display_name || user.full_name}
      />

      {journeyError && (
        <Alert tone="warning" title="Chưa tải được hành trình">
          {journeyError.message}
        </Alert>
      )}
      {urgent && (
        <Alert tone="error" title={urgent.title}>
          Xem chi tiết ở mục Thông báo từ BTC.
        </Alert>
      )}

      <div className="grid gap-4 xl:grid-cols-12">
        <div className="flex flex-col gap-4 xl:col-span-8">
          {journey && (
            <>
              {/* Theo thứ tự thời gian của chuyến đi (docs/07 §3.2): đi → ở → về. */}
              <JourneySection
                title="Chiều đi"
                items={[
                  ...outboundBuses
                    .filter((bus) => runsBefore(bus, journey.flights.outbound))
                    .map(busItem),
                  journey.flights.outbound && {
                    key: 'flight-outbound',
                    node: <FlightCard flight={journey.flights.outbound} />,
                  },
                  ...outboundBuses
                    .filter((bus) => !runsBefore(bus, journey.flights.outbound))
                    .map(busItem),
                ]}
              />
              <JourneySection
                title="Tại điểm đến"
                items={[
                  journey.accommodation && {
                    key: 'hotel',
                    node: <HotelCard accommodation={journey.accommodation} />,
                  },
                  journey.gala && { key: 'gala', node: <GalaCard gala={journey.gala} /> },
                ]}
              />
              <JourneySection
                title="Chiều về"
                items={[
                  ...returnBuses.map(busItem),
                  journey.flights.return && {
                    key: 'flight-return',
                    node: <FlightCard flight={journey.flights.return} />,
                  },
                ]}
              />
              <PendingTiles parts={journey.pending} reasons={journey.pending_reasons} />
            </>
          )}
          <RegistrationPanel event={event} registration={registration} />
        </div>

        <div className="flex flex-col gap-4 xl:col-span-4">
          {journey && <AnnouncementsPanel announcements={journey.announcements} />}
          {journey && <ItineraryPanel items={journey.itinerary} />}
          <ProgressPanel event={event} registration={registration} />
          <QuickLinks />
        </div>
      </div>
    </div>
  )
}

/**
 * Xe chạy trước chuyến bay hay sau? So giờ thật, không đoán theo mã chặng — số chặng là dữ
 * liệu của từng kỳ (CLAUDE.md cạm bẫy #3). Xe chưa có giờ thì xếp sau chuyến bay.
 */
function runsBefore(bus, flight) {
  const busTime = bus.gather_time || bus.departure_time
  if (!flight || !busTime) return false
  return new Date(busTime) < new Date(flight.departure_time)
}

function busItem(bus) {
  return { key: `bus-${bus.trip_leg.id}`, node: <BusCard bus={bus} /> }
}

/* --- Một chặng của chuyến đi: thẻ xếp 2 cột trên màn hình vừa, 1 cột trên điện thoại --- */
function JourneySection({ title, items }) {
  const visible = items.filter(Boolean)
  if (visible.length === 0) return null

  return (
    <section>
      <h2 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">{title}</h2>
      <div className="grid gap-4 lg:grid-cols-2">
        {visible.map((item) => (
          <div key={item.key} className="min-w-0">
            {item.node}
          </div>
        ))}
      </div>
    </section>
  )
}

/* --- Băng thông tin kỳ: gộp lời chào, tên kỳ, địa điểm, ngày và đếm ngược vào một dải --- */
function EventBanner({ event, statusLabel, remaining, userName }) {
  return (
    <section className="overflow-hidden rounded-xl bg-gradient-to-r from-brand-700 to-brand-600 text-white">
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 px-4 py-4 sm:px-5">
        <div className="min-w-0">
          <p className="text-xs text-brand-200">
            Chào {userName} · {event.code}
          </p>
          <h1 className="mt-0.5 text-lg leading-tight font-bold text-balance sm:text-xl">
            {event.name}
          </h1>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-brand-100">
            {event.destination && (
              <span className="inline-flex items-center gap-1.5">
                <MapPin className="size-3.5" aria-hidden="true" />
                {event.destination}
              </span>
            )}
            <span className="inline-flex items-center gap-1.5">
              <Calendar className="size-3.5" aria-hidden="true" />
              {formatDate(event.start_date)} – {formatDate(event.end_date)}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-5">
          {remaining > 0 && (
            <div className="text-right">
              <p className="text-2xl leading-none font-bold tabular-nums">{remaining}</p>
              <p className="text-xs text-brand-200">ngày nữa</p>
            </div>
          )}
          <span className="rounded-full bg-white/15 px-3 py-1 text-xs font-medium ring-1 ring-white/20 ring-inset">
            {statusLabel}
          </span>
        </div>
      </div>
    </section>
  )
}

/* --- Đăng ký: dàn ngang nhiều cột thay vì 2 cột thưa --- */
function RegistrationPanel({ event, registration }) {
  if (!registration) {
    return (
      <Card title="Đăng ký tham gia">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="max-w-prose text-sm text-slate-600">
            {event.can_register
              ? 'Bạn chưa đăng ký. Hoàn tất đăng ký để BTC xếp chuyến bay, xe và phòng cho bạn.'
              : 'Bạn chưa đăng ký và thời gian đăng ký đã đóng. Liên hệ BTC nếu cần hỗ trợ.'}
          </p>
          {event.can_register && (
            <Link to="/register-event">
              <Button icon={ClipboardList} size="sm">
                Đăng ký ngay
              </Button>
            </Link>
          )}
        </div>
      </Card>
    )
  }

  const meta = REGISTRATION_STATUS_META[registration.status] ?? {
    label: registration.status,
    tone: 'slate',
  }
  const busLegs = registration.bus_needs?.filter((need) => need.needs_bus) ?? []

  return (
    <Card
      title="Đăng ký của bạn"
      action={
        <div className="flex shrink-0 items-center gap-2">
          <Badge tone={meta.tone}>{meta.label}</Badge>
          {registration.can_edit && (
            <Link to="/register-event">
              <Button variant="secondary" size="sm">
                Chỉnh sửa
              </Button>
            </Link>
          )}
        </div>
      }
    >
      <dl className="grid grid-cols-2 gap-x-5 gap-y-3 sm:grid-cols-4">
        <Field label="Tham gia">{registration.is_participating ? 'Có' : 'Không'}</Field>
        <Field label="Ca đăng ký">{registration.shift?.name ?? '—'}</Field>
        <Field label="Đi xe BTC">
          {busLegs.length ? `${busLegs.length}/${registration.bus_needs.length} chặng` : 'Không'}
        </Field>
        <Field label="Quy định">
          {registration.agreed_terms_version ? `Đã đồng ý ${registration.agreed_terms_version}` : '—'}
        </Field>
      </dl>

      {registration.latest_cancellation?.status === 'pending' && (
        <Alert tone="warning" className="mt-3" title="Yêu cầu huỷ đang chờ Ban tổ chức duyệt">
          Vé máy bay, xe, phòng và ghế Gala của bạn vẫn được giữ trong lúc chờ.{' '}
          <Link to="/register-event" className="font-medium underline underline-offset-2">
            Xem hoặc rút yêu cầu
          </Link>
        </Alert>
      )}

      {busLegs.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5 border-t border-slate-100 pt-3">
          {busLegs.map((leg) => (
            <span
              key={leg.trip_leg_id}
              className="inline-flex items-center gap-1.5 rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-700"
            >
              <Bus className="size-3.5 text-slate-400" aria-hidden="true" />
              {leg.trip_leg_name}
              {leg.pickup_point_name && (
                <span className="text-slate-500">· {leg.pickup_point_name}</span>
              )}
            </span>
          ))}
        </div>
      )}

      {registration.wish_note && (
        <p className="mt-3 border-t border-slate-100 pt-3 text-sm text-slate-600">
          <span className="text-xs tracking-wide text-slate-400 uppercase">Ghi chú của bạn: </span>
          {registration.wish_note}
        </p>
      )}

      {!registration.is_participating && registration.not_participating_reason && (
        <p className="mt-3 text-sm text-slate-500">
          Lý do không tham gia: {registration.not_participating_reason}
        </p>
      )}

      {registration.penalty_applied && (
        <Alert tone="warning" className="mt-3">
          Bạn huỷ sau hạn đăng ký nên có thể phải chịu chi phí theo quy định. BTC sẽ liên hệ.
        </Alert>
      )}
    </Card>
  )
}

function Field({ label, children }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs tracking-wide text-slate-400 uppercase">{label}</dt>
      <dd className="mt-0.5 truncate text-sm font-medium text-slate-900">{children}</dd>
    </div>
  )
}

/* --- Tiến trình: thay cho 4 thẻ lớn rỗng, cho thấy đang ở đâu trong quy trình --- */
function ProgressPanel({ event, registration }) {
  const steps = [
    {
      label: 'Gửi đăng ký',
      done: Boolean(registration),
      note: registration ? 'Đã hoàn tất' : 'Chưa đăng ký',
    },
    {
      label: 'BTC đóng đăng ký',
      done: event.status !== 'registration_open' && event.status !== 'draft',
      note: event.can_register ? 'Đang mở' : 'Đã đóng',
    },
    {
      label: 'Phân bổ chuyến bay, xe, phòng',
      done: event.is_published,
      note: event.is_published ? 'Xong' : 'BTC đang xử lý',
    },
    {
      label: 'Công bố thông tin',
      done: event.is_published,
      note: event.is_published ? 'Đã công bố' : 'Chưa công bố',
    },
  ]

  return (
    <Card title="Tiến trình chương trình">
      <ol className="relative space-y-3.5">
        {steps.map((step, index) => (
          <li key={step.label} className="flex gap-3">
            <div className="flex flex-col items-center">
              <span
                className={`grid size-5 shrink-0 place-items-center rounded-full text-white ${
                  step.done ? 'bg-emerald-500' : 'bg-slate-300'
                }`}
              >
                {step.done ? (
                  <Check className="size-3" strokeWidth={3} aria-hidden="true" />
                ) : (
                  <span className="size-1.5 rounded-full bg-white" />
                )}
              </span>
              {index < steps.length - 1 && <span className="mt-1 w-px flex-1 bg-slate-200" />}
            </div>
            <div className="-mt-0.5 min-w-0 pb-0.5">
              <p className="text-sm font-medium text-slate-900">{step.label}</p>
              <p className="text-xs text-slate-500">{step.note}</p>
            </div>
          </li>
        ))}
      </ol>
    </Card>
  )
}

const QUICK_LINKS = [
  { to: '/schedule', icon: Calendar, label: 'Lịch trình chương trình', hint: '3 ngày, từng hoạt động' },
  { to: '/profile', icon: UserRound, label: 'Hồ sơ cá nhân', hint: 'Ảnh, CCCD, size áo' },
  { to: '/register-event', icon: FileText, label: 'Quy định & phí phạt', hint: 'Điều khoản bạn đã đồng ý' },
]

function QuickLinks() {
  return (
    <Card title="Lối tắt" bodyClassName="p-0">
      <ul className="divide-y divide-slate-100">
        {QUICK_LINKS.map(({ to, icon: Icon, label, hint }) => (
          <li key={to}>
            <Link
              to={to}
              className="flex items-center gap-3 px-4 py-2.5 transition hover:bg-slate-50"
            >
              <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-slate-100 text-slate-500">
                <Icon className="size-4" aria-hidden="true" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium text-slate-900">{label}</span>
                <span className="block truncate text-xs text-slate-500">{hint}</span>
              </span>
              <ChevronRight className="size-4 shrink-0 text-slate-300" aria-hidden="true" />
            </Link>
          </li>
        ))}
      </ul>
    </Card>
  )
}
