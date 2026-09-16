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

export const ROLE_TONES = {
  [ROLES.EMPLOYEE]: 'slate',
  [ROLES.TEAM_LEADER]: 'blue',
  [ROLES.ADMIN]: 'brand',
  [ROLES.SUPER_ADMIN]: 'rose',
}

/** Lọc danh sách CBNV theo đăng ký của kỳ đang chạy — khớp `RegistrationFilter` ở backend. */
export const USER_REGISTRATION_FILTERS = {
  none: 'Chưa đăng ký',
  participating: 'Tham gia',
  not_participating: 'Không tham gia',
  cancelled: 'Đã huỷ',
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

/** Nhãn ngắn cho thanh vòng đời trên dashboard — đúng thứ tự `EventStatus` ở backend. */
export const EVENT_LIFECYCLE = [
  { status: EVENT_STATUS.DRAFT, label: 'Nháp' },
  { status: EVENT_STATUS.REGISTRATION_OPEN, label: 'Mở đăng ký' },
  { status: EVENT_STATUS.REGISTRATION_CLOSED, label: 'Đóng đăng ký' },
  { status: EVENT_STATUS.ALLOCATION_PROCESSING, label: 'Phân bổ' },
  { status: EVENT_STATUS.INFORMATION_PUBLISHED, label: 'Công bố' },
  { status: EVENT_STATUS.EVENT_STARTED, label: 'Diễn ra' },
  { status: EVENT_STATUS.COMPLETED, label: 'Kết thúc' },
]

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
  // Phân xe (docs/05-allocation-algorithm.md §6)
  NO_BUS_CAPACITY: { label: 'Không đủ ghế xe', tone: 'rose', blocking: true },
  MISSING_FLIGHT_ASSIGNMENT: { label: 'Chưa có chuyến bay', tone: 'rose', blocking: true },
  MIXED_FLIGHT_ON_BUS: { label: 'Xe chở khách nhiều chuyến bay', tone: 'amber', blocking: false },
  BUS_UNDERUTILIZED: { label: 'Xe quá vắng', tone: 'amber', blocking: false },
  PICKUP_MISMATCH: { label: 'Lệch điểm đón', tone: 'amber', blocking: false },
  SURPLUS_BUS: { label: 'Xe thừa', tone: 'slate', blocking: false },
  // Xếp phòng (docs/05-allocation-algorithm.md §7)
  NO_ROOM_CAPACITY: { label: 'Hết giường đúng giới tính', tone: 'rose', blocking: true },
  MISSING_GENDER: { label: 'Chưa khai giới tính', tone: 'rose', blocking: true },
  PINNED_ROOM_CONFLICT: { label: 'Xếp tay sai phòng', tone: 'amber', blocking: false },
  ALONE_FROM_TEAM: { label: 'Ở phòng không có đồng đội', tone: 'slate', blocking: false },
  HEALTH_NOTE: { label: 'Có ghi chú sức khoẻ', tone: 'slate', blocking: false },
  EMPTY_ROOM: { label: 'Phòng trống', tone: 'slate', blocking: false },
}

export const SEVERITY_TONES = {
  error: 'rose',
  warning: 'amber',
  info: 'slate',
}

/** Ngưỡng đổi màu cột slot: gần đầy là cảnh báo, đầy là chặn. */
export const LOAD_WARNING_RATIO = 0.9

/** --- My Journey --- */

export const JOURNEY_PARTS = {
  flights: { label: 'Chuyến bay', hint: 'Mã chuyến, giờ bay, sân bay' },
  buses: { label: 'Xe đưa đón', hint: 'Giờ tập trung, điểm đón, Trưởng xe' },
  accommodation: { label: 'Khách sạn', hint: 'Số phòng, người ở cùng' },
  gala: { label: 'Gala Dinner', hint: 'Bàn và ghế của bạn' },
}

/** Vì sao một phần hành trình còn trống — khớp `pending_reasons` của /journey/me. */
export const PENDING_REASON_LABELS = {
  not_published: 'Đang chờ BTC công bố',
  not_assigned: 'BTC chưa xếp phần này cho bạn',
  not_participating: 'Chỉ dành cho CBNV xác nhận tham gia',
}

export const ANNOUNCEMENT_SEVERITY_META = {
  info: { label: 'Thông tin', tone: 'blue' },
  warning: { label: 'Lưu ý', tone: 'amber' },
  urgent: { label: 'Khẩn', tone: 'rose' },
}

export const ROOM_TYPE_LABELS = {
  single: 'Phòng đơn',
  twin: 'Phòng 2 giường',
  double: 'Giường đôi',
  triple: 'Phòng 3 người',
  quad: 'Phòng 4 người',
}

/** Giới tính được ở phòng — khớp `RoomGenderPolicy` ở backend. */
export const ROOM_POLICY_META = {
  male: { label: 'Nam', tone: 'blue' },
  female: { label: 'Nữ', tone: 'rose' },
  any: { label: 'Không giới hạn', tone: 'slate' },
}

/** --- Dashboard BTC --- */

/** Hệ quả của việc chuyển sang từng trạng thái — hiện trong hộp thoại xác nhận. */
export const STATUS_CHANGE_HINTS = {
  draft: 'Kỳ trở về nháp: CBNV không còn thấy form đăng ký.',
  registration_open: 'CBNV gửi và sửa được đăng ký.',
  registration_closed: 'CBNV không sửa được đăng ký nữa. BTC bắt đầu ghi được kết quả phân bổ.',
  allocation_processing: 'BTC chạy và chỉnh phân bổ. CBNV chưa thấy kết quả trong My Journey.',
  information_published: 'CBNV thấy ngay chuyến bay, xe, phòng của mình trong My Journey.',
  event_started: 'Chương trình bắt đầu diễn ra.',
  completed: 'Kết thúc kỳ. Không chuyển tiếp được nữa.',
}

/** Tên dễ đọc cho `audit_logs.action`. Action lạ thì hiện nguyên mã. */
export const AUDIT_ACTION_LABELS = {
  'event.created': 'Tạo kỳ',
  'event.updated': 'Sửa thông tin kỳ',
  'event.activated': 'Đặt kỳ đang chạy',
  'event.settings_updated': 'Sửa cấu hình kỳ',
  'event.status_changed': 'Đổi trạng thái kỳ',
  'registration.submitted': 'CBNV gửi đăng ký',
  'registration.updated': 'CBNV sửa đăng ký',
  'registration.cancelled': 'CBNV tự huỷ đăng ký',
  'registration.cancellation_requested': 'CBNV gửi yêu cầu huỷ',
  'registration.cancellation_withdrawn': 'CBNV rút yêu cầu huỷ',
  'registration.cancellation_approved': 'BTC duyệt huỷ đăng ký',
  'registration.cancellation_rejected': 'BTC từ chối yêu cầu huỷ',
  'registration.cancelled_by_admin': 'BTC huỷ đăng ký thay CBNV',
  'registration.reregistered': 'CBNV đăng ký lại sau khi huỷ',
  'team.leader_changed': 'Đổi Trưởng nhóm',
  'flight.created': 'Thêm chuyến bay',
  'flight.updated': 'Sửa chuyến bay',
  'flight.deleted': 'Xoá chuyến bay',
  'flight.allocated': 'Chạy phân bổ chuyến bay',
  'flight_assignment.moved': 'Chuyển người sang chuyến khác',
  'flight_assignment.bulk_moved': 'Chuyển nhiều người sang chuyến khác',
  'flight_assignment.removed': 'Bỏ xếp chuyến bay',
  'bus.created': 'Thêm xe',
  'bus.updated': 'Sửa xe',
  'bus.deleted': 'Xoá xe',
  'bus.leader_changed': 'Đổi Trưởng xe',
  'bus.allocated': 'Chạy phân xe',
  'bus_assignment.moved': 'Chuyển người sang xe khác',
  'hotel.created': 'Thêm khách sạn',
  'hotel.updated': 'Sửa khách sạn',
  'hotel.deleted': 'Xoá khách sạn',
  'room.created': 'Thêm phòng',
  'room.updated': 'Sửa phòng',
  'room.deleted': 'Xoá phòng',
  'room.imported': 'Import danh sách phòng',
  'room.allocated': 'Chạy xếp phòng tự động',
  'room_assignment.created': 'Xếp phòng',
  'room_assignment.moved': 'Chuyển phòng',
  'room_assignment.captain_changed': 'Đổi trưởng phòng',
  'room_assignment.removed': 'Bỏ xếp phòng',
  'reminder.sent': 'Gửi email nhắc CBNV',
  'user.created': 'Tạo tài khoản CBNV',
  'user.updated': 'Sửa hồ sơ CBNV',
  'user.role_changed': 'Đổi vai trò',
  'user.activated': 'Mở lại tài khoản',
  'user.deactivated': 'Khoá tài khoản',
  'user.password_reset': 'Đặt lại mật khẩu',
  'user.unlocked': 'Gỡ khoá đăng nhập',
  'user.imported': 'Import danh sách CBNV',
  'export.downloaded': 'Tải file Excel',
  'email.resent': 'Gửi lại email lỗi',
  'bus_assignment.created': 'Xếp tay một người lên xe',
  'bus_assignment.removed': 'Bỏ xếp xe',
  'gala.layout_created': 'Tạo sơ đồ Gala',
  'gala.layout_updated': 'Sửa sơ đồ Gala',
  'gala.table_created': 'Thêm bàn Gala',
  'gala.table_updated': 'Sửa bàn Gala',
  'gala.table_deleted': 'Xoá bàn Gala',
  'gala.drawn': 'Bốc thăm thứ tự team',
  'gala.selection_opened': 'Mở chọn ghế Gala',
  'gala.turn_ended': 'Kết thúc lượt chọn ghế',
  'gala.selection_finalized': 'Chốt chỗ ngồi Gala',
  'gala.seats_confirmed': 'Team xác nhận ghế Gala',
  'gala.member_assigned': 'Xếp thành viên vào ghế Gala',
  'gala.seat_updated': 'BTC sửa ghế Gala',
  'gala.selection_reopened': 'Mở lại chọn ghế Gala',
  'gala.members_auto_assigned': 'Xếp ngẫu nhiên thành viên vào ghế Gala',
  'rag.reindexed': 'Nạp lại kiến thức trợ lý',
}

/** Các loại email nhắc BTC gửi chủ động — khớp `ReminderKind` ở backend. */
export const REMINDER_KINDS = {
  missing_documents: {
    title: 'Nhắc bổ sung CCCD / ngày sinh',
    short: 'Thiếu giấy tờ',
    description: 'Gửi cho người đã xác nhận tham gia nhưng hồ sơ chưa đủ để xuất vé máy bay.',
  },
  not_registered: {
    title: 'Nhắc gửi đăng ký',
    short: 'Chưa phản hồi',
    description: 'Gửi cho CBNV chưa gửi đăng ký (tham gia hay không) trong kỳ này.',
  },
}

/** Huỷ đăng ký theo giai đoạn kỳ — khớp `CancellationMode` / `CancellationStatus` ở backend. */
export const CANCELLATION_MODE_LABELS = {
  self: 'Tự huỷ trước công bố',
  request: 'Yêu cầu sau công bố',
  admin: 'BTC huỷ ngoại lệ',
}

export const CANCELLATION_STATUS_META = {
  pending: { label: 'Chờ duyệt', tone: 'amber' },
  approved: { label: 'Đã huỷ', tone: 'rose' },
  rejected: { label: 'Từ chối', tone: 'slate' },
  withdrawn: { label: 'CBNV đã rút', tone: 'slate' },
}

/** Nhóm chỗ đã gỡ khi huỷ — khớp khoá `released` do `cancellation_service` trả về. */
export const RELEASED_LABELS = {
  flights: 'Vé máy bay',
  buses: 'Xe',
  room: 'Phòng',
  gala: 'Ghế Gala',
  roles: 'Bỏ vai trò',
}

/** Trạng thái dòng nhật ký email — khớp `EmailStatus` ở backend. */
export const EMAIL_STATUS_META = {
  sent: { label: 'Đã gửi', tone: 'emerald' },
  failed: { label: 'Lỗi', tone: 'rose' },
  queued: { label: 'Đang chờ', tone: 'blue' },
}

/** Khoá cache của TanStack Query — gom lại để invalidate không bị gõ sai chuỗi. */
export const QUERY_KEYS = {
  me: ['auth', 'me'],
  activeEvent: ['events', 'active'],
  eventOverview: (id) => ['events', id, 'overview'],
  myRegistration: ['registrations', 'me'],
  journey: ['journey', 'me'],
  dashboard: ['admin', 'dashboard'],
  reminders: (kind) => ['admin', 'reminders', kind],
  emailLogs: (params) => ['admin', 'email-logs', 'list', params],
  emailStats: ['admin', 'email-logs', 'stats'],
  buses: (filters) => ['buses', 'list', filters],
  busAssignments: (filters) => ['bus-assignments', filters],
  busPassengers: (busId) => ['buses', busId, 'passengers'],
  hotels: ['hotels'],
  rooms: (filters) => ['rooms', 'list', filters],
  roomSummary: ['rooms', 'summary'],
  occupants: (roomId) => ['rooms', roomId, 'occupants'],
  roomAssignments: (filters) => ['room-assignments', filters],
  users: (params) => ['users', 'list', params],
  user: (userId) => ['users', 'detail', userId],
  registrationStats: ['registrations', 'stats'],
  registrations: (filters) => ['registrations', 'list', filters],
  cancellationsAll: ['admin', 'cancellations'],
  cancellations: (params) => ['admin', 'cancellations', params],
  formOptions: ['master-data', 'registration-form'],
  terms: (eventId) => ['events', eventId, 'terms'],
  flights: (filters) => ['flights', 'list', filters],
  flightSummary: ['flights', 'summary'],
  passengers: (flightId) => ['flights', flightId, 'passengers'],
  assignments: (filters) => ['flight-assignments', filters],
  teams: ['master-data', 'teams'],
  galaView: ['gala', 'view'],
  galaMembers: (teamId) => ['gala', 'members', teamId ?? 'mine'],
  galaMyTurn: ['gala', 'my-turn'],
  chatStatus: ['chat', 'status'],
  chatSessions: ['chat', 'sessions'],
  chatMessages: (sessionId) => ['chat', 'messages', sessionId],
  ragStatus: ['admin', 'rag', 'status'],
}

/** --- Trợ lý Team Building (chatbot) --- */

export const CHAT_ASSISTANT_NAME = 'Tibi'
export const CHAT_MAX_LENGTH = 1000

/** Câu hỏi gợi ý — đều là thông tin chung BTC công bố, không phải dữ liệu cá nhân. */
export const CHAT_SUGGESTIONS = [
  'Lịch trình ngày đầu tiên có gì?',
  'Gala Dinner tổ chức ở đâu, mấy giờ?',
  'Huỷ đăng ký có bị phạt không?',
  'Khách sạn nhận phòng lúc mấy giờ?',
  'Cần chuẩn bị giấy tờ gì để đi máy bay?',
]

/** Loại nguồn trích dẫn — khớp `source_type` backend gắn cho từng tài liệu trong knowledge base. */
export const CHAT_SOURCE_LABELS = {
  terms: 'Quy định',
  faq: 'Hỏi đáp',
  guide: 'Hướng dẫn',
  itinerary: 'Lịch trình',
  announcement: 'Thông báo',
  event: 'Thông tin chương trình',
  flight: 'Chuyến bay',
  bus: 'Xe đưa đón',
  hotel: 'Khách sạn',
  gala: 'Gala Dinner',
}

/** --- Gala Dinner --- */

/** Khớp `GalaSelectionStatus` ở backend. */
export const GALA_SELECTION_STATUS_META = {
  closed: { label: 'Chưa bốc thăm', tone: 'slate' },
  drawing: { label: 'Đã bốc thăm — chờ mở chọn ghế', tone: 'amber' },
  open: { label: 'Đang chọn ghế', tone: 'emerald' },
  finalized: { label: 'Đã chốt chỗ ngồi', tone: 'brand' },
}

/** Khớp `DrawStatus` ở backend. */
export const GALA_DRAW_STATUS_META = {
  waiting: { label: 'Chờ lượt', tone: 'slate' },
  active: { label: 'Đang chọn', tone: 'emerald' },
  done: { label: 'Xong', tone: 'brand' },
  skipped: { label: 'Bỏ lượt', tone: 'rose' },
}

/** Trạng thái ghế trả về từ `/gala/layout`. `selected` là ghế đang chọn trên màn hình, chưa giữ. */
export const GALA_SEAT_STATE_LABELS = {
  available: 'Trống',
  selected: 'Đang chọn',
  held_by_me: 'Team bạn đang giữ',
  held_by_other: 'Team khác đang giữ',
  taken: 'Đã có team',
  unavailable: 'Không khả dụng',
}

export const GALA_STAGE_POSITION_LABELS = {
  top: 'Phía trên',
  bottom: 'Phía dưới',
  left: 'Bên trái',
  right: 'Bên phải',
}
