import { renderToString } from 'react-dom/server'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { ToastProvider } from '../src/context/ToastContext'
import { QUERY_KEYS } from '../src/utils/constants'
import DashboardPage from '../src/pages/admin/DashboardPage'
import RegistrationsPage from '../src/pages/admin/RegistrationsPage'
import StatusControl from '../src/pages/admin/dashboard/StatusControl'
import { OPTIONS } from './fixtures.js'

const CHECKLIST = [
  { key: 'registration_closed', label: 'Đóng đăng ký', done: true, required: true, detail: null, link: null },
  { key: 'flight_documents', label: 'Đủ giấy tờ để xuất vé', done: false, required: true, detail: '1 người thiếu CCCD hoặc ngày sinh.', link: '/admin/registrations?missing_documents=true' },
  { key: 'flight_capacity', label: 'Đủ ghế máy bay hai chiều', done: false, required: true, detail: 'Chiều về chưa có chuyến', link: '/admin/flights' },
  { key: 'buses_assigned', label: 'Xếp xe cho người cần xe', done: false, required: true, detail: 'HN → Sân bay: còn 1 người', link: null },
  { key: 'emails_ok', label: 'Email gửi không lỗi', done: false, required: false, detail: '2 email gửi lỗi', link: null },
]

const DASHBOARD = {
  generated_at: '2026-09-13T02:00:00+00:00',
  event: {
    id: 1, code: 'TB2026', name: 'Team Building 2026', destination: 'Phú Quốc',
    start_date: '2026-10-15', end_date: '2026-10-17', status: 'allocation_processing',
    status_label: 'Đang phân bổ', registration_closes_at: '2026-09-25T10:00:00+00:00', is_published: false,
    next_statuses: [
      { status: 'information_published', label: 'Đã công bố thông tin', is_forward: true, requires_reason: false },
      { status: 'registration_closed', label: 'Đã đóng đăng ký', is_forward: false, requires_reason: true },
    ],
  },
  registrations: {
    total_users: 122, submitted: 104, not_submitted: 15, participating: 99, not_participating: 5,
    cancelled: 3, by_shift: { CA1: 38, CA2: 61 }, bus_demand_by_leg: { CITY_TO_AIRPORT: 72 },
    missing_flight_documents: 1,
  },
  teams: [
    { team_id: 1, code: 'IT-HN', name: 'Công nghệ HN', color: '#7c3aed', members: 20, submitted: 18, participating: 17, not_participating: 1, cancelled: 0, not_submitted: 2, response_rate: 0.9, participation_rate: 0.85 },
    { team_id: 2, code: 'HR', name: 'Nhân sự', color: null, members: 8, submitted: 8, participating: 8, not_participating: 0, cancelled: 0, not_submitted: 0, response_rate: 1, participation_rate: 1 },
    { team_id: null, code: null, name: 'Chưa gán team', color: null, members: 2, submitted: 0, participating: 0, not_participating: 0, cancelled: 0, not_submitted: 2, response_rate: 0, participation_rate: 0 },
  ],
  flights: [
    { direction: 'outbound', flights: 4, usable_capacity: 108, assigned: 99, unassigned: 0, remaining: 9, shortfall: 0 },
    { direction: 'return', flights: 0, usable_capacity: 0, assigned: 0, unassigned: 99, remaining: 0, shortfall: 99 },
  ],
  buses: [
    { trip_leg_id: 1, code: 'CITY_TO_AIRPORT', name: 'HN → Sân bay', direction: 'outbound', demand: 72, buses: 2, capacity: 90, assigned: 71, unassigned: 1, shortfall: 0 },
    { trip_leg_id: 2, code: 'AIRPORT_TO_HOTEL', name: 'Sân bay → Khách sạn', direction: 'outbound', demand: 0, buses: 0, capacity: 0, assigned: 0, unassigned: 0, shortfall: 0 },
  ],
  rooms: { participants: 99, assigned: 40, unassigned: 59, total_beds: 110, uncovered: 2 },
  gala: { configured: false, tables: 0, seats: 0, assigned: 0 },
  emails: { total: 30, queued: 1, sent: 27, failed: 2, by_template: {}, email_enabled: false },
  checklist: CHECKLIST,
  ready_to_publish: false,
  recent_activity: [
    { id: 9, action: 'event.status_changed', entity_type: 'event', entity_id: 1, actor_name: 'Trưởng BTC', reason: null, created_at: '2026-09-13T01:00:00+00:00' },
    { id: 8, action: 'flight_assignment.moved', entity_type: 'flight_assignment', entity_id: 4, actor_name: 'Trưởng BTC', reason: 'Đổi ca theo xin phép', created_at: '2026-09-12T10:00:00+00:00' },
    { id: 7, action: 'something.unknown', entity_type: 'x', entity_id: null, actor_name: null, reason: null, created_at: '2026-09-12T09:00:00+00:00' },
  ],
}

const EMPTY_DASHBOARD = {
  ...DASHBOARD,
  event: { ...DASHBOARD.event, status: 'completed', status_label: 'Đã kết thúc', next_statuses: [] },
  registrations: { ...DASHBOARD.registrations, participating: 0, missing_flight_documents: 0, by_shift: {}, bus_demand_by_leg: {} },
  teams: [],
  flights: [],
  buses: [],
  rooms: { participants: 0, assigned: 0, unassigned: 0, total_beds: 0, uncovered: 0 },
  gala: { configured: true, tables: 12, seats: 120, assigned: 0 },
  recent_activity: [],
}

const REGISTRATIONS = {
  items: [
    {
      id: 7, event_id: 1, user_id: 1, is_participating: true, not_participating_reason: null,
      shift: { id: 1, code: 'CA1', name: 'Ca 1' }, departure_location_id: 1, wish_note: null, companion_count: 0,
      status: 'submitted', submitted_at: '2026-09-11T15:35:48+00:00', cancelled_at: null, cancel_reason: null,
      penalty_applied: false, can_edit: false, agreed_terms_version: 'v1', has_consent: true,
      bus_needs: [{ trip_leg_id: 1, trip_leg_code: 'CITY_TO_AIRPORT', trip_leg_name: 'HN → Sân bay', needs_bus: true, pickup_point_id: 1, pickup_point_name: 'Keangnam', note: null }],
      user: { id: 1, employee_code: 'NV001', full_name: 'Trần Thanh Chi', email: 'chi@company.vn', phone: null, gender: 'female', team_id: 1, team_name: 'Team Alpha', work_location_id: 1, can_fly: false },
    },
    {
      id: 8, event_id: 1, user_id: 2, is_participating: false, not_participating_reason: 'Việc gia đình',
      shift: null, departure_location_id: null, wish_note: null, companion_count: 0,
      status: 'cancelled', submitted_at: '2026-09-10T15:35:48+00:00', cancelled_at: '2026-09-12T01:00:00+00:00', cancel_reason: 'Bận',
      penalty_applied: true, can_edit: false, agreed_terms_version: null, has_consent: false, bus_needs: [],
      user: { id: 2, employee_code: null, full_name: 'Lê Hữu Nam', email: 'nam@company.vn', phone: null, gender: 'male', team_id: null, team_name: null, work_location_id: null, can_fly: true },
    },
  ],
  total: 42, page: 1, page_size: 20,
}

function render(label, element, seed = () => {}, entry = '/') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  seed(queryClient)
  try {
    const html = renderToString(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[entry]}>
          <ToastProvider>{element}</ToastProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    )
    console.log(`${label}: OK (${html.length} ký tự)`)
  } catch (error) {
    console.log(`${label}: LỖI -> ${error.message}`)
    console.log(String(error.stack).split('\n').slice(0, 6).join('\n'))
  }
}

render('Dashboard BTC — đang phân bổ', <DashboardPage />, (qc) => qc.setQueryData(QUERY_KEYS.dashboard, DASHBOARD))
render('Dashboard BTC — kỳ đã kết thúc, chưa có dữ liệu', <DashboardPage />, (qc) =>
  qc.setQueryData(QUERY_KEYS.dashboard, EMPTY_DASHBOARD),
)
render('Nút chuyển trạng thái', <StatusControl event={DASHBOARD.event} checklist={CHECKLIST} />)

render('Danh sách đăng ký', <RegistrationsPage />, (qc) => {
  qc.setQueryData(QUERY_KEYS.formOptions, OPTIONS)
  qc.setQueryData(QUERY_KEYS.registrations({ page: 1, page_size: 20 }), REGISTRATIONS)
})
render(
  'Danh sách đăng ký — lọc thiếu giấy tờ, trống',
  <RegistrationsPage />,
  (qc) => {
    qc.setQueryData(QUERY_KEYS.formOptions, OPTIONS)
    qc.setQueryData(
      QUERY_KEYS.registrations({ missing_documents: 'true', page: 1, page_size: 20 }),
      { items: [], total: 0, page: 1, page_size: 20 },
    )
  },
  '/admin/registrations?missing_documents=true',
)
