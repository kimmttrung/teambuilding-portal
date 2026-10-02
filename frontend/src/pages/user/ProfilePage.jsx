import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { ArrowLeft, KeyRound, Save, TriangleAlert, X } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../context/ToastContext'
import { useChangePassword, useUpdateProfile } from '../../hooks/useProfile'
import { buildProfilePatch, changePasswordSchema, missingFlightFields, profileSchema } from '../../utils/schemas'
import Button from '../../components/common/Button'
import Input from '../../components/common/Input'
import Alert from '../../components/common/Alert'
import AvatarUploader from '../../components/profile/AvatarUploader'
import { DocumentFields, EmergencyFields, IdentityFields, PreferenceFields, profileDefaults } from '../../components/profile/ProfileFields'
import '../../components/profile/F1Surface.css'

export default function ProfilePage() {
  const { user } = useAuth()
  const toast = useToast()
  const { mutateAsync: updateProfile, isPending } = useUpdateProfile()
  const [editingIdentity, setEditingIdentity] = useState(false)
  const { register, handleSubmit, reset, watch, formState: { errors, isDirty } } = useForm({
    resolver: zodResolver(profileSchema), defaultValues: profileDefaults(user), mode: 'onTouched',
  })
  useEffect(() => { reset(profileDefaults(user)) }, [user, reset])
  const values = watch()
  const missing = missingFlightFields(values)
  const missingDocuments = [...missing, ...(!values.id_card_issue_date ? ['ngày cấp CCCD / hộ chiếu'] : [])]
  const ticketName = user.full_name.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D').toUpperCase()

  async function onSubmit(submittedValues) {
    const patch = buildProfilePatch(submittedValues, user)
    if (!Object.keys(patch).length) { toast.info('Không có thay đổi nào để lưu.'); return }
    try { await updateProfile(patch); toast.success('Đã lưu hồ sơ.') }
    catch (error) { toast.error(error.message) }
  }

  return (
    <div className="f1-surface f1-profile">
      <div className="mb-6 flex items-center justify-between md:hidden">
        <Link to="/my-journey" className="flex items-center gap-3 text-[15px] font-bold"><ArrowLeft className="size-[18px]" />Hồ sơ & giấy tờ</Link>
        <span className="text-xs text-ink-faint" aria-live="polite">{isPending ? 'Đang lưu…' : isDirty ? 'Chưa lưu' : 'Đã lưu'}</span>
      </div>
      <header className="mb-[22px] flex items-center gap-4">
        <AvatarUploader user={user} compact className="shrink-0" />
        <div className="min-w-0 flex-1">
          <div className="hidden md:block">
            <h1 className="text-[32px] leading-[40px] font-bold tracking-[-0.7px]">{user.full_name}</h1>
            <p className="mt-1 text-[15px] text-ink-muted">{[user.team ? `Team ${user.team.name}` : null, user.employee_code, user.email].filter(Boolean).join(' · ')}</p>
          </div>
          <p className="text-[13px] leading-[19px] text-ink-muted md:hidden">Ảnh dùng cho danh sách xe và sơ đồ Gala.</p>
        </div>
        <span className="hidden text-[13px] text-ink-faint md:block" aria-live="polite">{isPending ? 'Đang lưu…' : isDirty ? 'Có thay đổi chưa lưu' : 'Đã lưu'}</span>
      </header>

      {user.must_change_password && <Alert tone="warning" title="Bạn đang dùng mật khẩu do BTC cấp" className="mb-4">Bạn cần đổi mật khẩu bên dưới trước khi sử dụng các tính năng khác.</Alert>}
      {missingDocuments.length > 0 && <div className="f1-profile-warning flex items-start gap-2.5 text-[14px] leading-5" role="status">
        <TriangleAlert className="mt-0.5 size-[18px] shrink-0" aria-hidden="true" />
        <p>Còn thiếu <strong>{missingDocuments.join(', ')}</strong> — BTC cần để kiểm tra giấy tờ và xuất vé.</p>
      </div>}

      <form id="profile-form" onSubmit={handleSubmit(onSubmit, () => setEditingIdentity(true))} noValidate>
        <div className="f1-profile-grid">
          <section className="f1-panel">
            <h2 className="f1-panel-title">Giấy tờ đi máy bay</h2>
            <DocumentFields register={register} errors={errors} figma required documentType={values.id_card_type} missingIssueDate={!values.id_card_issue_date} />
            <p className="f1-profile-ticket-name mt-4 text-xs leading-[18px] text-ink-faint">Tên trên vé: {ticketName} — phải khớp giấy tờ bạn mang.</p>
          </section>
          <section className="f1-panel">
            <h2 className="f1-panel-title">Áo, ăn uống, sức khoẻ</h2>
            <PreferenceFields register={register} errors={errors} healthNote={values.health_note} figma />
          </section>
          <section className="f1-panel">
            <h2 className="f1-panel-title">Liên hệ khi cần</h2>
            <EmergencyFields register={register} errors={errors} figma />
          </section>
          <section className="f1-panel hidden md:block">
            <h2 className="f1-panel-title mb-1">Không đi được nữa?</h2>
            <p className="text-[14px] leading-[21px] text-ink-muted">Việc huỷ tham gia và phí áp dụng theo trạng thái kỳ và quy định của BTC.</p>
            <Link to="/register-event" className="mt-4 inline-flex min-h-8 items-center gap-2 rounded-md border border-hairline px-3 text-[14px] text-[#a8231a]">
              <X className="size-4" />Gửi yêu cầu huỷ tham gia
            </Link>
          </section>
        </div>
        {/* Các trường hiện có vẫn truy cập được, nhưng không lấn vào bố cục giấy tờ của Figma. */}
        <div className="mt-6">
          <button type="button" className="text-[13px] font-medium text-ink-muted hover:text-primary" aria-expanded={editingIdentity} onClick={() => setEditingIdentity((value) => !value)}>
            {editingIdentity ? 'Ẩn thông tin cơ bản' : 'Chỉnh sửa thông tin cơ bản'}
          </button>
          {editingIdentity && <section className="f1-panel mt-3"><h2 className="f1-panel-title">Thông tin cơ bản</h2><IdentityFields register={register} errors={errors} /></section>}
        </div>
        {isDirty && <div className="sticky bottom-20 z-10 mt-4 flex items-center justify-end gap-3 rounded-lg border border-hairline bg-surface p-3 shadow-soft md:bottom-4">
          <Button variant="secondary" type="button" onClick={() => reset(profileDefaults(user))}>Bỏ thay đổi</Button>
          <Button type="submit" icon={Save} loading={isPending}>Lưu hồ sơ</Button>
        </div>}
      </form>
      <ChangePasswordCard />
    </div>
  )
}

function ChangePasswordCard() {
  const toast = useToast()
  const { user } = useAuth()
  const required = user.must_change_password
  const [open, setOpen] = useState(required)
  const { mutateAsync: changePassword, isPending } = useChangePassword()
  const { register, handleSubmit, reset, formState: { errors } } = useForm({
    resolver: zodResolver(changePasswordSchema), defaultValues: { current_password: '', new_password: '', confirm_password: '' },
  })
  async function onSubmit(values) {
    try { await changePassword(values); reset(); setOpen(false); toast.success('Đã đổi mật khẩu. Các thiết bị khác đã bị đăng xuất.') }
    catch (error) { toast.error(error.message) }
  }
  return (
    <section className="mt-4">
      {!open ? <button type="button" onClick={() => setOpen(true)} className="inline-flex items-center gap-2 text-[13px] font-medium text-ink-muted hover:text-primary"><KeyRound className="size-4" />Đổi mật khẩu</button> :
        <div className="f1-panel max-w-[536px]">
          <h2 className="f1-panel-title">Đổi mật khẩu</h2>
          <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
            <Input label="Mật khẩu hiện tại" type="password" autoComplete="current-password" required error={errors.current_password?.message} {...register('current_password')} />
            <Input label="Mật khẩu mới" type="password" autoComplete="new-password" required hint="Tối thiểu 8 ký tự, có cả chữ và số" error={errors.new_password?.message} {...register('new_password')} />
            <Input label="Nhập lại mật khẩu mới" type="password" autoComplete="new-password" required error={errors.confirm_password?.message} {...register('confirm_password')} />
            <div className="flex gap-2"><Button type="submit" icon={KeyRound} loading={isPending}>Đổi mật khẩu</Button>
              {!required && <Button type="button" variant="ghost" onClick={() => { reset(); setOpen(false) }}>Huỷ</Button>}
            </div>
          </form>
        </div>}
    </section>
  )
}
