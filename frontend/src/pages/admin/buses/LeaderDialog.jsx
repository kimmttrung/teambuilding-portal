import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Save } from 'lucide-react'
import { useBusAssignments, useSetBusLeader } from '../../../hooks/useBuses'
import { useToast } from '../../../context/ToastContext'
import { leaderSchema } from '../../../utils/schemas'
import Alert from '../../../components/common/Alert'
import Button from '../../../components/common/Button'
import Input from '../../../components/common/Input'
import Modal from '../../../components/common/Modal'
import Select from '../../../components/common/Select'

const MODES = [
  { value: 'employee', label: 'CBNV trong đoàn', hint: 'Lấy tên, số điện thoại từ hồ sơ' },
  { value: 'outsider', label: 'Người ngoài', hint: 'Hướng dẫn viên, nhân viên nhà xe…' },
  { value: 'none', label: 'Chưa có', hint: 'Bỏ Trưởng xe hiện tại' },
]

/**
 * Gán Trưởng xe. Người đang đi trên chính xe này xếp lên đầu danh sách: Trưởng xe phải có
 * mặt trên xe để điểm danh, chọn nhầm người xe khác là lỗi hay gặp nhất.
 */
export default function LeaderDialog({ bus, participants = [], onClose }) {
  const toast = useToast()
  const { mutateAsync: saveLeader, isPending } = useSetBusLeader()
  const { data: passengerPage } = useBusAssignments({ bus_id: bus.id, page_size: 200 })

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(leaderSchema),
    mode: 'onTouched',
    defaultValues: {
      mode: bus.leader_user_id || !bus.leader_name ? 'employee' : 'outsider',
      leader_user_id: bus.leader_user_id ? String(bus.leader_user_id) : '',
      leader_name: bus.leader_user_id ? '' : (bus.leader_name ?? ''),
      leader_phone: bus.leader_user_id ? '' : (bus.leader_phone ?? ''),
    },
  })
  const mode = watch('mode')

  const onBus = passengerPage?.items ?? []
  const onBusIds = new Set(onBus.map((row) => row.user_id))
  const others = participants
    .filter((registration) => !onBusIds.has(registration.user.id))
    .sort((left, right) => left.user.full_name.localeCompare(right.user.full_name, 'vi'))
  const currentIsListed =
    !bus.leader_user_id ||
    onBusIds.has(bus.leader_user_id) ||
    others.some((registration) => registration.user.id === bus.leader_user_id)

  async function onSubmit(values) {
    const payload =
      values.mode === 'employee'
        ? { leader_user_id: Number(values.leader_user_id) }
        : values.mode === 'outsider'
          ? { leader_name: values.leader_name, leader_phone: values.leader_phone }
          : {}
    try {
      await saveLeader({ busId: bus.id, payload })
      toast.success(
        values.mode === 'none'
          ? `Đã bỏ Trưởng xe của xe ${bus.bus_code}.`
          : `Đã cập nhật Trưởng xe của xe ${bus.bus_code}.`,
      )
      onClose()
    } catch (saveError) {
      toast.error(saveError.message)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={`Trưởng xe ${bus.bus_code}`}
      description="Trưởng xe điểm danh và gọi người đến muộn — nên là người đi trên chính xe này"
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="sm" onClick={onClose}>
            Huỷ
          </Button>
          <Button type="submit" form="leader-form" size="sm" icon={Save} loading={isPending}>
            Lưu
          </Button>
        </div>
      }
    >
      <form id="leader-form" onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-3.5" noValidate>
        <fieldset className="grid gap-2 sm:grid-cols-3">
          <legend className="sr-only">Loại Trưởng xe</legend>
          {MODES.map((item) => (
            <label
              key={item.value}
              className={`cursor-pointer rounded-lg border-2 p-2.5 text-sm transition focus-within:ring-2 focus-within:ring-brand-300 ${
                mode === item.value ? 'border-brand-600 bg-brand-50' : 'border-slate-200 hover:border-slate-300'
              }`}
            >
              <input type="radio" value={item.value} className="sr-only" {...register('mode')} />
              <span className="block font-medium text-slate-900">{item.label}</span>
              <span className="block text-xs text-slate-500">{item.hint}</span>
            </label>
          ))}
        </fieldset>

        {mode === 'employee' && (
          <Select
            label="CBNV"
            required
            placeholder="— Chọn người —"
            error={errors.leader_user_id?.message}
            {...register('leader_user_id')}
          >
            {!currentIsListed && (
              <option value={bus.leader_user_id}>{bus.leader_name} (hiện tại)</option>
            )}
            {onBus.length > 0 && (
              <optgroup label="Đang đi xe này">
                {onBus.map((row) => (
                  <option key={`bus-${row.user_id}`} value={row.user_id}>
                    {row.full_name}
                    {row.team_name ? ` — ${row.team_name}` : ''}
                  </option>
                ))}
              </optgroup>
            )}
            <optgroup label="CBNV tham gia khác">
              {others.map((registration) => (
                <option key={registration.user.id} value={registration.user.id}>
                  {registration.user.full_name}
                  {registration.user.team_name ? ` — ${registration.user.team_name}` : ''}
                </option>
              ))}
            </optgroup>
          </Select>
        )}

        {mode === 'outsider' && (
          <div className="grid gap-3 sm:grid-cols-2">
            <Input label="Họ tên" required error={errors.leader_name?.message} {...register('leader_name')} />
            <Input
              label="Số điện thoại"
              type="tel"
              required
              error={errors.leader_phone?.message}
              {...register('leader_phone')}
            />
          </div>
        )}

        {mode === 'none' && (
          <Alert tone="warning">
            Xe không có Trưởng xe thì CBNV không biết gọi ai khi lỡ giờ tập trung.
          </Alert>
        )}
      </form>
    </Modal>
  )
}
