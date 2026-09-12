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

export const SHIRT_SIZES = ['XS', 'S', 'M', 'L', 'XL', 'XXL', 'XXXL']

/** Thông điệp lỗi tiếng Việt cho các mã backend cần diễn giải thêm ngữ cảnh. */
export const ERROR_HINTS = {
  MISSING_PROFILE_FIELDS: 'Bổ sung thông tin còn thiếu trong hồ sơ rồi gửi lại.',
  TERMS_VERSION_MISMATCH: 'Tải lại trang để đọc bản quy định mới nhất.',
  REGISTRATION_CLOSED: 'Liên hệ Ban tổ chức nếu bạn cần hỗ trợ đặc biệt.',
  NETWORK_ERROR: 'Kiểm tra kết nối mạng rồi thử lại.',
}

/** Khoá cache của TanStack Query — gom lại để invalidate không bị gõ sai chuỗi. */
export const QUERY_KEYS = {
  me: ['auth', 'me'],
  activeEvent: ['events', 'active'],
  eventOverview: (id) => ['events', id, 'overview'],
  myRegistration: ['registrations', 'me'],
  registrationStats: ['registrations', 'stats'],
  registrations: (filters) => ['registrations', 'list', filters],
  formOptions: ['master-data', 'registration-form'],
  teams: ['master-data', 'teams'],
}
