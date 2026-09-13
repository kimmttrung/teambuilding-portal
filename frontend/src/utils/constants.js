/** Nhãn hiển thị và hằng số dùng chung. Gom về một chỗ để không rải chuỗi khắp nơi. */

export const ROLES = {
  EMPLOYEE: 'employee',
  TEAM_LEADER: 'team_leader',
  ADMIN: 'admin',
  SUPER_ADMIN: 'super_admin',
}

export const ADMIN_ROLES = [ROLES.ADMIN, ROLES.SUPER_ADMIN]
export const LEADER_ROLES = [ROLES.TEAM_LEADER, ...ADMIN_ROLES]

export const ROLE_LABELS = {
  [ROLES.EMPLOYEE]: 'CBNV',
  [ROLES.TEAM_LEADER]: 'Trưởng nhóm',
  [ROLES.ADMIN]: 'Ban tổ chức',
  [ROLES.SUPER_ADMIN]: 'Quản trị hệ thống',
}

export const EVENT_STATUS = {
  DRAFT: 'draft',
  REGISTRATION_OPEN: 'registration_open',
  REGISTRATION_CLOSED: 'registration_closed',
  ALLOCATION_PROCESSING: 'allocation_processing',
  INFORMATION_PUBLISHED: 'information_published',
  EVENT_STARTED: 'event_started',
  COMPLETED: 'completed',
}

/** Nhãn + màu badge cho từng trạng thái chương trình. */
export const EVENT_STATUS_META = {
  [EVENT_STATUS.DRAFT]: { label: 'Nháp', tone: 'slate' },
  [EVENT_STATUS.REGISTRATION_OPEN]: { label: 'Đang mở đăng ký', tone: 'emerald' },
  [EVENT_STATUS.REGISTRATION_CLOSED]: { label: 'Đã đóng đăng ký', tone: 'amber' },
  [EVENT_STATUS.ALLOCATION_PROCESSING]: { label: 'Đang phân bổ', tone: 'blue' },
  [EVENT_STATUS.INFORMATION_PUBLISHED]: { label: 'Đã công bố thông tin', tone: 'brand' },
  [EVENT_STATUS.EVENT_STARTED]: { label: 'Đang diễn ra', tone: 'brand' },
  [EVENT_STATUS.COMPLETED]: { label: 'Đã kết thúc', tone: 'slate' },
}

export const REGISTRATION_STATUS_META = {
  draft: { label: 'Nháp', tone: 'slate' },
  submitted: { label: 'Đã đăng ký', tone: 'emerald' },
  cancelled: { label: 'Đã huỷ', tone: 'rose' },
}

export const GENDER_LABELS = {
  male: 'Nam',
  female: 'Nữ',
  other: 'Khác',
}

export const GENDERS = Object.keys(GENDER_LABELS)

export const SHIRT_SIZES = ['XS', 'S', 'M', 'L', 'XL', 'XXL', 'XXXL']

export const ID_CARD_TYPE_LABELS = {
  cccd: 'CCCD / CMND',
  passport: 'Hộ chiếu',
}

export const ID_CARD_TYPES = Object.keys(ID_CARD_TYPE_LABELS)

/** 5 bước của form đăng ký (docs/07-frontend.md §3.1). */
export const REGISTRATION_STEPS = [
  { id: 'profile', label: 'Thông tin cá nhân' },
  { id: 'participation', label: 'Xác nhận tham gia' },
  { id: 'shift', label: 'Chọn ca đi' },
  { id: 'bus', label: 'Nhu cầu xe' },
  { id: 'consent', label: 'Mong muốn & quy định' },
]

/** Tiền tố khoá localStorage cho bản nháp đăng ký — kèm event và user để không lẫn. */
export const REGISTRATION_DRAFT_PREFIX = 'tb_registration_draft_v1'

/** Thông điệp lỗi tiếng Việt cho các mã backend cần diễn giải thêm ngữ cảnh. */
export const ERROR_HINTS = {
  MISSING_PROFILE_FIELDS: 'Bổ sung thông tin còn thiếu trong hồ sơ rồi gửi lại.',
  TERMS_VERSION_MISMATCH: 'Tải lại trang để đọc bản quy định mới nhất.',
  REGISTRATION_CLOSED: 'Liên hệ Ban tổ chức nếu bạn cần hỗ trợ đặc biệt.',
  NETWORK_ERROR: 'Kiểm tra kết nối mạng rồi thử lại.',
}

/** --- Chuyến bay --- */

export const FLIGHT_DIRECTIONS = {
  OUTBOUND: 'outbound',
  RETURN: 'return',
}

export const FLIGHT_DIRECTION_LABELS = {
  [FLIGHT_DIRECTIONS.OUTBOUND]: 'Chiều đi',
  [FLIGHT_DIRECTIONS.RETURN]: 'Chiều về',
}

export const ASSIGNMENT_MODE_LABELS = {
  auto: 'Tự động',
  manual: 'BTC xếp tay',
}

/**
 * Nhãn và màu cho từng loại flag của thuật toán (docs/05-allocation-algorithm.md §4).
 * `blocking` = phải xử lý trước khi công bố, không chỉ là gợi ý.
 */
export const ALLOCATION_FLAG_META = {
  UNASSIGNED: { label: 'Không có chỗ', tone: 'rose', blocking: true },
  SHIFT_LOCKED_VIOLATION: { label: 'Vi phạm ca đã khoá', tone: 'rose', blocking: true },
  TEAM_SPLIT_EXCEEDED: { label: 'Tách team quá giới hạn', tone: 'rose', blocking: true },
  MISSING_ID_CARD: { label: 'Thiếu giấy tờ bay', tone: 'rose', blocking: true },
  TEAM_SPLIT: { label: 'Team bị tách', tone: 'amber', blocking: false },
  SHIFT_NOT_SATISFIED: { label: 'Lệch ca nguyện vọng', tone: 'amber', blocking: false },
  TINY_CHUNK: { label: 'Mảnh nhỏ lẻ', tone: 'slate', blocking: false },
}

export const SEVERITY_TONES = {
  error: 'rose',
  warning: 'amber',
  info: 'slate',
}

/** Ngưỡng đổi màu cột slot: gần đầy là cảnh báo, đầy là chặn. */
export const LOAD_WARNING_RATIO = 0.9

/** Khoá cache của TanStack Query — gom lại để invalidate không bị gõ sai chuỗi. */
export const QUERY_KEYS = {
  me: ['auth', 'me'],
  activeEvent: ['events', 'active'],
  eventOverview: (id) => ['events', id, 'overview'],
  myRegistration: ['registrations', 'me'],
  registrationStats: ['registrations', 'stats'],
  registrations: (filters) => ['registrations', 'list', filters],
  formOptions: ['master-data', 'registration-form'],
  terms: (eventId) => ['events', eventId, 'terms'],
  flights: (filters) => ['flights', 'list', filters],
  flightSummary: ['flights', 'summary'],
  passengers: (flightId) => ['flights', flightId, 'passengers'],
  assignments: (filters) => ['flight-assignments', filters],
  teams: ['master-data', 'teams'],
}
