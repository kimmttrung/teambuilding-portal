import { renderToString } from 'react-dom/server'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { ToastProvider } from '../src/context/ToastContext'
import { QUERY_KEYS } from '../src/utils/constants'
import RoomsPage from '../src/pages/admin/RoomsPage'
import HotelFormModal from '../src/pages/admin/rooms/HotelFormModal'
import RoomDetailModal from '../src/pages/admin/rooms/RoomDetailModal'
import RoomFormModal from '../src/pages/admin/rooms/RoomFormModal'
import RoomImportModal from '../src/pages/admin/rooms/RoomImportModal'
import RoomPickerDialog from '../src/pages/admin/rooms/RoomPickerDialog'

const STAMP = '2026-09-12T04:00:00+00:00'

const HOTELS = [
  {
    id: 1, event_id: 1, name: 'Sunset Beach Resort', address: 'Trần Hưng Đạo, Phú Quốc', phone: '0297 3999 888',
    check_in_at: '2026-10-15T07:00:00+00:00', check_out_at: '2026-10-17T05:00:00+00:00',
    map_url: 'javascript:alert(1)', note: null, room_count: 4, bed_count: 9, assigned_count: 3,
    created_at: STAMP, updated_at: STAMP,
  },
  {
    id: 2, event_id: 1, name: 'Seashells Hotel', address: null, phone: null, check_in_at: null, check_out_at: null,
    map_url: null, note: null, room_count: 1, bed_count: 2, assigned_count: 0, created_at: STAMP, updated_at: STAMP,
  },
]

const room = (id, hotelId, number, floor, policy, capacity, occupied, extra = {}) => ({
  id, hotel_id: hotelId, hotel_name: hotelId === 1 ? 'Sunset Beach Resort' : 'Seashells Hotel',
  room_number: number, room_type: capacity === 3 ? 'triple' : 'twin', capacity, floor, gender_policy: policy,
  note: null, occupied, remaining: capacity - occupied, has_captain: occupied > 0, ...extra,
})

const ROOMS = [
  room(101, 1, '1204', '12', 'male', 2, 2),
  room(102, 1, '1205', '12', 'female', 3, 1, { has_captain: false }),
  room(103, 1, '901', '9', 'male', 2, 0),
  room(104, 1, 'VIP', null, 'any', 2, 0, { room_type: null, note: 'Phòng dự phòng' }),
  room(201, 2, '301', '3', 'female', 2, 0),
]

const SUMMARY = {
  participants: 6, assigned: 3, unassigned: 3, total_beds: 11, uncovered: 1,
  by_policy: [
    { gender_policy: 'male', rooms: 2, beds: 4, occupied: 2, remaining: 2, participants: 5, shortfall: 1 },
    { gender_policy: 'female', rooms: 2, beds: 5, occupied: 1, remaining: 4, participants: 1, shortfall: 0 },
    { gender_policy: 'any', rooms: 1, beds: 2, occupied: 0, remaining: 2, participants: 0, shortfall: 0 },
  ],
}

const ASSIGNMENTS = {
  items: [7, 8, 9].map((registrationId, index) => ({
    id: 300 + index, registration_id: registrationId, user_id: index + 1, full_name: `Người ${index + 1}`,
    employee_code: null, gender: 'male', team_id: 1, team_name: 'Team Alpha', room_id: 101, room_number: '1204',
    hotel_id: 1, hotel_name: 'Sunset Beach Resort', is_room_captain: index === 0, assignment_mode: 'manual', assigned_at: STAMP,
  })),
  total: 3, page: 1, page_size: 200,
}

const person = (id, name, gender, team = 'Team Beta') => ({ id, user: { id: id + 100, full_name: name, team_id: 2, team_name: team, gender, can_fly: true }, bus_needs: [] })

const PARTICIPANTS = {
  items: [
    person(7, 'Người 1', 'male'), person(8, 'Người 2', 'male'), person(9, 'Người 3', 'female'),
    person(10, 'Đặng Quang Thắng', 'male'), person(11, 'Phạm Thu Hà', 'female'), person(12, 'Alex Nguyễn', null, null),
  ],
  total: 6, page: 1, page_size: 200,
}

const OCCUPANTS = [
  {
    assignment_id: 300, registration_id: 7, user_id: 1, full_name: 'Người 1', employee_code: 'NV001', gender: 'male',
    team_id: 1, team_name: 'Team Alpha', is_room_captain: true, assignment_mode: 'manual', assigned_at: STAMP,
    dietary_restriction: 'Chay', has_health_note: true,
  },
  {
    assignment_id: 301, registration_id: 8, user_id: 2, full_name: 'Người 2', employee_code: null, gender: 'male',
    team_id: 1, team_name: 'Team Alpha', is_room_captain: false, assignment_mode: 'auto', assigned_at: STAMP,
    dietary_restriction: null, has_health_note: false,
  },
]

const UNASSIGNED = [
  { registration_id: 10, full_name: 'Đặng Quang Thắng', team_name: 'Team Beta', gender: 'male' },
  { registration_id: 11, full_name: 'Phạm Thu Hà', team_name: 'Team Beta', gender: 'female' },
  { registration_id: 12, full_name: 'Alex Nguyễn', team_name: null, gender: null },
]

function seed(qc, { hotels = HOTELS } = {}) {
  qc.setQueryData(QUERY_KEYS.hotels, hotels)
  qc.setQueryData(QUERY_KEYS.rooms({}), hotels.length ? ROOMS : [])
  qc.setQueryData(QUERY_KEYS.roomSummary, SUMMARY)
  qc.setQueryData(QUERY_KEYS.roomAssignments({ page_size: 200 }), ASSIGNMENTS)
  qc.setQueryData(QUERY_KEYS.registrations({ is_participating: true, status: 'submitted', page_size: 200 }), PARTICIPANTS)
  qc.setQueryData(QUERY_KEYS.occupants(101), OCCUPANTS)
  qc.setQueryData(QUERY_KEYS.occupants(104), [])
}

function render(label, element, seedFn = () => {}, entry = '/admin/rooms') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  seedFn(queryClient)
  try {
    const html = renderToString(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[entry]}>
          <ToastProvider>{element}</ToastProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    )
    // Link bản đồ `javascript:` do BTC nhập phải bị chặn, không được lọt ra href.
    if (html.includes('javascript:')) throw new Error('href javascript: lọt ra HTML')
    console.log(`${label}: OK (${html.length} ký tự)`)
  } catch (error) {
    console.log(`${label}: LỖI -> ${error.message}`)
    console.log(String(error.stack).split('\n').slice(0, 6).join('\n'))
  }
}

render('Khách sạn & phòng — có dữ liệu', <RoomsPage />, (qc) => seed(qc))
render('Khách sạn & phòng — lọc phòng nam còn chỗ', <RoomsPage />, (qc) => seed(qc), '/admin/rooms?policy=male&available=1')
render('Khách sạn & phòng — khách sạn thứ hai', <RoomsPage />, (qc) => seed(qc), '/admin/rooms?hotel=2')
render('Khách sạn & phòng — chưa có khách sạn', <RoomsPage />, (qc) => seed(qc, { hotels: [] }))
render('Chi tiết phòng đầy người', <RoomDetailModal room={ROOMS[0]} rooms={ROOMS} unassigned={UNASSIGNED} onEdit={() => {}} onClose={() => {}} />, (qc) => seed(qc))
render('Chi tiết phòng trống không giới hạn', <RoomDetailModal room={ROOMS[3]} rooms={ROOMS} unassigned={UNASSIGNED} onEdit={() => {}} onClose={() => {}} />, (qc) => seed(qc))
render('Chọn phòng cho người nam', <RoomPickerDialog title="Xếp phòng" person={UNASSIGNED[0]} rooms={ROOMS} onConfirm={() => {}} onClose={() => {}} />)
render('Chọn phòng cho người chưa khai giới tính (hết phòng)', <RoomPickerDialog title="Xếp phòng" person={UNASSIGNED[2]} rooms={ROOMS.slice(0, 3)} onConfirm={() => {}} onClose={() => {}} />)
render('Import phân phòng', <RoomImportModal onClose={() => {}} />)
render('Form thêm khách sạn', <HotelFormModal hotel={null} onClose={() => {}} />)
render('Form sửa khách sạn', <HotelFormModal hotel={HOTELS[0]} onClose={() => {}} />)
render('Form thêm phòng', <RoomFormModal room={null} hotels={HOTELS} defaultHotelId={1} onClose={() => {}} />)
render('Form sửa phòng đang có người', <RoomFormModal room={ROOMS[0]} hotels={HOTELS} defaultHotelId={1} onClose={() => {}} />)
