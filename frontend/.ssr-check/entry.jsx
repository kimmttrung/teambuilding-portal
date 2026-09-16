import { renderToString } from 'react-dom/server'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { ToastProvider } from '../src/context/ToastContext'
import { QUERY_KEYS } from '../src/utils/constants'
import RegisterEventPage from '../src/pages/user/RegisterEventPage'
import ProfilePage from '../src/pages/user/ProfilePage'

const EVENT = {
  id: 1, code: 'TB2026', name: 'Team Building 2026', destination: 'Phú Quốc',
  start_date: '2026-10-15', end_date: '2026-10-17', status: 'registration_open',
  status_label: 'Đang mở đăng ký', registration_opens_at: '2026-09-01T00:00:00+00:00',
  registration_closes_at: '2026-09-25T10:00:00+00:00', terms_version: 'v1',
  banner_url: null, can_register: true, is_published: false,
}

const OPTIONS = {
  teams: [{ id: 1, code: 'T1', name: 'Team Alpha', is_active: true, member_count: 10 }],
  departments: [{ id: 1, code: 'IT', name: 'Công nghệ', display_order: 0, is_active: true }],
  work_locations: [
    { id: 1, code: 'HN', name: 'Hà Nội', city: 'Hà Nội', airport_code: 'HAN', display_order: 1, is_active: true },
    { id: 2, code: 'HCM', name: 'TP. Hồ Chí Minh', city: 'TP.HCM', airport_code: 'SGN', display_order: 2, is_active: true },
  ],
  shifts: [
    { id: 1, event_id: 1, code: 'CA1', name: 'Ca 1 – bay sáng', description: 'Bay sáng sớm', earliest_departure: '05:30', display_order: 1 },
    { id: 2, event_id: 1, code: 'CA2', name: 'Ca 2 – bay chiều', description: null, earliest_departure: '14:00', display_order: 2 },
  ],
  trip_legs: [
    { id: 1, event_id: 1, code: 'CITY_TO_AIRPORT', name: 'HN/HCM → Sân bay', direction: 'outbound', leg_date: '2026-10-15', is_airport_linked: true, display_order: 1 },
    { id: 2, event_id: 1, code: 'AIRPORT_TO_HOTEL', name: 'Sân bay → Khách sạn', direction: 'outbound', leg_date: '2026-10-15', is_airport_linked: true, display_order: 2 },
  ],
  pickup_points: [
    { id: 1, event_id: 1, trip_leg_id: 1, work_location_id: 1, name: 'Toà nhà Keangnam', address: 'Phạm Hùng', map_url: null, display_order: 0 },
  ],
}

const REGISTRATION = {
  id: 7, event_id: 1, user_id: 1, is_participating: true, not_participating_reason: null,
  shift: { id: 1, code: 'CA1', name: 'Ca 1 – bay sáng' }, departure_location_id: 1,
  wish_note: null, companion_count: 0, status: 'submitted',
  submitted_at: '2026-09-11T15:35:48+00:00', cancelled_at: null, cancel_reason: null,
  penalty_applied: false, can_edit: true, agreed_terms_version: 'v1',
  bus_needs: [
    { trip_leg_id: 1, trip_leg_code: 'CITY_TO_AIRPORT', trip_leg_name: 'HN/HCM → Sân bay', needs_bus: true, pickup_point_id: 1, pickup_point_name: 'Toà nhà Keangnam', note: null },
    { trip_leg_id: 2, trip_leg_code: 'AIRPORT_TO_HOTEL', trip_leg_name: 'Sân bay → Khách sạn', needs_bus: false, pickup_point_id: null, pickup_point_name: null, note: null },
  ],
}

function render(label, element, seed) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  seed(queryClient)
  try {
    const html = renderToString(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
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

const seedBase = (queryClient) => {
  queryClient.setQueryData(QUERY_KEYS.activeEvent, EVENT)
  queryClient.setQueryData(QUERY_KEYS.formOptions, OPTIONS)
}

render('Đăng ký — chưa có đăng ký (hồ sơ thiếu CCCD)', <RegisterEventPage />, (qc) => {
  seedBase(qc)
  qc.setQueryData(QUERY_KEYS.myRegistration, null)
})

render('Đăng ký — đang sửa đăng ký đã gửi', <RegisterEventPage />, (qc) => {
  seedBase(qc)
  qc.setQueryData(QUERY_KEYS.myRegistration, REGISTRATION)
})

render('Đăng ký — đã đóng đăng ký', <RegisterEventPage />, (qc) => {
  qc.setQueryData(QUERY_KEYS.activeEvent, { ...EVENT, can_register: false, status: 'registration_closed' })
  qc.setQueryData(QUERY_KEYS.formOptions, OPTIONS)
  qc.setQueryData(QUERY_KEYS.myRegistration, { ...REGISTRATION, can_edit: false })
})

const closed = { ...EVENT, can_register: false, status: 'information_published', is_published: true }
const PENDING_REQUEST = {
  id: 3, mode: 'request', status: 'pending', reason: 'Trùng lịch công tác', requested_at: '2026-09-14T02:00:00+00:00',
  decided_at: null, decision_note: null, penalty_applied: false, penalty_note: null,
}

for (const [label, registration] of [
  ['Đăng ký đã chốt — tự huỷ trước công bố', { ...REGISTRATION, can_edit: false, cancel_policy: 'self', latest_cancellation: null }],
  ['Đăng ký đã chốt — sau công bố, gửi yêu cầu huỷ', { ...REGISTRATION, can_edit: false, cancel_policy: 'request', latest_cancellation: null }],
  ['Đăng ký đã chốt — yêu cầu huỷ đang chờ duyệt', { ...REGISTRATION, can_edit: false, cancel_policy: 'request', latest_cancellation: PENDING_REQUEST }],
  ['Đăng ký đã chốt — BTC đã từ chối yêu cầu', { ...REGISTRATION, can_edit: false, cancel_policy: 'request', latest_cancellation: { ...PENDING_REQUEST, status: 'rejected', decision_note: 'Vé đã xuất' } }],
  ['Đăng ký đã chốt — chương trình đã bắt đầu', { ...REGISTRATION, can_edit: false, cancel_policy: 'contact_btc', latest_cancellation: null }],
]) {
  render(label, <RegisterEventPage />, (qc) => {
    qc.setQueryData(QUERY_KEYS.activeEvent, closed)
    qc.setQueryData(QUERY_KEYS.formOptions, OPTIONS)
    qc.setQueryData(QUERY_KEYS.myRegistration, registration)
  })
}

render('Hồ sơ cá nhân', <ProfilePage />, seedBase)

await import('./steps.jsx')
await import('./admin.jsx')
await import('./journey.jsx')
await import('./dashboard.jsx')
await import('./buses.jsx')
await import('./rooms.jsx')
await import('./users.jsx')
await import('./gala.jsx')
await import('./chat.jsx')
await import('./itinerary.jsx')
await import('./announcements.jsx')
await import('./settings.jsx')
await import('./landing.jsx')
