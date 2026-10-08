import { useEffect } from 'react'
import { useFieldArray, useFormContext } from 'react-hook-form'
import { BusFront, ChevronDown, MapPin } from 'lucide-react'
import { formatDate } from '../../../utils/format'
import Input from '../../../components/common/Input'
import { isReturnDropoff, pointsForLeg } from './pickupPoints'
import StepIntro from './StepIntro'

const DIRECTION_LABELS = { outbound: 'Chiều đi', return: 'Chiều về' }

/** Bước 4 — layout mới: một danh sách chặng gọn, toggle xe và điểm đón nằm ngay trong dòng. */
export default function BusStep({ options }) {
  const {
    getValues,
    register,
    watch,
    setValue,
    formState: { errors },
  } = useFormContext()
  const { fields } = useFieldArray({ name: 'bus_needs' })
  const legs = options.trip_legs ?? []
  const busNeeds = watch('bus_needs') ?? []
  const departureLocationId = watch('departure_location_id')
  const selectedCount = busNeeds.filter((need) => need.needs_bus).length

  // Đổi thành phố xuất phát thì điểm của thành phố kia không còn hợp lệ.
  useEffect(() => {
    const needs = getValues('bus_needs') ?? []
    needs.forEach((need, index) => {
      const leg = legs.find((item) => item.id === need.trip_leg_id)
      if (!leg) return
      const available = pointsForLeg(options.pickup_points, leg, departureLocationId)
      if (Boolean(need.has_pickup_options) !== available.length > 0) {
        setValue(`bus_needs.${index}.has_pickup_options`, available.length > 0)
      }
      const stillValid = available.some((point) => String(point.id) === String(need.pickup_point_id))
      if (need.pickup_point_id && !stillValid) {
        setValue(`bus_needs.${index}.pickup_point_id`, '')
      }
    })
  }, [departureLocationId, getValues, legs, options.pickup_points, setValue])

  return (
    <div className="flex flex-col gap-4">
      <StepIntro
        step="4"
        eyebrow="Nhu cầu xe"
        title="Chặng nào bạn cần xe đưa đón?"
        description="Tắt chặng bạn tự đi. BTC xếp xe theo chuyến bay của bạn."
        mobileEyebrow="Nhu cầu xe"
        mobileTitle="Chặng nào bạn cần xe đưa đón?"
        mobileDescription="Tắt chặng bạn tự đi. BTC xếp xe theo chuyến bay của bạn."
      />

      {legs.length === 0 ? (
        <div className="rounded-xl border border-hairline bg-surface px-4 py-5 text-body-sm text-ink-muted">
          BTC chưa khai báo các chặng đưa đón cho kỳ này. Bạn vẫn có thể tiếp tục, thông tin xe sẽ
          được cập nhật sau.
        </div>
      ) : (
        <section className="overflow-hidden rounded-xl border border-hairline bg-surface shadow-soft max-md:shadow-none">
          <div className="flex items-center justify-between border-b border-hairline px-3.5 py-2.5 max-md:hidden">
            <div>
              <p className="text-body-sm font-semibold text-ink">Nhu cầu xe của bạn</p>
              <p className="mt-0.5 text-caption text-ink-muted">
                Đã chọn {selectedCount}/{legs.length} chặng đi xe BTC
              </p>
            </div>
            <BusFront className="size-5 text-primary" aria-hidden="true" />
          </div>

          <div className="divide-y divide-hairline">
            {fields.map((field, index) => {
              const leg = legs.find((item) => item.id === field.trip_leg_id)
              if (!leg) return null

              const needsBus = Boolean(busNeeds[index]?.needs_bus)
              const dropoff = isReturnDropoff(leg)
              const pickupOptions = pointsForLeg(options.pickup_points, leg, departureLocationId)
                .map((point) => ({
                  value: String(point.id),
                  label: point.address ? `${point.name}, ${point.address}` : point.name,
                }))

              return (
                <div key={field.id} className={`px-3.5 py-2.5 max-md:px-4 max-md:py-3.5 ${!needsBus ? 'bg-canvas-soft/45' : ''}`}>
                  <div className="flex items-start gap-3">
                    <span
                      className={`mt-0.5 grid size-8 shrink-0 place-items-center rounded-md max-md:size-8 max-md:rounded-lg ${
                        needsBus ? 'bg-accent-green text-on-primary' : 'bg-hairline text-ink-faint'
                      }`}
                    >
                      <BusFront className="size-4" aria-hidden="true" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className={`text-body-sm font-semibold ${needsBus ? 'text-ink' : 'text-ink-muted'}`}>
                        {leg.name}
                      </p>
                      <p className="mt-0.5 text-caption text-ink-muted">
                        {leg.leg_date ? formatDate(leg.leg_date) : null}
                        {leg.leg_date && ' · '}
                        {needsBus ? DIRECTION_LABELS[leg.direction] ?? leg.direction : 'Bạn tự đi'}
                      </p>
                    </div>
                    <BusToggle
                      selected={needsBus}
                      onSelect={() => {
                        setValue(`bus_needs.${index}.needs_bus`, !needsBus, { shouldValidate: true })
                        if (needsBus) setValue(`bus_needs.${index}.pickup_point_id`, '')
                      }}
                    />
                  </div>

                  {needsBus && (
                    <div className="mt-2.5 ml-11 flex flex-col gap-2 sm:max-w-[360px]">
                      {pickupOptions.length > 0 ? (
                        <label className="relative block">
                          <MapPin className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-muted" aria-hidden="true" />
                          <select
                            aria-label={`${dropoff ? 'Điểm trả' : 'Điểm đón'} cho ${leg.name}`}
                            className="h-10 w-full appearance-none rounded-md border border-input-border bg-surface pr-9 pl-9 text-body-sm text-ink outline-none transition focus:border-primary"
                            {...register(`bus_needs.${index}.pickup_point_id`)}
                          >
                            <option value="">{dropoff ? 'Chọn điểm trả' : 'Chọn điểm đón'}</option>
                            {pickupOptions.map((point) => (
                              <option key={point.value} value={point.value}>{point.label}</option>
                            ))}
                          </select>
                          <ChevronDown className="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-ink-muted" aria-hidden="true" />
                          {errors.bus_needs?.[index]?.pickup_point_id && (
                            <p className="mt-1.5 text-caption text-rose-600">
                              {errors.bus_needs[index].pickup_point_id.message}
                            </p>
                          )}
                        </label>
                      ) : (
                        <p className="text-caption text-ink-muted">
                          {dropoff ? 'BTC sẽ thông báo điểm trả sau.' : 'BTC sẽ thông báo điểm tập trung sau.'}
                        </p>
                      )}
                      <Input aria-label={`Ghi chú cho ${leg.name}`} placeholder="Ghi chú cho chặng này (không bắt buộc)" error={errors.bus_needs?.[index]?.note?.message} {...register(`bus_needs.${index}.note`)} />
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </section>
      )}
    </div>
  )
}

function BusToggle({ selected, onSelect }) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      aria-label={selected ? 'Đang chọn xe BTC' : 'Tự đi'}
      onClick={onSelect}
      className={`relative h-7 w-11 shrink-0 rounded-full transition ${selected ? 'bg-primary' : 'bg-input-border'}`}
    >
      <span className={`absolute top-1 size-5 rounded-full bg-white shadow-soft transition ${selected ? 'left-5' : 'left-1'}`} />
    </button>
  )
}
