import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Plus } from 'lucide-react'
import { useCreateEvent } from '../../hooks/useEvent'
import { useToast } from '../../context/ToastContext'
import { eventSchema } from '../../utils/schemas'
import Alert from '../common/Alert'
import Button from '../common/Button'
import Input from '../common/Input'
import Modal from '../common/Modal'

const EMPTY = { code: '', name: '', destination: '', start_date: '', end_date: '' }

/**
 * BTC mở kỳ Team Building cho mùa sau, không cần chạm vào database.
 *
 * Kỳ mới luôn là bản **nháp** và không thành kỳ mặc định: CBNV chưa thấy gì, BTC dựng xong chuyến
 * bay / khách sạn / sơ đồ Gala rồi mới mở đăng ký. Tạo xong tự chuyển sang kỳ đó.
 */
export default function EventCreateModal({ open, onClose }) {
  const toast = useToast()
  const { mutateAsync: create, isPending } = useCreateEvent()

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm({ resolver: zodResolver(eventSchema), defaultValues: EMPTY, mode: 'onTouched' })

  async function onSubmit(values) {
    try {
      const created = await create({
        code: values.code.trim().toUpperCase(),
        name: values.name.trim(),
        destination: values.destination?.trim() || null,
        start_date: values.start_date,
        end_date: values.end_date,
      })
      toast.success(`Đã tạo kỳ ${created.code}. Bạn đang xem kỳ này.`)
      reset(EMPTY)
      onClose()
    } catch (error) {
      toast.error(error.message)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Thêm kỳ Team Building"
      description="Kỳ mới là bản nháp, chỉ Ban tổ chức nhìn thấy"
      footer={
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" size="sm" onClick={onClose}>
            Huỷ
          </Button>
          <Button type="submit" form="event-create-form" size="sm" icon={Plus} loading={isPending}>
            Tạo kỳ
          </Button>
        </div>
      }
    >
      <Alert tone="info" className="mb-4">
        Tạo xong, hệ thống chuyển bạn sang kỳ mới. Dựng ca bay, chuyến bay, chặng xe, khách sạn và sơ
        đồ Gala cho kỳ đó rồi mới chuyển trạng thái sang <strong>Mở đăng ký</strong>.
      </Alert>

      <form
        id="event-create-form"
        onSubmit={handleSubmit(onSubmit)}
        className="grid gap-3.5 sm:grid-cols-2"
        noValidate
      >
        <Input
          label="Mã kỳ"
          required
          placeholder="TB2027"
          error={errors.code?.message}
          {...register('code')}
        />
        <Input
          label="Điểm đến"
          placeholder="Đà Nẵng"
          error={errors.destination?.message}
          {...register('destination')}
        />
        <div className="sm:col-span-2">
          <Input
            label="Tên kỳ"
            required
            placeholder="Team Building 2027 – Đà Nẵng"
            error={errors.name?.message}
            {...register('name')}
          />
        </div>
        <Input
          label="Ngày bắt đầu"
          type="date"
          required
          error={errors.start_date?.message}
          {...register('start_date')}
        />
        <Input
          label="Ngày kết thúc"
          type="date"
          required
          error={errors.end_date?.message}
          {...register('end_date')}
        />
      </form>
    </Modal>
  )
}
