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
import RoomAllocationModal from '../src/pages/admin/rooms/RoomAllocationModal'

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
    id: registrationId, registration_id: registrationId, user_id: index + 1, full_name: `Người ${index + 1}`,
    employee_code: null, gender: index === 2 ? 'female' : 'male', team_id: 1, team_name: 'Team Alpha', room_id: index === 2 ? 102 : 101, room_number: index === 2 ? '1205' : '1204',
    hotel_id: 1, hotel_name: 'Sunset Beach Resort', is_room_captain: index === 0, assignment_mode: 'manual', assigned_at: STAMP,
  })),
  total: 3, page: 1, page_size: 200,
}

const OCCUPANTS = [
  {
    assignment_id: 7, registration_id: 7, user_id: 1, full_name: 'Người 1', employee_code: 'NV001', gender: 'male',
    team_id: 1, team_name: 'Team Alpha', is_room_captain: true, assignment_mode: 'manual', assigned_at: STAMP,
    dietary_restriction: 'Chay', has_health_note: true,
  },
  {
    assignment_id: 8, registration_id: 8, user_id: 2, full_name: 'Người 2', employee_code: null, gender: 'male',
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
  qc.setQueryData(QUERY_KEYS.roomBoardAssignments, ASSIGNMENTS.items)
  qc.setQueryData(QUERY_KEYS.roomUnassigned({ q: undefined }), { pages: [{ items: UNASSIGNED, total: 3, page: 1, page_size: 200 }], pageParams: [1] })
  qc.setQueryData(QUERY_KEYS.roomUnassigned({ gender: undefined, q: undefined }), { pages: [{ items: UNASSIGNED, total: 3, page: 1, page_size: 200 }], pageParams: [1] })
  qc.setQueryData(QUERY_KEYS.activeEvent, { id: 1, status: 'registration_closed' })
  qc.setQueryData(QUERY_KEYS.occupants(101), OCCUPANTS)
  qc.setQueryData(QUERY_KEYS.occupants(104), [])
}

function render(label, element, seedFn = () => {}, entry = '/admin/rooms', verify = () => {}) {
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
    verify(html)
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
render('Xếp phòng tự động (chưa chạy)', <RoomAllocationModal onClose={() => {}} />)

const assertHtml = (html, condition, message) => {
  if (!condition) throw new Error(message)
}
render('Phòng — lọc tầng qua URL', <RoomsPage />, seed, '/admin/rooms?floor=9', (html) =>
  assertHtml(
    html,
    html.includes('901') && !html.includes('aria-label="Phòng 1204'),
    'Không lọc đúng tầng',
  ),
)
render(
  'Phòng — khách sạn URL không tồn tại',
  <RoomsPage />,
  seed,
  '/admin/rooms?hotel=999',
  (html) => assertHtml(html, html.includes('Phòng 1204'), 'Không trở về khách sạn hợp lệ'),
)
render('Phòng — chưa ghi tầng', <RoomsPage />, seed, '/admin/rooms?floor=__none__', (html) =>
  assertHtml(
    html,
    html.includes('Phòng VIP') && !html.includes('aria-label="Phòng 1204'),
    'Sai bộ lọc tầng chưa ghi',
  ),
)
render(
  'Phòng — danh sách hơn 200 người',
  <RoomsPage />,
  (qc) => {
    seed(qc)
    qc.setQueryData(QUERY_KEYS.roomUnassigned({ q: undefined }), {
      pages: [{ items: UNASSIGNED, total: 203, page: 1, page_size: 200 }],
      pageParams: [1],
    })
  },
  '/admin/rooms',
  (html) =>
    assertHtml(
      html,
      html.includes('203') && html.includes('Tải thêm người'),
      'Thiếu tổng hoặc nút phân trang',
    ),
)
render(
  'Chọn phòng — không nhận nữ vào phòng nam',
  <RoomPickerDialog
    title="Xếp phòng"
    person={UNASSIGNED[1]}
    rooms={[ROOMS[2]]}
    onConfirm={() => {}}
    onClose={() => {}}
  />,
  () => {},
  '/admin/rooms',
  (html) =>
    assertHtml(
      html,
      html.includes('Không còn phòng phù hợp') && !html.includes('value="103"'),
      'Cho chọn phòng sai giới',
    ),
)

function failCachedQuery(qc, queryKey, message) {
  qc.getQueryCache().find({ queryKey, exact: true }).setState({ status: 'error', error: new Error(message) })
}
render('Phòng — API lỗi không hiện trạng thái rỗng giả', <RoomsPage />, (qc) => {
  seed(qc)
  failCachedQuery(qc, QUERY_KEYS.rooms({}), 'API phòng đang không sẵn sàng')
}, '/admin/rooms', (html) => assertHtml(html, html.includes('Không tải được khách sạn và phòng') && !html.includes('Chưa có khách sạn nào'), 'Lỗi tải bị hiểu nhầm là chưa có khách sạn'))
render('Phòng — không hiện người cũ khi tải danh sách lỗi', <RoomsPage />, (qc) => {
  seed(qc)
  failCachedQuery(qc, QUERY_KEYS.roomUnassigned({ q: undefined }), 'Không tải được người chưa có phòng')
}, '/admin/rooms', (html) => assertHtml(html, html.includes('Không tải được người chưa có phòng') && !html.includes('Đặng Quang Thắng'), 'Người trong cache cũ còn hiển thị khi request lỗi'))
render('Chi tiết phòng — lỗi quyền không hiện người trong cache', <RoomDetailModal room={ROOMS[0]} rooms={ROOMS} onEdit={() => {}} onClose={() => {}} />, (qc) => {
  seed(qc)
  failCachedQuery(qc, QUERY_KEYS.occupants(101), 'Bạn không được xem danh sách này')
}, '/admin/rooms', (html) => assertHtml(html, html.includes('Bạn không được xem danh sách này') && !html.includes('Người 1'), 'Người ở phòng trong cache còn hiển thị sau lỗi quyền'))
