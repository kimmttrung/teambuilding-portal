/**
 * Zod schema dùng chung cho form.
 *
 * Mỗi luật ở đây phải khớp với validate của backend (app/schemas/user.py,
 * app/schemas/registration.py). Lệch nhau thì người dùng điền xong mới bị chối —
 * validate phía client chỉ để báo sớm, backend vẫn là nơi quyết định.
 */

import { z } from 'zod'
import { GENDERS, ID_CARD_TYPES, SHIRT_SIZES } from './constants'

/** Ô trống trong form là chuỗi rỗng, không phải null — chuẩn hoá trước khi kiểm tra. */
const optionalText = (max, message = `Tối đa ${max} ký tự`) =>
  z.string().trim().max(max, message).optional()

const optionalEnum = (values, message) =>
  z
    .string()
    .optional()
    .refine((value) => !value || values.includes(value), { message })

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/
const PHONE = /^0\d{8,10}$/

const optionalPhone = (label) =>
  z
    .string()
    .trim()
    .optional()
    .refine((value) => !value || PHONE.test(value.replace(/[\s.-]/g, '')), {
      message: `${label} phải là 10-11 số và bắt đầu bằng 0`,
    })

const optionalPastDate = (label) =>
  z
    .string()
    .trim()
    .optional()
    .refine((value) => !value || ISO_DATE.test(value), { message: `${label} không hợp lệ` })
    .refine((value) => !value || new Date(value) <= new Date(), {
      message: `${label} không thể ở tương lai`,
    })

/** Hồ sơ cá nhân — dùng cho cả trang /profile và bước 1 của form đăng ký. */
export const profileSchema = z
  .object({
    display_name: optionalText(255),
    phone: optionalPhone('Số điện thoại'),
    personal_email: z
      .string()
      .trim()
      .optional()
      .refine((value) => !value || z.string().email().safeParse(value).success, {
        message: 'Email cá nhân không hợp lệ',
      }),
    gender: optionalEnum(GENDERS, 'Giới tính không hợp lệ'),
    date_of_birth: optionalPastDate('Ngày sinh'),
    address: optionalText(512),

    id_card_type: optionalEnum(ID_CARD_TYPES, 'Loại giấy tờ không hợp lệ'),
    id_card_number: optionalText(32),
    id_card_issue_date: optionalPastDate('Ngày cấp'),
    id_card_issue_place: optionalText(255),

    shirt_size: optionalEnum(SHIRT_SIZES, 'Size áo không hợp lệ'),
    dietary_restriction: optionalText(255),
    health_note: optionalText(2000),
    emergency_contact_name: optionalText(255),
    emergency_contact_phone: optionalPhone('Số điện thoại liên hệ khẩn cấp'),
  })
  .superRefine((values, context) => {
    // Số CCCD 12 số (CMND cũ 9 số), hộ chiếu là chữ + số. Sai định dạng ở đây
    // nghĩa là vé máy bay xuất ra sai giấy tờ, sân bay không cho lên.
    const number = values.id_card_number?.replace(/\s/g, '')

    if (number) {
      const isPassport = values.id_card_type === 'passport'
      const valid = isPassport
        ? /^[A-Za-z0-9]{6,12}$/.test(number)
        : /^(\d{9}|\d{12})$/.test(number)
      if (!valid) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['id_card_number'],
          message: isPassport
            ? 'Số hộ chiếu gồm 6-12 chữ và số'
            : 'Số CCCD gồm 12 số (CMND cũ 9 số)',
        })
      }
    }

    if (
      values.id_card_issue_date &&
      values.date_of_birth &&
      values.id_card_issue_date < values.date_of_birth
    ) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['id_card_issue_date'],
        message: 'Ngày cấp không thể trước ngày sinh',
      })
    }
  })

/** Thiếu những trường này là BTC không xuất được vé — khớp REQUIRED_PROFILE_FIELDS của backend. */
export const FLIGHT_REQUIRED_FIELDS = [
  { name: 'date_of_birth', label: 'Ngày sinh' },
  { name: 'id_card_number', label: 'Số CCCD/Hộ chiếu' },
  { name: 'phone', label: 'Số điện thoại' },
  { name: 'gender', label: 'Giới tính' },
]

export function missingFlightFields(profile) {
  return FLIGHT_REQUIRED_FIELDS.filter(({ name }) => !profile?.[name]).map(({ label }) => label)
}

/**
 * Nhu cầu xe của một chặng.
 *
 * `has_pickup_options` không gửi lên API: nó cho schema biết chặng này có điểm đón
 * để chọn hay không. BTC có thể chưa khai điểm đón cho chặng sân bay → khách sạn,
 * lúc đó bắt chọn điểm đón là chặn người dùng vì lỗi dữ liệu của BTC.
 */
const busNeedSchema = z.object({
  trip_leg_id: z.number().int(),
  needs_bus: z.boolean(),
  pickup_point_id: z.string().optional(),
  note: optionalText(512),
  has_pickup_options: z.boolean().optional(),
})

/**
 * Toàn bộ form đăng ký 5 bước trong một schema.
 *
 * Dùng một schema cho cả form (thay vì mỗi bước một schema) để `trigger` của
 * React Hook Form validate được từng bước mà không phải tự ghép lại dữ liệu,
 * và nút "Gửi đăng ký" ở bước cuối vẫn kiểm tra lại tất cả.
 */
export const registrationFormSchema = z
  .object({
    profile: profileSchema,
    is_participating: z.enum(['yes', 'no'], { message: 'Vui lòng chọn có hoặc không tham gia' }),
    not_participating_reason: optionalText(512),
    shift_id: z.string().optional(),
    departure_location_id: z.string().optional(),
    bus_needs: z.array(busNeedSchema),
    wish_note: optionalText(2000),
    companion_count: z.coerce
      .number({ message: 'Số người đi cùng phải là số' })
      .int('Số người đi cùng phải là số nguyên')
      .min(0, 'Không được là số âm')
      .max(5, 'Tối đa 5 người'),
    agreed_terms: z.boolean(),
    // Phiên bản quy định người dùng thực sự đã đọc trong modal. Gửi đúng bản này lên
    // API: backend chối nếu lệch với bản hiện hành (TERMS_VERSION_MISMATCH), đó là
    // cách phát hiện người dùng mở form từ trước khi BTC sửa quy định.
    agreed_terms_version: z.string().optional(),
  })
  .superRefine((values, context) => {
    if (values.is_participating !== 'yes') return

    const missing = missingFlightFields(values.profile)
    if (missing.length) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['profile'],
        message: `Còn thiếu: ${missing.join(', ')}.`,
      })
    }

    if (!values.shift_id) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['shift_id'],
        message: 'Vui lòng chọn ca đi',
      })
    }

    // Chọn đi xe nhưng chưa chọn điểm đón thì BTC không biết dừng ở đâu.
    values.bus_needs.forEach((need, index) => {
      if (need.needs_bus && need.has_pickup_options && !need.pickup_point_id) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['bus_needs', index, 'pickup_point_id'],
          message: 'Chọn điểm đón cho chặng này',
        })
      }
    })

    if (!values.agreed_terms) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['agreed_terms'],
        message: 'Phải đọc và đồng ý quy định chương trình mới gửi được đăng ký',
      })
    }
  })

/** Đổi mật khẩu — khớp ChangePasswordRequest của backend. */
export const changePasswordSchema = z
  .object({
    current_password: z.string().min(1, 'Nhập mật khẩu hiện tại'),
    new_password: z
      .string()
      .min(8, 'Mật khẩu mới tối thiểu 8 ký tự')
      .regex(/[A-Za-zÀ-ỹ]/, 'Mật khẩu phải có ít nhất một chữ cái')
      .regex(/\d/, 'Mật khẩu phải có ít nhất một chữ số'),
    confirm_password: z.string().min(1, 'Nhập lại mật khẩu mới'),
  })
  .refine((values) => values.new_password === values.confirm_password, {
    path: ['confirm_password'],
    message: 'Hai mật khẩu không giống nhau',
  })
  .refine((values) => values.new_password !== values.current_password, {
    path: ['new_password'],
    message: 'Mật khẩu mới phải khác mật khẩu hiện tại',
  })

/**
 * Dọn dữ liệu hồ sơ trước khi gửi lên API.
 *
 * Backend dùng `extra="forbid"` và pattern regex: chuỗi rỗng sẽ bị chối
 * (ví dụ `shirt_size=""` không khớp `^(XS|S|...)$`), nên ô trống phải thành null.
 * Chỉ gửi trường thực sự đổi, để audit log không đầy bản ghi "sửa mà không đổi gì".
 */
export function buildProfilePatch(formProfile, currentUser) {
  const patch = {}

  for (const [field, rawValue] of Object.entries(formProfile ?? {})) {
    const value = typeof rawValue === 'string' ? rawValue.trim() || null : (rawValue ?? null)
    const current = currentUser?.[field] ?? null
    if (value !== current) patch[field] = value
  }

  return patch
}
