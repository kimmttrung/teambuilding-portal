import { useFormContext } from 'react-hook-form'
import { useAuth } from '../../../context/AuthContext'
import { missingFlightFields } from '../../../utils/schemas'
import Alert from '../../../components/common/Alert'
import Card from '../../../components/common/Card'
import AvatarUploader from '../../../components/profile/AvatarUploader'
import {
  DocumentFields,
  EmergencyFields,
  IdentityFields,
  PreferenceFields,
} from '../../../components/profile/ProfileFields'

/**
 * Bước 1 — xác nhận thông tin cá nhân.
 *
 * Dữ liệu đã auto-fill từ hồ sơ; CBNV chỉ sửa chỗ sai. Các trường BTC cần để xuất
 * vé máy bay được đánh dấu bắt buộc và nhắc ở đầu bước, nhưng chỉ chặn ở bước 2 khi
 * người dùng chọn tham gia — người không tham gia không cần khai giấy tờ.
 */
export default function ProfileStep() {
  const { user } = useAuth()
  const {
    register,
    watch,
    formState: { errors },
  } = useFormContext()

  const profile = watch('profile')
  const missing = missingFlightFields(profile)
  const profileErrors = errors.profile

  return (
    <div className="flex flex-col gap-4">
      {missing.length > 0 ? (
        <Alert tone="warning" title="Còn thiếu thông tin để xuất vé máy bay">
          <p>
            Thiếu: <strong>{missing.join(', ')}</strong>. BTC cần đúng các thông tin này để đặt vé
            và bố trí phòng, nên bạn phải điền đủ nếu tham gia chương trình.
          </p>
        </Alert>
      ) : (
        <Alert tone="info">
          Thông tin dưới đây lấy từ hồ sơ của bạn. Kiểm tra lại và sửa nếu có gì chưa đúng —
          chỉnh ở đây cũng là cập nhật hồ sơ cá nhân.
        </Alert>
      )}

      <Card title="Ảnh đại diện" description="Dùng trong danh sách xe, sơ đồ Gala và thẻ tên">
        <AvatarUploader user={user} />
      </Card>

      <Card title="Thông tin cơ bản">
        <div className="mb-3.5 grid gap-3.5 rounded-lg bg-slate-50 p-3 sm:grid-cols-3">
          <ReadOnly label="Họ tên" value={user.full_name} />
          <ReadOnly label="Mã nhân viên" value={user.employee_code} />
          <ReadOnly label="Email công ty" value={user.email} />
        </div>
        <p className="mb-3.5 text-xs text-slate-500">
          Họ tên, mã nhân viên, email công ty và team do BTC quản lý. Cần sửa thì liên hệ BTC.
        </p>
        <IdentityFields register={register} errors={profileErrors} prefix="profile." />
      </Card>

      <Card title="Giấy tờ đi máy bay" description="Phải khớp giấy tờ bạn mang theo khi bay">
        <DocumentFields register={register} errors={profileErrors} prefix="profile." />
      </Card>

      <Card title="Áo, ăn uống và sức khoẻ">
        <PreferenceFields
          register={register}
          errors={profileErrors}
          prefix="profile."
          healthNote={profile?.health_note}
        />
      </Card>

      <Card title="Liên hệ khi cần" description="BTC gọi người này nếu có sự cố trong chuyến đi">
        <EmergencyFields register={register} errors={profileErrors} prefix="profile." />
      </Card>
    </div>
  )
}

function ReadOnly({ label, value }) {
  return (
    <div className="min-w-0">
      <p className="text-xs tracking-wide text-slate-400 uppercase">{label}</p>
      <p className="mt-0.5 truncate text-sm font-medium text-slate-900">{value || '—'}</p>
    </div>
  )
}
