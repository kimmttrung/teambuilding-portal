import { renderToString } from 'react-dom/server'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { ToastProvider } from '../src/context/ToastContext'
import { QUERY_KEYS } from '../src/utils/constants'
import MyJourneyPage from '../src/pages/user/MyJourneyPage'
import SchedulePage from '../src/pages/user/SchedulePage'
import { EVENT, REGISTRATION } from './fixtures.js'

const BASE = {
  event: {
    id: 1, code: 'TB2026', name: 'Team Building 2026', status: 'information_published',
    destination: 'Phú Quốc', start_date: '2026-10-15', end_date: '2026-10-17', is_published: true,
  },
  profile: {
    user_id: 1, full_name: 'Nguyễn Văn Đi', display_name: null, employee_code: 'NV001',
    avatar_url: null, phone: '0911000111', team: { id: 1, name: 'Công nghệ HN', color: '#7c3aed' },
  },
  registration: {
    status: 'submitted', is_participating: true, requested_shift_code: 'CA1', requested_shift_name: 'Ca 1',
  },
  itinerary: [
    { id: 1, day_date: '2026-10-15', start_time: '04:30', end_time: null, title: 'Tập trung tại điểm đón', description: null, location: 'Theo xe đã phân công', audience: 'all' },
    { id: 2, day_date: '2026-10-15', start_time: '06:30', end_time: '08:40', title: 'Bay HAN – PQC', description: null, location: 'Nội Bài', audience: 'CA1' },
    { id: 3, day_date: '2026-10-16', start_time: '18:30', end_time: null, title: 'Gala Dinner', description: 'Dress code: trắng', location: 'Sảnh Pearl', audience: 'all' },
  ],
  announcements: [
    { id: 1, title: 'Đổi giờ tập trung xe XE-01', content: '**Có mặt sớm 15 phút**.\n- Mang CCCD', severity: 'urgent', published_at: '2026-09-12T06:00:00+00:00' },
    { id: 2, title: 'Chào mừng', content: 'Nội dung chung', severity: 'info', published_at: '2026-09-10T00:00:00+00:00' },
  ],
}

const FULL = {
  ...BASE,
  flights: {
    outbound: { flight_code: 'VN1234', airline: 'Vietnam Airlines', direction: 'outbound', shift_code: 'CA1', departure_airport: 'HAN', arrival_airport: 'PQC', departure_time: '2026-10-15T06:30:00+00:00', arrival_time: '2026-10-15T08:40:00+00:00', seat_number: '12A', ticket_code: null },
    return: { flight_code: 'VN1235', airline: 'Vietnam Airlines', direction: 'return', shift_code: 'CA1', departure_airport: 'PQC', arrival_airport: 'HAN', departure_time: '2026-10-17T15:00:00+00:00', arrival_time: '2026-10-17T17:10:00+00:00', seat_number: null, ticket_code: 'ABC123' },
  },
  buses: [
    {
      trip_leg: { id: 1, code: 'CITY_TO_AIRPORT', name: 'HN → Sân bay', direction: 'outbound', leg_date: '2026-10-15', display_order: 1 },
      bus_code: 'XE-01', plate_number: '29B-123.45', gather_time: '2026-10-15T04:30:00+00:00', departure_time: '2026-10-15T04:45:00+00:00',
      pickup_point: { name: 'Toà nhà Keangnam', address: 'Phạm Hùng', map_url: 'javascript:alert(1)' },
      dropoff_point: 'Sân bay Nội Bài', leader: { name: 'Lê Trưởng Xe', phone: '0933 000 333' }, driver: null, linked_flight_code: 'VN1234',
    },
    {
      trip_leg: { id: 3, code: 'HOTEL_TO_AIRPORT', name: 'Khách sạn → Sân bay', direction: 'return', leg_date: '2026-10-17', display_order: 3 },
      bus_code: 'XE-07', plate_number: null, gather_time: null, departure_time: null,
      pickup_point: null, dropoff_point: null, leader: null, driver: null, linked_flight_code: null,
    },
  ],
  accommodation: {
    hotel_name: 'Sunset Beach Resort', address: 'Trần Hưng Đạo, Phú Quốc', phone: '0297 3999 888', map_url: null,
    check_in_at: '2026-10-15T07:00:00+00:00', check_out_at: '2026-10-17T05:00:00+00:00',
    room_number: '1204', room_type: 'twin', floor: '12', is_room_captain: true,
    roommates: [{ full_name: 'Trần Văn Cùng', phone: '0922000222', team_name: 'Công nghệ HN', is_room_captain: false }],
  },
  gala: { name: 'Gala Dinner', venue: 'Sảnh Pearl', starts_at: '2026-10-16T11:30:00+00:00', table_code: 'B07', table_name: 'Bàn Công nghệ', seat_number: 3 },
  pending: [],
  pending_reasons: {},
}

const NOT_PUBLISHED = {
  ...BASE,
  event: { ...BASE.event, status: 'allocation_processing', is_published: false },
  flights: { outbound: null, return: null },
  buses: [],
  accommodation: null,
  gala: null,
  pending: ['flights', 'buses', 'accommodation', 'gala'],
  pending_reasons: { flights: 'not_published', buses: 'not_published', accommodation: 'not_published', gala: 'not_published' },
}

const PARTIAL = {
  ...FULL,
  flights: { ...FULL.flights, return: null },
  accommodation: null,
  pending: ['flights', 'accommodation'],
  pending_reasons: { flights: 'not_assigned', accommodation: 'not_assigned' },
}

const NOT_PARTICIPATING = {
  ...NOT_PUBLISHED,
  registration: null,
  itinerary: [],
  announcements: [],
  pending_reasons: { flights: 'not_participating', buses: 'not_participating', accommodation: 'not_participating', gala: 'not_participating' },
}

function render(label, element, journey, registration = REGISTRATION) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  queryClient.setQueryData(QUERY_KEYS.activeEvent, { ...EVENT, is_published: journey.event.is_published })
  queryClient.setQueryData(QUERY_KEYS.myRegistration, registration)
  queryClient.setQueryData(QUERY_KEYS.journey, journey)
  try {
    const html = renderToString(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <ToastProvider>{element}</ToastProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    )
    // Link bản đồ `javascript:` do dữ liệu nhập vào phải bị chặn, không được lọt ra href.
    if (html.includes('javascript:')) throw new Error('href javascript: lọt ra HTML')
    console.log(`${label}: OK (${html.length} ký tự)`)
  } catch (error) {
    console.log(`${label}: LỖI -> ${error.message}`)
    console.log(String(error.stack).split('\n').slice(0, 6).join('\n'))
  }
}

render('My Journey — đã công bố, xếp đủ', <MyJourneyPage />, FULL)
render('My Journey — chưa công bố', <MyJourneyPage />, NOT_PUBLISHED)
render('My Journey — xếp chưa đủ', <MyJourneyPage />, PARTIAL)
render('My Journey — chưa đăng ký', <MyJourneyPage />, NOT_PARTICIPATING, null)
const CANCELLED = { ...REGISTRATION, status: 'cancelled', can_edit: false, cancel_policy: null }
render('My Journey — đã huỷ, còn đăng ký lại được', <MyJourneyPage />, NOT_PARTICIPATING, { ...CANCELLED, reregister_allowed: true })
render('My Journey — đã huỷ sau công bố', <MyJourneyPage />, NOT_PARTICIPATING, { ...CANCELLED, reregister_allowed: false })
render('Lịch trình — có dữ liệu', <SchedulePage />, FULL)
render('Lịch trình — trống', <SchedulePage />, NOT_PARTICIPATING, null)
