import { renderToString } from 'react-dom/server'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { ToastProvider } from '../src/context/ToastContext'
import { QUERY_KEYS } from '../src/utils/constants'
import FlightsPage from '../src/pages/admin/FlightsPage'
import FlightBoardPage from '../src/pages/admin/FlightBoardPage'
import AllocationPreviewModal from '../src/pages/admin/flights/AllocationPreviewModal'
import FlightFormModal from '../src/pages/admin/flights/FlightFormModal'
import MoveDialog from '../src/pages/admin/flights/MoveDialog'
import FlagList from '../src/components/admin/FlagList'
import EventSwitcher from '../src/components/layout/EventSwitcher'
import { EVENT, OPTIONS } from './fixtures.js'

const FLIGHTS = [
  {
    id: 1, event_id: 1, flight_code: 'VN1234', airline: 'Vietnam Airlines', direction: 'outbound',
    shift_id: 1, shift_code: 'CA1', shift_name: 'Ca 1 – bay sáng',
    departure_airport: 'HAN', arrival_airport: 'PQC',
    departure_time: '2026-10-15T06:30:00+00:00', arrival_time: '2026-10-15T08:40:00+00:00',
    capacity: 60, reserved_slots: 2, usable_capacity: 58, assigned_count: 49, remaining_slots: 9,
    load_ratio: 0.845, note: null, is_active: true,
    created_at: '2026-09-01T00:00:00+00:00', updated_at: '2026-09-01T00:00:00+00:00',
  },
  {
    id: 2, event_id: 1, flight_code: 'VN1250', airline: 'Vietnam Airlines', direction: 'outbound',
    shift_id: 2, shift_code: 'CA2', shift_name: 'Ca 2 – bay chiều',
    departure_airport: 'HAN', arrival_airport: 'PQC',
    departure_time: '2026-10-15T19:15:00+00:00', arrival_time: '2026-10-15T21:25:00+00:00',
    capacity: 52, reserved_slots: 2, usable_capacity: 50, assigned_count: 50, remaining_slots: 0,
    load_ratio: 1, note: null, is_active: true,
    created_at: '2026-09-01T00:00:00+00:00', updated_at: '2026-09-01T00:00:00+00:00',
  },
  {
    id: 3, event_id: 1, flight_code: 'VN1299', airline: null, direction: 'return',
    shift_id: null, shift_code: null, shift_name: null,
    departure_airport: 'PQC', arrival_airport: 'HAN',
    departure_time: '2026-10-17T15:00:00+00:00', arrival_time: '2026-10-17T17:10:00+00:00',
    capacity: 40, reserved_slots: 0, usable_capacity: 40, assigned_count: 0, remaining_slots: 40,
    load_ratio: 0, note: 'Chuyến dự phòng', is_active: false,
    created_at: '2026-09-01T00:00:00+00:00', updated_at: '2026-09-01T00:00:00+00:00',
  },
]

const SUMMARY = {
  participants: 99,
  directions: [
    {
      direction: 'outbound', flights: 2, capacity: 112, reserved: 4, usable_capacity: 108,
      assigned: 99, remaining: 9, shortfall: 0,
      by_shift: [
        { shift_id: 1, shift_code: 'CA1', shift_name: 'Ca 1', flights: 1, capacity: 60, usable_capacity: 58, assigned: 49, remaining: 9, requested: 38, shortfall: 0 },
        { shift_id: 2, shift_code: 'CA2', shift_name: 'Ca 2', flights: 1, capacity: 52, usable_capacity: 50, assigned: 50, remaining: 0, requested: 61, shortfall: 11 },
      ],
    },
    {
      direction: 'return', flights: 0, capacity: 0, reserved: 0, usable_capacity: 0,
      assigned: 0, remaining: 0, shortfall: 99, by_shift: [],
    },
  ],
}

const ASSIGNMENTS = {
  items: [
    {
      id: 11, registration_id: 101, user_id: 1, full_name: 'Trần Thanh Chi', employee_code: 'NV001',
      team_id: 1, team_name: 'Team Alpha', flight_id: 1, flight_code: 'VN1234', direction: 'outbound',
      flight_shift_id: 1, requested_shift_id: 1, requested_shift_code: 'CA1', shift_mismatch: false,
      shift_locked: false, seat_number: null, ticket_code: null, assignment_mode: 'auto',
      assigned_at: '2026-09-12T04:00:00+00:00', assigned_by: 2, note: null, has_flight_documents: true,
    },
    {
      id: 12, registration_id: 102, user_id: 2, full_name: 'Lê Hữu Nam', employee_code: 'NV002',
      team_id: 1, team_name: 'Team Alpha', flight_id: 2, flight_code: 'VN1250', direction: 'outbound',
      flight_shift_id: 2, requested_shift_id: 1, requested_shift_code: 'CA1', shift_mismatch: true,
      shift_locked: true, seat_number: null, ticket_code: null, assignment_mode: 'manual',
      assigned_at: '2026-09-12T05:00:00+00:00', assigned_by: 2, note: null, has_flight_documents: false,
    },
  ],
  total: 2, page: 1, page_size: 200,
}

const PARTICIPANTS = {
  items: [
    { id: 101, user: { id: 1, full_name: 'Trần Thanh Chi', team_id: 1, team_name: 'Team Alpha', can_fly: true } },
    { id: 102, user: { id: 2, full_name: 'Lê Hữu Nam', team_id: 1, team_name: 'Team Alpha', can_fly: false } },
    { id: 103, user: { id: 3, full_name: 'Đặng Quang Thắng', team_id: 2, team_name: 'Team Beta', can_fly: false } },
  ],
  total: 3, page: 1, page_size: 200,
}

const PREVIEW_FLAGS = [
  { type: 'UNASSIGNED', severity: 'error', message: 'Đặng Quang Thắng không còn chỗ trên chiều này.', registration_id: 103, team_id: 2, flight_id: null, details: {} },
  { type: 'MISSING_ID_CARD', severity: 'error', message: 'Lê Hữu Nam thiếu CCCD hoặc ngày sinh nên không xuất được vé.', registration_id: 102, team_id: 1, flight_id: null, details: {} },
  { type: 'SHIFT_NOT_SATISFIED', severity: 'warning', message: 'Lê Hữu Nam xin ca khác nhưng được xếp chuyến VN1250.', registration_id: 102, team_id: 1, flight_id: 2, details: {} },
  { type: 'TEAM_SPLIT', severity: 'warning', message: 'Team Alpha bị tách thành 2 chuyến (1 + 1).', registration_id: null, team_id: 1, flight_id: null, details: { chunks: [1, 1] } },
  { type: 'TINY_CHUNK', severity: 'info', message: 'Chỉ 1 người của team Alpha đi riêng một chuyến.', registration_id: null, team_id: 1, flight_id: 2, details: { chunk_size: 1 } },
]

function render(label, element, seed = () => {}) {
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

const seedFlights = (qc) => {
  qc.setQueryData(QUERY_KEYS.activeEvent, EVENT)
  qc.setQueryData(QUERY_KEYS.formOptions, OPTIONS)
  qc.setQueryData(QUERY_KEYS.flights({}), FLIGHTS)
  qc.setQueryData(QUERY_KEYS.flightSummary, SUMMARY)
}

render('Quản lý chuyến bay', <FlightsPage />, seedFlights)

render('Quản lý chuyến bay — chưa có chuyến nào', <FlightsPage />, (qc) => {
  seedFlights(qc)
  qc.setQueryData(QUERY_KEYS.flights({}), [])
})

render('Bảng điều chỉnh', <FlightBoardPage />, (qc) => {
  seedFlights(qc)
  qc.setQueryData(QUERY_KEYS.flights({ direction: 'outbound', is_active: true }), FLIGHTS.slice(0, 2))
  qc.setQueryData(QUERY_KEYS.assignments({ direction: 'outbound', page_size: 200 }), ASSIGNMENTS)
  qc.setQueryData(
    QUERY_KEYS.registrations({ is_participating: true, status: 'submitted', page_size: 200 }),
    PARTICIPANTS,
  )
})

render('Bảng điều chỉnh — chiều chưa có chuyến', <FlightBoardPage />, (qc) => {
  seedFlights(qc)
  qc.setQueryData(QUERY_KEYS.flights({ direction: 'outbound', is_active: true }), [])
  qc.setQueryData(QUERY_KEYS.assignments({ direction: 'outbound', page_size: 200 }), { items: [], total: 0, page: 1, page_size: 200 })
  qc.setQueryData(
    QUERY_KEYS.registrations({ is_participating: true, status: 'submitted', page_size: 200 }),
    PARTICIPANTS,
  )
})

render('Modal thêm chuyến bay', <FlightFormModal open flight={null} shifts={OPTIONS.shifts} onClose={() => {}} />)
render('Modal sửa chuyến bay', <FlightFormModal open flight={FLIGHTS[0]} shifts={OPTIONS.shifts} onClose={() => {}} />)
render('Modal phân bổ (chưa chạy)', <AllocationPreviewModal open shiftCodes={{ 1: 'CA1', 2: 'CA2' }} onClose={() => {}} />)
render(
  'Hộp thoại chuyển người',
  <MoveDialog
    open
    people={[{ registration_id: 101, full_name: 'Trần Thanh Chi' }]}
    sourceLabel="VN1234"
    targetFlight={FLIGHTS[0]}
    flightOptions={FLIGHTS}
    onClose={() => {}}
    onConfirm={() => {}}
  />,
)
render('Danh sách flag (5 loại)', <FlagList flags={PREVIEW_FLAGS} />)

// --- Bộ chọn kỳ (docs/13 task 6) ---

const SECOND_EVENT = {
  ...EVENT,
  id: 2, code: 'TB2027', name: 'Team Building 2027 – Đà Nẵng', destination: 'Đà Nẵng',
  start_date: '2027-04-16', end_date: '2027-04-18',
}

const seedEvents = (events) => (qc) => {
  qc.setQueryData(QUERY_KEYS.activeEvent, EVENT)
  qc.setQueryData(QUERY_KEYS.selectableEvents, events)
}

render('Bộ chọn kỳ — 2 kỳ song song', <EventSwitcher />, seedEvents([EVENT, SECOND_EVENT]))
render('Bộ chọn kỳ — thu gọn (mobile)', <EventSwitcher compact />, seedEvents([EVENT, SECOND_EVENT]))
// Một kỳ thì không hiện gì: ô chọn có đúng một lựa chọn chỉ làm rối thanh bên.
render('Bộ chọn kỳ — chỉ 1 kỳ, ẩn', <EventSwitcher />, seedEvents([EVENT]))
render('Bộ chọn kỳ — chưa tải xong', <EventSwitcher />)
