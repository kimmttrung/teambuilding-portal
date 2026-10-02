import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowRight,
  BedDouble,
  Bell,
  Bus,
  Calendar,
  CalendarPlus,
  ChevronRight,
  MapPin,
  PartyPopper,
  Phone,
  Plane,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import { useActiveEvent } from '../../hooks/useEvent'
import { useMyJourney } from '../../hooks/useJourney'
import { useAuth } from '../../context/AuthContext'
import { daysUntil, formatDate, formatDateWithWeekday, formatTime } from '../../utils/format'
import { buildIcs, downloadIcs, mapsUrl, telHref } from '../../utils/travel'
import Alert from '../../components/common/Alert'
import Badge from '../../components/common/Badge'
import MarkdownText from '../../components/common/MarkdownText'
import Spinner from '../../components/common/Spinner'
import ChatPanel from '../../components/chat/ChatPanel'
import ChatMascot from '../../components/chat/ChatMascot'
import PageContainer from '../../components/layout/PageContainer'
import BusPassengersModal from './journey/BusPassengersModal'

export default function MyJourneyPage() {
  const { user } = useAuth()
  const [passengersOf, setPassengersOf] = useState(null)
  const [chatOpen, setChatOpen] = useState(false)
  const { data: activeEvent, isLoading: loadingEvent, error: eventError } = useActiveEvent()
  const { data: journey, isLoading: loadingJourney, error: journeyError } = useMyJourney({
    enabled: Boolean(activeEvent),
  })

  if (loadingEvent || (activeEvent && loadingJourney && !journey)) return <Spinner />
  if (eventError) {
    return <Alert tone="warning" title="Chưa có kỳ Team Building nào">{eventError.message}</Alert>
  }
  if (journeyError && !journey) {
    return <Alert tone="warning" title="Chưa tải được hành trình">{journeyError.message}</Alert>
  }

  const event = journey?.event ?? activeEvent
  if (!event) return <Spinner />

  const published = Boolean(event.is_published || event.status === 'information_published')
  const hasLeaderBuses = published && (journey?.led_buses ?? []).length > 0
  if (!journey?.registration && !hasLeaderBuses && event.status !== 'event_started' && event.status !== 'completed') {
    return <WaitingRegistration event={event} user={user} />
  }

  return (
    <>
      <JourneyWorkspace
        event={event}
        journey={journey}
        user={user}
        offline={Boolean(journeyError)}
        chatOpen={chatOpen}
        onOpenChat={() => setChatOpen(true)}
        onCloseChat={() => setChatOpen(false)}
        onOpenPassengers={setPassengersOf}
      />
      {chatOpen && (
        <div className="md:hidden">
          <ChatPanel user={user} onClose={() => setChatOpen(false)} />
        </div>
      )}
      {passengersOf && (
        <BusPassengersModal bus={passengersOf} onClose={() => setPassengersOf(null)} />
      )}
    </>
  )
}

function JourneyWorkspace({ event, journey, user, offline, chatOpen, onOpenChat, onCloseChat, onOpenPassengers }) {
  const published = Boolean(event.is_published || event.status === 'information_published')
  const displayJourney = published ? journey : hideAllocations(journey)
  const firstName = getFirstName(
    journey?.profile?.display_name || journey?.profile?.full_name || user?.full_name,
  )
  const remaining = daysUntil(event.start_date)
  const next = findNextAssignment(displayJourney)
  const pending = displayJourney?.pending ?? []

  return (
    <>
      <div className="md:hidden">
        <MobileJourney
          event={event}
          journey={displayJourney}
          user={user}
          offline={offline}
          onOpenChat={onOpenChat}
          onOpenPassengers={onOpenPassengers}
        />
      </div>
      <div className="hidden md:block">
        <PageContainer className="relative">
          <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_360px]">
            <main className="min-w-0">
              <section className="mb-7">
                <p className="text-body-md text-ink-muted">Chào {firstName},</p>
            <h1 className={`mt-2 text-page-title text-balance text-ink ${published && remaining > 0 ? 'max-w-3xl' : 'max-w-none'}`}>
              {published && remaining > 0 ? (
                <>
                  Còn {remaining} ngày
                  {' '}là tới {event.destination || 'Team Building'}.
                </>
              ) : (
                'Hành trình của bạn.'
              )}
                </h1>
              </section>

              {!published && <WaitingNotice event={event} reasons={journey?.pending_reasons} />}
              {published && next && <NextAssignment assignment={next} />}

              <section className="mt-8">
                <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                  <h2 className="text-heading-2 text-ink">Tấm vé của bạn</h2>
                  {published && <CalendarButton label="Thêm tất cả vào lịch" journey={displayJourney} />}
                </div>
                {published ? (
                  <TicketGrid journey={displayJourney} onOpenPassengers={onOpenPassengers} />
                ) : (
                  <PendingTicketGrid parts={pending} reasons={journey?.pending_reasons} />
                )}
              </section>

              {(displayJourney?.led_buses ?? []).length > 0 && (
                <LeaderBuses buses={displayJourney.led_buses} onOpenPassengers={onOpenPassengers} />
              )}

              {published && displayJourney?.itinerary?.length > 0 && (
                <Link
                  to="/schedule"
                  className="mt-5 flex items-center justify-between rounded-xl border border-hairline bg-surface px-4 py-3 text-body-sm font-semibold text-ink shadow-soft transition hover:border-primary/40"
                >
                  <span className="flex items-center gap-2">
                    <Calendar className="size-4 text-primary" />
                    Xem lịch trình sự kiện
                  </span>
                  <ChevronRight className="size-4 text-ink-muted" />
                </Link>
              )}

              <RegistrationSummary registration={journey?.registration} />
            </main>

            <aside className="flex min-w-0 flex-col gap-5">
              {!chatOpen && (
                <>
                  <AnnouncementRail announcements={displayJourney?.announcements} />
                  <TibiCard onOpen={onOpenChat} />
                </>
              )}
            </aside>
          </div>
          {chatOpen && (
            <div className="mt-5 w-full xl:absolute xl:right-0 xl:top-0 xl:mt-0 xl:w-[380px]">
              <ChatPanel user={user} embedded onClose={onCloseChat} />
            </div>
          )}
        </PageContainer>
      </div>
    </>
  )
}

function MobileJourney({ event, journey, user, offline, onOpenChat, onOpenPassengers }) {
  const [selectedTicket, setSelectedTicket] = useState(null)
  const published = Boolean(event.is_published || event.status === 'information_published')
  const next = findNextAssignment(journey)
  const firstName = getFirstName(
    journey?.profile?.display_name || journey?.profile?.full_name || user?.full_name,
  )

  return (
    <div className="relative min-h-[calc(100dvh-7rem)]">
      {offline && <MobileOfflineBanner />}

      {!offline && published && (
        <MobileGreeting event={event} firstName={firstName} next={next} />
      )}

      {offline && next && <MobileLiveBanner assignment={next} />}

      <section className="mt-6">
        <div className="mb-3 flex items-end justify-between gap-3 px-1">
          <h2 className="text-heading-3 text-ink">Tấm vé của bạn</h2>
          {journey?.updated_at && (
            <span className="text-eyebrow text-ink-faint">{formatDate(journey.updated_at)}</span>
          )}
        </div>
        {published ? (
          <TicketGrid
            journey={journey}
            mobile
            onOpenTicket={setSelectedTicket}
            onOpenPassengers={onOpenPassengers}
          />
        ) : (
          <PendingTicketGrid parts={journey?.pending} reasons={journey?.pending_reasons} />
        )}
      </section>

      {(journey?.led_buses ?? []).length > 0 && (
        <LeaderBuses buses={journey.led_buses} onOpenPassengers={onOpenPassengers} />
      )}

      {offline && (
        <p className="mt-5 px-2 text-center text-caption text-ink-faint">
          Tibi, đổi đăng ký và dữ liệu mới cần kết nối mạng.
        </p>
      )}

      <MobileTibiButton onOpen={onOpenChat} />
      {selectedTicket?.type === 'flight' && (
        <MobileFlightSheet
          flight={selectedTicket.data}
          onClose={() => setSelectedTicket(null)}
        />
      )}
    </div>
  )
}

function MobileGreeting({ event, firstName, next }) {
  const remaining = daysUntil(event.start_date)
  if (!next) return null

  return (
    <>
      <section className="mb-6 px-1">
        <p className="text-body-sm text-ink-muted">Chào {firstName},</p>
        <h1 className="mt-1 text-page-title text-ink">
          {remaining > 0 ? (
            <>
              Còn {remaining} ngày
              {' '}là tới {event.destination || 'Team Building'}.
            </>
          ) : (
            <>Hành trình của bạn.</>
          )}
        </h1>
      </section>
      <MobileNextCard assignment={next} />
    </>
  )
}

function MobileNextCard({ assignment }) {
  const mapHref = mapsUrl(assignment.place)
  const phoneHref = telHref(assignment.phone)

  return (
    <section className="relative overflow-hidden rounded-2xl bg-secondary px-5 py-5 text-white shadow-soft">
      <span className="absolute right-5 top-5 size-2.5 rounded-full bg-accent-pink" />
      <p className="text-caption text-white/70">Tiếp theo · {assignment.dateLabel}</p>
      <div className="mt-2 flex items-end gap-4">
        <span className="text-display-2 leading-none tabular-nums">{assignment.time}</span>
        <span className="pb-1 text-body-sm text-white/70">
          {assignment.kind === 'bus' ? 'xe đón' : 'chuyến bay'}
          {daysUntil(assignment.when) > 0 ? ` · còn ${daysUntil(assignment.when)} ngày` : ''}
        </span>
      </div>
      <p className="mt-2 truncate text-body-md font-semibold">{assignment.title}</p>
      <div className="mt-4 grid grid-cols-2 gap-2">
        {mapHref && (
          <a
            href={mapHref}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center justify-center gap-2 rounded-full bg-white px-3 py-2.5 text-button font-medium text-ink"
          >
            <MapPin className="size-4" />
            Chỉ đường
          </a>
        )}
        {phoneHref && (
          <a
            href={phoneHref}
            className="inline-flex items-center justify-center gap-2 rounded-full bg-white/15 px-3 py-2.5 text-button font-medium text-white"
          >
            <Phone className="size-4" />
            Gọi Trưởng xe
          </a>
        )}
      </div>
    </section>
  )
}

function MobileLiveBanner({ assignment }) {
  return (
    <section className="rounded-2xl bg-secondary px-4 py-4 text-white">
      <p className="text-caption text-white/70">Đang diễn ra · {assignment.dateLabel}</p>
      <div className="mt-1 flex items-baseline gap-3">
        <span className="text-display-2 leading-none tabular-nums">{assignment.time}</span>
        <span className="text-body-sm text-white/70">{assignment.title}</span>
      </div>
      <p className="mt-2 text-body-sm font-semibold">{assignment.subtitle}</p>
    </section>
  )
}

function MobileOfflineBanner() {
  return (
    <section className="rounded-xl bg-ink px-5 py-4 text-white">
      <p className="text-body-sm font-semibold">Đang ngoại tuyến</p>
      <p className="mt-1 text-caption leading-relaxed text-white/70">
        Dữ liệu đã tải trước vẫn có thể xem. Kết nối mạng để cập nhật hành trình.
      </p>
    </section>
  )
}

function MobileTibiButton({ onOpen }) {
  return (
    <div className="fixed right-4 bottom-24 z-40 flex items-end gap-2 md:hidden">
      <button
        type="button"
        onClick={onOpen}
        className="rounded-2xl rounded-br-sm bg-white px-3 py-2 text-left text-caption text-ink-secondary shadow-soft ring-1 ring-hairline"
      >
        <strong className="block text-body-sm text-ink">Hỏi Tibi nhé!</strong>
        Ca bay, giấy tờ, trang phục...
      </button>
      <button
        type="button"
        onClick={onOpen}
        aria-label="Mở trợ lý Tibi"
        className="grid size-16 place-items-center rounded-full bg-white shadow-lg ring-4 ring-brand-100"
      >
        <ChatMascot size={56} />
      </button>
    </div>
  )
}

function MobileFlightSheet({ flight, onClose }) {
  const details = [
    { label: 'Chuyến', value: flight.flight_code },
    flight.seat_number && { label: 'Số ghế', value: flight.seat_number },
    flight.ticket_code && { label: 'Mã vé', value: flight.ticket_code },
    flight.airline && { label: 'Hãng bay', value: flight.airline },
  ].filter(Boolean)
  const departureMap = mapsUrl({ name: flight.departure_airport })

  return (
    <div className="fixed inset-0 z-50 flex items-end bg-black/35 md:hidden" onClick={onClose}>
      <section
        role="dialog"
        aria-modal="true"
        aria-label={`Chi tiết chuyến bay ${flight.flight_code}`}
        className="max-h-[88dvh] w-full overflow-y-auto rounded-t-3xl bg-white px-5 pb-6 pt-4 shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mx-auto mb-4 h-1 w-9 rounded-full bg-slate-200" />
        <div className="flex items-center justify-between gap-3">
          <p className="flex min-w-0 items-center gap-2 text-body-sm font-semibold text-ink">
            <span className="grid size-7 place-items-center rounded-lg bg-sky-100 text-sky-700">
              <Plane className="size-4" />
            </span>
            <span className="truncate">
              Chuyến bay · {formatDateWithWeekday(flight.departure_time)}
            </span>
          </p>
          <button type="button" onClick={onClose} className="rounded-full p-2 text-ink-muted hover:bg-canvas-soft" aria-label="Đóng chi tiết">
            ×
          </button>
        </div>

        <div className="mt-5 flex items-end justify-between gap-3">
          <AirportTime time={formatTime(flight.departure_time)} airport={flight.departure_airport} />
          <span className="pb-2 text-2xl text-ink-faint">✈</span>
          <AirportTime time={formatTime(flight.arrival_time)} airport={flight.arrival_airport} align="right" />
        </div>

        {details.length > 0 && (
          <div className="mt-5 grid grid-cols-2 gap-2">
            {details.map((detail) => (
              <div key={detail.label} className="rounded-xl border border-hairline px-3 py-3">
                <p className="text-caption text-ink-faint">{detail.label}</p>
                <p className="mt-1 text-body-md font-semibold text-ink">{detail.value}</p>
              </div>
            ))}
          </div>
        )}

        <div className="mt-5 flex flex-wrap gap-2">
          <CalendarButton label="Thêm vào lịch" data={flight} type="flight" />
          {departureMap && (
            <a href={departureMap} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 rounded-full bg-primary px-4 py-2.5 text-button font-medium text-white">
              <MapPin className="size-4" />
              Chỉ đường
            </a>
          )}
        </div>
      </section>
    </div>
  )
}

function AirportTime({ time, airport, align = 'left' }) {
  return (
    <div className={align === 'right' ? 'text-right' : ''}>
      <p className="text-display-2 leading-none tabular-nums text-ink">{time}</p>
      <p className="mt-1 text-caption font-medium uppercase text-ink-muted">{airport}</p>
    </div>
  )
}

function WaitingRegistration({ event, user }) {
  const canRegister = event.can_register ?? event.status === 'registration_open'

  return (
    <PageContainer className="pt-8">
      <p className="text-body-md text-ink-muted">Chào {getFirstName(user?.full_name)},</p>
      <h1 className="mt-1 max-w-xl text-page-title text-ink">
        {event.destination || 'Team Building'}
        {' '}đang chờ bạn.
      </h1>
      <div className="mt-8 rounded-2xl bg-secondary px-6 py-7 text-on-primary shadow-soft sm:px-8">
        <p className="text-caption text-white/70">Đăng ký tham gia</p>
        <p className="mt-1 text-heading-2 leading-tight">Bạn chưa có đăng ký cho kỳ này.</p>
        <p className="mt-2 max-w-lg text-body-sm leading-relaxed text-white/70">
          Hoàn tất đăng ký để BTC có thể xếp chuyến bay, xe, phòng và chỗ Gala cho bạn.
        </p>
        {canRegister && (
          <Link
            to="/register-event"
            className="mt-6 inline-flex items-center gap-2 rounded-full bg-white px-5 py-3 text-button font-semibold text-ink hover:bg-white/90"
          >
            Bắt đầu đăng ký <ArrowRight className="size-4" />
          </Link>
        )}
      </div>
    </PageContainer>
  )
}

function hideAllocations(journey) {
  if (!journey) return journey
  return {
    ...journey,
    flights: {},
    buses: [],
    led_buses: [],
    accommodation: null,
    gala: null,
  }
}

function WaitingNotice({ event, reasons = {} }) {
  return (
    <section className="rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4">
      <div className="flex items-start gap-3">
        <span className="grid size-9 shrink-0 place-items-center rounded-full bg-amber-100 text-amber-700">
          <ShieldCheck className="size-4" />
        </span>
        <div>
          <h2 className="text-body-md font-semibold text-amber-950">BTC đang chuẩn bị hành trình</h2>
          <p className="mt-1 text-body-sm leading-relaxed text-amber-900/75">
            Thông tin phân bổ sẽ chỉ xuất hiện sau khi chương trình được công bố.
          </p>
          {Object.keys(reasons).length > 0 && (
            <p className="mt-2 text-caption text-amber-900/70">
              Dự kiến công bố cùng thông tin chuyến đi của {event.destination || 'chương trình'}.
            </p>
          )}
        </div>
      </div>
    </section>
  )
}

function NextAssignment({ assignment }) {
  const mapHref = mapsUrl(assignment.place)

  return (
    <section className="relative overflow-hidden rounded-2xl bg-secondary px-6 py-5 text-white shadow-soft sm:px-7">
      <span className="absolute right-6 top-5 size-2.5 rounded-full bg-accent-pink" />
      <span className="absolute right-24 top-5 size-2 rounded-full bg-sky-300" />
      <p className="text-caption text-white/70">Tiếp theo · {assignment.dateLabel}</p>
      <div className="mt-2 flex flex-wrap items-end justify-between gap-5">
        <div className="flex items-end gap-5">
          <span className="text-heading-1 leading-none tabular-nums">{assignment.time}</span>
          <div className="pb-1">
            <p className="text-heading-2 leading-tight">{assignment.title}</p>
            <p className="mt-1 text-body-sm text-white/65">{assignment.subtitle}</p>
          </div>
        </div>
        {mapHref && (
          <a
            href={mapHref}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded-full bg-white px-4 py-2.5 text-button font-semibold text-ink hover:bg-white/90"
          >
            <MapPin className="size-4" />
            Chỉ đường
          </a>
        )}
      </div>
    </section>
  )
}

function TicketGrid({ journey, onOpenPassengers, onOpenTicket, mobile = false }) {
  const tickets = []
  const buses = [...(journey?.buses ?? [])].sort(
    (a, b) => (a.trip_leg?.display_order ?? 0) - (b.trip_leg?.display_order ?? 0),
  )

  buses.forEach((bus) => tickets.push({ type: 'bus', key: `bus-${bus.bus_id}`, data: bus }))
  if (journey?.flights?.outbound) {
    tickets.push({ type: 'flight', key: 'flight-outbound', data: journey.flights.outbound })
  }
  if (journey?.accommodation) tickets.push({ type: 'hotel', key: 'hotel', data: journey.accommodation })
  if (journey?.gala) tickets.push({ type: 'gala', key: 'gala', data: journey.gala })
  if (journey?.flights?.return) {
    tickets.push({ type: 'flight', key: 'flight-return', data: journey.flights.return })
  }

  if (tickets.length === 0) {
    return <PendingTicketGrid parts={journey?.pending} reasons={journey?.pending_reasons} />
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {tickets.map((ticket) => (
        <TicketCard
          key={ticket.key}
          {...ticket}
          mobile={mobile}
          onOpenPassengers={onOpenPassengers}
          onOpenTicket={onOpenTicket}
        />
      ))}
    </div>
  )
}

function TicketCard({ type, data, mobile = false, onOpenPassengers, onOpenTicket }) {
  const meta = {
    bus: { Icon: Bus, tone: 'green', label: data.trip_leg?.name || 'Xe đưa đón' },
    flight: {
      Icon: Plane,
      tone: 'sky',
      label: `Chuyến bay ${data.direction === 'return' ? 'về' : 'đi'}`,
    },
    hotel: { Icon: BedDouble, tone: 'purple', label: data.hotel_name },
    gala: { Icon: PartyPopper, tone: 'pink', label: data.name || 'Gala' },
  }[type]
  const tones = {
    green: 'bg-emerald-100 text-emerald-700',
    sky: 'bg-sky-100 text-sky-700',
    purple: 'bg-violet-100 text-violet-700',
    pink: 'bg-pink-100 text-pink-700',
  }

  return (
    <article className="relative overflow-hidden rounded-xl border border-hairline bg-surface shadow-soft">
      <div className="flex items-center gap-2 px-4 pt-4 text-caption font-semibold text-ink-secondary">
        <span className={`grid size-6 place-items-center rounded-md ${tones[meta.tone]}`}>
          <meta.Icon className="size-3.5" />
        </span>
        <span className="truncate">
          {meta.label}
          {type !== 'hotel' && data.trip_leg?.leg_date ? ` · ${shortDate(data.trip_leg.leg_date)}` : ''}
        </span>
      </div>
      <div className="px-4 pb-3 pt-3">
        <TicketBody type={type} data={data} />
      </div>
      <TicketFooter
        type={type}
        data={data}
        mobile={mobile}
        onOpenPassengers={onOpenPassengers}
        onOpenTicket={onOpenTicket}
      />
    </article>
  )
}

function TicketBody({ type, data }) {
  if (type === 'bus') return <BusBody bus={data} />
  if (type === 'flight') return <FlightBody flight={data} />
  if (type === 'hotel') return <HotelBody stay={data} />
  return <GalaBody gala={data} />
}

function BusBody({ bus }) {
  const gather = bus.gather_time || bus.departure_time

  return (
    <div className="flex items-end gap-4">
      <div>
        <p className="text-heading-1 leading-none tabular-nums text-ink">{formatTime(gather)}</p>
        <p className="mt-1 text-eyebrow uppercase text-ink-muted">Tập trung</p>
      </div>
      <div className="min-w-0">
        <p className="text-heading-2 leading-none text-ink">{bus.bus_code}</p>
        <p className="mt-1 truncate text-eyebrow text-ink-muted">
          {bus.plate_number || 'Chưa có biển số'}
        </p>
      </div>
    </div>
  )
}

function FlightBody({ flight }) {
  return (
    <div className="flex items-end justify-between gap-3">
      <div>
        <p className="text-heading-2 leading-none text-ink">{formatTime(flight.departure_time)}</p>
        <p className="mt-1 text-eyebrow uppercase text-ink-muted">{flight.departure_airport}</p>
      </div>
      <span className="pb-2 text-xl text-ink-faint">→</span>
      <div className="text-right">
        <p className="text-heading-2 leading-none text-ink">{formatTime(flight.arrival_time)}</p>
        <p className="mt-1 text-eyebrow uppercase text-ink-muted">{flight.arrival_airport}</p>
      </div>
    </div>
  )
}

function HotelBody({ stay }) {
  return (
    <div>
      <div className="flex items-baseline gap-3">
        <p className="text-heading-2 leading-none text-ink">P.{stay.room_number}</p>
        <span className="text-body-sm text-ink-faint">{stay.room_type || 'Phòng nghỉ'}</span>
      </div>
      <p className="mt-2 truncate text-body-sm text-ink-muted">
        {stay.roommates?.length
          ? `Ở cùng ${stay.roommates.map((mate) => mate.full_name).join(', ')}`
          : stay.hotel_name}
      </p>
    </div>
  )
}

function GalaBody({ gala }) {
  return (
    <div className="flex items-end gap-6">
      <div>
        <p className="text-heading-2 leading-none text-ink">Bàn {gala.table_code}</p>
        <p className="mt-1 text-eyebrow uppercase text-ink-muted">
          {gala.table_name || 'Gala Dinner'}
        </p>
      </div>
      <div>
        <p className="text-heading-2 leading-none text-ink">Ghế {gala.seat_number}</p>
        <p className="mt-1 text-eyebrow uppercase text-ink-muted">{gala.venue || 'Khu A'}</p>
      </div>
    </div>
  )
}

function TicketFooter({ type, data, mobile = false, onOpenPassengers, onOpenTicket }) {
  if (type === 'bus') {
    return (
      <div className="flex min-h-11 items-center justify-between gap-2 border-t border-dashed border-hairline px-4 text-caption text-ink-muted">
        <span className="truncate">
          {data.leader?.name || data.pickup_point?.name || 'Điểm đón theo thông báo'}
        </span>
        <span className="flex items-center gap-3">
          {data.leader?.phone && <PhoneLink phone={data.leader.phone} label="Gọi" />}
          {data.pickup_point && <MapLink place={data.pickup_point} />}
          {data.leader?.is_current_user && (
            <button
              type="button"
              onClick={() => onOpenPassengers?.(data)}
              className="text-primary hover:underline"
            >
              Danh sách
            </button>
          )}
        </span>
      </div>
    )
  }

  if (type === 'flight') {
    return (
      <div className="flex min-h-11 items-center justify-between gap-2 border-t border-dashed border-hairline px-4 text-caption text-ink-muted">
        <span>
          {data.flight_code}
          {data.shift_code ? ` · ${formatShift(data.shift_code)}` : ''}
        </span>
        {mobile ? (
          <button
            type="button"
            onClick={() => onOpenTicket?.({ type: 'flight', data })}
            className="font-semibold text-primary hover:underline"
          >
            Chi tiết
          </button>
        ) : (
          <CalendarButton label="Thêm vào lịch" data={data} type="flight" />
        )}
      </div>
    )
  }

  if (type === 'hotel') {
    return (
      <div className="flex min-h-11 items-center justify-between gap-2 border-t border-dashed border-hairline px-4 text-caption text-ink-muted">
        <span>{data.hotel_name}</span>
        {(data.map_url || data.address) && (
          <MapLink place={{ name: data.hotel_name, address: data.address, map_url: data.map_url }} />
        )}
      </div>
    )
  }

  return (
    <div className="flex min-h-11 items-center justify-between gap-2 border-t border-dashed border-hairline px-4 text-caption text-ink-muted">
      <span>{data.starts_at ? formatDate(data.starts_at) : 'Theo lịch BTC'}</span>
      <span className="font-semibold text-primary">Xem sơ đồ</span>
    </div>
  )
}

function PendingTicketGrid({ parts = [], reasons = {} }) {
  const labels = {
    flights: ['Chuyến bay', Plane],
    buses: ['Xe đưa đón', Bus],
    accommodation: ['Khách sạn', BedDouble],
    gala: ['Gala Dinner', PartyPopper],
  }
  const shown = parts.length ? parts : Object.keys(labels)

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {shown.map((part) => {
        const [label, Icon] = labels[part] || ['Hành trình', Sparkles]
        return (
          <div key={part} className="rounded-xl border border-dashed border-hairline bg-surface p-4">
            <span className="grid size-8 place-items-center rounded-lg bg-canvas-soft text-ink-muted">
              <Icon className="size-4" />
            </span>
            <p className="mt-3 text-body-md font-semibold text-ink">{label}</p>
            <p className="mt-1 text-caption leading-relaxed text-ink-muted">
              {reasonText(reasons[part])}
            </p>
            <div className="mt-3 h-2 w-3/4 animate-pulse rounded-full bg-hairline" />
          </div>
        )
      })}
    </div>
  )
}

function LeaderBuses({ buses, onOpenPassengers }) {
  return (
    <section aria-label="Xe bạn phụ trách" className="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-4">
      <p className="flex items-center gap-2 text-body-sm font-semibold text-amber-950">
        <ShieldCheck className="size-4" />
        Xe bạn phụ trách
      </p>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        {buses.map((bus) => (
          <button
            key={bus.bus_id}
            type="button"
            onClick={() => onOpenPassengers?.(bus)}
            className="flex items-center justify-between rounded-lg bg-white px-3 py-2 text-left text-caption ring-1 ring-amber-200 transition hover:ring-amber-400"
          >
            <span>
              <strong className="block text-ink">{bus.bus_code}</strong>
              <span className="text-ink-muted">
                {bus.passenger_count}/{bus.capacity} hành khách
              </span>
            </span>
            <ChevronRight className="size-4 text-amber-700" />
          </button>
        ))}
      </div>
    </section>
  )
}

function AnnouncementRail({ announcements = [] }) {
  return (
    <section className="rounded-xl border border-hairline bg-surface p-5 shadow-soft">
      <div className="flex items-center justify-between">
        <h2 className="text-body-md font-semibold text-ink">Từ BTC</h2>
        <Bell className="size-4 text-ink-muted" />
      </div>
      {announcements.length === 0 ? (
        <p className="mt-4 text-body-sm text-ink-muted">Chưa có thông báo mới.</p>
      ) : (
        <div className="mt-3 divide-y divide-hairline">
          {announcements.slice(0, 3).map((item, index) => (
            <details key={item.id} className="group py-3 first:pt-0 last:pb-0" open={index === 0}>
              <summary className="flex cursor-pointer list-none items-start gap-2 [&::-webkit-details-marker]:hidden">
                <AnnouncementBadge severity={item.severity} />
                <span className="min-w-0 flex-1">
                  <span className="block text-body-sm font-medium text-ink">{item.title}</span>
                  <span className="mt-1 block text-caption text-ink-muted group-open:hidden">Xem chi tiết</span>
                </span>
                <ChevronRight className="mt-1 size-4 shrink-0 text-ink-faint transition group-open:rotate-90" />
              </summary>
              <MarkdownText content={item.content} className="mt-3" />
            </details>
          ))}
        </div>
      )}
    </section>
  )
}

function AnnouncementBadge({ severity }) {
  const meta = {
    urgent: { tone: 'rose', label: 'Khẩn' },
    warning: { tone: 'amber', label: 'Lưu ý' },
    info: { tone: 'green', label: 'Thay đổi' },
  }[severity] ?? { tone: 'slate', label: 'Thông tin' }

  return <Badge tone={meta.tone}>{meta.label}</Badge>
}

function TibiCard({ onOpen }) {
  const prompts = ['Trang phục Gala Dinner?', 'Cần mang theo giấy tờ gì?', 'Quy định huỷ tham gia?']

  return (
    <section className="rounded-xl border border-hairline bg-surface p-5 shadow-soft">
      <div className="flex items-center gap-3">
        <span className="grid size-12 place-items-center rounded-full bg-cyan-50 ring-1 ring-cyan-100">
          <ChatMascot size={42} />
        </span>
        <div>
          <h2 className="text-body-md font-semibold text-ink">Hỏi Tibi</h2>
          <p className="text-caption text-ink-muted">Trợ lý theo tài liệu của BTC</p>
        </div>
      </div>
      <div className="mt-4 flex flex-col gap-2">
        {prompts.map((prompt) => (
          <button
            key={prompt}
            type="button"
            onClick={onOpen}
            className="rounded-lg border border-hairline px-3 py-2 text-left text-body-sm text-ink hover:border-primary/40"
          >
            {prompt}
          </button>
        ))}
      </div>
    </section>
  )
}

function RegistrationSummary({ registration }) {
  if (!registration) return null

  return (
    <section className="mt-6 rounded-xl border border-hairline bg-surface p-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-body-sm font-semibold text-ink">Đăng ký của bạn</h2>
        <Badge tone="emerald">
          {registration.status === 'cancelled' ? 'Đã huỷ' : 'Đã đăng ký'}
        </Badge>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-x-6 gap-y-4 text-caption sm:grid-cols-4 sm:items-end">
        <Info label="Tham gia" value={registration.is_participating ? 'Có' : 'Không'} />
        <Info label="Ca đi" value={formatShift(registration.requested_shift_name || registration.requested_shift_code)} />
        <Info label="Trạng thái" value={formatRegistrationStatus(registration.status)} />
        <Link to="/register-event" className="font-semibold text-primary hover:underline">
          Xem đăng ký <ChevronRight className="inline size-3.5" />
        </Link>
      </div>
    </section>
  )
}

function Info({ label, value }) {
  return (
    <div className="min-w-0">
      <p className="text-ink-muted">{label}</p>
      <p className="mt-1 truncate font-semibold text-ink">{value}</p>
    </div>
  )
}

function CalendarButton({ label, data, type, journey }) {
  const event = type === 'flight' ? flightCalendarEvent(data) : journeyCalendarEvent(journey)
  const addToCalendar = () => {
    if (label === 'Thêm tất cả vào lịch') return downloadJourneyCalendar(journey)
    if (event) downloadIcs(`chuyen-bay-${data.flight_code}`, event)
  }

  return (
    <button type="button" onClick={addToCalendar} className="inline-flex items-center gap-1.5 font-semibold text-primary hover:underline">
      <CalendarPlus className="size-3.5" />
      {label}
    </button>
  )
}

function flightCalendarEvent(flight) {
  if (!flight?.departure_time) return null
  return {
    uid: `flight-${flight.flight_code}`,
    title: `Chuyến bay ${flight.flight_code}`,
    start: flight.departure_time,
    end: flight.arrival_time,
    location: `${flight.departure_airport} → ${flight.arrival_airport}`,
    description: flight.airline || 'Team Building',
  }
}

function journeyCalendarEvent(journey) {
  const flight = journey?.flights?.outbound || journey?.flights?.return
  if (flight) return flightCalendarEvent(flight)
  const bus = journey?.buses?.[0]
  if (!bus?.gather_time) return null
  return {
    uid: `bus-${bus.bus_id}`,
    title: `Xe ${bus.bus_code}`,
    start: bus.gather_time,
    end: bus.departure_time,
    location: bus.pickup_point?.name,
    description: bus.trip_leg?.name,
  }
}

function downloadJourneyCalendar(journey) {
  const events = [journey?.flights?.outbound, journey?.flights?.return]
    .filter(Boolean)
    .map(flightCalendarEvent)

  for (const bus of journey?.buses ?? []) {
    if (bus.gather_time) {
      events.push({
        uid: `bus-${bus.bus_id}`,
        title: `Xe ${bus.bus_code}`,
        start: bus.gather_time,
        end: bus.departure_time,
        location: bus.pickup_point?.name,
        description: bus.trip_leg?.name,
      })
    }
  }

  if (journey?.accommodation?.check_in_at) {
    events.push({
      uid: 'accommodation',
      title: `Nhận phòng ${journey.accommodation.hotel_name}`,
      start: journey.accommodation.check_in_at,
      end: journey.accommodation.check_out_at,
      location: journey.accommodation.address,
    })
  }
  if (journey?.gala?.starts_at) {
    events.push({
      uid: 'gala',
      title: journey.gala.name || 'Gala Dinner',
      start: journey.gala.starts_at,
      location: journey.gala.venue,
      description: `Bàn ${journey.gala.table_code} · Ghế ${journey.gala.seat_number}`,
    })
  }

  for (const item of journey?.itinerary ?? []) {
    if (!item.day_date) continue
    const hasTime = Boolean(item.start_time)
    events.push({
      uid: `itinerary-${item.id ?? `${item.day_date}-${item.start_time ?? 'all-day'}-${item.title}`}`,
      title: item.title,
      start: hasTime ? `${item.day_date}T${item.start_time}:00+07:00` : item.day_date,
      end: hasTime && item.end_time ? `${item.day_date}T${item.end_time}:00+07:00` : undefined,
      location: item.location,
      description: [item.description, journey.event?.name].filter(Boolean).join(' · '),
      allDay: !hasTime,
      alarmMinutes: hasTime ? 60 : null,
    })
  }

  const coveredDates = new Set(events.map((event) => calendarDate(event.start)).filter(Boolean))
  for (const date of eventDateRange(journey?.event)) {
    if (coveredDates.has(date)) continue
    events.push({
      uid: `event-day-${date}`,
      title: `Team Building · ${journey.event.destination || journey.event.name}`,
      start: date,
      description: journey.event.name,
      allDay: true,
      alarmMinutes: null,
    })
  }

  const blocks = events.filter(Boolean).map((event) => {
    const ics = buildIcs(event)
    return ics.slice(ics.indexOf('BEGIN:VEVENT'), ics.indexOf('END:VEVENT') + 'END:VEVENT'.length)
  })
  if (blocks.length === 0) return

  const blob = new Blob(
    [
      ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Team Building Portal//VI', 'CALSCALE:GREGORIAN', ...blocks, 'END:VCALENDAR'].join('\r\n'),
    ],
    { type: 'text/calendar;charset=utf-8' },
  )
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'hanh-trinh-team-building.ics'
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function calendarDate(value) {
  const match = String(value ?? '').match(/^(\d{4}-\d{2}-\d{2})/)
  return match?.[1] ?? null
}

function eventDateRange(event) {
  if (!event?.start_date || !event?.end_date) return []
  const start = new Date(`${event.start_date}T00:00:00Z`)
  const end = new Date(`${event.end_date}T00:00:00Z`)
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return []

  const dates = []
  for (const cursor = new Date(start); cursor <= end; cursor.setUTCDate(cursor.getUTCDate() + 1)) {
    dates.push(cursor.toISOString().slice(0, 10))
  }
  return dates
}

function MapLink({ place }) {
  const href = mapsUrl(place)
  if (!href) return <span className="truncate">{place?.name || place?.address}</span>
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 font-semibold text-primary hover:underline">
      <MapPin className="size-3.5" />
      Bản đồ
    </a>
  )
}

function PhoneLink({ phone, label }) {
  const href = telHref(phone)
  if (!href) return null
  return (
    <a href={href} className="inline-flex items-center gap-1 font-semibold text-primary hover:underline">
      <Phone className="size-3.5" />
      {label || phone}
    </a>
  )
}

function findNextAssignment(journey) {
  const items = []
  for (const bus of journey?.buses ?? []) {
    items.push({
      kind: 'bus',
      when: bus.gather_time || bus.departure_time,
      title: `${bus.bus_code} · ${bus.pickup_point?.name || bus.trip_leg?.name || 'Xe đưa đón'}`,
      subtitle: bus.leader?.name
        ? `Trưởng xe ${bus.leader.name}${bus.leader.phone ? ` · ${bus.leader.phone}` : ''}`
        : bus.plate_number || '',
      place: bus.pickup_point,
      phone: bus.leader?.phone,
    })
  }
  for (const flight of [journey?.flights?.outbound, journey?.flights?.return].filter(Boolean)) {
    items.push({
      kind: 'flight',
      when: flight.departure_time,
      title: `Chuyến bay ${flight.flight_code}`,
      subtitle: `${flight.departure_airport} → ${flight.arrival_airport}`,
      place: { name: flight.departure_airport },
    })
  }

  items.sort((a, b) => new Date(a.when || 0) - new Date(b.when || 0))
  const item = items.find((entry) => entry.when && new Date(entry.when) >= new Date()) || items[0]
  if (!item?.when) return null
  return { ...item, time: formatTime(item.when), dateLabel: shortDateWithWeekday(item.when) }
}

function shortDate(value) {
  return value ? formatDate(value).slice(0, 5) : '—'
}

function shortDateWithWeekday(value) {
  return value
    ? new Intl.DateTimeFormat('vi-VN', { weekday: 'short', day: '2-digit', month: '2-digit' }).format(new Date(value))
    : '—'
}

function formatShift(value) {
  if (!value) return '—'
  const text = String(value)
  const match = text.match(/(?:ca|shift)[\s_-]*([12])/i)
  if (match) return `Ca ${match[1]}`
  if (/morning|early|sáng/i.test(text)) return 'Ca 1'
  if (/evening|late|sau/i.test(text)) return 'Ca 2'
  return text
}

function formatRegistrationStatus(value) {
  const labels = {
    draft: 'Bản nháp',
    submitted: 'Đã đăng ký',
    cancelled: 'Đã huỷ',
  }
  return labels[value] || value || '—'
}

function getFirstName(value = '') {
  const parts = value.trim().split(/\s+/)
  return parts[parts.length - 1] || 'bạn'
}

function reasonText(reason) {
  if (reason === 'not_published') return 'Đang chờ BTC công bố'
  if (reason === 'not_assigned') return 'BTC chưa xếp phần này cho bạn'
  if (reason === 'not_participating') return 'Chỉ dành cho người xác nhận tham gia'
  return 'Thông tin sẽ hiển thị khi sẵn sàng'
}
