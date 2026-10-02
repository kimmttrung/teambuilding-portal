import { useState } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Save } from 'lucide-react'
import { useBusAssignments, useSetBusLeader } from '../../../hooks/useBuses'
import { useUsers } from '../../../hooks/useUsers'
import { useToast } from '../../../context/ToastContext'
import { leaderSchema } from '../../../utils/schemas'
import { BUS_LABELS, BUS_LEADER_MODES } from '../../../utils/constants'
import Alert from '../../../components/common/Alert'
import Button from '../../../components/common/Button'
import Input from '../../../components/common/Input'
import Modal from '../../../components/common/Modal'
import SearchBox from '../../../components/common/SearchBox'
import Select from '../../../components/common/Select'
import Spinner from '../../../components/common/Spinner'

/** CBNV đang hoạt động, kể cả người chưa đăng ký; ưu tiên người trên chính xe. */
export default function LeaderDialog({ bus, onClose }) {
  const toast = useToast()
  const save = useSetBusLeader()
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState(
    bus.leader_user_id
      ? { id: bus.leader_user_id, full_name: bus.leader_name }
      : null,
  )
  const {
    register,
    handleSubmit,
    control,
    setError,
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
  const mode = useWatch({ control, name: 'mode' })
  const users = useUsers(
    { is_active: true, q: search || undefined, page, page_size: 50 },
    { enabled: mode === 'employee' },
  )
  const passengers = useBusAssignments(
    { bus_id: bus.id, page_size: 200 },
    { enabled: mode === 'employee' },
  )
  const riders = passengers.data?.items ?? []
  const onBusIds = new Set(riders.map((row) => row.user_id))
  const others = (users.data?.items ?? []).filter(
    (user) => !onBusIds.has(user.id),
  )
  const selectedMissing =
    selected &&
    !onBusIds.has(selected.id) &&
    !others.some((user) => user.id === selected.id)

  async function submit(values) {
    const payload =
      values.mode === 'employee'
        ? { leader_user_id: Number(values.leader_user_id) }
        : values.mode === 'outsider'
          ? {
              leader_name: values.leader_name,
              leader_phone: values.leader_phone,
            }
          : {}
    try {
      await save.mutateAsync({ busId: bus.id, payload })
      toast.success(`Đã cập nhật Trưởng xe ${bus.bus_code}.`)
      onClose()
    } catch (error) {
      setError('root', { message: error.message })
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={`Trưởng xe ${bus.bus_code}`}
      description="Tài khoản được chỉ định chỉ xem hành khách xe mình sau công bố."
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            {BUS_LABELS.cancel}
          </Button>
          <Button
            type="submit"
            form="leader-form"
            icon={Save}
            loading={save.isPending}
          >
            {BUS_LABELS.save}
          </Button>
        </div>
      }
    >
      {mode === 'employee' && (
        <div className="mb-4 flex flex-col gap-3">
          <SearchBox
            label={BUS_LABELS.searchUsers}
            placeholder="Tên, email, mã nhân viên"
            onSearch={(value) => {
              setSearch(value)
              setPage(1)
            }}
          />
          {users.isLoading && <Spinner label="Đang tải CBNV…" />}
          {users.error && (
            <Alert tone="error">
              {users.error.message}
              <Button variant="secondary" onClick={() => users.refetch()}>
                {BUS_LABELS.retry}
              </Button>
            </Alert>
          )}
          {users.data && (
            <div className="flex items-center justify-between gap-2 text-caption text-ink-muted">
              <span>
                {users.data.total} tài khoản · Trang {page}
              </span>
              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  className="min-h-11"
                  disabled={page <= 1 || users.isFetching}
                  onClick={() => setPage(page - 1)}
                >
                  {BUS_LABELS.previous}
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  className="min-h-11"
                  disabled={page * 50 >= users.data.total || users.isFetching}
                  onClick={() => setPage(page + 1)}
                >
                  {BUS_LABELS.next}
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
      <form
        id="leader-form"
        onSubmit={handleSubmit(submit)}
        className="flex flex-col gap-4"
        noValidate
      >
        {errors.root && <Alert tone="error">{errors.root.message}</Alert>}
        <fieldset className="grid gap-2 sm:grid-cols-3">
          <legend className="sr-only">Loại Trưởng xe</legend>
          {BUS_LEADER_MODES.map((item) => (
            <label
              key={item.value}
              className={`flex min-h-11 cursor-pointer items-center gap-2 rounded-md border p-3 text-caption ${mode === item.value ? 'border-primary bg-primary/5 text-primary' : 'border-hairline text-ink-muted'}`}
            >
              <input
                type="radio"
                value={item.value}
                className="accent-primary"
                {...register('mode')}
              />
              {item.label}
            </label>
          ))}
        </fieldset>
        {mode === 'employee' && (
          <Select
            label={BUS_LABELS.employee}
            required
            placeholder="— Chọn người —"
            error={errors.leader_user_id?.message}
            {...register('leader_user_id', {
              onChange: (event) => {
                const id = Number(event.target.value)
                setSelected(
                  others.find((user) => user.id === id) ??
                    (() => {
                      const row = riders.find((rider) => rider.user_id === id)
                      return row ? { id, full_name: row.full_name } : null
                    })(),
                )
              },
            })}
          >
            {selectedMissing && (
              <option value={selected.id}>
                {selected.full_name} (đã chọn)
              </option>
            )}
            {riders.length > 0 && (
              <optgroup label="Đang đi xe này">
                {riders.map((row) => (
                  <option key={row.user_id} value={row.user_id}>
                    {row.full_name} · {row.team_name ?? 'Chưa có team'}
                  </option>
                ))}
              </optgroup>
            )}
            <optgroup label="Tài khoản đang hoạt động">
              {others.map((user) => (
                <option key={user.id} value={user.id}>
                  {user.full_name} · {user.employee_code}
                </option>
              ))}
            </optgroup>
          </Select>
        )}
        {mode === 'outsider' && (
          <>
            <Alert tone="info">
              Người ngoài nhận thông tin qua BTC; không có tài khoản để mở danh
              sách hành khách.
            </Alert>
            <div className="grid gap-3 sm:grid-cols-2">
              <Input
                label={BUS_LABELS.fullName}
                required
                error={errors.leader_name?.message}
                {...register('leader_name')}
              />
              <Input
                label={BUS_LABELS.phone}
                type="tel"
                required
                error={errors.leader_phone?.message}
                {...register('leader_phone')}
              />
            </div>
          </>
        )}
        {mode === 'none' && (
          <Alert tone="warning">
            Xe sẽ không có Trưởng xe. Hãy chỉ định lại trước chuyến đi.
          </Alert>
        )}
      </form>
    </Modal>
  )
}
