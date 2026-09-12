import { useFormContext } from 'react-hook-form'
import { Ban, Calendar, Check, MapPin, X } from 'lucide-react'
import { FLIGHT_REQUIRED_FIELDS } from '../../../utils/schemas'
import { daysUntil, formatDate, formatDateTime } from '../../../utils/format'
import Card from '../../../components/common/Card'

/**
 * Cột phụ của form đăng ký: thông tin kỳ, lựa chọn đang chọn và tình trạng hồ sơ.
 *
 * Đọc trực tiếp từ form context nên cập nhật ngay khi người dùng bấm — CBNV thấy
 * được toàn bộ những gì mình sắp gửi mà không phải quay lại từng bước để kiểm tra.
 */
export default function WizardSidebar({ event, options, isEditing, onRequestCancel }) {
  const { watch } = useFormContext()
  const values = watch()

  const participating = values.is_participating === 'yes'
  const notParticipating = values.is_participating === 'no'
  const shift = options.shifts?.find((item) => String(item.id) === values.shift_id)
  const location = options.work_locations?.find(
    (item) => String(item.id) === values.departure_location_id,
  )
  const busLegs = (values.bus_needs ?? []).filter((need) => need.needs_bus)
  const remainingDays = daysUntil(event.registration_closes_at)

  return (
    <>
      <Card title="Kỳ Team Building" description={event.code}>
        <p className="font-semibold text-slate-900">{event.name}</p>
        <dl className="mt-2.5 flex flex-col gap-2 text-sm">
          {event.destination && (
            <div className="flex items-center gap-2 text-slate-600">
              <MapPin className="size-4 shrink-0 text-slate-400" aria-hidden="true" />
              {event.destination}
            </div>
          )}
          <div className="flex items-center gap-2 text-slate-600">
            <Calendar className="size-4 shrink-0 text-slate-400" aria-hidden="true" />
            {formatDate(event.start_date)} – {formatDate(event.end_date)}
          </div>
        </dl>

        {event.registration_closes_at && (
          <div className="mt-3 rounded-lg bg-slate-50 px-3 py-2.5">
            <p className="text-xs tracking-wide text-slate-400 uppercase">Hạn đăng ký</p>
            <p className="mt-0.5 text-sm font-medium text-slate-900">
              {formatDateTime(event.registration_closes_at)}
            </p>
            {remainingDays !== null && remainingDays >= 0 && (
              <p className="mt-0.5 text-xs text-amber-700">Còn {remainingDays} ngày để gửi hoặc sửa</p>
            )}
          </div>
        )}
      </Card>

      <Card title="Lựa chọn của bạn" description="Cập nhật theo từng bước bạn điền">
        <dl className="flex flex-col divide-y divide-slate-100">
          <Row label="Tham gia">
            {participating ? 'Có' : notParticipating ? 'Không' : <Pending />}
          </Row>

          {!notParticipating && (
            <>
              <Row label="Ca đi">{shift ? shift.name : <Pending />}</Row>
              <Row label="Xuất phát từ">
                {location ? location.name : 'Theo nơi làm việc của tôi'}
              </Row>
              <Row label="Đi xe BTC">
                {busLegs.length
                  ? `${busLegs.length}/${values.bus_needs.length} chặng`
                  : 'Chưa chọn chặng nào'}
              </Row>
              <Row label="Quy định">
                {values.agreed_terms ? 'Đã đồng ý' : <Pending text="Chưa đồng ý" />}
              </Row>
            </>
          )}

          {values.wish_note && <Row label="Mong muốn">{values.wish_note}</Row>}
        </dl>

        {busLegs.length > 0 && (
          <ul className="mt-3 flex flex-col gap-1.5 border-t border-slate-100 pt-3">
            {busLegs.map((need) => {
              const leg = options.trip_legs?.find((item) => item.id === need.trip_leg_id)
              const point = options.pickup_points?.find(
                (item) => String(item.id) === need.pickup_point_id,
              )
              return (
                <li key={need.trip_leg_id} className="text-xs text-slate-600">
                  <span className="font-medium text-slate-800">{leg?.name ?? 'Chặng'}</span>
                  {point && <span className="text-slate-500"> · {point.name}</span>}
                </li>
              )
            })}
          </ul>
        )}
      </Card>

      {participating && <FlightReadyCard profile={values.profile} />}

      {isEditing && (
        <Card title="Không đi được nữa?">
          <p className="text-sm text-slate-600">
            Huỷ đăng ký để BTC không tính suất của bạn. Huỷ sau hạn đăng ký có thể phải chịu chi phí
            vé và phòng đã đặt.
          </p>
          <button
            type="button"
            onClick={onRequestCancel}
            className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-rose-600 hover:underline"
          >
            <Ban className="size-4" aria-hidden="true" />
            Huỷ đăng ký tham gia
          </button>
        </Card>
      )}
    </>
  )
}

function FlightReadyCard({ profile }) {
  const done = FLIGHT_REQUIRED_FIELDS.filter(({ name }) => profile?.[name])

  return (
    <Card
      title="Điều kiện xuất vé"
      description={`${done.length}/${FLIGHT_REQUIRED_FIELDS.length} thông tin bắt buộc`}
    >
      <ul className="flex flex-col gap-2">
        {FLIGHT_REQUIRED_FIELDS.map(({ name, label }) => {
          const filled = Boolean(profile?.[name])
          return (
            <li key={name} className="flex items-center gap-2.5 text-sm">
              <span
                className={`grid size-5 shrink-0 place-items-center rounded-full text-white ${
                  filled ? 'bg-emerald-500' : 'bg-slate-300'
                }`}
              >
                {filled ? (
                  <Check className="size-3" strokeWidth={3} aria-hidden="true" />
                ) : (
                  <X className="size-3" strokeWidth={3} aria-hidden="true" />
                )}
              </span>
              <span className={filled ? 'text-slate-700' : 'font-medium text-slate-900'}>
                {label}
              </span>
            </li>
          )
        })}
      </ul>
    </Card>
  )
}

function Row({ label, children }) {
  return (
    <div className="flex items-start justify-between gap-3 py-2 first:pt-0 last:pb-0">
      <dt className="shrink-0 text-xs tracking-wide text-slate-400 uppercase">{label}</dt>
      <dd className="min-w-0 text-right text-sm font-medium text-slate-900">{children}</dd>
    </div>
  )
}

function Pending({ text = 'Chưa chọn' }) {
  return <span className="text-sm font-normal text-slate-400">{text}</span>
}
