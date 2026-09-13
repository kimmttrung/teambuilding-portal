import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Save } from 'lucide-react'
import { useSaveRoom } from '../../../hooks/useRooms'
import { useToast } from '../../../context/ToastContext'
import { ROOM_POLICY_META, ROOM_TYPE_LABELS } from '../../../utils/constants'
import { roomSchema } from '../../../utils/schemas'
import Alert from '../../../components/common/Alert'
import Button from '../../../components/common/Button'
import Input from '../../../components/common/Input'
import Modal from '../../../components/common/Modal'
import Select from '../../../components/common/Select'
import Textarea from '../../../components/common/Textarea'

const TYPE_OPTIONS = Object.entries(ROOM_TYPE_LABELS).map(([value, label]) => ({ value, label }))
const POLICY_OPTIONS = Object.entries(ROOM_POLICY_META).map(([value, meta]) => ({ value, label: meta.label }))

/**
 * Thêm / sửa phòng. Sửa phòng KHÔNG đổi được khách sạn (backend chặn) — tạo phòng mới thay vì
 * chuyển một phòng đang có người sang khách sạn khác.
 */
export default function RoomFormModal({ room, hotels = [], defaultHotelId, onClose }) {
  const toast = useToast()
  const { mutateAsync: save, isPending } = useSaveRoom()
  const editing = Boolean(room)

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(roomSchema),
    mode: 'onTouched',
    defaultValues: room
      ? {
          hotel_id: String(room.hotel_id),
          room_number: room.room_number ?? '',
          room_type: room.room_type ?? '',
          capacity: room.capacity ?? 2,
          floor: room.floor ?? '',
          gender_policy: room.gender_policy ?? 'any',
          note: room.note ?? '',
        }
      : {
          hotel_id: defaultHotelId ? String(defaultHotelId) : '',
          room_number: '',
          room_type: 'twin',
          capacity: 2,
          floor: '',
          gender_policy: 'any',
          note: '',
        },
  })

  async function onSubmit(values) {
    const payload = {
      room_number: values.room_number,
      room_type: values.room_type || null,
      capacity: Number(values.capacity),
      floor: values.floor || null,
      gender_policy: values.gender_policy,
      note: values.note || null,
    }
    // RoomUpdate cấm trường lạ: chỉ gửi khách sạn khi thêm mới.
    if (!editing) payload.hotel_id = Number(values.hotel_id)
    try {
      await save({ roomId: room?.id, payload })
      toast.success(editing ? `Đã cập nhật phòng ${values.room_number}.` : `Đã thêm phòng ${values.room_number}.`)
      onClose()
    } catch (saveError) {
      toast.error(saveError.message)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={editing ? `Sửa phòng ${room.room_number}` : 'Thêm phòng'}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="sm" onClick={onClose}>
            Huỷ
          </Button>
          <Button type="submit" form="room-form" size="sm" icon={Save} loading={isPending}>
            {editing ? 'Lưu thay đổi' : 'Thêm phòng'}
          </Button>
        </div>
      }
    >
      {editing && room.occupied > 0 && (
        <Alert tone="info" className="mb-4">
          Phòng đang có {room.occupied} người: không hạ sức chứa xuống dưới {room.occupied} được.
        </Alert>
      )}

      <form id="room-form" onSubmit={handleSubmit(onSubmit)} className="grid gap-3.5 sm:grid-cols-2" noValidate>
        {editing ? (
          <div className="flex flex-col gap-1.5 sm:col-span-2">
            <span className="text-sm font-medium text-slate-700">Khách sạn</span>
            <p className="rounded-lg bg-slate-50 px-3 py-2.5 text-sm text-slate-700 ring-1 ring-slate-200">
              {room.hotel_name}
            </p>
          </div>
        ) : (
          <div className="sm:col-span-2">
            <Select
              label="Khách sạn"
              required
              placeholder="— Chọn khách sạn —"
              options={hotels.map((hotel) => ({ value: String(hotel.id), label: hotel.name }))}
              error={errors.hotel_id?.message}
              {...register('hotel_id')}
            />
          </div>
        )}
        <Input label="Số phòng" required placeholder="1204" error={errors.room_number?.message} {...register('room_number')} />
        <Input label="Tầng" placeholder="12" error={errors.floor?.message} {...register('floor')} />
        <Select
          label="Loại phòng"
          placeholder="— Không ghi —"
          options={TYPE_OPTIONS}
          error={errors.room_type?.message}
          {...register('room_type')}
        />
        <Input
          label="Sức chứa (người)"
          type="number"
          min={1}
          max={10}
          required
          error={errors.capacity?.message}
          {...register('capacity')}
        />
        <div className="sm:col-span-2">
          <Select
            label="Dành cho"
            required
            options={POLICY_OPTIONS}
            hint="Phòng nam / nữ chặn cứng khi xếp. Người chưa khai giới tính chỉ vào được phòng không giới hạn."
            error={errors.gender_policy?.message}
            {...register('gender_policy')}
          />
        </div>
        <div className="sm:col-span-2">
          <Textarea label="Ghi chú" rows={2} maxLength={512} error={errors.note?.message} {...register('note')} />
        </div>
      </form>
    </Modal>
  )
}
