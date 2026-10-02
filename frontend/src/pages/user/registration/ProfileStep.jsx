import { useFormContext } from 'react-hook-form'
import { useAuth } from '../../../context/AuthContext'
import { missingFlightFields } from '../../../utils/schemas'
import Alert from '../../../components/common/Alert'
import AvatarUploader from '../../../components/profile/AvatarUploader'
import { DocumentFields, EmergencyFields, IdentityFields, PreferenceFields } from '../../../components/profile/ProfileFields'
import StepIntro from './StepIntro'

export default function ProfileStep() {
  const { user } = useAuth()
  const { register, watch, formState: { errors } } = useFormContext()
  const profile = watch('profile')
  const participating = watch('is_participating') === 'yes'
  const missing = missingFlightFields(profile)
  const profileErrors = errors.profile

  return (
    <div className="flex flex-col gap-4">
      <StepIntro
        step="1"
        eyebrow="Thông tin cá nhân"
        title="Kiểm tra thông tin của bạn"
        description="Thông tin này được dùng để đặt vé, bố trí phòng và liên hệ khi cần trong chuyến đi."
        mobileEyebrow="Thông tin của bạn"
        mobileTitle="Kiểm tra lại thông tin nhé."
        mobileDescription="Lấy từ hồ sơ công ty. BTC dùng để đặt vé, nên cần khớp giấy tờ."
      />

      <div className="flex flex-col gap-4">
      {missing.length > 0 ? (
        <Alert tone="warning" title="Còn thiếu thông tin để xuất vé máy bay">
          Thiếu: <strong>{missing.join(', ')}</strong>. Bạn cần điền đủ nếu tham gia chương trình.
        </Alert>
      ) : (
        <Alert tone="info">Thông tin lấy từ hồ sơ cá nhân. Kiểm tra lại và sửa nếu có gì chưa đúng.</Alert>
      )}

      <Section title="Ảnh đại diện" description="Dùng trong danh sách xe, sơ đồ Gala và thẻ tên">
        <AvatarUploader user={user} />
      </Section>

      <Section title="Thông tin cơ bản">
        <div className="mb-3 grid gap-2 rounded-lg bg-canvas-soft p-2.5 sm:grid-cols-3">
          <ReadOnly label="Họ tên" value={user.full_name} />
          <ReadOnly label="Mã nhân viên" value={user.employee_code} />
          <ReadOnly label="Email công ty" value={user.email} />
        </div>
        <IdentityFields register={register} errors={profileErrors} prefix="profile." required={participating} />
      </Section>

      <Section title="Giấy tờ đi máy bay" description="Phải khớp giấy tờ bạn mang theo khi bay">
        <DocumentFields register={register} errors={profileErrors} prefix="profile." required={participating} />
      </Section>

      <Section title="Áo, ăn uống và sức khoẻ">
        <PreferenceFields register={register} errors={profileErrors} prefix="profile." healthNote={profile?.health_note} />
      </Section>

      <Section title="Liên hệ khi cần" description="BTC gọi người này nếu có sự cố trong chuyến đi">
        <EmergencyFields register={register} errors={profileErrors} prefix="profile." />
      </Section>
      </div>
    </div>
  )
}

function Section({ title, description, children }) {
  return (
    <section className="rounded-xl border border-hairline bg-surface p-3.5 shadow-soft">
      <p className="text-body-sm font-semibold text-ink">{title}</p>
      {description && <p className="mt-0.5 text-caption text-ink-muted">{description}</p>}
      <div className="mt-3">{children}</div>
    </section>
  )
}

function ReadOnly({ label, value }) {
  return <div className="min-w-0"><p className="text-eyebrow tracking-wide text-ink-muted uppercase">{label}</p><p className="mt-0.5 truncate text-body-sm font-semibold text-ink">{value || '—'}</p></div>
}
