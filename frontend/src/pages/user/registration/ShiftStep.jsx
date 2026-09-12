import { useFormContext } from 'react-hook-form'
import { Clock } from 'lucide-react'
import Alert from '../../../components/common/Alert'
import Card from '../../../components/common/Card'
import ChoiceCard from '../../../components/common/ChoiceCard'
import Select from '../../../components/common/Select'

/**
 * Bước 3 — chọn ca đi.
 *
 * Nói rõ đây là NGUYỆN VỌNG. Thuật toán phân bổ ưu tiên giữ nguyên team và cân số
 * ghế từng chuyến (docs/05-allocation-algorithm.md), nên nguyện vọng ca có thể không
 * được đáp ứng — hứa chắc ở đây sẽ thành khiếu nại lúc công bố kết quả.
 */
export default function ShiftStep({ options }) {
  const {
    register,
    watch,
    setValue,
    formState: { errors },
  } = useFormContext()

  const shiftId = watch('shift_id')
  const shifts = options.shifts ?? []
  const locationOptions = (options.work_locations ?? []).map((location) => ({
    value: String(location.id),
    label: location.city ? `${location.name} (${location.city})` : location.name,
  }))

  return (
    <div className="flex flex-col gap-4">
      <Alert tone="warning" title="Đây là nguyện vọng, không phải chỗ đã giữ">
        BTC phân bổ theo nguồn lực chung: số ghế mỗi chuyến, việc giữ nguyên team và ưu tiên
        của chương trình. Hệ thống cố gắng đáp ứng nguyện vọng của bạn nhưng không cam kết 100%.
      </Alert>

      <Card title="Ca bạn muốn đi" description="Chọn một ca">
        {shifts.length === 0 ? (
          <p className="text-sm text-slate-500">
            BTC chưa cấu hình ca đi cho kỳ này. Bạn cứ tiếp tục các bước sau, BTC sẽ xếp ca giúp bạn.
          </p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {shifts.map((shift) => (
              <ChoiceCard
                key={shift.id}
                name="shift_id"
                value={String(shift.id)}
                icon={Clock}
                checked={shiftId === String(shift.id)}
                onChange={(value) => setValue('shift_id', value, { shouldValidate: true })}
                title={shift.name}
                description={shift.description}
                meta={shift.earliest_departure ? `Sớm nhất khoảng ${shift.earliest_departure}` : null}
              />
            ))}
          </div>
        )}

        {errors.shift_id && <p className="mt-2.5 text-sm text-rose-600">{errors.shift_id.message}</p>}
      </Card>

      <Card
        title="Nơi bạn xuất phát"
        description="Dùng để chọn sân bay đi và điểm đón xe phù hợp"
      >
        <Select
          label="Địa điểm xuất phát"
          placeholder="— Theo địa điểm làm việc của tôi —"
          options={locationOptions}
          hint="Để trống nếu bạn đi từ chính nơi làm việc hằng ngày"
          error={errors.departure_location_id?.message}
          {...register('departure_location_id')}
        />
      </Card>
    </div>
  )
}
