import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router-dom'
import { zodResolver } from '@hookform/resolvers/zod'
import { Save } from 'lucide-react'
import { useSaveFlight } from '../../../hooks/useFlights'
import { useToast } from '../../../context/ToastContext'
import { FLIGHT_DIRECTION_LABELS } from '../../../utils/constants'
import { formatShortDateTime, fromDateTimeInput, toDateTimeInput } from '../../../utils/format'
import { flightSchema } from '../../../utils/schemas'
import Alert from '../../../components/common/Alert'
import Button from '../../../components/common/Button'
import Input from '../../../components/common/Input'
import Modal from '../../../components/common/Modal'
import Select from '../../../components/common/Select'
import Textarea from '../../../components/common/Textarea'

const DIRECTION_OPTIONS = Object.entries(FLIGHT_DIRECTION_LABELS).map(([value, label]) => ({
  value,
  label,
}))

const EMPTY = {
  flight_code: '',
  airline: '',
  direction: 'outbound',
  shift_id: '',
  departure_airport: '',
  arrival_airport: '',
  departure_time: '',
  arrival_time: '',
  capacity: 60,
  reserved_slots: 0,
  note: '',
  is_active: true,
}

/** Thêm / sửa chuyến bay. `flight = null` là thêm mới. */
export default function FlightFormModal({ open, onClose, flight, shifts = [] }) {
  const toast = useToast()
  const { mutateAsync: save, isPending } = useSaveFlight()
  // Xe ra/đón sân bay không còn khớp giờ bay mới — backend chặn, hiện danh sách để BTC chỉnh xe trước.
  const [busConflicts, setBusConflicts] = useState([])

  const {
    register,
    handleSubmit,
    reset,
    watch,
    setValue,
    formState: { errors },
  } = useForm({ resolver: zodResolver(flightSchema), defaultValues: EMPTY, mode: 'onTouched' })

  useEffect(() => {
    reset(flight ? toFormValues(flight) : EMPTY)
    setBusConflicts([])
  }, [flight, reset, open])

  const assigned = flight?.assigned_count ?? 0

  async function onSubmit(values) {
    try {
      await save({ flightId: flight?.id, payload: toPayload(values) })
      toast.success(flight ? `Đã cập nhật chuyến ${values.flight_code}.` : 'Đã thêm chuyến bay.')
      onClose()
    } catch (error) {
      if (error.code === 'FLIGHT_BUS_TIME_CONFLICT') {
        setBusConflicts(error.details?.buses ?? [])
        toast.error('Giờ bay mới không khớp giờ xe. Chỉnh xe trước rồi lưu lại.')
        return
      }
      toast.error(error.message)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="lg"
      title={flight ? `Sửa chuyến ${flight.flight_code}` : 'Thêm chuyến bay'}
      description="Giờ nhập theo giờ Việt Nam, hệ thống tự đổi sang UTC khi lưu"
      footer={
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" size="sm" onClick={onClose}>
            Huỷ
          </Button>
          <Button
            type="submit"
            form="flight-form"
            size="sm"
            icon={Save}
            loading={isPending}
          >
            {flight ? 'Lưu thay đổi' : 'Thêm chuyến'}
          </Button>
        </div>
      }
    >
      {assigned > 0 && (
        <Alert tone="info" className="mb-4">
          Chuyến này đã xếp {assigned} người. Không thể hạ ghế dùng được xuống dưới {assigned},
          cũng không tắt được chuyến khi còn hành khách.
        </Alert>
      )}

      {busConflicts.length > 0 && (
        <Alert tone="error" title="Chưa lưu: giờ bay mới lệch với xe" className="mb-4">
          <ul className="mt-1 list-disc space-y-0.5 pl-5">
            {busConflicts.map((bus) => (
              <li key={bus.bus_id}>
                <strong>{bus.bus_code}</strong> ({bus.trip_leg_name}, chạy{' '}
                {formatShortDateTime(bus.departure_time || bus.gather_time)}): {bus.reason}
              </li>
            ))}
          </ul>
          <p className="mt-2">
            Sửa giờ xe hoặc chuyển hành khách sang xe khác ở{' '}
            <Link
              to={`/admin/buses?leg=${busConflicts[0].trip_leg_id}`}
              className="font-medium underline"
            >
              màn hình Xe
            </Link>
            , rồi lưu lại chuyến bay.
          </p>
        </Alert>
      )}

      <form
        id="flight-form"
        onSubmit={handleSubmit(onSubmit)}
        className="grid gap-3.5 sm:grid-cols-2"
        noValidate
      >
        <Input
          label="Mã chuyến"
          required
          placeholder="VN1234"
          error={errors.flight_code?.message}
          {...register('flight_code')}
        />
        <Input
          label="Hãng bay"
          placeholder="Vietnam Airlines"
          error={errors.airline?.message}
          {...register('airline')}
        />
        <Select
          label="Chiều bay"
          required
          options={DIRECTION_OPTIONS}
          error={errors.direction?.message}
          {...register('direction')}
        />
        <Select
          label="Ca"
          placeholder="— Chưa gán ca —"
          options={shifts.map((shift) => ({ value: String(shift.id), label: shift.name }))}
          hint="Ca quyết định việc đáp ứng nguyện vọng khi phân bổ"
          error={errors.shift_id?.message}
          {...register('shift_id')}
        />
        <Input
          label="Sân bay đi"
          required
          placeholder="HAN"
          className="uppercase"
          error={errors.departure_airport?.message}
          {...register('departure_airport')}
        />
        <Input
          label="Sân bay đến"
          required
          placeholder="PQC"
          className="uppercase"
          error={errors.arrival_airport?.message}
          {...register('arrival_airport')}
        />
        <Input
          label="Giờ khởi hành (giờ VN)"
          type="datetime-local"
          required
          error={errors.departure_time?.message}
          {...register('departure_time')}
        />
        <Input
          label="Giờ đến (giờ VN)"
          type="datetime-local"
          required
          error={errors.arrival_time?.message}
          {...register('arrival_time')}
        />
        <Input
          label="Tổng số ghế"
          type="number"
          min={1}
          required
          error={errors.capacity?.message}
          {...register('capacity')}
        />
        <Input
          label="Ghế giữ lại"
          type="number"
          min={0}
          hint="Ghế dự phòng, thuật toán không xếp vào"
          error={errors.reserved_slots?.message}
          {...register('reserved_slots')}
        />
        <Textarea
          label="Ghi chú"
          rows={2}
          maxLength={2000}
          counterValue={watch('note') ?? ''}
          className="sm:col-span-2"
          error={errors.note?.message}
          {...register('note')}
        />
        <label className="flex items-center gap-2.5 sm:col-span-2">
          <input
            type="checkbox"
            className="size-4 accent-brand-600"
            checked={Boolean(watch('is_active'))}
            onChange={(event) => setValue('is_active', event.target.checked)}
          />
          <span className="text-sm text-slate-700">
            Chuyến đang dùng (bỏ tick để loại khỏi phân bổ)
          </span>
        </label>
      </form>
    </Modal>
  )
}

function toFormValues(flight) {
  return {
    flight_code: flight.flight_code ?? '',
    airline: flight.airline ?? '',
    direction: flight.direction,
    shift_id: flight.shift_id ? String(flight.shift_id) : '',
    departure_airport: flight.departure_airport ?? '',
    arrival_airport: flight.arrival_airport ?? '',
    departure_time: toDateTimeInput(flight.departure_time),
    arrival_time: toDateTimeInput(flight.arrival_time),
    capacity: flight.capacity ?? 0,
    reserved_slots: flight.reserved_slots ?? 0,
    note: flight.note ?? '',
    is_active: flight.is_active ?? true,
  }
}

function toPayload(values) {
  return {
    flight_code: values.flight_code.trim().toUpperCase(),
    airline: values.airline?.trim() || null,
    direction: values.direction,
    shift_id: values.shift_id ? Number(values.shift_id) : null,
    departure_airport: values.departure_airport.trim().toUpperCase(),
    arrival_airport: values.arrival_airport.trim().toUpperCase(),
    departure_time: fromDateTimeInput(values.departure_time),
    arrival_time: fromDateTimeInput(values.arrival_time),
    capacity: Number(values.capacity),
    reserved_slots: Number(values.reserved_slots),
    note: values.note?.trim() || null,
    is_active: values.is_active,
  }
}
