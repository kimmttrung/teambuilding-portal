import { renderToString } from 'react-dom/server'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { ToastProvider } from '../src/context/ToastContext'
import { QUERY_KEYS } from '../src/utils/constants'
import PeoplePage from '../src/pages/admin/PeoplePage'
import PersonLocator from '../src/components/admin/PersonLocator'
import { highlightTargets } from '../src/hooks/usePeople'

const LOCATION = {
  user_id: 7,
  full_name: 'Bùi Quang Trung',
  email: 'trung@company.vn',
  employee_code: 'NV007',
  phone: '0915409396',
  team_id: 1,
  team_name: 'Kinh doanh Hà Nội',
  team_color: '#4f46e5',
  registration_id: 30,
  registration_status: 'submitted',
  is_participating: true,
  shift: { id: 1, code: 'CA1', name: 'Ca 1 – bay sáng' },
  flights: {
    outbound: {
      flight_id: 2, flight_code: 'VN1250', airline: 'Vietnam Airlines',
      departure_airport: 'HAN', arrival_airport: 'PQC',
      departure_time: '2026-10-15T12:15:00+00:00', arrival_time: '2026-10-15T14:25:00+00:00',
      seat_number: '12A', assignment_mode: 'auto',
    },
    return: null,
  },
  buses: [
    {
      trip_leg_id: 1, leg_code: 'CITY_TO_AIRPORT', leg_name: 'HN/HCM → Sân bay', direction: 'outbound',
      bus_id: 3, bus_code: 'XE-03', pickup_point_id: 1, pickup_name: 'Toà nhà Keangnam',
      departure_time: '2026-10-14T21:45:00+00:00', assignment_mode: 'manual',
    },
    {
      trip_leg_id: 2, leg_code: 'AIRPORT_TO_CITY', leg_name: 'Sân bay → HN/HCM', direction: 'return',
      bus_id: null, bus_code: null, pickup_point_id: null, pickup_name: null,
      departure_time: null, assignment_mode: null,
    },
  ],
  room: {
    room_id: 5, room_number: '805', floor: '8', room_type: 'twin',
    hotel_id: 1, hotel_name: 'Sunset Beach Resort', is_room_captain: true, assignment_mode: 'auto',
  },
  gala: { seat_id: 87, seat_number: 7, table_id: 9, table_code: 'B09', table_name: null },
}

const CANCELLED = {
  ...LOCATION,
  user_id: 8,
  full_name: 'Lê Thị Huỷ',
  registration_status: 'cancelled',
  is_participating: true,
  flights: { outbound: null, return: null },
  buses: LOCATION.buses.map((leg) => ({ ...leg, bus_id: null, bus_code: null, pickup_name: null })),
  room: null,
  gala: null,
}

const MATCHES = [
  {
    user_id: 7, full_name: 'Bùi Quang Trung', email: 'trung@company.vn',
    employee_code: 'NV007', team_name: 'Kinh doanh Hà Nội',
    registration_status: 'submitted', is_participating: true,
  },
  {
    user_id: 9, full_name: 'Bùi Quang Trứ', email: 'tru@company.vn',
    employee_code: 'NV009', team_name: 'Marketing',
    registration_status: null, is_participating: false,
  },
]

function render(label, element, seed = () => {}, entry = '/admin/people') {
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

const seedLocation = (location) => (qc) => {
  qc.setQueryData(QUERY_KEYS.personLocation(location.user_id), location)
}

render('Tra cứu lộ trình — chưa chọn ai', <PeoplePage />)
render('Tra cứu lộ trình — đủ chỗ, thiếu 1 chặng xe', <PeoplePage />, seedLocation(LOCATION), '/admin/people?person=7')
render('Tra cứu lộ trình — người đã huỷ', <PeoplePage />, seedLocation(CANCELLED), '/admin/people?person=8')
render('Tra cứu lộ trình — đang tải', <PeoplePage />, () => {}, '/admin/people?person=7')

render('Thanh tìm người — chưa tìm gì', <PersonLocator />)
render('Thanh tìm người — đã chọn người', <PersonLocator />, seedLocation(LOCATION), '/admin/flights?person=7')
render(
  'Thanh tìm người — có gợi ý',
  <PersonLocator />,
  (qc) => qc.setQueryData(QUERY_KEYS.peopleSearch('bui quang'), MATCHES),
)
render('Thanh tìm người — người đã huỷ', <PersonLocator />, seedLocation(CANCELLED), '/admin/rooms?person=8')

function check(label, ok) {
  console.log(`${label}: ${ok ? 'OK' : 'LỖI'}`)
}

// Một người đi nhiều chặng nên phải tô được NHIỀU thẻ xe cùng lúc, không phải một.
const targets = highlightTargets(LOCATION)
check('Tô đỏ — gom đúng id từng loại',
  targets.flights.has(2) && targets.buses.has(3) && targets.rooms.has(5) && targets.seats.has(87))
check('Tô đỏ — bỏ qua phần chưa xếp', targets.flights.size === 1 && targets.buses.size === 1)
check('Tô đỏ — không có ai đang tra cứu thì rỗng', highlightTargets(null).flights.size === 0)
