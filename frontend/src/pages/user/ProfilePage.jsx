import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Check, ClipboardList, KeyRound, Save, ShieldCheck, X } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../context/ToastContext'
import { useChangePassword, useUpdateProfile } from '../../hooks/useProfile'
import { useRegistrationFormOptions } from '../../hooks/useRegistration'
import { GENDER_LABELS, ROLE_LABELS } from '../../utils/constants'
import { formatDate } from '../../utils/format'
import {
  buildProfilePatch,
  changePasswordSchema,
  FLIGHT_REQUIRED_FIELDS,
  missingFlightFields,
  profileSchema,
} from '../../utils/schemas'
import Alert from '../../components/common/Alert'
import Badge from '../../components/common/Badge'
import Button from '../../components/common/Button'
import Card from '../../components/common/Card'
import Input from '../../components/common/Input'
import PageHeader from '../../components/common/PageHeader'
import AvatarUploader from '../../components/profile/AvatarUploader'
import {
  DocumentFields,
  EmergencyFields,
  IdentityFields,
  PreferenceFields,
  profileDefaults,
} from '../../components/profile/ProfileFields'

/**
 * Hồ sơ cá nhân.
 *
 * Chỉ những trường CBNV được tự sửa (UserProfileUpdate ở backend). Họ tên, email công ty,
 * team, phòng ban là việc của BTC — hiện ở đây dạng chỉ đọc để CBNV biết mà báo khi sai.
 */
export default function ProfilePage() {
  const { user } = useAuth()
  const toast = useToast()
  const { data: options } = useRegistrationFormOptions()
  const { mutateAsync: updateProfile, isPending } = useUpdateProfile()

  const {
    register,
    handleSubmit,
    reset,
    watch,
    formState: { errors, isDirty },
  } = useForm({
    resolver: zodResolver(profileSchema),
    defaultValues: profileDefaults(user),
    mode: 'onTouched',
  })

  // Ảnh đại diện và đăng ký (profile_patch) cũng đổi hồ sơ — nạp lại form khi user đổi.
  useEffect(() => {
    reset(profileDefaults(user))
  }, [user, reset])

  const values = watch()
  const missing = missingFlightFields(values)

  async function onSubmit(submittedValues) {
    const patch = buildProfilePatch(submittedValues, user)
    if (Object.keys(patch).length === 0) {
      toast.info('Không có thay đổi nào để lưu.')
      return
    }

    try {
      await updateProfile(patch)
      toast.success('Đã lưu hồ sơ.')
    } catch (error) {
      toast.error(error.message)
    }
  }

  return (
    <>
      <PageHeader
        title="Hồ sơ cá nhân"
        description="Thông tin BTC dùng để xuất vé máy bay, bố trí phòng và liên hệ khi cần"
      />

      <div className="flex flex-col gap-4">
        {user.must_change_password && (
          <Alert tone="warning" title="Bạn đang dùng mật khẩu do BTC cấp">
            Hãy đổi mật khẩu ở cột bên phải để bảo vệ tài khoản.
          </Alert>
        )}

        <IdentityCard user={user} options={options} missing={missing} />

        <div className="grid gap-4 xl:grid-cols-12">
          <form
            onSubmit={handleSubmit(onSubmit)}
            className="flex flex-col gap-4 xl:col-span-8"
            noValidate
          >
            <Card title="Thông tin cơ bản">
              <IdentityFields register={register} errors={errors} />
            </Card>

            <Card
              title="Giấy tờ đi máy bay"
              description="Phải khớp giấy tờ bạn mang theo khi làm thủ tục bay"
            >
              <DocumentFields register={register} errors={errors} />
            </Card>

            <Card title="Áo, ăn uống và sức khoẻ">
              <PreferenceFields
                register={register}
                errors={errors}
                healthNote={values.health_note}
              />
            </Card>

            <Card title="Liên hệ khi cần" description="BTC gọi người này nếu có sự cố trong chuyến đi">
              <EmergencyFields register={register} errors={errors} />
            </Card>

            {/* Nút lưu dính đáy: form dài, cuộn lên xuống tìm nút rất mệt.
                bottom-20 để không bị thanh điều hướng dưới của mobile che. */}
            <div className="sticky bottom-20 z-10 flex items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white/95 px-4 py-3 backdrop-blur md:bottom-4">
              <p className="text-xs text-slate-500">
                {isDirty ? 'Có thay đổi chưa lưu.' : 'Mọi thay đổi đã được lưu.'}
              </p>
              <Button type="submit" icon={Save} loading={isPending} disabled={!isDirty}>
                Lưu hồ sơ
              </Button>
            </div>
          </form>

          <aside className="flex flex-col gap-4 xl:col-span-4">
            <FlightReadyCard values={values} />
            <ChangePasswordCard />
          </aside>
        </div>
      </div>
    </>
  )
}

/** Thẻ đầu trang: ảnh, tên và những thông tin do BTC quản lý. */
function IdentityCard({ user, options, missing }) {
  const location = options?.work_locations?.find((item) => item.id === user.work_location_id)
  const department = options?.departments?.find((item) => item.id === user.department_id)

  return (
    <Card>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
        <AvatarUploader user={user} className="shrink-0" />

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-bold text-slate-900">{user.full_name}</h2>
            <Badge tone="slate">{ROLE_LABELS[user.role] ?? user.role}</Badge>
            {missing.length === 0 ? (
              <Badge tone="emerald">Đủ giấy tờ bay</Badge>
            ) : (
              <Badge tone="amber">Thiếu {missing.length} thông tin để bay</Badge>
            )}
            {user.gender && <Badge tone="blue">{GENDER_LABELS[user.gender] ?? user.gender}</Badge>}
          </div>

          <dl className="mt-3 grid grid-cols-2 gap-x-5 gap-y-3 sm:grid-cols-3 2xl:grid-cols-6">
            <ReadOnlyField label="Mã nhân viên" value={user.employee_code} />
            <ReadOnlyField label="Email công ty" value={user.email} />
            <ReadOnlyField label="Team" value={user.team?.name} />
            <ReadOnlyField label="Phòng ban" value={department?.name} />
            <ReadOnlyField label="Nơi làm việc" value={location?.name} />
            <ReadOnlyField
              label="Ngày vào công ty"
              value={user.join_date ? formatDate(user.join_date) : null}
            />
          </dl>

          <p className="mt-3 text-xs text-slate-400">
            Họ tên, email công ty, team và phòng ban do Ban tổ chức quản lý. Nếu sai, liên hệ BTC.
          </p>
        </div>
      </div>
    </Card>
  )
}

function ReadOnlyField({ label, value }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs tracking-wide text-slate-400 uppercase">{label}</dt>
      <dd className="mt-0.5 truncate text-sm font-medium text-slate-900">{value || '—'}</dd>
    </div>
  )
}

/** Checklist 4 trường bắt buộc để BTC xuất được vé — cập nhật ngay khi đang gõ. */
function FlightReadyCard({ values }) {
  const done = FLIGHT_REQUIRED_FIELDS.filter(({ name }) => values[name])

  return (
    <Card
      title="Điều kiện xuất vé máy bay"
      description={`Đã khai ${done.length}/${FLIGHT_REQUIRED_FIELDS.length} thông tin bắt buộc`}
    >
      <ul className="flex flex-col gap-2">
        {FLIGHT_REQUIRED_FIELDS.map(({ name, label }) => {
          const filled = Boolean(values[name])
          return (
            <li key={name} className="flex items-center gap-2.5 text-sm">
              <span
                className={`grid size-5 shrink-0 place-items-center rounded-full text-white ${
                  filled ? 'bg-emerald-500' : 'bg-slate-300'
                }`}
              >
                {filled ? (
                  <Check className="size-3" strokeWidth={3} aria-hidden="true" />
                ) : (
                  <X className="size-3" strokeWidth={3} aria-hidden="true" />
                )}
              </span>
              <span className={filled ? 'text-slate-700' : 'font-medium text-slate-900'}>
                {label}
              </span>
            </li>
          )
        })}
      </ul>

      {done.length < FLIGHT_REQUIRED_FIELDS.length ? (
        <Alert tone="warning" className="mt-3.5">
          Thiếu thông tin này thì bạn không gửi được đăng ký tham gia, và BTC không đặt được vé.
        </Alert>
      ) : (
        <Link
          to="/register-event"
          className="mt-3.5 inline-flex items-center gap-1.5 text-sm font-medium text-brand-700 hover:underline"
        >
          <ClipboardList className="size-4" aria-hidden="true" />
          Sang trang đăng ký Team Building
        </Link>
      )}
    </Card>
  )
}

/** Đổi mật khẩu. Backend đăng xuất mọi thiết bị khác, phiên hiện tại giữ nguyên. */
function ChangePasswordCard() {
  const toast = useToast()
  const [open, setOpen] = useState(false)
  const { mutateAsync: changePassword, isPending } = useChangePassword()

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(changePasswordSchema),
    defaultValues: { current_password: '', new_password: '', confirm_password: '' },
  })

  async function onSubmit(values) {
    try {
      await changePassword(values)
      reset()
      setOpen(false)
      toast.success('Đã đổi mật khẩu. Các thiết bị khác đã bị đăng xuất.')
    } catch (error) {
      toast.error(error.message)
    }
  }

  return (
    <Card
      title="Mật khẩu"
      description="Đổi mật khẩu sẽ đăng xuất các thiết bị khác"
      action={
        !open && (
          <Button
            type="button"
            variant="secondary"
            size="sm"
            icon={KeyRound}
            onClick={() => setOpen(true)}
          >
            Đổi
          </Button>
        )
      }
    >
      {!open ? (
        <p className="flex items-start gap-2 text-sm text-slate-500">
          <ShieldCheck className="mt-0.5 size-4 shrink-0 text-slate-400" aria-hidden="true" />
          Mật khẩu tối thiểu 8 ký tự, có cả chữ và số.
        </p>
      ) : (
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-3.5" noValidate>
          <Input
            label="Mật khẩu hiện tại"
            type="password"
            autoComplete="current-password"
            required
            error={errors.current_password?.message}
            {...register('current_password')}
          />
          <Input
            label="Mật khẩu mới"
            type="password"
            autoComplete="new-password"
            required
            hint="Tối thiểu 8 ký tự, có cả chữ và số"
            error={errors.new_password?.message}
            {...register('new_password')}
          />
          <Input
            label="Nhập lại mật khẩu mới"
            type="password"
            autoComplete="new-password"
            required
            error={errors.confirm_password?.message}
            {...register('confirm_password')}
          />
          <div className="flex gap-2">
            <Button type="submit" icon={KeyRound} loading={isPending}>
              Đổi mật khẩu
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                reset()
                setOpen(false)
              }}
            >
              Huỷ
            </Button>
          </div>
        </form>
      )}
    </Card>
  )
}
