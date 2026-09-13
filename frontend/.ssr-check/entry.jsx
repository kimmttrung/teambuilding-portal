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

render('Hồ sơ cá nhân', <ProfilePage />, seedBase)

await import('./steps.jsx')
await import('./admin.jsx')
await import('./journey.jsx')
await import('./dashboard.jsx')
