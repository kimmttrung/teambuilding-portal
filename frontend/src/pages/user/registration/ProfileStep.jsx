import { useAuth } from '../../../context/AuthContext'
import { missingProfileFields, PROFILE_REQUIRED_FIELDS } from '../../../utils/schemas'
import { formatDate } from '../../../utils/format'
import { GENDER_LABELS, ID_CARD_TYPE_LABELS } from '../../../utils/constants'
import Avatar from '../../../components/common/Avatar'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
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

  return (
    <div className="flex flex-col gap-4">
      <StepIntro
        compact
        step="1"
        eyebrow="Thông tin cá nhân"
        title="Hồ sơ của bạn"
        description="Dùng để đặt vé, bố trí phòng và liên hệ trong chuyến đi."
        mobileEyebrow="Thông tin của bạn"
        mobileTitle="Hồ sơ của bạn"
        mobileDescription="Khớp giấy tờ bạn mang theo."
      />
      <Card bodyClassName="p-0">
        <div className="flex flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:px-6">
          <Avatar user={user} size="lg" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-heading-3 text-ink">{user.full_name}</p>
            <p className="mt-0.5 truncate text-body-sm text-ink-muted">
              {[user.employee_code, user.email].filter(Boolean).join(' · ')}
            </p>
            {missing.length ? (
              <p className="mt-1 text-caption text-accent-orange-deep">
                Thiếu: <strong>{missing.join(', ')}</strong>. Cập nhật hồ sơ trước khi đăng ký tham gia.
              </p>
            ) : (
              <p className="mt-1 text-caption text-ink-faint">Lấy từ hồ sơ. Cần đổi thì cập nhật rồi quay lại.</p>
            )}
          </div>
          <Button type="button" variant="secondary" size="sm" onClick={onEditProfile}>
            Cập nhật hồ sơ
          </Button>
        </div>
        <div className="divide-y divide-hairline border-t border-hairline">
          <Section title="Thông tin cơ bản">{renderFields(fields, user)}</Section>
          <Section title="Giấy tờ đi máy bay">{renderFields(documents, user)}</Section>
          <Section title="Áo, ăn uống và sức khoẻ">{renderFields([
            ['shirt_size', 'Size áo'],
            ['dietary_restriction', 'Ăn kiêng / dị ứng thực phẩm'],
            ['health_note', 'Tình trạng sức khoẻ cần lưu ý'],
          ], user)}</Section>
          <Section title="Liên hệ khi cần">{renderFields([
            ['emergency_contact_name', 'Người liên hệ khi cần'],
            ['emergency_contact_phone', 'Số điện thoại người liên hệ'],
          ], user)}</Section>
        </div>
      </Card>
    </div>
  )
}

function renderFields(items, user) {
  return (
    <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {items.map(([name, label, display]) => (
        <div key={name} className="min-w-0">
          <dt className="text-caption text-ink-muted">
            {label}
            {REQUIRED.has(name) && <span className="ml-1 text-rose-600">*</span>}
          </dt>
          <dd className="mt-0.5 whitespace-pre-wrap break-words text-body-sm font-medium text-ink">
            {(display ?? user[name]) || '—'}
          </dd>
        </div>
      ))}
    </dl>
  )
}

function Section({ title, children }) {
  return (
    <section className="px-4 py-4 sm:px-6">
      <h2 className="mb-3 text-body-sm font-semibold text-ink">{title}</h2>
      {children}
    </section>
  )
}
