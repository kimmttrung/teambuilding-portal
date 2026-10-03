import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { ChevronDown, KeyRound, Save, TriangleAlert } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../context/ToastContext'
import { useUpdateProfile } from '../../hooks/useProfile'
import { buildProfilePatch, missingProfileFields, selfProfileSchema } from '../../utils/schemas'
import Button from '../../components/common/Button'
import Card from '../../components/common/Card'
import PageHeader from '../../components/common/PageHeader'
import AvatarUploader from '../../components/profile/AvatarUploader'
import ChangePasswordForm from '../../components/profile/ChangePasswordForm'
import {
  DocumentFields,
  EmergencyFields,
  IdentityFields,
  PreferenceFields,
  profileDefaults,
} from '../../components/profile/ProfileFields'

/**
 * Hồ sơ cá nhân: một form, một nút lưu. Sáu trường BTC cần để xuất vé và xếp phòng là bắt buộc —
 * thiếu thì không lưu được (`selfProfileSchema`, backend cũng từ chối `PROFILE_REQUIRED_FIELDS`).
 * Đổi mật khẩu nằm ở thẻ riêng vì đi qua endpoint khác và không liên quan tới nút Lưu hồ sơ.
 */
export default function ProfilePage() {
  const { user } = useAuth()
  const toast = useToast()
  const location = useLocation()
  const navigate = useNavigate()
  const returnToRegistration = location.state?.returnToRegistration === true
  function continueRegistration() {
    navigate('/register-event', { state: { registrationDraft: location.state?.registrationDraft } })
  }
  const { mutateAsync: updateProfile, isPending } = useUpdateProfile()
  const {
    register,
    handleSubmit,
    reset,
    watch,
    formState: { errors, isDirty },
  } = useForm({
    resolver: zodResolver(selfProfileSchema),
    defaultValues: profileDefaults(user),
    mode: 'onTouched',
  })

  // Lưu xong hoặc đổi ảnh thì `user` đổi: nạp lại để "có thay đổi chưa lưu" về đúng trạng thái.
  useEffect(() => {
    reset(profileDefaults(user))
  }, [user, reset])

  const values = watch()
  const missing = missingProfileFields(values)
  // Tên in trên vé là họ tên không dấu, viết hoa — phải khớp giấy tờ mang theo.
  const ticketName = user.full_name
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .toUpperCase()

  async function onSubmit(submittedValues) {
    const patch = buildProfilePatch(submittedValues, user)
    if (!Object.keys(patch).length) {
      toast.info('Không có thay đổi nào để lưu.')
      return
    }
    try {
      await updateProfile(patch)
      toast.success('Đã lưu hồ sơ.')
      if (returnToRegistration) continueRegistration()
    } catch (error) {
      toast.error(error.message)
    }
  }

  function onInvalid() {
    const stillMissing = missingProfileFields(values)
    toast.error(
      stillMissing.length
        ? `Chưa lưu được. Còn thiếu: ${stillMissing.join(', ')}.`
        : 'Chưa lưu được. Kiểm tra lại những ô đang báo đỏ.',
    )
  }

  return (
    <>
      <PageHeader title="Hồ sơ của tôi" description="Thông tin BTC dùng để xuất vé máy bay, xếp phòng và liên lạc với bạn." />

      {returnToRegistration && (
        <div className="mb-4 rounded-xl border border-hairline bg-surface p-4 text-body-sm">
          <p>Điền đủ các trường có dấu * và lưu hồ sơ để tiếp tục đăng ký.</p>
          <Button type="button" variant="secondary" className="mt-3" disabled={isDirty || missing.length > 0} onClick={continueRegistration}>Tiếp tục đăng ký</Button>
          <Link to="/register-event" state={{ registrationDraft: location.state?.registrationDraft }} className="ml-3 text-primary underline">Quay lại đăng ký</Link>
        </div>
      )}
      <div className="flex flex-col gap-6">
        <Card>
          <div className="flex items-center gap-4">
            <AvatarUploader user={user} compact className="shrink-0" />
            <div className="min-w-0">
              <p className="truncate text-heading-3 text-ink">{user.full_name}</p>
              <p className="mt-0.5 truncate text-body-sm text-ink-muted">
                {[user.team ? `Team ${user.team.name}` : null, user.employee_code, user.email].filter(Boolean).join(' · ')}
              </p>
              <p className="mt-1 text-caption text-ink-faint">Ảnh dùng cho danh sách xe và sơ đồ Gala.</p>
            </div>
          </div>
        </Card>

        <form onSubmit={handleSubmit(onSubmit, onInvalid)} noValidate>
          <Card
            title="Hồ sơ cá nhân"
            description="Ô có dấu * là bắt buộc — thiếu thì chưa lưu được hồ sơ"
            bodyClassName="p-0"
          >
            {missing.length > 0 && (
              <div
                role="status"
                className="mx-4 mt-4 flex items-start gap-2.5 rounded-lg bg-amber-50 px-4 py-3 text-caption text-amber-900 sm:mx-6"
              >
                <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                <p>
                  Còn thiếu <strong>{missing.join(', ')}</strong>. BTC cần các thông tin này để xuất vé và xếp phòng.
                </p>
              </div>
            )}

            <fieldset disabled={isPending} className="divide-y divide-hairline">
              <Section title="Thông tin cá nhân">
                <IdentityFields register={register} errors={errors} required />
              </Section>
              <Section title="Giấy tờ đi máy bay" note={`Tên trên vé: ${ticketName} — phải khớp giấy tờ bạn mang.`}>
                <DocumentFields register={register} errors={errors} required requireIssueDate />
              </Section>
              <Section title="Áo, ăn uống, sức khoẻ">
                <PreferenceFields register={register} errors={errors} healthNote={values.health_note} />
              </Section>
              <Section title="Liên hệ khi cần">
                <EmergencyFields register={register} errors={errors} />
              </Section>
            </fieldset>

            {/* Nút lưu luôn trong tầm mắt: form dài, cuộn tới đâu cũng lưu được. */}
            <div className="sticky bottom-[72px] z-10 flex flex-wrap items-center justify-between gap-3 rounded-b-lg border-t border-hairline bg-surface px-4 py-3 sm:px-6 md:bottom-0">
              <p className="text-caption text-ink-muted" aria-live="polite">
                {isPending ? 'Đang lưu…' : isDirty ? 'Có thay đổi chưa lưu' : 'Chưa có thay đổi'}
              </p>
              <div className="flex gap-2">
                {isDirty && (
                  <Button type="button" variant="secondary" onClick={() => reset(profileDefaults(user))}>
                    Bỏ thay đổi
                  </Button>
                )}
                {/* Hồ sơ còn thiếu thì vẫn bấm được, để các ô thiếu báo đỏ ngay cả khi chưa sửa gì. */}
                <Button type="submit" icon={Save} loading={isPending} disabled={!isDirty && missing.length === 0}>
                  Lưu hồ sơ
                </Button>
              </div>
            </div>
          </Card>
        </form>

        <SecurityCard />

        <p className="text-caption text-ink-muted">
          Không đi được nữa?{' '}
          <Link to="/register-event" className="font-medium text-primary hover:underline">
            Xem đăng ký và gửi yêu cầu huỷ tham gia
          </Link>
        </p>
      </div>
    </>
  )
}

function Section({ title, note, children }) {
  return (
    <section className="px-4 py-5 sm:px-6">
      <h3 className="mb-3 text-body-sm font-semibold text-ink">{title}</h3>
      {children}
      {note && <p className="mt-3 text-caption text-ink-faint">{note}</p>}
    </section>
  )
}

/** Đổi mật khẩu: cùng một nút vừa mở vừa đóng, đóng thì form bị gỡ nên chữ đã gõ không còn. */
function SecurityCard() {
  const [open, setOpen] = useState(false)

  return (
    <Card
      title="Bảo mật"
      description="Đổi mật khẩu sẽ đăng xuất các thiết bị khác"
      action={
        <Button
          type="button"
          variant="secondary"
          size="sm"
          icon={open ? undefined : KeyRound}
          aria-expanded={open}
          aria-controls="change-password-panel"
          onClick={() => setOpen((value) => !value)}
        >
          {open ? 'Đóng' : 'Đổi mật khẩu'}
          <ChevronDown className={`size-4 transition-transform ${open ? 'rotate-180' : ''}`} aria-hidden="true" />
        </Button>
      }
      bodyClassName={open ? '' : 'hidden'}
    >
      {open && (
        <div id="change-password-panel" className="max-w-md">
          <ChangePasswordForm onDone={() => setOpen(false)} onCancel={() => setOpen(false)} />
        </div>
      )}
    </Card>
  )
}
