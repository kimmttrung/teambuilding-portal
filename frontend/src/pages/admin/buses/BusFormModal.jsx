import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Save } from 'lucide-react'
import { useFlights } from '../../../hooks/useFlights'
import { useSaveBus } from '../../../hooks/useBuses'
import { useToast } from '../../../context/ToastContext'
import { FLIGHT_DIRECTION_LABELS } from '../../../utils/constants'
import { formatShortDateTime, fromDateTimeInput, toDateTimeInput } from '../../../utils/format'
import { busSchema } from '../../../utils/schemas'
import Alert from '../../../components/common/Alert'
import Button from '../../../components/common/Button'
import Input from '../../../components/common/Input'
import Modal from '../../../components/common/Modal'
import Select from '../../../components/common/Select'
import Textarea from '../../../components/common/Textarea'

const EMPTY = {
  trip_leg_id: '',
  bus_code: '',
  plate_number: '',
  capacity: 45,
  pickup_point_id: '',
  dropoff_point: '',
  gather_time: '',
  departure_time: '',
  linked_flight_id: '',
  driver_name: '',
  driver_phone: '',
  note: '',
}

/**
 * Thêm / sửa xe. `bus = null` là thêm mới. Nơi gọi chỉ dựng component khi mở, nên giá trị
 * mặc định lấy thẳng lúc khởi tạo, không cần effect `reset`.
 *
 * Sửa xe KHÔNG đổi được chặng (backend chặn): xe đang chở người mà đổi chặng thì mọi phân xe
 * của nó thành vô nghĩa. Trưởng xe gán ở hộp thoại riêng.
 */
export default function BusFormModal({ bus, legs = [], pickupPoints = [], defaultLegId, onClose }) {
  const toast = useToast()
  const { mutateAsync: save, isPending } = useSaveBus()
  const { data: flights } = useFlights()
  const editing = Boolean(bus)

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(busSchema),
    mode: 'onTouched',
    defaultValues: bus ? toFormValues(bus) : { ...EMPTY, trip_leg_id: defaultLegId ? String(defaultLegId) : '' },
  })

  const legId = Number(watch('trip_leg_id')) || null
  const leg = legs.find((item) => item.id === legId) ?? null
  const points = pickupPoints.filter((point) => !point.trip_leg_id || point.trip_leg_id === legId)
  const flightOptions = (flights ?? []).filter((flight) => !leg || flight.direction === leg.direction)

  async function onSubmit(values) {
    try {
      await save({ busId: bus?.id, payload: toPayload(values, { editing }) })
      toast.success(editing ? `Đã cập nhật xe ${values.bus_code.toUpperCase()}.` : 'Đã thêm xe.')
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
      title={editing ? `Sửa xe ${bus.bus_code}` : 'Thêm xe'}
      description="Giờ nhập theo giờ Việt Nam, hệ thống tự đổi sang UTC khi lưu"
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="sm" onClick={onClose}>
            Huỷ
          </Button>
          <Button type="submit" form="bus-form" size="sm" icon={Save} loading={isPending}>
            {editing ? 'Lưu thay đổi' : 'Thêm xe'}
          </Button>
        </div>
      }
    >
      {editing && bus.assigned_count > 0 && (
        <Alert tone="info" className="mb-4">
          Xe này đã xếp {bus.assigned_count} người: không hạ số chỗ xuống dưới {bus.assigned_count} được.
        </Alert>
      )}

      <form id="bus-form" onSubmit={handleSubmit(onSubmit)} className="grid gap-3.5 sm:grid-cols-2" noValidate>
        {editing ? (
          <div className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-slate-700">Chặng</span>
            <p className="rounded-lg bg-slate-50 px-3 py-2.5 text-sm text-slate-700 ring-1 ring-slate-200">
              {bus.trip_leg_name}
            </p>
            <p className="text-xs text-slate-500">Không đổi chặng được — tạo xe mới cho chặng khác.</p>
          </div>
        ) : (
          <Select
            label="Chặng"
            required
            placeholder="— Chọn chặng —"
            options={legs.map((item) => ({ value: String(item.id), label: item.name }))}
            error={errors.trip_leg_id?.message}
            {...register('trip_leg_id')}
          />
        )}
        <Input
          label="Mã xe"
          required
          placeholder="XE-01"
          className="uppercase"
          error={errors.bus_code?.message}
          {...register('bus_code')}
        />
        <Input label="Biển số" placeholder="29B-123.45" error={errors.plate_number?.message} {...register('plate_number')} />
        <Input
          label="Số chỗ"
          type="number"
          min={1}
          max={100}
          required
          hint="Số ghế dành cho CBNV, không tính tài xế"
          error={errors.capacity?.message}
          {...register('capacity')}
        />
        <Select
          label="Điểm đón"
          placeholder="— Không cố định —"
          options={points.map((point) => ({ value: String(point.id), label: point.name }))}
          hint="Thuật toán ưu tiên xếp người chọn đúng điểm đón này"
          error={errors.pickup_point_id?.message}
          {...register('pickup_point_id')}
        />
        <Input label="Điểm trả" placeholder="Sân bay Nội Bài – ga T1" error={errors.dropoff_point?.message} {...register('dropoff_point')} />
        <Input
          label="Giờ tập trung (giờ VN)"
          type="datetime-local"
          error={errors.gather_time?.message}
          {...register('gather_time')}
        />
        <Input
          label="Giờ xe chạy (giờ VN)"
          type="datetime-local"
          error={errors.departure_time?.message}
          {...register('departure_time')}
        />
        <Select
          label="Gắn với chuyến bay"
          placeholder="— Không gắn —"
          options={flightOptions.map((flight) => ({
            value: String(flight.id),
            label: `${flight.flight_code} · ${formatShortDateTime(flight.departure_time)}`,
          }))}
          hint={
            leg?.is_airport_linked
              ? 'Chặng gắn sân bay: gắn chuyến để xe chở đúng người bay chuyến đó'
              : leg
                ? `Chỉ hiện chuyến ${FLIGHT_DIRECTION_LABELS[leg.direction]?.toLowerCase() ?? ''}`
                : undefined
          }
          className="sm:col-span-2"
          error={errors.linked_flight_id?.message}
          {...register('linked_flight_id')}
        />
        <Input label="Tài xế" error={errors.driver_name?.message} {...register('driver_name')} />
        <Input label="SĐT tài xế" type="tel" error={errors.driver_phone?.message} {...register('driver_phone')} />
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

function toFormValues(bus) {
  return {
    trip_leg_id: String(bus.trip_leg_id),
    bus_code: bus.bus_code ?? '',
    plate_number: bus.plate_number ?? '',
    capacity: bus.capacity ?? 45,
    pickup_point_id: bus.pickup_point_id ? String(bus.pickup_point_id) : '',
    dropoff_point: bus.dropoff_point ?? '',
    gather_time: toDateTimeInput(bus.gather_time),
    departure_time: toDateTimeInput(bus.departure_time),
    linked_flight_id: bus.linked_flight_id ? String(bus.linked_flight_id) : '',
    driver_name: bus.driver_name ?? '',
    driver_phone: bus.driver_phone ?? '',
    note: bus.note ?? '',
  }
}

function toPayload(values, { editing }) {
  const payload = {
    bus_code: values.bus_code.trim().toUpperCase(),
    plate_number: values.plate_number || null,
    capacity: Number(values.capacity),
    pickup_point_id: values.pickup_point_id ? Number(values.pickup_point_id) : null,
    dropoff_point: values.dropoff_point || null,
    gather_time: fromDateTimeInput(values.gather_time),
    departure_time: fromDateTimeInput(values.departure_time),
    linked_flight_id: values.linked_flight_id ? Number(values.linked_flight_id) : null,
    driver_name: values.driver_name || null,
    driver_phone: values.driver_phone || null,
    note: values.note || null,
  }
  // BusUpdate cấm trường lạ: chỉ gửi chặng khi thêm mới.
  if (!editing) payload.trip_leg_id = Number(values.trip_leg_id)
  return payload
}
