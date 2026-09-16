import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { CheckCircle2, Save } from 'lucide-react'
import { useActivateEvent, useUpdateEvent } from '../../../hooks/useEvent'
import { useToast } from '../../../context/ToastContext'
import { fromDateTimeInput, toDateTimeInput } from '../../../utils/format'
import { eventInfoSchema } from '../../../utils/schemas'
import Alert from '../../../components/common/Alert'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import Input from '../../../components/common/Input'

/**
 * Thông tin kỳ + nút đặt làm kỳ mặc định.
 *
 * Mốc mở/đóng đăng ký nhập theo giờ Việt Nam rồi đổi sang UTC khi lưu — cùng cách form chuyến bay
 * làm. Ghi thẳng giờ UTC là hạn thật lệch 7 tiếng so với thứ ghi trong quy định và email nhắc.
 */
export default function EventInfoTab({ event }) {
  const toast = useToast()
  const { mutateAsync: save, isPending } = useUpdateEvent()
  const { mutateAsync: activate, isPending: activating } = useActivateEvent()

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isDirty },
  } = useForm({ resolver: zodResolver(eventInfoSchema), defaultValues: toForm(event), mode: 'onTouched' })

  useEffect(() => {
    reset(toForm(event))
  }, [event, reset])

  async function onSubmit(values) {
    try {
      await save({ eventId: event.id, payload: toPayload(values) })
      toast.success('Đã lưu thông tin kỳ.')
    } catch (error) {
      toast.error(error.message)
    }
  }

  async function onActivate() {
    const message =
      `Đặt "${event.name}" làm kỳ mặc định?\n\n` +
      'Kỳ mặc định là thứ mọi người thấy khi chưa chọn kỳ nào — đổi là ảnh hưởng toàn bộ CBNV.'
    if (!window.confirm(message)) return
    try {
      await activate(event.id)
      toast.success(`${event.name} giờ là kỳ mặc định.`)
    } catch (error) {
      toast.error(error.message)
    }
  }

  return (
    <div className="grid gap-4">
      <Card
        title="Thông tin kỳ"
        description="Tên, điểm đến và mốc thời gian hiện trên mọi màn hình của CBNV"
        action={
          <Button type="submit" form="event-info-form" size="sm" icon={Save} loading={isPending} disabled={!isDirty}>
            Lưu thay đổi
          </Button>
        }
      >
        <form
          id="event-info-form"
          noValidate
          onSubmit={handleSubmit(onSubmit)}
          className="grid gap-3.5 sm:grid-cols-2"
        >
          <Input label="Mã kỳ" value={event.code} disabled hint="Không đổi được sau khi tạo" readOnly />
          <Input label="Điểm đến" error={errors.destination?.message} {...register('destination')} />
          <div className="sm:col-span-2">
            <Input label="Tên kỳ" required error={errors.name?.message} {...register('name')} />
          </div>
          <Input label="Ngày bắt đầu" type="date" required error={errors.start_date?.message} {...register('start_date')} />
          <Input label="Ngày kết thúc" type="date" required error={errors.end_date?.message} {...register('end_date')} />
          <Input
            label="Mở đăng ký lúc"
            type="datetime-local"
            hint="Giờ Việt Nam"
            error={errors.registration_opens_at?.message}
            {...register('registration_opens_at')}
          />
          <Input
            label="Đóng đăng ký lúc"
            type="datetime-local"
            hint="Giờ Việt Nam. Huỷ sau mốc này bị tính phí phạt"
            error={errors.registration_closes_at?.message}
            {...register('registration_closes_at')}
          />
          <div className="sm:col-span-2">
            <Input label="Ảnh bìa (URL)" error={errors.banner_url?.message} {...register('banner_url')} />
          </div>
        </form>
      </Card>

      <Card title="Kỳ mặc định" description="Kỳ mà người chưa chọn gì sẽ nhìn thấy">
        {event.is_active ? (
          <Alert tone="success" title="Đây đang là kỳ mặc định">
            Mọi CBNV mở cổng lên sẽ thấy kỳ này. Sang mùa sau, mở kỳ mới rồi quay lại đây đặt kỳ đó làm
            mặc định.
          </Alert>
        ) : (
          <div className="flex flex-col gap-3">
            <Alert tone="info">
              Kỳ này chỉ hiện với người tự chọn nó trên thanh bên. Đặt làm mặc định thì mọi CBNV sẽ thấy
              nó ngay khi đăng nhập.
            </Alert>
            <div>
              <Button icon={CheckCircle2} loading={activating} onClick={onActivate}>
                Đặt làm kỳ mặc định
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}

function toForm(event) {
  return {
    name: event.name ?? '',
    destination: event.destination ?? '',
    start_date: event.start_date ?? '',
    end_date: event.end_date ?? '',
    registration_opens_at: toDateTimeInput(event.registration_opens_at) ?? '',
    registration_closes_at: toDateTimeInput(event.registration_closes_at) ?? '',
    banner_url: event.banner_url ?? '',
  }
}

function toPayload(values) {
  return {
    name: values.name.trim(),
    destination: values.destination?.trim() || null,
    start_date: values.start_date,
    end_date: values.end_date,
    registration_opens_at: values.registration_opens_at
      ? fromDateTimeInput(values.registration_opens_at)
      : null,
    registration_closes_at: values.registration_closes_at
      ? fromDateTimeInput(values.registration_closes_at)
      : null,
    banner_url: values.banner_url?.trim() || null,
  }
}
