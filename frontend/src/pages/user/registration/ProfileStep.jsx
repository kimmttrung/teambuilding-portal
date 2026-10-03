import { useAuth } from '../../../context/AuthContext'
import { missingProfileFields, PROFILE_REQUIRED_FIELDS } from '../../../utils/schemas'
import { formatDate } from '../../../utils/format'
import { GENDER_LABELS, ID_CARD_TYPE_LABELS } from '../../../utils/constants'
import Alert from '../../../components/common/Alert'
import Button from '../../../components/common/Button'
import StepIntro from './StepIntro'

const REQUIRED = new Set(PROFILE_REQUIRED_FIELDS.map(({ name }) => name))

export default function ProfileStep({ onEditProfile }) {
  const { user } = useAuth()
  const missing = missingProfileFields(user)
  const fields = [
    ['full_name', 'Họ tên'], ['employee_code', 'Mã nhân viên'], ['email', 'Email công ty'],
    ['display_name', 'Tên gọi trong chương trình'], ['gender', 'Giới tính', GENDER_LABELS[user.gender]],
    ['date_of_birth', 'Ngày sinh', user.date_of_birth && formatDate(user.date_of_birth)],
    ['phone', 'Số điện thoại'], ['personal_email', 'Email cá nhân'], ['address', 'Địa chỉ hiện tại'],
  ]
  const documents = [
    ['id_card_type', 'Loại giấy tờ', ID_CARD_TYPE_LABELS[user.id_card_type]],
    ['id_card_number', 'Số CCCD / Hộ chiếu'],
    ['id_card_issue_date', 'Ngày cấp', user.id_card_issue_date && formatDate(user.id_card_issue_date)],
    ['id_card_issue_place', 'Nơi cấp'],
  ]
  function renderFields(items) {
    return <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{items.map(([name, label, display]) => (
      <div key={name} className="min-w-0">
        <dt className="text-caption text-ink-muted">{label}{REQUIRED.has(name) && <span className="ml-1 text-rose-600">*</span>}</dt>
        <dd className="mt-1 whitespace-pre-wrap break-words text-body-sm font-medium text-ink">{(display ?? user[name]) || '—'}</dd>
      </div>
    ))}</dl>
  }
  return (
    <div className="flex flex-col gap-4">
      <StepIntro step="1" eyebrow="Thông tin cá nhân" title="Kiểm tra thông tin của bạn"
        description="Thông tin lấy từ Hồ sơ, dùng để đặt vé, bố trí phòng và liên hệ trong chuyến đi."
        mobileEyebrow="Thông tin của bạn" mobileTitle="Kiểm tra lại thông tin nhé."
        mobileDescription="Thông tin cần khớp giấy tờ bạn mang theo." />
      <Alert tone={missing.length ? 'warning' : 'info'} title={missing.length ? 'Còn thiếu thông tin bắt buộc' : 'Thông tin từ hồ sơ cá nhân'}>
        {missing.length ? <>Thiếu: <strong>{missing.join(', ')}</strong>. Cần cập nhật Hồ sơ trước khi tiếp tục đăng ký tham gia. Nếu không tham gia, bạn có thể tiếp tục để gửi lựa chọn.</> : 'Cần thay đổi thông tin? Hãy cập nhật tại Hồ sơ rồi quay lại đăng ký.'}
        <div className="mt-3"><Button type="button" variant="secondary" onClick={onEditProfile}>Cập nhật hồ sơ</Button></div>
      </Alert>
      <Section title="Ảnh đại diện">
        {user.avatar_url ? <img src={user.avatar_url} alt={`Ảnh đại diện ${user.full_name}`} className="size-20 rounded-full object-cover" /> : <p className="text-body-sm text-ink-muted">Chưa có ảnh đại diện</p>}
      </Section>
      <Section title="Thông tin cơ bản">{renderFields(fields)}</Section>
      <Section title="Giấy tờ đi máy bay">{renderFields(documents)}</Section>
      <Section title="Áo, ăn uống và sức khoẻ">{renderFields([
        ['shirt_size', 'Size áo'], ['dietary_restriction', 'Ăn kiêng / dị ứng thực phẩm'], ['health_note', 'Tình trạng sức khoẻ cần lưu ý'],
      ])}</Section>
      <Section title="Liên hệ khi cần">{renderFields([
        ['emergency_contact_name', 'Người liên hệ khi cần'], ['emergency_contact_phone', 'Số điện thoại người liên hệ'],
      ])}</Section>
    </div>
  )
}

function Section({ title, children }) {
  return <section className="rounded-xl border border-hairline bg-surface p-3.5 shadow-soft">
    <h2 className="text-body-sm font-semibold text-ink">{title}</h2><div className="mt-3">{children}</div>
  </section>
}
