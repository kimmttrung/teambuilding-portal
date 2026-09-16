import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Save } from 'lucide-react'
import { useSaveItineraryItem } from '../../../hooks/useItinerary'
import { useToast } from '../../../context/ToastContext'
import { itineraryItemSchema } from '../../../utils/schemas'
import Button from '../../../components/common/Button'
import Input from '../../../components/common/Input'
import Modal from '../../../components/common/Modal'
import Select from '../../../components/common/Select'
import Textarea from '../../../components/common/Textarea'

const EMPTY = {
  day_date: '',
  start_time: '',
  end_time: '',
  title: '',
  location: '',
  description: '',
  audience: 'all',
}

/**
 * Thêm / sửa mốc lịch trình. `item = null` là thêm mới (ngày mặc định là ngày đang xem).
 * Đối tượng lấy từ master data thật (ca của kỳ + team) để không gõ sai mã khiến mốc
 * biến mất với mọi người — backend vẫn chặn lại lần nữa.
 */
export default function ItineraryFormModal({ open, onClose, item, defaultDay, event, audiences }) {
  const toast = useToast()
  const { mutateAsync: save, isPending } = useSaveItineraryItem()

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm({ resolver: zodResolver(itineraryItemSchema), defaultValues: EMPTY, mode: 'onTouched' })

  useEffect(() => {
    if (!open) return
    reset(item ? toFormValues(item) : { ...EMPTY, day_date: defaultDay ?? event?.start_date ?? '' })
  }, [item, defaultDay, event, reset, open])

  async function onSubmit(values) {
    try {
      await save({ itemId: item?.id, payload: toPayload(values) })
      toast.success(item ? 'Đã cập nhật mốc lịch trình.' : 'Đã thêm mốc lịch trình.')
      onClose()
    } catch (error) {
      toast.error(error.message)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={item ? 'Sửa mốc lịch trình' : 'Thêm mốc lịch trình'}
      description="CBNV thấy lịch mới ngay sau khi lưu (có thể cần tải lại trang)"
      footer={
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" size="sm" onClick={onClose}>
            Huỷ
          </Button>
          <Button type="submit" form="itinerary-form" size="sm" icon={Save} loading={isPending}>
            {item ? 'Lưu thay đổi' : 'Thêm mốc'}
          </Button>
        </div>
      }
    >
      <form id="itinerary-form" onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-3">
        <div className="grid gap-3 sm:grid-cols-3">
          <Input
            label="Ngày"
            type="date"
            required
            min={event?.start_date}
            max={event?.end_date}
            hint={event ? `Trong kỳ ${event.start_date} – ${event.end_date}` : undefined}
            error={errors.day_date?.message}
            {...register('day_date')}
          />
          <Input label="Bắt đầu" type="time" error={errors.start_time?.message} {...register('start_time')} />
          <Input label="Kết thúc" type="time" error={errors.end_time?.message} {...register('end_time')} />
        </div>
        <Input label="Hoạt động" required placeholder="Ví dụ: Gala Dinner & Vinh danh" error={errors.title?.message} {...register('title')} />
        <Input label="Địa điểm" placeholder="Ví dụ: Sảnh Pearl" error={errors.location?.message} {...register('location')} />
        <Select label="Dành cho" required options={audiences} error={errors.audience?.message} {...register('audience')} />
        <Textarea label="Ghi chú thêm" rows={2} error={errors.description?.message} {...register('description')} />
      </form>
    </Modal>
  )
}

function toFormValues(item) {
  return {
    day_date: item.day_date ?? '',
    start_time: item.start_time ?? '',
    end_time: item.end_time ?? '',
    title: item.title ?? '',
    location: item.location ?? '',
    description: item.description ?? '',
    audience: item.audience ?? 'all',
  }
}

/** Ô trống thành null cho khớp `extra="forbid"` + pattern của backend. */
function toPayload(values) {
  const text = (value) => {
    const trimmed = (value ?? '').trim()
    return trimmed === '' ? null : trimmed
  }
  return {
    day_date: values.day_date,
    start_time: values.start_time || null,
    end_time: values.end_time || null,
    title: values.title.trim(),
    location: text(values.location),
    description: text(values.description),
    audience: values.audience,
  }
}
