import { useFormContext } from 'react-hook-form'
import { Check, Moon, PlaneTakeoff, Sun } from 'lucide-react'
import { formatDate } from '../../../utils/format'
import StepIntro from './StepIntro'

/** Bước 3 — chọn ca bay bằng các thẻ chuyến trực quan theo layout Figma mới. */
export default function ShiftStep({ event, options }) {
  const {
    register,
    watch,
    setValue,
    formState: { errors },
  } = useFormContext()
  const shiftId = watch('shift_id')
  const departureLocationId = watch('departure_location_id')
  const shifts = options.shifts ?? []
  const locations = options.work_locations ?? []

  return (
    <div className="flex flex-col gap-4">
      <StepIntro
        step="3"
        eyebrow="Ca bay"
        title="Chọn ca đi"
        description="Chọn khung giờ phù hợp. BTC sẽ cố gắng giữ các thành viên cùng team trên cùng chuyến."
        mobileEyebrow="Chọn ca đi"
        mobileTitle="Bạn muốn bay vào lúc nào?"
        mobileDescription="Đây là nguyện vọng. BTC xếp theo số chỗ, nên không chắc chắn 100%."
      />

      <div className="hidden flex-col gap-4 md:flex">
        <section className="rounded-xl border border-hairline bg-surface p-3 shadow-soft">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-body-sm font-semibold text-ink">Ca bay mong muốn</p>
            <p className="mt-0.5 text-caption text-ink-muted">
              {event?.start_date ? `Ngày đi ${formatDate(event.start_date)}` : 'Chọn một ca'}
            </p>
          </div>
          <PlaneTakeoff className="size-5 text-primary" aria-hidden="true" />
        </div>

        {shifts.length === 0 ? (
          <p className="mt-5 rounded-lg bg-canvas-soft px-4 py-3 text-body-sm text-ink-muted">
            BTC chưa cấu hình ca bay. Bạn vẫn có thể tiếp tục, BTC sẽ xếp ca giúp bạn.
          </p>
        ) : (
          <div className="mt-3 grid gap-2.5 sm:grid-cols-2">
            {shifts.map((shift) => {
              const selected = shiftId === String(shift.id)
              const time = shift.earliest_departure || 'Theo lịch BTC'
              return (
                <label
                  key={shift.id}
                    className={`relative block cursor-pointer rounded-xl border p-3 transition ${
                    selected
                      ? 'border-primary bg-brand-50 ring-1 ring-primary'
                      : 'border-hairline bg-surface hover:border-primary'
                  }`}
                >
                  <input
                    type="radio"
                    value={String(shift.id)}
                    className="sr-only"
                    {...register('shift_id')}
                  />
                  <span className="flex items-start justify-between gap-3">
                    <span>
                      <span className="text-eyebrow font-semibold tracking-[0.12em] text-primary uppercase">
                        {shift.code}
                      </span>
                      <span className="mt-1 block text-body-md font-semibold text-ink">
                        {shift.name?.replace(' – ', ' · ') || `Ca ${shift.code}`}
                      </span>
                    </span>
                    <span className={`grid size-6 place-items-center rounded-full border ${selected ? 'border-primary bg-primary text-on-primary' : 'border-input-border text-transparent'}`}>
                      <Check className="size-3.5" strokeWidth={3} aria-hidden="true" />
                    </span>
                  </span>
                  <span className="mt-3 flex items-end justify-between border-t border-hairline pt-2.5">
                    <span>
                      <span className="block text-caption text-ink-muted">Khởi hành sớm nhất</span>
                      <span className="mt-0.5 block text-body-sm font-semibold text-ink">{time}</span>
                    </span>
                    <span className="text-caption text-ink-muted">HAN / SGN → PQC</span>
                  </span>
                </label>
              )
            })}
          </div>
        )}

        {errors.shift_id && <p className="mt-3 text-caption text-rose-600">{errors.shift_id.message}</p>}
      </section>

      <section className="rounded-xl border border-hairline bg-surface p-3 shadow-soft">
        <div>
          <p className="text-body-sm font-semibold text-ink">Bạn xuất phát từ đâu?</p>
          <p className="mt-0.5 text-caption text-ink-muted">Dùng để BTC ghép chuyến bay và xe phù hợp.</p>
        </div>
        <div className="mt-3 grid gap-2.5 sm:grid-cols-2">
          {locations.map((location) => {
            const selected = departureLocationId === String(location.id)
            return (
              <label
                key={location.id}
                className={`flex cursor-pointer items-center gap-3 rounded-lg border px-3 py-2.5 transition ${selected ? 'border-primary bg-brand-50' : 'border-hairline hover:border-primary'}`}
              >
                <input
                  type="radio"
                  value={String(location.id)}
                  className="size-4 accent-primary"
                  {...register('departure_location_id')}
                  onChange={() => setValue('departure_location_id', String(location.id), { shouldValidate: true })}
                />
                <span className="min-w-0">
                  <span className="block text-body-sm font-semibold text-ink">{location.name}</span>
                  <span className="block text-caption text-ink-muted">{location.airport_code || location.city}</span>
                </span>
              </label>
            )
          })}
        </div>
        {errors.departure_location_id && <p className="mt-3 text-caption text-rose-600">{errors.departure_location_id.message}</p>}
      </section>
      </div>

      <MobileShiftOptions
        shifts={shifts}
        shiftId={shiftId}
        locations={locations}
        departureLocationId={departureLocationId}
        register={register}
        setValue={setValue}
        errors={errors}
      />
    </div>
  )
}

function MobileShiftOptions({ shifts, shiftId, locations, departureLocationId, register, setValue, errors }) {
  return (
    <div className="flex flex-col gap-3 md:hidden">
      {shifts.length === 0 ? (
        <p className="rounded-xl border border-hairline bg-surface px-4 py-3 text-body-sm text-ink-muted">
          BTC chưa cấu hình ca bay cho kỳ này. Hãy liên hệ BTC để được hỗ trợ.
        </p>
      ) : (
        shifts.map((shift, index) => {
          const selected = shiftId === String(shift.id)
          const evening = index > 0 || /chiều|tối|17/i.test(shift.name || '')
          return (
            <label key={shift.id} className={`flex min-h-[106px] cursor-pointer items-center gap-3 rounded-xl border p-4 ${selected ? 'border-primary bg-brand-50 ring-1 ring-primary' : 'border-hairline bg-surface'}`}>
              <input type="radio" value={String(shift.id)} className="sr-only" {...register('shift_id')} />
              <span className={`grid size-12 shrink-0 place-items-center rounded-xl ${evening ? 'bg-secondary text-white' : 'bg-accent-orange text-white'}`}><>{evening ? <Moon className="size-6" aria-hidden="true" /> : <Sun className="size-6" aria-hidden="true" />}</></span>
              <span className="min-w-0 flex-1"><strong className="block text-body-md text-ink">{formatMobileShift(shift.name, shift.code)}</strong><span className="mt-1 block text-body-sm text-ink-muted">{evening ? 'Bay sau 17:00, sau giờ giao dịch.' : 'Bay trước 12:00, nhận phòng đầu giờ chiều.'}</span></span>
              <span className={`grid size-6 shrink-0 place-items-center rounded-full border ${selected ? 'border-primary bg-primary text-white' : 'border-input-border text-transparent'}`}><Check className="size-3.5" strokeWidth={3} aria-hidden="true" /></span>
            </label>
          )
        })
      )}
      {errors.shift_id && <p className="text-caption text-rose-600">{errors.shift_id.message}</p>}

      <section className="rounded-xl border border-hairline bg-surface p-4">
        <p className="text-body-sm font-semibold text-ink">Bạn xuất phát từ đâu?</p>
        <p className="mt-0.5 text-caption text-ink-muted">Dùng để BTC ghép chuyến bay và xe phù hợp.</p>
        <div className="mt-3 flex flex-col gap-2">
          {locations.map((location) => {
            const selected = departureLocationId === String(location.id)
            return (
              <label key={location.id} className={`flex cursor-pointer items-center gap-3 rounded-lg border px-3 py-2.5 transition ${selected ? 'border-primary bg-brand-50' : 'border-hairline hover:border-primary'}`}>
                <input
                  type="radio"
                  value={String(location.id)}
                  className="size-4 accent-primary"
                  {...register('departure_location_id')}
                  onChange={() => setValue('departure_location_id', String(location.id), { shouldValidate: true })}
                />
                <span className="min-w-0">
                  <span className="block text-body-sm font-semibold text-ink">{location.name}</span>
                  <span className="block text-caption text-ink-muted">{location.airport_code || location.city}</span>
                </span>
              </label>
            )
          })}
        </div>
        {errors.departure_location_id && <p className="mt-2 text-caption text-rose-600">{errors.departure_location_id.message}</p>}
      </section>
    </div>
  )
}

function formatMobileShift(name, code) {
  if (!name) return code ? `Ca ${code}` : 'Chưa chọn ca'
  return name.replace(' – ', ' · ').replace('bay ', '').replace('Bay ', '')
}
