import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Save } from 'lucide-react'
import { useUpdateUser } from '../../../hooks/useUsers'
import { useToast } from '../../../context/ToastContext'
import { adminUserSchema } from '../../../utils/schemas'
import Button from '../../../components/common/Button'
import Input from '../../../components/common/Input'
import Select from '../../../components/common/Select'
import {
  DocumentFields,
  EmergencyFields,
  IdentityFields,
  PreferenceFields,
  profileDefaults,
} from '../../../components/profile/ProfileFields'

const ID_FIELDS = ['team_id', 'department_id', 'work_location_id']

/**
 * BTC sửa hồ sơ một CBNV. Phần cá nhân dùng lại đúng các ô nhập của trang /profile để hai
 * nơi không lệch nhãn hay luật kiểm tra. Chỉ gửi những trường thực sự đổi.
 */
export default function UserProfileForm({ user, options, readOnly = false }) {
  const toast = useToast()
  const { mutateAsync: save, isPending } = useUpdateUser()

  const {
    register,
    handleSubmit,
    reset,
    watch,
    formState: { errors, isDirty },
  } = useForm({
    resolver: zodResolver(adminUserSchema),
    defaultValues: formDefaults(user),
    mode: 'onTouched',
  })

  async function onSubmit(values) {
    const patch = buildPatch(values, user)
    if (Object.keys(patch).length === 0) {
      toast.info('Không có thay đổi nào để lưu.')
      return
    }
    try {
      const updated = await save({ userId: user.id, payload: patch })
      reset(formDefaults(updated))
      toast.success(`Đã lưu hồ sơ ${updated.full_name}.`)
    } catch (saveError) {
      toast.error(saveError.message)
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate>
      <fieldset disabled={readOnly || isPending} className="flex flex-col gap-5">
        <Section title="Công việc" description="Chỉ BTC sửa được. Đổi email là đổi tên đăng nhập của người này.">
          <div className="grid gap-3.5 sm:grid-cols-2">
            <Input label="Mã nhân viên" error={errors.employee_code?.message} {...register('employee_code')} />
            <Input label="Họ tên" required error={errors.full_name?.message} {...register('full_name')} />
            <Input label="Email công ty" type="email" required error={errors.email?.message} {...register('email')} />
            <Input label="Chức danh" error={errors.job_title?.message} {...register('job_title')} />
            <Select
              label="Team"
              placeholder="— Chưa gán team —"
              options={(options?.teams ?? []).map((team) => ({ value: String(team.id), label: team.name }))}
              {...register('team_id')}
            />
            <Select
              label="Phòng ban"
              placeholder="— Chưa gán —"
              options={(options?.departments ?? []).map((item) => ({ value: String(item.id), label: item.name }))}
              {...register('department_id')}
            />
            <Select
              label="Nơi làm việc"
              placeholder="— Chưa gán —"
              options={(options?.work_locations ?? []).map((item) => ({ value: String(item.id), label: item.name }))}
              {...register('work_location_id')}
            />
            <Input label="Ngày vào làm" type="date" error={errors.join_date?.message} {...register('join_date')} />
          </div>
        </Section>

        <Section title="Thông tin cá nhân">
          <IdentityFields register={register} errors={errors} />
        </Section>
        <Section title="Giấy tờ đi máy bay">
          <DocumentFields register={register} errors={errors} />
        </Section>
        <Section title="Áo, ăn uống và sức khoẻ">
          <PreferenceFields register={register} errors={errors} healthNote={watch('health_note')} />
        </Section>
        <Section title="Liên hệ khi cần">
          <EmergencyFields register={register} errors={errors} />
        </Section>
      </fieldset>

      {!readOnly && (
        <div className="sticky bottom-0 mt-4 flex items-center justify-between gap-3 border-t border-slate-100 bg-white/95 pt-3 backdrop-blur">
          <p className="text-xs text-slate-500">{isDirty ? 'Có thay đổi chưa lưu.' : 'Chưa có thay đổi.'}</p>
          <Button type="submit" size="sm" icon={Save} loading={isPending} disabled={!isDirty}>
            Lưu hồ sơ
          </Button>
        </div>
      )}
    </form>
  )
}

function Section({ title, description, children }) {
  return (
    <section>
      <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
      {description && <p className="mt-0.5 text-xs text-slate-500">{description}</p>}
      <div className="mt-2.5">{children}</div>
    </section>
  )
}

function formDefaults(user) {
  return {
    ...profileDefaults(user),
    employee_code: user.employee_code ?? '',
    full_name: user.full_name ?? '',
    email: user.email ?? '',
    team_id: user.team_id ? String(user.team_id) : '',
    department_id: user.department_id ? String(user.department_id) : '',
    work_location_id: user.work_location_id ? String(user.work_location_id) : '',
    job_title: user.job_title ?? '',
    join_date: user.join_date ?? '',
  }
}

function buildPatch(values, user) {
  const patch = {}
  for (const [field, raw] of Object.entries(values)) {
    let value = typeof raw === 'string' ? raw.trim() || null : (raw ?? null)
    if (ID_FIELDS.includes(field)) value = value ? Number(value) : null
    if (value !== (user[field] ?? null)) patch[field] = value
  }
  return patch
}
