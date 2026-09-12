import { useFieldArray, useFormContext } from 'react-hook-form'
import { Bus, Car, Calendar } from 'lucide-react'
import { formatDate } from '../../../utils/format'
import Alert from '../../../components/common/Alert'
import Card from '../../../components/common/Card'
import Input from '../../../components/common/Input'
import Select from '../../../components/common/Select'

const DIRECTION_LABELS = { outbound: 'Chiều đi', return: 'Chiều về' }

/**
 * Bước 4 — nhu cầu xe từng chặng.
 *
 * Một dòng cho mỗi chặng BTC khai báo (không hard-code 4 chặng: số chặng là dữ liệu
 * gắn event). Form luôn gửi trạng thái đủ của mọi chặng, backend ghi đè toàn bộ —
 * nhờ vậy bỏ tick một chặng thì nhu cầu cũ biến mất thật.
 */
export default function BusStep({ options }) {
  const {
    register,
    watch,
    setValue,
    formState: { errors },
  } = useFormContext()
  const { fields } = useFieldArray({ name: 'bus_needs' })

  const legs = options.trip_legs ?? []
  const busNeeds = watch('bus_needs') ?? []
  const selectedCount = busNeeds.filter((need) => need.needs_bus).length

  if (legs.length === 0) {
    return (
      <Alert tone="info" title="Chưa có chặng xe nào">
        BTC chưa khai báo các chặng đưa đón cho kỳ này. Bạn tiếp tục bước sau, BTC sẽ thông báo
        khi có thông tin xe.
      </Alert>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <Alert tone="info" title="Chọn những chặng bạn cần xe của BTC">
        Chặng nào bạn tự đi thì chọn "Tự đi" — BTC không xếp ghế trống cho bạn và tiết kiệm được
        một chỗ trên xe. Đã chọn {selectedCount}/{legs.length} chặng đi xe BTC.
      </Alert>

      {fields.map((field, index) => {
        const leg = legs.find((item) => item.id === field.trip_leg_id)
        if (!leg) return null

        const needsBus = busNeeds[index]?.needs_bus ?? false
        const pickupOptions = (options.pickup_points ?? [])
          .filter((point) => point.trip_leg_id === null || point.trip_leg_id === leg.id)
          .map((point) => ({
            value: String(point.id),
            label: point.address ? `${point.name} — ${point.address}` : point.name,
          }))

        return (
          <Card
            key={field.id}
            title={leg.name}
            description={[
              DIRECTION_LABELS[leg.direction] ?? leg.direction,
              leg.leg_date ? formatDate(leg.leg_date) : null,
            ]
              .filter(Boolean)
              .join(' · ')}
            action={
              <Calendar className="size-4 shrink-0 text-slate-300" aria-hidden="true" />
            }
          >
            <div className="grid gap-2.5 sm:grid-cols-2">
              <BusToggle
                legId={leg.id}
                selected={needsBus === true}
                onSelect={() => {
                  setValue(`bus_needs.${index}.needs_bus`, true, { shouldValidate: true })
                }}
                icon={Bus}
                title="Đi xe của BTC"
                description="BTC xếp ghế và cử trưởng xe cho chặng này"
              />
              <BusToggle
                legId={leg.id}
                selected={needsBus === false}
                onSelect={() => {
                  setValue(`bus_needs.${index}.needs_bus`, false, { shouldValidate: true })
                  // Không đi xe thì điểm đón vô nghĩa — backend cũng xoá, giữ ở client cho khớp.
                  setValue(`bus_needs.${index}.pickup_point_id`, '')
                }}
                icon={Car}
                title="Tự đi"
                description="Bạn tự tới điểm hẹn bằng phương tiện của mình"
              />
            </div>

            {needsBus && (
              <div className="mt-3.5 grid gap-3.5 border-t border-slate-100 pt-3.5 sm:grid-cols-2">
                {pickupOptions.length > 0 ? (
                  <Select
                    label="Điểm đón"
                    required
                    placeholder="— Chọn điểm đón —"
                    options={pickupOptions}
                    error={errors.bus_needs?.[index]?.pickup_point_id?.message}
                    {...register(`bus_needs.${index}.pickup_point_id`)}
                  />
                ) : (
                  <p className="text-sm text-slate-500 sm:col-span-2">
                    Chặng này chưa có điểm đón để chọn. BTC sẽ thông báo giờ và chỗ tập trung sau.
                  </p>
                )}
                <Input
                  label="Ghi chú cho chặng này"
                  placeholder="Ví dụ: đi cùng con nhỏ, có hành lý lớn"
                  error={errors.bus_needs?.[index]?.note?.message}
                  {...register(`bus_needs.${index}.note`)}
                />
              </div>
            )}
          </Card>
        )
      })}
    </div>
  )
}

/** Nút chọn Có/Không của một chặng. Không dùng radio để hai chặng khác nhau
 *  không vô tình dùng chung một `name`. */
function BusToggle({ legId, selected, onSelect, icon: Icon, title, description }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      aria-label={`${title} — chặng ${legId}`}
      className={`flex items-start gap-3 rounded-xl border-2 p-3 text-left transition
        ${selected ? 'border-brand-600 bg-brand-50' : 'border-slate-200 bg-white hover:border-slate-300'}`}
    >
      <Icon
        className={`mt-0.5 size-4.5 shrink-0 ${selected ? 'text-brand-600' : 'text-slate-400'}`}
        aria-hidden="true"
      />
      <span className="min-w-0">
        <span className="block text-sm font-semibold text-slate-900">{title}</span>
        <span className="mt-0.5 block text-xs leading-snug text-slate-500">{description}</span>
      </span>
    </button>
  )
}
