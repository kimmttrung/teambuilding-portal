import { useForm, useWatch } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { ArrowRight } from 'lucide-react'
import { busPickSchema } from '../../../utils/schemas'
import { BUS_LABELS } from '../../../utils/constants'
import Alert from '../../../components/common/Alert'
import Button from '../../../components/common/Button'
import Modal from '../../../components/common/Modal'
import Select from '../../../components/common/Select'
import Textarea from '../../../components/common/Textarea'

/** Xếp/chuyển thủ công cùng chặng, có lý do và cảnh báo ngoại lệ ngay trong form. */
export default function BusPickerDialog({
  title,
  person,
  buses = [],
  currentBusId = null,
  pending = false,
  onConfirm,
  onClose,
}) {
  const {
    register,
    handleSubmit,
    control,
    setError,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: zodResolver(busPickSchema),
    defaultValues: { bus_id: '', reason: '' },
    mode: 'onTouched',
  })
  const { bus_id: busId, reason } = useWatch({ control })
  const options = buses.filter(
    (bus) => bus.id !== currentBusId && bus.remaining_seats > 0,
  )
  const chosen = options.find((bus) => String(bus.id) === busId)
  const pickupMismatch =
    chosen &&
    person.pickup_point_id &&
    chosen.pickup_point_id &&
    chosen.pickup_point_id !== person.pickup_point_id
  const flightMismatch =
    chosen?.linked_flight_id &&
    person.flight_id &&
    chosen.linked_flight_id !== person.flight_id
  async function submit(values) {
    try {
      await onConfirm({ busId: Number(values.bus_id), reason: values.reason })
    } catch (error) {
      setError('root', { message: error.message })
    }
  }
  return (
    <Modal
      open
      onClose={onClose}
      title={title}
      description={[person.full_name, person.team_name]
        .filter(Boolean)
        .join(' · ')}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            {BUS_LABELS.cancel}
          </Button>
          <Button
            type="submit"
            form="bus-picker"
            icon={ArrowRight}
            loading={pending || isSubmitting}
            disabled={!options.length}
          >
            {BUS_LABELS.confirm}
          </Button>
        </div>
      }
    >
      <form
        id="bus-picker"
        onSubmit={handleSubmit(submit)}
        className="flex flex-col gap-4"
        noValidate
      >
        {errors.root && <Alert tone="error">{errors.root.message}</Alert>}
        {!options.length && (
          <Alert tone="warning">
            Không còn xe trống trong chặng này. Thêm xe hoặc tăng số chỗ trước.
          </Alert>
        )}
        <Select
          label={BUS_LABELS.title}
          required
          placeholder="— Chọn xe —"
          error={errors.bus_id?.message}
          options={options.map((bus) => ({
            value: String(bus.id),
            label: `${bus.bus_code} — còn ${bus.remaining_seats} chỗ${bus.pickup_point_name ? ` · ${bus.pickup_point_name}` : ''}`,
          }))}
          {...register('bus_id')}
        />
        {person.pickup_point_name && (
          <p className="text-caption text-ink-muted">
            Điểm đón đã chọn:{' '}
            <strong className="text-ink">{person.pickup_point_name}</strong>
          </p>
        )}
        {pickupMismatch && (
          <Alert tone="warning">
            Xe {chosen.bus_code} đón ở {chosen.pickup_point_name}, khác điểm đón
            đã chọn. Hãy báo lại cho hành khách.
          </Alert>
        )}
        {flightMismatch && (
          <Alert tone="warning">
            Xe này gắn với chuyến bay khác. Hãy kiểm tra giờ tập trung trước khi
            chuyển.
          </Alert>
        )}
        <Textarea
          label={BUS_LABELS.reason}
          required
          rows={3}
          maxLength={500}
          counterValue={reason}
          error={errors.reason?.message}
          hint="Lưu vào nhật ký thay đổi, tối thiểu 3 ký tự"
          {...register('reason')}
        />
      </form>
    </Modal>
  )
}
