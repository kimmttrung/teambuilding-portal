import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Save } from 'lucide-react'
import { useSaveGalaLayout } from '../../../hooks/useGala'
import { useToast } from '../../../context/ToastContext'
import { GALA_STAGE_POSITION_LABELS } from '../../../utils/constants'
import { fromDateTimeInput, toDateTimeInput } from '../../../utils/format'
import { galaLayoutSchema } from '../../../utils/schemas'
import Button from '../../../components/common/Button'
import Input from '../../../components/common/Input'
import Modal from '../../../components/common/Modal'
import Select from '../../../components/common/Select'

const EMPTY = {
  name: 'Gala Dinner',
  venue: '',
  starts_at: '',
  stage_position: 'top',
  grid_width: '12',
  grid_height: '8',
  turn_seconds: '',
  hold_seconds: '',
}

/** Tạo / sửa thông tin sơ đồ Gala. Bỏ trống thời gian lượt, giữ ghế = dùng cấu hình của kỳ. */
export default function LayoutFormModal({ layout, onClose }) {
  const toast = useToast()
  const { mutateAsync: save, isPending } = useSaveGalaLayout()
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(galaLayoutSchema),
    mode: 'onTouched',
    defaultValues: layout ? toFormValues(layout) : EMPTY,
  })

  async function onSubmit(values) {
    try {
      await save({ isNew: !layout, payload: toPayload(values, Boolean(layout)) })
      toast.success(layout ? 'Đã cập nhật sơ đồ.' : 'Đã tạo sơ đồ Gala. Thêm bàn để bắt đầu.')
      onClose()
    } catch (saveError) {
      toast.error(saveError.message)
    }
  }

  return (
    <Modal
      open
      size="lg"
      onClose={onClose}
      title={layout ? 'Sửa sơ đồ Gala' : 'Tạo sơ đồ Gala'}
      description="Lưới toạ độ quyết định chỗ đặt bàn trên sơ đồ"
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="sm" onClick={onClose}>
            Huỷ
          </Button>
          <Button type="submit" form="gala-layout-form" size="sm" icon={Save} loading={isPending}>
            {layout ? 'Lưu thay đổi' : 'Tạo sơ đồ'}
          </Button>
        </div>
      }
    >
      <form id="gala-layout-form" onSubmit={handleSubmit(onSubmit)} className="grid gap-3.5 sm:grid-cols-2" noValidate>
        <div className="sm:col-span-2">
          <Input label="Tên" required error={errors.name?.message} {...register('name')} />
        </div>
        <Input label="Địa điểm" placeholder="Sảnh Pearl" error={errors.venue?.message} {...register('venue')} />
        <Input label="Bắt đầu (giờ VN)" type="datetime-local" error={errors.starts_at?.message} {...register('starts_at')} />
        <Select
          label="Sân khấu"
          required
          error={errors.stage_position?.message}
          options={Object.entries(GALA_STAGE_POSITION_LABELS).map(([value, label]) => ({ value, label }))}
          {...register('stage_position')}
        />
        <div className="grid grid-cols-2 gap-3">
          <Input label="Số cột" type="number" min={4} max={40} required error={errors.grid_width?.message} {...register('grid_width')} />
          <Input label="Số hàng" type="number" min={4} max={40} required error={errors.grid_height?.message} {...register('grid_height')} />
        </div>
        <Input
          label="Mỗi lượt (giây)"
          type="number"
          min={30}
          max={3600}
          placeholder="Theo cấu hình kỳ (300)"
          error={errors.turn_seconds?.message}
          {...register('turn_seconds')}
        />
        <Input
          label="Giữ ghế tạm (giây)"
          type="number"
          min={15}
          max={1800}
          placeholder="Theo cấu hình kỳ (120)"
          error={errors.hold_seconds?.message}
          {...register('hold_seconds')}
        />
      </form>
    </Modal>
  )
}

function toFormValues(layout) {
  return {
    name: layout.name ?? '',
    venue: layout.venue ?? '',
    starts_at: toDateTimeInput(layout.starts_at),
    stage_position: layout.stage_position ?? 'top',
    grid_width: String(layout.grid_width),
    grid_height: String(layout.grid_height),
    turn_seconds: String(layout.turn_seconds ?? ''),
    hold_seconds: String(layout.hold_seconds ?? ''),
  }
}

function toPayload(values, isEdit) {
  const payload = {
    name: values.name,
    venue: values.venue || null,
    starts_at: fromDateTimeInput(values.starts_at),
    stage_position: values.stage_position,
    grid_width: Number(values.grid_width),
    grid_height: Number(values.grid_height),
  }
  // Khi sửa, ô trống nghĩa là giữ nguyên — không gửi null lên ghi đè.
  for (const field of ['turn_seconds', 'hold_seconds']) {
    if (values[field]) payload[field] = Number(values[field])
    else if (!isEdit) payload[field] = null
  }
  return payload
}
