import {
  GENDER_LABELS,
  ID_CARD_TYPE_LABELS,
  SHIRT_SIZES,
} from '../../utils/constants'
import Input from '../common/Input'
import Select from '../common/Select'
import Textarea from '../common/Textarea'

/**
 * Các nhóm ô nhập của hồ sơ cá nhân.
 *
 * Dùng chung cho trang /profile và bước 1 của form đăng ký: hai nơi cùng sửa một
 * bộ trường, tách ra đây để không có chỗ nào thiếu trường hay lệch nhãn.
 * `prefix` là tiền tố tên field ('profile.' trong form đăng ký, '' ở trang hồ sơ),
 * `errors` truyền vào đã được thu hẹp đúng nhánh tương ứng.
 */

const GENDER_OPTIONS = Object.entries(GENDER_LABELS).map(([value, label]) => ({ value, label }))
const ID_CARD_OPTIONS = Object.entries(ID_CARD_TYPE_LABELS).map(([value, label]) => ({
  value,
  label,
}))
const SHIRT_OPTIONS = SHIRT_SIZES.map((size) => ({ value: size, label: size }))

function makeField(register, errors, prefix) {
  return function field(name) {
    return { ...register(`${prefix}${name}`), error: errors?.[name]?.message }
  }
}

export function IdentityFields({ register, errors, prefix = '', required = false }) {
  const field = makeField(register, errors, prefix)

  return (
    <div className="grid gap-3 lg:grid-cols-3">
      <Input label="Tên gọi trong chương trình" placeholder="Ví dụ: Trung IT" {...field('display_name')} />
      <Select
        label="Giới tính"
        required={required}
        placeholder="— Chọn giới tính —"
        options={GENDER_OPTIONS}
        hint="BTC xếp phòng khách sạn theo giới tính"
        {...field('gender')}
      />
      <Input label="Ngày sinh" type="date" required={required} {...field('date_of_birth')} />
      <Input
        label="Số điện thoại"
        type="tel"
        inputMode="numeric"
        placeholder="0912345678"
        required={required}
        {...field('phone')}
      />
      <Input
        label="Email cá nhân"
        type="email"
        placeholder="ten@gmail.com"
        hint="Dùng khi email công ty không nhận được thông báo"
        {...field('personal_email')}
      />
      <Input
        label="Địa chỉ hiện tại"
        placeholder="Số nhà, đường, phường/xã, tỉnh/thành"
        className="lg:col-span-1"
        {...field('address')}
      />
    </div>
  )
}

export function DocumentFields({ register, errors, prefix = '', required = false, figma = false, documentType = 'cccd', missingIssueDate = false }) {
  const field = makeField(register, errors, prefix)

  return (
    <div className={figma ? 'flex flex-col gap-4' : 'grid gap-3 lg:grid-cols-4'}>
      {figma ? <div className="f1-segment" role="group" aria-label="Loại giấy tờ">
        {ID_CARD_OPTIONS.map(({ value, label }) => <label key={value}>
          <input type="radio" value={value} {...register(`${prefix}id_card_type`)} /><span>{value === 'cccd' ? 'CCCD' : label}</span>
        </label>)}
      </div> : <Select label="Loại giấy tờ" options={ID_CARD_OPTIONS} {...field('id_card_type')} />}
      <Input
        label={figma ? documentType === 'passport' ? 'Số hộ chiếu' : 'Số CCCD' : 'Số CCCD / Hộ chiếu'}
        inputMode={figma && documentType === 'passport' ? 'text' : 'numeric'}
        placeholder={figma && documentType === 'passport' ? 'Số hộ chiếu' : '12 số trên CCCD'}
        required={required}
        hint={figma ? undefined : 'Phải khớp giấy tờ bạn mang khi bay'}
        {...field('id_card_number')}
      />
      <div className={figma ? 'grid grid-cols-2 gap-3' : 'contents'}>
        <Input label="Ngày cấp" type="date" {...field('id_card_issue_date')}
          error={errors?.id_card_issue_date?.message || (figma && missingIssueDate ? 'Cần bổ sung ngày cấp' : undefined)} />
        <Input label="Nơi cấp" placeholder="Cục CS QLHC về TTXH" {...field('id_card_issue_place')} />
      </div>
    </div>
  )
}

export function PreferenceFields({ register, errors, prefix = '', healthNote, figma = false }) {
  const field = makeField(register, errors, prefix)

  return (
    <div className={figma ? 'flex flex-col gap-4' : 'grid gap-3 lg:grid-cols-2'}>
      {figma ? <fieldset>
        <legend className="f1-label">Size áo</legend>
        <div className="f1-shirt">{SHIRT_SIZES.filter((size) => !['XS', 'XXXL'].includes(size)).map((size) => <label key={size}>
          <input type="radio" value={size} {...register(`${prefix}shirt_size`)} /><span>{size}</span>
        </label>)}</div>
        <details className="mt-2 text-xs text-ink-faint"><summary className="cursor-pointer">Size khác</summary>
          <div className="f1-shirt">{['XS', 'XXXL'].map((size) => <label key={size}>
            <input type="radio" value={size} {...register(`${prefix}shirt_size`)} /><span>{size}</span>
          </label>)}</div>
        </details>
        {errors?.shirt_size && <p className="mt-1 text-xs text-rose-600">{errors.shirt_size.message}</p>}
      </fieldset> : <Select label="Size áo" placeholder="— Chọn size —" options={SHIRT_OPTIONS} {...field('shirt_size')} />}
      <Input
        label={figma ? 'Ăn kiêng / dị ứng' : 'Ăn kiêng / dị ứng thực phẩm'}
        placeholder={figma ? 'Ví dụ: ăn chay, dị ứng hải sản' : 'Ăn chay, dị ứng hải sản…'}
        {...field('dietary_restriction')}
      />
      <div className={figma ? 'f1-profile-health' : 'lg:col-span-2'}><Textarea
        label="Tình trạng sức khoẻ cần lưu ý"
        rows={figma ? 2 : 3}
        maxLength={2000}
        counterValue={figma ? undefined : healthNote ?? ''}
        placeholder="Bệnh nền, thuốc đang dùng, hạn chế vận động…"
        hint={figma ? 'Chỉ BTC xem được.' : 'Chỉ BTC xem được, dùng khi cần xử lý y tế trong chuyến đi'}
        {...field('health_note')}
      /></div>
    </div>
  )
}

export function EmergencyFields({ register, errors, prefix = '', figma = false }) {
  const field = makeField(register, errors, prefix)

  return (
    <div className={figma ? 'grid grid-cols-2 gap-3' : 'grid gap-3 lg:grid-cols-2'}>
      <Input label={figma ? 'Người liên hệ' : 'Người liên hệ khi cần'} placeholder="Họ tên" {...field('emergency_contact_name')} />
      <Input
        label={figma ? 'Số điện thoại' : 'Số điện thoại người liên hệ'}
        type="tel"
        inputMode="numeric"
        placeholder="0912345678"
        {...field('emergency_contact_phone')}
      />
    </div>
  )
}

/** Giá trị mặc định cho form: API trả null, ô nhập cần chuỗi rỗng. */
export const PROFILE_FIELD_NAMES = [
  'display_name',
  'phone',
  'personal_email',
  'gender',
  'date_of_birth',
  'address',
  'id_card_type',
  'id_card_number',
  'id_card_issue_date',
  'id_card_issue_place',
  'shirt_size',
  'dietary_restriction',
  'health_note',
  'emergency_contact_name',
  'emergency_contact_phone',
]

export function profileDefaults(user) {
  return Object.fromEntries(
    PROFILE_FIELD_NAMES.map((name) => [
      name,
      // Mặc định CCCD cho người chưa từng khai: đa số CBNV dùng CCCD, không phải hộ chiếu.
      name === 'id_card_type' ? (user?.id_card_type ?? 'cccd') : (user?.[name] ?? ''),
    ]),
  )
}
