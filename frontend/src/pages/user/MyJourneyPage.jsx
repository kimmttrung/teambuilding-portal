import { Link } from 'react-router-dom'
import {
  BedDouble,
  Bus,
  Calendar,
  Check,
  ChevronRight,
  ClipboardList,
  FileText,
  MapPin,
  PartyPopper,
  Plane,
  UserRound,
} from 'lucide-react'
import { useActiveEvent, useMyRegistration } from '../../hooks/useEvent'
import { useAuth } from '../../context/AuthContext'
import { EVENT_STATUS_META, REGISTRATION_STATUS_META } from '../../utils/constants'
import { daysUntil, formatDate } from '../../utils/format'
import Alert from '../../components/common/Alert'
import Badge from '../../components/common/Badge'
import Button from '../../components/common/Button'
import Card from '../../components/common/Card'
import Spinner from '../../components/common/Spinner'

export default function MyJourneyPage() {
  const { user } = useAuth()
  const { data: event, isLoading, error } = useActiveEvent()
  const { data: registration, isLoading: loadingRegistration } = useMyRegistration()

  if (isLoading || loadingRegistration) return <Spinner />
  if (error) {
    return (
      <Alert tone="warning" title="Chưa có kỳ Team Building nào">
        {error.message}
      </Alert>
    )
  }

  const statusMeta = EVENT_STATUS_META[event.status] ?? { label: event.status, tone: 'slate' }
  const remaining = daysUntil(event.start_date)
  const participating = registration?.is_participating && registration?.status === 'submitted'

  return (
    <div className="flex flex-col gap-4">
      <EventBanner
        event={event}
        statusLabel={statusMeta.label}
        remaining={remaining}
        userName={user.display_name || user.full_name}
      />

      <div className="grid gap-4 xl:grid-cols-12">
        <div className="flex flex-col gap-4 xl:col-span-8">
          <RegistrationPanel event={event} registration={registration} />
          <JourneyTiles published={event.is_published} participating={participating} />
        </div>

        <div className="flex flex-col gap-4 xl:col-span-4">
          <ProgressPanel event={event} registration={registration} />
          <QuickLinks />
        </div>
      </div>
    </div>
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

/* --- 4 hạng mục sẽ được công bố: ô vuông gọn, 4 cột trên màn hình rộng --- */
const JOURNEY_ITEMS = [
  { icon: Plane, title: 'Chuyến bay', hint: 'Mã chuyến, giờ bay, sân bay' },
  { icon: Bus, title: 'Xe đưa đón', hint: 'Giờ tập trung, điểm đón, trưởng xe' },
  { icon: BedDouble, title: 'Khách sạn', hint: 'Số phòng, người ở cùng' },
  { icon: PartyPopper, title: 'Gala Dinner', hint: 'Bàn và ghế của bạn' },
]

function JourneyTiles({ published, participating }) {
  return (
    <Card
      title="Thông tin hành trình"
      description={
        participating
          ? published
            ? 'BTC đã công bố — chi tiết hiển thị tại đây'
            : 'Sẽ hiển thị ngay khi BTC công bố kết quả phân bổ'
          : 'Chỉ dành cho CBNV xác nhận tham gia'
      }
      bodyClassName="grid grid-cols-2 gap-2.5 lg:grid-cols-4"
    >
      {JOURNEY_ITEMS.map(({ icon: Icon, title, hint }) => (
        <div
          key={title}
          className="rounded-lg border border-slate-200 bg-slate-50/60 p-3 transition hover:border-slate-300"
        >
          <span className="grid size-8 place-items-center rounded-lg bg-white text-slate-500 ring-1 ring-slate-200">
            <Icon className="size-4" aria-hidden="true" />
          </span>
          <p className="mt-2 text-sm font-semibold text-slate-900">{title}</p>
          <p className="mt-0.5 text-xs leading-snug text-slate-500">{hint}</p>
          <p className="mt-2 text-xs font-medium text-amber-700">
            {participating ? 'Chờ công bố' : 'Không áp dụng'}
          </p>
        </div>
      ))}
    </Card>
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
