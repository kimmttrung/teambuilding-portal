import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { RotateCcw, Save } from 'lucide-react'
import { useEventSettings, useSaveEventSettings } from '../../../hooks/useEvent'
import { useToast } from '../../../context/ToastContext'
import Alert from '../../../components/common/Alert'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import Input from '../../../components/common/Input'
import Spinner from '../../../components/common/Spinner'

/**
 * Trọng số thuật toán + thời gian chọn ghế Gala (`event_settings`).
 *
 * Nhóm theo việc chứ không theo tên khoá: BTC nghĩ "xếp chuyến bay" / "xếp phòng" / "Gala", không nghĩ
 * "allocation.*". Mô tả lấy thẳng từ backend (`description` của từng khoá) để hai nơi không lệch nhau.
 *
 * Chỉ ảnh hưởng **lần chạy phân bổ sau** — đổi số ở đây không tự xếp lại chỗ đã xếp.
 */
const GROUPS = [
  {
    title: 'Xếp chuyến bay',
    hint: 'Điểm càng cao thì thuật toán càng cố giữ tiêu chí đó.',
    keys: [
      'allocation.team_weight',
      'allocation.shift_weight',
      'allocation.split_penalty',
      'allocation.max_split_per_team',
      'allocation.min_chunk_size',
    ],
  },
  {
    title: 'Xếp phòng',
    hint: 'Tính theo từng cặp người ở chung một phòng.',
    keys: ['rooms.team_weight', 'rooms.flight_weight', 'rooms.department_weight'],
  },
  {
    title: 'Gala Dinner',
    hint: 'Tính bằng giây. Đổi khi đang mở chọn ghế chỉ áp cho lượt sau.',
    keys: ['gala.hold_seconds', 'gala.turn_seconds'],
  },
]

const LABELS = {
  'allocation.team_weight': 'Thưởng giữ người cùng team một chuyến',
  'allocation.shift_weight': 'Thưởng đúng ca nguyện vọng',
  'allocation.split_penalty': 'Phạt mỗi lần team bị tách thêm',
  'allocation.max_split_per_team': 'Số mảnh tối đa một team bị tách',
  'allocation.min_chunk_size': 'Mảnh tách ra nhỏ nhất',
  'rooms.team_weight': 'Thưởng cặp cùng team ở chung phòng',
  'rooms.flight_weight': 'Thưởng cặp cùng chuyến bay chiều đi',
  'rooms.department_weight': 'Thưởng cặp cùng phòng ban',
  'gala.hold_seconds': 'Thời gian giữ ghế tạm (giây)',
  'gala.turn_seconds': 'Thời gian mỗi lượt chọn ghế (giây)',
}

export default function WeightsTab({ event }) {
  const toast = useToast()
  const { data: settings, isLoading, error } = useEventSettings(event.id)
  const { mutateAsync: save, isPending } = useSaveEventSettings(event.id)

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isDirty },
  } = useForm({ defaultValues: {}, mode: 'onTouched' })

  useEffect(() => {
    if (settings) reset(toForm(settings))
  }, [settings, reset])

  if (isLoading) return <Spinner label="Đang tải cấu hình…" />
  if (error) return <Alert tone="error">{error.message}</Alert>

  async function onSubmit(values) {
    try {
      await save(Object.fromEntries(Object.entries(values).map(([key, value]) => [key, Number(value)])))
      toast.success('Đã lưu cấu hình. Áp dụng từ lần chạy phân bổ sau.')
    } catch (saveError) {
      toast.error(saveError.message)
    }
  }

  return (
    <form id="weights-form" noValidate onSubmit={handleSubmit(onSubmit)} className="grid gap-4">
      <Alert tone="info">
        Đổi các số này <strong>không xếp lại</strong> chỗ đã xếp — chỉ lần chạy phân bổ tiếp theo mới
        dùng tới. Muốn áp dụng ngay thì chạy lại phân bổ ở màn hình tương ứng.
      </Alert>

      {GROUPS.map((group) => (
        <Card
          key={group.title}
          title={group.title}
          description={group.hint}
          action={
            group === GROUPS[0] && (
              <div className="flex gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  icon={RotateCcw}
                  onClick={() => reset(toForm(settings))}
                  disabled={!isDirty}
                >
                  Hoàn tác
                </Button>
                <Button type="submit" form="weights-form" size="sm" icon={Save} loading={isPending} disabled={!isDirty}>
                  Lưu cấu hình
                </Button>
              </div>
            )
          }
        >
          <div className="grid gap-3.5 sm:grid-cols-2 xl:grid-cols-3">
            {group.keys.map((key) => (
              <Input
                key={key}
                type="number"
                label={LABELS[key] ?? key}
                hint={settings?.[key]?.description}
                error={errors[key]?.message}
                {...register(key, {
                  required: 'Nhập một số',
                  min: { value: 0, message: 'Không được âm' },
                })}
              />
            ))}
          </div>
        </Card>
      ))}
    </form>
  )
}

function toForm(settings) {
  return Object.fromEntries(Object.entries(settings).map(([key, row]) => [key, row.value]))
}
