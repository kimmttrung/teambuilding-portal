import { renderToString } from 'react-dom/server'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { ToastProvider } from '../src/context/ToastContext'
import { QUERY_KEYS } from '../src/utils/constants'
import BusesPage from '../src/pages/admin/BusesPage'
import BusCard from '../src/pages/admin/buses/BusCard'
import BusAllocationModal from '../src/pages/admin/buses/BusAllocationModal'
import BusFormModal from '../src/pages/admin/buses/BusFormModal'
import BusPassengersModal from '../src/pages/admin/buses/BusPassengersModal'
import BusPickerDialog from '../src/pages/admin/buses/BusPickerDialog'
import LeaderDialog from '../src/pages/admin/buses/LeaderDialog'
import { EVENT, OPTIONS } from './fixtures.js'

const STAMP = '2026-09-12T04:00:00+00:00'

const BUSES = [
  {
    id: 11, event_id: 1, trip_leg_id: 1, trip_leg_code: 'CITY_TO_AIRPORT', trip_leg_name: 'HN/HCM → Sân bay',
    direction: 'outbound', airport_linked: true, bus_code: 'XE-01', plate_number: '29B-123.45', capacity: 2,
    assigned_count: 2, remaining_seats: 0, load_ratio: 1, pickup_point_id: 1, pickup_point_name: 'Toà nhà Keangnam',
    dropoff_point: 'Nội Bài T1', gather_time: '2026-10-15T04:30:00+00:00', departure_time: '2026-10-15T04:45:00+00:00',
    leader_user_id: 1, leader_name: 'Trần Thanh Chi', leader_phone: '0915409396', driver_name: 'Bác Hùng',
    driver_phone: '0900000000', linked_flight_id: 1, linked_flight_code: 'VN1234', note: null,
    created_at: STAMP, updated_at: STAMP,
  },
  {
    id: 12, event_id: 1, trip_leg_id: 1, trip_leg_code: 'CITY_TO_AIRPORT', trip_leg_name: 'HN/HCM → Sân bay',
    direction: 'outbound', airport_linked: true, bus_code: 'XE-02', plate_number: null, capacity: 45,
    assigned_count: 0, remaining_seats: 45, load_ratio: 0, pickup_point_id: null, pickup_point_name: null,
    dropoff_point: null, gather_time: null, departure_time: null, leader_user_id: null, leader_name: null,
    leader_phone: null, driver_name: null, driver_phone: null, linked_flight_id: null, linked_flight_code: null,
    note: null, created_at: STAMP, updated_at: STAMP,
  },
]

const ASSIGNMENTS = {
  items: [
    {
      id: 101, registration_id: 7, user_id: 1, full_name: 'Trần Thanh Chi', employee_code: 'NV001', phone: '0915409396',
      team_id: 1, team_name: 'Team Alpha', bus_id: 11, bus_code: 'XE-01', trip_leg_id: 1, pickup_point_id: 1,
      pickup_point_name: 'Toà nhà Keangnam', flight_code: 'VN1234', pickup_mismatch: false, flight_mismatch: false,
      assignment_mode: 'auto', assigned_at: STAMP,
    },
    {
      id: 102, registration_id: 8, user_id: 2, full_name: 'Lê Hữu Nam', employee_code: null, phone: null,
      team_id: null, team_name: null, bus_id: 11, bus_code: 'XE-01', trip_leg_id: 1, pickup_point_id: 2,
      pickup_point_name: 'Trụ sở Hoàn Kiếm', flight_code: 'VN1250', pickup_mismatch: true, flight_mismatch: true,
      assignment_mode: 'manual', assigned_at: STAMP,
    },
  ],
  total: 2, page: 1, page_size: 200,
}

const need = (legId, pickupId, pickupName) => ({
  trip_leg_id: legId, trip_leg_code: 'CITY_TO_AIRPORT', trip_leg_name: 'HN/HCM → Sân bay', needs_bus: true,
  pickup_point_id: pickupId, pickup_point_name: pickupName, note: null,
})

const PARTICIPANTS = {
  items: [
    { id: 7, user: { id: 1, full_name: 'Trần Thanh Chi', team_id: 1, team_name: 'Team Alpha', can_fly: true }, bus_needs: [need(1, 1, 'Toà nhà Keangnam')] },
    { id: 8, user: { id: 2, full_name: 'Lê Hữu Nam', team_id: null, team_name: null, can_fly: false }, bus_needs: [need(1, 2, 'Trụ sở Hoàn Kiếm')] },
    { id: 9, user: { id: 3, full_name: 'Đặng Quang Thắng', team_id: 2, team_name: 'Team Beta', can_fly: true }, bus_needs: [need(1, 1, 'Toà nhà Keangnam'), need(2, null, null)] },
    { id: 10, user: { id: 4, full_name: 'Phạm Thu Hà', team_id: 2, team_name: 'Team Beta', can_fly: true }, bus_needs: [need(1, null, null)] },
  ],
  total: 4, page: 1, page_size: 200,
}

const FLIGHTS = [
  { id: 1, flight_code: 'VN1234', direction: 'outbound', departure_time: '2026-10-15T06:30:00+00:00' },
  { id: 3, flight_code: 'VN1235', direction: 'return', departure_time: '2026-10-17T15:00:00+00:00' },
]

const PARTICIPANTS_KEY = { is_participating: true, status: 'submitted', page_size: 200 }

function seedPage(qc, { options = OPTIONS, buses = BUSES } = {}) {
  qc.setQueryData(QUERY_KEYS.activeEvent, EVENT)
  qc.setQueryData(QUERY_KEYS.formOptions, options)
  qc.setQueryData(QUERY_KEYS.busUnassigned({ trip_leg_id: 1 }), {
    pages: [{ items: [{ id: 109, registration_id: 9, user_id: 3, full_name: 'Đặng Quang Thắng', team_name: 'Team Beta', pickup_point_id: 1, pickup_point_name: 'Toà nhà Keangnam' }, { id: 110, registration_id: 10, user_id: 4, full_name: 'Phạm Thu Hà', team_name: 'Team Beta', pickup_point_id: null }], total: 2, page: 1, page_size: 200 }],
    pageParams: [1],
  })
  qc.setQueryData(QUERY_KEYS.users({ is_active: true, q: undefined, page: 1, page_size: 50 }), { items: [{ id: 1, full_name: 'Trần Thanh Chi', employee_code: 'NV001', is_active: true }], total: 1, page: 1, page_size: 50 })
  qc.setQueryData(QUERY_KEYS.buses({ trip_leg_id: 1 }), buses)
  qc.setQueryData(QUERY_KEYS.buses({}), buses)
  qc.setQueryData(QUERY_KEYS.busAssignments({ trip_leg_id: 1, page_size: 200 }), buses.length ? ASSIGNMENTS : { items: [], total: 0, page: 1, page_size: 200 })
  qc.setQueryData(QUERY_KEYS.registrations(PARTICIPANTS_KEY), PARTICIPANTS)
  qc.setQueryData(QUERY_KEYS.flights({}), FLIGHTS)
  qc.setQueryData(QUERY_KEYS.busAssignments({ bus_id: 11, page_size: 200 }), ASSIGNMENTS)
}

function render(label, element, seed = () => {}, entry = '/admin/buses', verify = () => {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, retryOnMount: false } } })
  seed(queryClient)
  try {
    const html = renderToString(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[entry]}>
          <ToastProvider>{element}</ToastProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    )
    verify(html)
    console.log(`${label}: OK (${html.length} ký tự)`)
  } catch (error) {
    process.exitCode = 1
    console.log(`${label}: LỖI -> ${error.message}`)
    console.log(String(error.stack).split('\n').slice(0, 6).join('\n'))
  }
}

render('Xe đưa đón — có xe, có người chưa xếp', <BusesPage />, (qc) => seedPage(qc))
render('Xe đưa đón — chặng chưa có xe', <BusesPage />, (qc) => seedPage(qc, { buses: [] }))
render('Xe đưa đón — kỳ chưa có chặng', <BusesPage />, (qc) => seedPage(qc, { options: { ...OPTIONS, trip_legs: [] } }))
render(
  'Xe đưa đón — xe lệch giờ bay',
  <BusesPage />,
  (qc) =>
    seedPage(qc, {
      buses: [
        {
          ...BUSES[0],
          timing_issues: [
            'xe chạy lúc 15/10/2026 06:59, chuyến VN1234 cất cánh lúc 15/10/2026 07:00 — chỉ cách nhau 1 phút, cần tối thiểu 30 phút',
          ],
        },
        BUSES[1],
      ],
    }),
)
render(
  'Thẻ xe — hai lỗi giờ cùng lúc',
  <BusCard
    bus={{
      ...BUSES[0],
      timing_issues: [
        'xe đón có mặt lúc 15/10/2026 09:30, chuyến VN1234 hạ cánh lúc 15/10/2026 09:00 — xe tới muộn 30 phút, chỉ cho phép muộn 5 phút',
        'xe rời sân bay lúc 15/10/2026 10:00, 60 phút sau khi chuyến VN1250 hạ cánh (15/10/2026 09:00) — không chờ quá 45 phút; xe đón nhiều chuyến hạ cánh cách xa nhau thì phải tách xe',
      ],
    }}
    onPassengers={() => {}}
    onLeader={() => {}}
    onEdit={() => {}}
    onDelete={() => {}}
  />,
)
render('Form thêm xe', <BusFormModal bus={null} legs={OPTIONS.trip_legs} pickupPoints={OPTIONS.pickup_points} defaultLegId={1} onClose={() => {}} />, (qc) => seedPage(qc))
render('Form sửa xe đang có khách', <BusFormModal bus={BUSES[0]} legs={OPTIONS.trip_legs} pickupPoints={OPTIONS.pickup_points} defaultLegId={1} onClose={() => {}} />, (qc) => seedPage(qc))
render('Phân xe tự động (chưa chạy)', <BusAllocationModal legs={OPTIONS.trip_legs} defaultLegId={1} onClose={() => {}} />)
render('Hành khách xe (có người lệch)', <BusPassengersModal bus={BUSES[0]} buses={BUSES} onClose={() => {}} />, (qc) => seedPage(qc))
render('Trưởng xe — CBNV', <LeaderDialog bus={BUSES[0]} participants={PARTICIPANTS.items} onClose={() => {}} />, (qc) => seedPage(qc))
render('Trưởng xe — người ngoài', <LeaderDialog bus={{ ...BUSES[1], leader_name: 'HDV Minh', leader_phone: '0988000111' }} participants={PARTICIPANTS.items} onClose={() => {}} />, (qc) => seedPage(qc))
render('Chọn xe cho người chưa có xe', <BusPickerDialog title="Xếp xe" person={{ registration_id: 10, full_name: 'Phạm Thu Hà', team_name: 'Team Beta', pickup_point_id: 1, pickup_point_name: 'Toà nhà Keangnam' }} buses={BUSES} onConfirm={() => {}} onClose={() => {}} />)
render('Chọn xe khi mọi xe đã đầy', <BusPickerDialog title="Chuyển xe" person={{ registration_id: 7, full_name: 'Trần Thanh Chi' }} buses={[BUSES[0]]} currentBusId={12} onConfirm={() => {}} onClose={() => {}} />)

function mustInclude(html, value) {
  if (!html.includes(value)) throw new Error(`Thiếu nội dung: ${value}`)
}
render('F4 — tổng chưa xếp không bị giới hạn 200 dòng', <BusesPage />, (qc) => {
  seedPage(qc)
  const key = QUERY_KEYS.busUnassigned({ trip_leg_id: 1 })
  const current = qc.getQueryData(key)
  qc.setQueryData(key, { ...current, pages: [{ ...current.pages[0], total: 205 }] })
}, '/admin/buses?leg=1', (html) => { mustInclude(html, '205'); mustInclude(html, 'Xem thêm') })
render('F4 — chặng URL sai quay về chặng hợp lệ', <BusesPage />, (qc) => seedPage(qc), '/admin/buses?leg=999', (html) => { mustInclude(html, 'XE-01'); mustInclude(html, 'Đặng Quang Thắng') })
render('F4 — lỗi danh sách chưa xếp không hiện tất cả đã có xe', <BusesPage />, (qc) => {
  seedPage(qc)
  const query = qc.getQueryCache().find({ queryKey: QUERY_KEYS.busUnassigned({ trip_leg_id: 1 }) })
  query.setState({ data: undefined, status: 'error', error: new Error('Không tải được người cần xe') })
}, '/admin/buses?leg=1', (html) => {
  mustInclude(html, 'Không tải được người cần xe')
  if (html.includes('Mọi người cần xe ở chặng này đều đã có xe.')) throw new Error('Hiện trạng thái rỗng khi API lỗi')
})
