import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Save } from 'lucide-react'
import { useSaveHotel } from '../../../hooks/useRooms'
import { useToast } from '../../../context/ToastContext'
import { fromDateTimeInput, toDateTimeInput } from '../../../utils/format'
import { hotelSchema } from '../../../utils/schemas'
import Button from '../../../components/common/Button'
import Input from '../../../components/common/Input'
import Modal from '../../../components/common/Modal'
import Textarea from '../../../components/common/Textarea'

const EMPTY = {
  name: '',
  address: '',
  phone: '',
  check_in_at: '',
  check_out_at: '',
  map_url: '',
  note: '',
}

/** Thêm / sửa khách sạn. Nơi gọi chỉ dựng khi mở nên giá trị mặc định lấy lúc khởi tạo. */
export default function HotelFormModal({ hotel, onClose }) {
  const toast = useToast()
  const { mutateAsync: save, isPending } = useSaveHotel()

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(hotelSchema),
    mode: 'onTouched',
    defaultValues: hotel ? toFormValues(hotel) : EMPTY,
  })

  async function onSubmit(values) {
    try {
      await save({ hotelId: hotel?.id, payload: toPayload(values) })
      toast.success(hotel ? `Đã cập nhật ${values.name}.` : 'Đã thêm khách sạn.')
      onClose()
    } catch (saveError) {
      toast.error(saveError.message)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={hotel ? `Sửa ${hotel.name}` : 'Thêm khách sạn'}
      description="Thông tin này hiện trong My Journey của CBNV"
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="sm" onClick={onClose}>
            Huỷ
          </Button>
          <Button type="submit" form="hotel-form" size="sm" icon={Save} loading={isPending}>
            {hotel ? 'Lưu thay đổi' : 'Thêm khách sạn'}
          </Button>
        </div>
      }
    >
      <form id="hotel-form" onSubmit={handleSubmit(onSubmit)} className="grid gap-3.5 sm:grid-cols-2" noValidate>
        <div className="sm:col-span-2">
          <Input label="Tên khách sạn" required error={errors.name?.message} {...register('name')} />
        </div>
        <div className="sm:col-span-2">
          <Input label="Địa chỉ" error={errors.address?.message} {...register('address')} />
        </div>
        <Input label="Điện thoại lễ tân" type="tel" error={errors.phone?.message} {...register('phone')} />
        <Input
          label="Link Google Maps"
          type="url"
          placeholder="https://maps.google.com/…"
          hint="Để trống thì My Journey tự tìm theo tên + địa chỉ"
          error={errors.map_url?.message}
          {...register('map_url')}
        />
        <Input
          label="Nhận phòng (giờ VN)"
          type="datetime-local"
          error={errors.check_in_at?.message}
          {...register('check_in_at')}
        />
        <Input
          label="Trả phòng (giờ VN)"
          type="datetime-local"
          error={errors.check_out_at?.message}
          {...register('check_out_at')}
        />
        <div className="sm:col-span-2">
          <Textarea
            label="Ghi chú"
            rows={2}
            maxLength={2000}
            counterValue={watch('note') ?? ''}
            error={errors.note?.message}
            {...register('note')}
          />
        </div>
      </form>
    </Modal>
  )
}

function toFormValues(hotel) {
  return {
    name: hotel.name ?? '',
    address: hotel.address ?? '',
    phone: hotel.phone ?? '',
    check_in_at: toDateTimeInput(hotel.check_in_at),
    check_out_at: toDateTimeInput(hotel.check_out_at),
    map_url: hotel.map_url ?? '',
    note: hotel.note ?? '',
  }
}

function toPayload(values) {
  return {
    name: values.name,
    address: values.address || null,
    phone: values.phone || null,
    check_in_at: fromDateTimeInput(values.check_in_at),
    check_out_at: fromDateTimeInput(values.check_out_at),
    map_url: values.map_url || null,
    note: values.note || null,
  }
}
