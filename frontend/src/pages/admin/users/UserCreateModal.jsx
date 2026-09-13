import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { UserPlus } from 'lucide-react'
import { useCreateUser } from '../../../hooks/useUsers'
import { useToast } from '../../../context/ToastContext'
import { GENDER_LABELS, ROLE_LABELS, ROLES } from '../../../utils/constants'
import { userCreateSchema } from '../../../utils/schemas'
import Button from '../../../components/common/Button'
import Input from '../../../components/common/Input'
import Modal from '../../../components/common/Modal'
import Select from '../../../components/common/Select'
import TemporaryPasswordNotice from './TemporaryPasswordNotice'

const GENDER_OPTIONS = Object.entries(GENDER_LABELS).map(([value, label]) => ({ value, label }))

/**
 * Tạo một tài khoản CBNV. Hệ thống sinh mật khẩu tạm và hiện đúng một lần sau khi tạo.
 * Vai trò Ban tổ chức chỉ quản trị hệ thống chọn được (backend cũng chặn).
 */
export default function UserCreateModal({ options, canCreateOrganizers = false, onClose }) {
  const toast = useToast()
  const { mutateAsync: create, isPending } = useCreateUser()
  const [created, setCreated] = useState(null)

  const roleOptions = Object.entries(ROLE_LABELS)
    .filter(([value]) => canCreateOrganizers || value === ROLES.EMPLOYEE || value === ROLES.TEAM_LEADER)
    .map(([value, label]) => ({ value, label }))

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(userCreateSchema),
    mode: 'onTouched',
    defaultValues: {
      employee_code: '',
      full_name: '',
      email: '',
      role: ROLES.EMPLOYEE,
      gender: '',
      phone: '',
      team_id: '',
      department_id: '',
      work_location_id: '',
      job_title: '',
      join_date: '',
    },
  })

  async function onSubmit(values) {
    const payload = {
      employee_code: values.employee_code,
      full_name: values.full_name,
      email: values.email,
      role: values.role,
      gender: values.gender || null,
      phone: values.phone || null,
      team_id: values.team_id ? Number(values.team_id) : null,
      department_id: values.department_id ? Number(values.department_id) : null,
      work_location_id: values.work_location_id ? Number(values.work_location_id) : null,
      job_title: values.job_title || null,
      join_date: values.join_date || null,
    }
    try {
      const result = await create(payload)
      toast.success(`Đã tạo tài khoản ${result.user.full_name}.`)
      setCreated(result)
    } catch (createError) {
      toast.error(createError.message)
    }
  }

  if (created) {
    return (
      <Modal
        open
        onClose={onClose}
        title={`Đã tạo tài khoản ${created.user.full_name}`}
        description={[created.user.employee_code, created.user.email].filter(Boolean).join(' · ')}
        footer={
          <div className="flex justify-end">
            <Button size="sm" onClick={onClose}>
              Đã lưu mật khẩu, đóng
            </Button>
          </div>
        }
      >
        <TemporaryPasswordNotice password={created.temporary_password} email={created.user.email} />
      </Modal>
    )
  }

  return (
    <Modal
      open
      size="lg"
      onClose={onClose}
      title="Thêm CBNV"
      description="Hệ thống sinh mật khẩu tạm; người dùng phải đổi ở lần đăng nhập đầu"
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="sm" onClick={onClose}>
            Huỷ
          </Button>
          <Button type="submit" form="user-create-form" size="sm" icon={UserPlus} loading={isPending}>
            Tạo tài khoản
          </Button>
        </div>
      }
    >
      <form id="user-create-form" onSubmit={handleSubmit(onSubmit)} className="grid gap-3.5 sm:grid-cols-2" noValidate>
        <Input label="Mã nhân viên" required placeholder="NV0123" error={errors.employee_code?.message} {...register('employee_code')} />
        <Input label="Họ tên" required error={errors.full_name?.message} {...register('full_name')} />
        <Input
          label="Email công ty"
          type="email"
          required
          hint="Dùng làm tên đăng nhập"
          error={errors.email?.message}
          {...register('email')}
        />
        <Select label="Vai trò" required options={roleOptions} error={errors.role?.message} {...register('role')} />
        <Select label="Giới tính" placeholder="— Chưa khai —" options={GENDER_OPTIONS} error={errors.gender?.message} {...register('gender')} />
        <Input label="Số điện thoại" type="tel" error={errors.phone?.message} {...register('phone')} />
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
        <Input label="Chức danh" error={errors.job_title?.message} {...register('job_title')} />
        <Input label="Ngày vào làm" type="date" error={errors.join_date?.message} {...register('join_date')} />
      </form>
    </Modal>
  )
}
