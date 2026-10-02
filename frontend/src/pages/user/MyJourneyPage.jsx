import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowRight,
  Bus,
  BedDouble,
  Calendar,
  Check,
  ChevronRight,
  ClipboardList,
  FileText,
  Plane,
  MapPin,
  PartyPopper,
  UserRound,
  Users,
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
import BusPassengersModal from './journey/BusPassengersModal'
import JourneyTimeline from './journey/JourneyTimeline'
import PendingTiles from './journey/PendingTiles'

export default function MyJourneyPage() {
  const { user } = useAuth()
  // Xe đang mở danh sách hành khách (chỉ Trưởng xe mới mở được).
  const [passengersOf, setPassengersOf] = useState(null)
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
  const urgent = journey?.announcements.find((item) => item.severity === 'urgent')

  if (!registration && event.status !== 'event_started' && event.status !== 'completed') {
    return <UnregisteredJourney event={event} user={user} journey={journey} />
  }

  return (
    <>
      <div className="md:hidden">
        <MobileJourneyOverview event={event} registration={registration} journey={journey} user={user} />
      </div>
      <div className="hidden flex-col gap-4 md:flex">
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
              {/* Một trục thời gian duy nhất: lịch trình + vé cá nhân gộp chung mốc. */}
              <JourneyTimeline journey={journey} onOpenPassengers={setPassengersOf} />
              <PendingTiles parts={journey.pending} reasons={journey.pending_reasons} />
            </>
          )}
          <RegistrationPanel event={event} registration={registration} />
        </div>

        <div className="flex flex-col gap-4 xl:col-span-4">
          {journey && <AnnouncementsPanel announcements={journey.announcements} />}
          <ProgressPanel event={event} registration={registration} />
          <QuickLinks />
        </div>
      </div>

      {passengersOf && (
        <BusPassengersModal bus={passengersOf} onClose={() => setPassengersOf(null)} />
      )}
    </div>
    </>
  )
}

function UnregisteredJourney({ event, user, journey }) {
  const team = journey?.profile?.team || journey?.team
  const teamCount = team?.member_count ?? team?.registered_count
  const teamCapacity = team?.capacity

  return (
    <div className="grid gap-10 pt-0 max-md:block max-md:pt-[34px] xl:grid-cols-[minmax(0,1fr)_360px] xl:gap-12">
      <section className="min-w-0">
        <p className="text-title text-ink-muted">Chào {user.display_name || user.full_name},</p>
        <h1 className="mt-1 max-w-xl text-display-2 text-ink max-md:max-w-[340px] max-md:text-[40px] max-md:leading-[0.98] max-md:tracking-[-1.8px] sm:text-display-1">
          {event.destination || 'Team Building'}<br />đang chờ bạn.
        </h1>

        <div className="mt-8 overflow-hidden rounded-2xl bg-secondary text-on-primary shadow-soft max-md:mt-6">
          <div className="flex flex-wrap items-center justify-between gap-8 px-7 py-7 max-md:grid max-md:grid-cols-2 max-md:gap-x-4 max-md:gap-y-4 max-md:px-5 max-md:py-[22px]">
            <div>
              <p className="text-caption text-white/70">Hạn đăng ký</p>
              <div className="mt-1 flex items-end gap-2">
                <span className="text-display-1 leading-none">{daysUntil(event.registration_closes_at) ?? '—'}</span>
                <span className="pb-1 text-title text-white/75">ngày</span>
              </div>
              <p className="mt-2 text-body-sm text-white/70">
                {event.registration_closes_at ? `Đóng ${formatDate(event.registration_closes_at)} · 23:59` : 'Thời hạn theo thông báo BTC'}
              </p>
            </div>
            <div className="max-w-52 max-md:max-w-none">
              <p className="text-title font-semibold">5 bước, khoảng 3 phút.</p>
              <p className="mt-1 text-body-sm leading-relaxed text-white/70">Tự lưu nháp — bạn có thể dừng và quay lại bất kỳ lúc nào.</p>
            </div>
            <Link to="/register-event" className="inline-flex shrink-0 items-center justify-center gap-2 rounded-full bg-white px-5 py-3 text-button font-semibold text-ink transition hover:bg-white/90 max-md:col-span-2 max-md:w-full">
              Bắt đầu đăng ký <ArrowRight className="size-4" aria-hidden="true" />
            </Link>
          </div>
        </div>

        <h2 className="mt-10 text-heading-2 text-ink max-md:mt-7 max-md:text-lg">Chuyến đi có gì</h2>
        <div className="mt-4 hidden gap-4 sm:grid md:grid">
          <TripPreview icon={Plane} color="bg-accent-sky" title="Bay HAN → PQC" text="Chọn ca sáng hoặc sau 17:00." />
          <TripPreview icon={BedDouble} color="bg-accent-purple-deep" title="2 đêm Sea Star" text="Phòng 2 người, xếp theo team." />
          <TripPreview icon={PartyPopper} color="bg-accent-pink" title="Gala Dinner" text="Trưởng nhóm chọn bàn cho team." />
        </div>
        <div className="mt-3 overflow-hidden rounded-xl border border-hairline bg-surface md:hidden">
          <MobileTripRow icon={Plane} color="bg-accent-sky" title="Bay Hà Nội → Phú Quốc" text="Chọn ca sáng hoặc sau 17:00" />
          <MobileTripRow icon={BedDouble} color="bg-accent-purple-deep" title="2 đêm Sea Star Resort" text="Phòng 2 người, xếp theo team" />
          <MobileTripRow icon={PartyPopper} color="bg-accent-pink" title="Gala Dinner · 16/10" text="Trưởng nhóm chọn bàn cho team" />
        </div>
        <div className="mt-4 flex items-center gap-2 rounded-lg border border-hairline bg-surface px-4 py-3 text-body-sm text-ink-muted md:hidden">
          <Users className="size-4 text-ink-muted" aria-hidden="true" /><strong className="text-ink">{teamCount ?? 14}/{teamCapacity ?? 20}</strong> người {team?.name || 'Team Product'} đã đăng ký
        </div>
      </section>

      <aside className="flex flex-col gap-5 max-md:mt-[18px] max-md:gap-0">
        <section className="rounded-xl border border-hairline bg-surface px-5 py-5 shadow-soft max-md:hidden">
          <p className="text-caption text-ink-muted">{team?.name || 'Team của bạn'}</p>
          <p className="mt-2 text-display-2 text-ink">{teamCount ?? '—'}<span className="text-ink-faint">{teamCapacity ? `/${teamCapacity}` : ''}</span></p>
          <p className="mt-1 text-body-sm text-ink-muted">người đã đăng ký</p>
          <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-hairline">
            <span className="block h-full rounded-full bg-ink" style={{ width: teamCount && teamCapacity ? `${Math.min((teamCount / teamCapacity) * 100, 100)}%` : '0%' }} />
          </div>
        </section>

        <section className="rounded-xl border border-hairline bg-surface px-5 py-5 shadow-soft">
          <p className="text-body-sm font-semibold text-ink">Lịch quan trọng</p>
          <dl className="mt-4 flex flex-col gap-3 text-body-sm">
            <ScheduleItem date={formatDate(event.registration_closes_at)} text="Đóng đăng ký" />
            <ScheduleItem date="05/10" text="BTC công bố vé, xe, phòng" />
            <ScheduleItem date="08/10" text="Trưởng nhóm chọn ghế Gala" />
            <ScheduleItem date={formatDate(event.start_date)} text="Khởi hành" />
          </dl>
        </section>
      </aside>
      </div>
  )
}

function MobileJourneyOverview({ event, registration, journey, user }) {
  const published = Boolean(event.is_published || event.status === 'information_published')
  const flights = journey?.flights ?? []
  const accommodation = journey?.accommodation
  const busCount = registration?.bus_needs?.filter((item) => item.needs_bus).length ?? 0

  return (
    <div className="pt-0 max-md:pt-5">
      <div className="mb-5">
        <p className="text-caption text-ink-muted">{published ? `Xin chào ${user.display_name || user.full_name},` : 'Đăng ký của bạn'}</p>
        <h1 className="mt-2 whitespace-pre-line text-[32px] leading-[1.02] font-bold tracking-[-1.2px] text-ink">
          {published ? 'Hành trình của bạn.' : 'BTC đang xếp\nchuyến cho bạn.'}
        </h1>
        <p className="mt-2 max-w-sm text-body-sm leading-relaxed text-ink-muted">
          {published ? 'Thông tin chuyến đi, xe, phòng và Gala đã được công bố.' : 'Vé máy bay, xe, phòng và ghế Gala sẽ hiện ở đây khi BTC công bố — dự kiến 05/10.'}
        </p>
      </div>

      <section className="overflow-hidden rounded-xl border border-hairline bg-surface">
        <MobileAssignment icon={Plane} label="Chuyến bay đi · 15/10" value={flights[0] ? `${flights[0].flight_code} · ${formatTime(flights[0].departure_time)}` : 'Chưa công bố'} detail={flights[0] ? `${flights[0].departure_airport} → ${flights[0].arrival_airport}` : 'BTC đang xếp chuyến'} tone="sky" />
        <MobileAssignment icon={BedDouble} label="Khách sạn Sea Star" value={accommodation ? `${accommodation.room_number} · ${accommodation.hotel_name}` : 'Chưa công bố'} detail={accommodation ? 'Thông tin phòng của bạn' : 'BTC đang xếp phòng theo team'} tone="purple" />
      </section>

      <section className="mt-6">
        <p className="mb-3 text-caption font-semibold text-ink-muted">Đăng ký của bạn</p>
        <div className="overflow-hidden rounded-xl border border-hairline bg-surface">
          <MobileSummaryRow label="Tham gia" value={registration.is_participating ? 'Có' : 'Không'} />
          <MobileSummaryRow label="Ca đi" value={registration.shift?.name?.replace(' – ', ' · ') || '—'} />
          <MobileSummaryRow label="Đi xe BTC" value={`${busCount}/${registration.bus_needs?.length ?? 0} chặng`} />
          <Link to="/register-event" className="block border-t border-hairline px-4 py-3 text-body-sm font-semibold text-primary">
            {registration.status === 'cancelled' ? 'Đăng ký lại · Muốn đi, gửi yêu cầu cho BTC' : 'Xem hoặc sửa đăng ký'}
          </Link>
        </div>
      </section>
    </div>
  )
}

function MobileAssignment({ icon: Icon, label, value, detail, tone }) {
  const colors = { sky: 'bg-sky-100 text-sky-600', purple: 'bg-violet-100 text-violet-700' }
  return (
    <div className="flex items-center gap-3 border-b border-hairline px-4 py-4 last:border-b-0">
      <span className={`grid size-9 shrink-0 place-items-center rounded-lg ${colors[tone]}`}><Icon className="size-4.5" aria-hidden="true" /></span>
      <div className="min-w-0 flex-1">
        <p className="text-caption font-medium text-ink-muted">{label}</p>
        <p className="mt-1 truncate text-body-sm font-semibold text-ink">{value}</p>
        <p className="truncate text-caption text-ink-muted">{detail}</p>
      </div>
      {value.startsWith('Chưa') ? <span className="rounded-md bg-accent-orange/15 px-2 py-1 text-eyebrow font-semibold text-accent-orange-deep">Chờ công bố</span> : null}
    </div>
  )
}

function MobileSummaryRow({ label, value }) {
  return <div className="flex items-center justify-between gap-4 border-b border-hairline px-4 py-4 last:border-b-0"><span className="text-body-sm text-ink-muted">{label}</span><strong className="text-right text-body-sm text-ink">{value}</strong></div>
}

function formatTime(value) {
  if (!value) return '—'
  return value.includes('T') ? value.slice(11, 16) : value.slice(-5)
}

function TripPreview({ icon: Icon, color, title, text }) {
  return (
    <article className="overflow-hidden rounded-xl border border-hairline bg-surface shadow-soft">
      <div className={`grid h-14 place-items-center ${color} text-white`}><Icon className="size-6" aria-hidden="true" /></div>
      <div className="px-4 py-4"><h3 className="text-body-md font-semibold text-ink">{title}</h3><p className="mt-1 text-body-sm leading-relaxed text-ink-muted">{text}</p></div>
    </article>
  )
}

function MobileTripRow({ icon: Icon, color, title, text }) {
  return <div className="flex items-center gap-3 border-b border-hairline px-4 py-3.5 last:border-b-0"><span className={`grid size-8 shrink-0 place-items-center rounded-lg ${color} text-white`}><Icon className="size-4" aria-hidden="true" /></span><span className="min-w-0"><strong className="block text-body-sm text-ink">{title}</strong><span className="block text-caption text-ink-muted">{text}</span></span></div>
}

function ScheduleItem({ date, text }) {
  return <div className="flex items-center gap-4"><dt className="w-12 shrink-0 font-semibold text-ink">{date || '—'}</dt><dd className="text-ink-secondary">{text}</dd></div>
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
          {registration.status === 'cancelled' && registration.reregister_allowed && (
            <Link to="/register-event">
              <Button size="sm" icon={ClipboardList}>
                Đăng ký lại
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

      {registration.status === 'cancelled' && (
        <Alert
          tone={registration.reregister_allowed ? 'info' : 'warning'}
          className="mt-3"
          title={registration.reregister_allowed ? 'Bạn đã huỷ đăng ký' : 'Bạn đã huỷ đăng ký — không đăng ký lại được'}
        >
          {registration.reregister_allowed
            ? 'Xử lý xong việc đột xuất? Bấm "Đăng ký lại" trước khi Ban tổ chức công bố thông tin. Chỗ cũ không tự giữ lại, Ban tổ chức sẽ xếp lại.'
            : 'Ban tổ chức đã công bố thông tin nên không đăng ký lại được trên hệ thống. Liên hệ Ban tổ chức nếu có trường hợp đặc biệt.'}
        </Alert>
      )}

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
