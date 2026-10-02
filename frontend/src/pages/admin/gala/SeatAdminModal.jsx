import { useForm, useWatch } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useGalaTeamMembers, useUpdateGalaSeat } from '../../../hooks/useGala'
import { useRegistrationFormOptions } from '../../../hooks/useRegistration'
import { useToast } from '../../../context/ToastContext'
import { GALA_SEAT_STATE_LABELS } from '../../../utils/constants'
import { galaSeatAdminSchema } from '../../../utils/schemas'
import Alert from '../../../components/common/Alert'
import Button from '../../../components/common/Button'
import Modal from '../../../components/common/Modal'
import Select from '../../../components/common/Select'
import Textarea from '../../../components/common/Textarea'

/** Can thiệp có lý do, kể cả nhả ghế đang giữ và ghế của người không có team. */
export default function SeatAdminModal({ seatId, tableId, view, onClose }) {
  const toast = useToast()
  const table = view.tables.find((item) => item.id === tableId)
  const seat = table?.seats.find((item) => item.id === seatId)
  const { data: options } = useRegistrationFormOptions()
  const { mutateAsync: update, isPending } = useUpdateGalaSeat()
  const {
    register,
    handleSubmit,
    control,
    setValue,
    setError,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(galaSeatAdminSchema),
    mode: 'onTouched',
    defaultValues: {
      action: 'assign',
      team_id: seat?.team_id == null ? '' : String(seat.team_id),
      registration_id: seat?.registration_id ? String(seat.registration_id) : '',
      reason: '',
    },
  })
  const action = useWatch({ control, name: 'action' })
  const teamId = useWatch({ control, name: 'team_id' })
  const reason = useWatch({ control, name: 'reason' })
  const {
    data: members = [],
    isLoading: membersLoading,
    error: membersError,
  } = useGalaTeamMembers(Number(teamId) || null, {
    enabled: action === 'assign' && Boolean(teamId),
  })
  if (!seat) return null
  const teams = (
    options?.teams ??
    view.draw.orders.map((order) => ({ id: order.team_id, name: order.team_name }))
  ).map((team) => ({ value: team.id, label: team.name }))
  async function submit(values) {
    let payload
    if (values.action === 'release') payload = { team_id: null }
    else if (values.action === 'lock') payload = { team_id: null, is_available: false }
    else if (values.action === 'unlock') payload = { is_available: true }
    else {
      payload = { team_id: Number(values.team_id) }
      if (values.registration_id) payload.registration_id = Number(values.registration_id)
      else if (
        seat.state === 'taken' &&
        seat.team_id === Number(values.team_id) &&
        seat.registration_id
      )
        payload.registration_id = null
    }
    try {
      await update({ seatId, payload: { ...payload, reason: values.reason } })
      toast.success('Đã cập nhật ghế.')
      onClose()
    } catch (err) {
      setError('root', { message: err.message })
    }
  }
  return (
    <Modal
      open
      title={`Ghế ${seat.seat_number} · Bàn ${table.table_code}`}
      description={`${GALA_SEAT_STATE_LABELS[seat.state]}${seat.team_name ? ` · ${seat.team_name}` : ''}${seat.occupant_name ? ` · ${seat.occupant_name}` : ''}`}
      onClose={onClose}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            Huỷ
          </Button>
          <Button
            type="submit"
            form="gala-seat-admin"
            loading={isPending}
            disabled={action === 'assign' && (!teamId || membersLoading || Boolean(membersError))}
          >
            Lưu thay đổi
          </Button>
        </div>
      }
    >
      <form id="gala-seat-admin" onSubmit={handleSubmit(submit)} noValidate className="space-y-4">
        {errors.root && <Alert tone="error">{errors.root.message}</Alert>}
        {!table.is_available && (
          <Alert tone="warning">Bàn đang khoá. Mở bàn trong Sửa bàn trước khi gán team.</Alert>
        )}
        <fieldset className="divide-y divide-hairline">
          <legend className="sr-only">Thao tác với ghế</legend>
          {[
            ['release', 'Nhả ghế', 'Ghế trở lại trống; bỏ người đang ngồi.'],
            ['lock', 'Đánh dấu không dùng', 'Ghế bị khoá, không thể chọn.'],
            ['unlock', 'Mở khoá ghế', 'Cho phép chọn lại ghế này.'],
            ['assign', 'Gán cho team', 'Chốt ghế cho team và chọn người ngồi.'],
          ].map(([value, label, hint]) => (
            <label key={value} className="flex min-h-16 cursor-pointer items-center gap-3 py-3">
              <input
                type="radio"
                value={value}
                {...register('action')}
                className="size-5 accent-primary"
              />
              <span>
                <span className="block text-body-md font-semibold text-ink">{label}</span>
                <span className="text-caption text-ink-muted">{hint}</span>
              </span>
            </label>
          ))}
        </fieldset>
        {action === 'assign' && (
          <>
            <Select
              label="Team sở hữu ghế"
              required
              placeholder="Chọn team"
              options={teams}
              error={errors.team_id?.message}
              {...register('team_id', {
                onChange: () => {
                  setValue('registration_id', '')
                },
              })}
            />
            {membersError && <Alert tone="error">{membersError.message}</Alert>}
            <Select
              label="Người ngồi"
              placeholder="Chưa gán người"
              disabled={!teamId || membersLoading}
              options={members.map((member) => ({
                value: member.registration_id,
                label: member.seat_id
                  ? `${member.full_name} · ${member.table_code} / ghế ${member.seat_number}`
                  : member.full_name,
              }))}
              {...register('registration_id')}
            />
          </>
        )}
        <Textarea
          label="Lý do"
          required
          rows={3}
          maxLength={500}
          counterValue={reason}
          hint="Tối thiểu 3 ký tự; lưu vào nhật ký thay đổi"
          error={errors.reason?.message}
          {...register('reason')}
        />
        {action === 'release' && (
          <Alert tone="warning">Ghế đang giữ hoặc đã xác nhận sẽ được trả về trống.</Alert>
        )}
      </form>
    </Modal>
  )
}
