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

/**
 * Chuyến bay — khớp FlightIn/FlightUpdate của backend.
 *
 * Giờ ở form là chuỗi của `<input type="datetime-local">` theo giờ Việt Nam; việc đổi sang
 * ISO UTC do `fromDateTimeInput` lo, nên ở đây chỉ kiểm thứ tự hai mốc giờ.
 */
export const flightSchema = z
  .object({
    flight_code: z
      .string()
      .trim()
      .min(2, 'Mã chuyến tối thiểu 2 ký tự')
      .max(16, 'Mã chuyến tối đa 16 ký tự')
      .regex(/^[A-Za-z0-9]+$/, 'Mã chuyến chỉ gồm chữ và số, ví dụ VN1234'),
    airline: optionalText(128),
    direction: z.enum(['outbound', 'return'], { message: 'Chọn chiều bay' }),
    shift_id: z.string().optional(),
    departure_airport: z
      .string()
      .trim()
      .regex(/^[A-Za-z]{3}$/, 'Mã sân bay gồm 3 chữ, ví dụ HAN'),
    arrival_airport: z
      .string()
      .trim()
      .regex(/^[A-Za-z]{3}$/, 'Mã sân bay gồm 3 chữ, ví dụ PQC'),
    departure_time: z.string().min(1, 'Nhập giờ khởi hành'),
    arrival_time: z.string().min(1, 'Nhập giờ đến'),
    capacity: z.coerce
      .number({ message: 'Số ghế phải là số' })
      .int('Số ghế phải là số nguyên')
      .min(1, 'Tối thiểu 1 ghế')
      .max(1000, 'Tối đa 1000 ghế'),
    reserved_slots: z.coerce
      .number({ message: 'Số ghế giữ lại phải là số' })
      .int('Số ghế giữ lại phải là số nguyên')
      .min(0, 'Không được âm'),
    note: optionalText(2000),
    is_active: z.boolean(),
  })
  .superRefine((values, context) => {
    if (values.departure_airport.toUpperCase() === values.arrival_airport.toUpperCase()) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['arrival_airport'],
        message: 'Sân bay đến phải khác sân bay đi',
      })
    }
    if (values.arrival_time && values.departure_time && values.arrival_time <= values.departure_time) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['arrival_time'],
        message: 'Giờ đến phải sau giờ khởi hành',
      })
    }
    if (values.reserved_slots > values.capacity) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['reserved_slots'],
        message: 'Ghế giữ lại không thể nhiều hơn tổng số ghế',
      })
    }
  })

/** Thêm / sửa xe — khớp `BusIn` / `BusUpdate` ở backend. Giờ nhập theo giờ VN. */
export const busSchema = z
  .object({
    trip_leg_id: z.string().min(1, 'Chọn chặng'),
    bus_code: z
      .string()
      .trim()
      .min(1, 'Nhập mã xe')
      .max(32, 'Mã xe tối đa 32 ký tự')
      .regex(/^[A-Za-z0-9_-]+$/, 'Mã xe chỉ gồm chữ, số, gạch ngang — ví dụ XE-01'),
    plate_number: optionalText(32),
    capacity: z.coerce
      .number({ message: 'Số chỗ phải là số' })
      .int('Số chỗ phải là số nguyên')
      .min(1, 'Tối thiểu 1 chỗ')
      .max(100, 'Tối đa 100 chỗ'),
    pickup_point_id: z.string().optional(),
    dropoff_point: optionalText(255),
    gather_time: z.string().optional(),
    departure_time: z.string().optional(),
    linked_flight_id: z.string().optional(),
    driver_name: optionalText(255),
    driver_phone: optionalText(32),
    note: optionalText(2000),
  })
  .superRefine((values, context) => {
    if (values.gather_time && values.departure_time && values.departure_time < values.gather_time) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['departure_time'],
        message: 'Giờ xe chạy phải sau giờ tập trung',
      })
    }
  })

/** Trưởng xe: CBNV trong đoàn, người ngoài (tên + số điện thoại), hoặc bỏ trống. */
export const leaderSchema = z
  .object({
    mode: z.enum(['employee', 'outsider', 'none']),
    leader_user_id: z.string().optional(),
    leader_name: optionalText(255),
    leader_phone: optionalText(32),
  })
  .superRefine((values, context) => {
    if (values.mode === 'employee' && !values.leader_user_id) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['leader_user_id'],
        message: 'Chọn CBNV làm Trưởng xe',
      })
    }
    if (values.mode === 'outsider') {
      if (!values.leader_name) {
        context.addIssue({ code: z.ZodIssueCode.custom, path: ['leader_name'], message: 'Nhập họ tên' })
      }
      if (!values.leader_phone) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['leader_phone'],
          message: 'Nhập số điện thoại để CBNV gọi được',
        })
      }
    }
  })

/** Thêm / sửa khách sạn — khớp `HotelIn` ở backend. Giờ nhận/trả phòng nhập theo giờ VN. */
export const hotelSchema = z
  .object({
    name: z.string().trim().min(1, 'Nhập tên khách sạn').max(255, 'Tối đa 255 ký tự'),
    address: optionalText(512),
    phone: optionalText(32),
    check_in_at: z.string().optional(),
    check_out_at: z.string().optional(),
    map_url: optionalText(512).refine((value) => !value || /^https?:\/\//i.test(value), {
      message: 'Link bản đồ phải bắt đầu bằng http:// hoặc https://',
    }),
    note: optionalText(2000),
  })
  .superRefine((values, context) => {
    if (values.check_in_at && values.check_out_at && values.check_out_at <= values.check_in_at) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['check_out_at'],
        message: 'Giờ trả phòng phải sau giờ nhận phòng',
      })
    }
  })

/** Thêm / sửa phòng — khớp `RoomIn` / `RoomUpdate` ở backend. */
export const roomSchema = z.object({
  hotel_id: z.string().min(1, 'Chọn khách sạn'),
  room_number: z
    .string()
    .trim()
    .min(1, 'Nhập số phòng')
    .max(32, 'Số phòng tối đa 32 ký tự')
    .regex(/^[A-Za-z0-9._-]+$/, 'Số phòng chỉ gồm chữ, số, dấu chấm, gạch — ví dụ 1204'),
  room_type: z.string().optional(),
  capacity: z.coerce
    .number({ message: 'Sức chứa phải là số' })
    .int('Sức chứa phải là số nguyên')
    .min(1, 'Tối thiểu 1 người')
    .max(10, 'Tối đa 10 người'),
  floor: optionalText(16),
  gender_policy: z.enum(['any', 'male', 'female'], { message: 'Chọn giới tính của phòng' }),
  note: optionalText(512),
})

/** Ô số dạng chuỗi (input type=number trả chuỗi). `required=false` cho phép bỏ trống. */
const intText = (min, max, label, { required = true } = {}) =>
  z
    .string()
    .trim()
    .refine((value) => !required || value !== '', { message: `Nhập ${label}` })
    .refine((value) => value === '' || (/^\d+$/.test(value) && Number(value) >= min && Number(value) <= max), {
      message: `${label[0].toUpperCase()}${label.slice(1)} là số nguyên từ ${min} đến ${max}`,
    })

/** Sơ đồ Gala — khớp `GalaLayoutIn` / `GalaLayoutUpdate` ở backend. */
export const galaLayoutSchema = z.object({
  name: z.string().trim().min(1, 'Nhập tên sơ đồ').max(255, 'Tối đa 255 ký tự'),
  venue: optionalText(255),
  starts_at: z.string().optional(),
  stage_position: z.enum(['top', 'bottom', 'left', 'right'], { message: 'Chọn vị trí sân khấu' }),
  grid_width: intText(4, 40, 'số cột'),
  grid_height: intText(4, 40, 'số hàng'),
  turn_seconds: intText(30, 3600, 'thời gian mỗi lượt', { required: false }),
  hold_seconds: intText(15, 1800, 'thời gian giữ ghế', { required: false }),
})

/** Bàn Gala — khớp `GalaTableIn` / `GalaTableUpdate` ở backend. */
export const galaTableSchema = z.object({
  table_code: z
    .string()
    .trim()
    .min(1, 'Nhập mã bàn')
    .max(16, 'Mã bàn tối đa 16 ký tự')
    .regex(/^[A-Za-z0-9._-]+$/, 'Mã bàn chỉ gồm chữ, số, dấu chấm, gạch — ví dụ B01'),
  table_name: optionalText(128),
  seat_count: intText(1, 24, 'số ghế'),
  pos_x: intText(0, 39, 'cột'),
  pos_y: intText(0, 39, 'hàng'),
  is_vip: z.boolean(),
  is_available: z.boolean(),
})

const EMPLOYEE_CODE = /^[A-Za-z0-9._-]{2,32}$/
const EMPLOYEE_CODE_MESSAGE = 'Mã nhân viên 2-32 ký tự: chữ, số, dấu chấm, gạch'

/** BTC tạo tài khoản CBNV — khớp `UserCreate` ở backend. Mật khẩu do hệ thống sinh. */
export const userCreateSchema = z.object({
  employee_code: z.string().trim().regex(EMPLOYEE_CODE, EMPLOYEE_CODE_MESSAGE),
  full_name: z.string().trim().min(1, 'Nhập họ tên').max(255, 'Tối đa 255 ký tự'),
  email: z.string().trim().email('Email công ty không hợp lệ'),
  role: z.enum(['employee', 'team_leader', 'admin', 'super_admin']),
  gender: optionalEnum(GENDERS, 'Giới tính không hợp lệ'),
  phone: optionalPhone('Số điện thoại'),
  team_id: z.string().optional(),
  department_id: z.string().optional(),
  work_location_id: z.string().optional(),
  job_title: optionalText(128),
  join_date: z.string().optional(),
})

/**
 * BTC sửa hồ sơ CBNV: phần công việc (chỉ BTC sửa được) + đúng bộ trường hồ sơ cá nhân mà
 * CBNV tự sửa — dùng chung `profileSchema` để hai nơi không lệch luật kiểm tra.
 */
export const adminUserSchema = z.intersection(
  z.object({
    employee_code: z
      .string()
      .trim()
      .optional()
      .refine((value) => !value || EMPLOYEE_CODE.test(value), { message: EMPLOYEE_CODE_MESSAGE }),
    full_name: z.string().trim().min(1, 'Nhập họ tên').max(255, 'Tối đa 255 ký tự'),
    email: z.string().trim().email('Email công ty không hợp lệ'),
    team_id: z.string().optional(),
    department_id: z.string().optional(),
    work_location_id: z.string().optional(),
    job_title: optionalText(128),
    join_date: z.string().optional(),
  }),
  profileSchema,
)

/** Lý do cho mọi thao tác điều chỉnh thủ công — backend đòi tối thiểu 3 ký tự. */
export const moveReasonSchema = z.object({
  reason: z
    .string()
    .trim()
    .min(3, 'Nhập lý do (ít nhất 3 ký tự) để lưu vào nhật ký')
    .max(500, 'Tối đa 500 ký tự'),
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
