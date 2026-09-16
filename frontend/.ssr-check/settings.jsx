import { renderToString } from 'react-dom/server'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { ToastProvider } from '../src/context/ToastContext'
import { QUERY_KEYS } from '../src/utils/constants'
import SettingsPage from '../src/pages/admin/SettingsPage'
import MasterDataPage from '../src/pages/admin/MasterDataPage'
import CrudSection from '../src/components/admin/CrudSection'
import { EVENT } from './fixtures.js'

const DEPARTMENTS = [
  { id: 1, code: 'IT', name: 'Công nghệ', display_order: 0, is_active: true },
  { id: 2, code: 'KD', name: 'Kinh doanh', display_order: 1, is_active: false },
]

const LOCATIONS = [
  { id: 1, code: 'HN', name: 'Hà Nội', city: 'Hà Nội', airport_code: 'HAN', display_order: 1, is_active: true },
]

const TEAMS = [
  { id: 1, code: 'KDHN', name: 'Kinh doanh Hà Nội', department_id: 2, leader_user_id: 5, color: '#4f46e5', is_active: true, member_count: 20 },
  { id: 2, code: 'MKT', name: 'Marketing', department_id: null, leader_user_id: null, color: null, is_active: true, member_count: 9 },
]

const SHIFTS = [
  { id: 1, event_id: 1, code: 'CA1', name: 'Ca 1 – bay sáng', description: null, earliest_departure: '06:00', display_order: 1 },
]

const LEGS = [
  { id: 1, event_id: 1, code: 'CITY_TO_AIRPORT', name: 'HN/HCM → Sân bay', direction: 'outbound', leg_date: '2026-10-15', is_airport_linked: true, display_order: 1 },
]

const PICKUPS = [
  { id: 1, event_id: 1, trip_leg_id: 1, work_location_id: 1, name: 'Toà nhà Keangnam', address: 'Phạm Hùng', map_url: null, display_order: 0 },
]

const SETTINGS = {
  'allocation.team_weight': { value: 10, description: 'Điểm thưởng khi giữ người cùng team trên một chuyến' },
  'allocation.shift_weight': { value: 6, description: 'Điểm thưởng khi đáp ứng đúng ca nguyện vọng' },
  'allocation.split_penalty': { value: 25, description: 'Điểm phạt mỗi lần một team bị tách thêm một mảnh' },
  'allocation.max_split_per_team': { value: 2, description: 'Số mảnh tối đa một team bị tách' },
  'allocation.min_chunk_size': { value: 3, description: 'Mảnh tách ra không được nhỏ hơn số này' },
  'rooms.team_weight': { value: 10, description: 'Điểm thưởng mỗi cặp cùng team ở chung phòng' },
  'rooms.flight_weight': { value: 4, description: 'Điểm thưởng mỗi cặp cùng chuyến bay chiều đi' },
  'rooms.department_weight': { value: 1, description: 'Điểm thưởng mỗi cặp cùng phòng ban' },
  'gala.hold_seconds': { value: 120, description: 'Thời gian giữ ghế tạm trước khi xác nhận' },
  'gala.turn_seconds': { value: 300, description: 'Thời gian mỗi lượt chọn ghế của một team' },
}

const DOCUMENTS = [
  {
    id: 1, event_id: 1, doc_type: 'faq', title: 'Câu hỏi thường gặp', content: 'Mang theo CCCD.',
    version: 'v1', is_indexed: false, updated_at: '2026-09-10T02:00:00+00:00',
    is_shared: false, can_edit: true,
  },
  {
    id: 2, event_id: null, doc_type: 'guide', title: 'Hướng dẫn dùng cổng', content: 'Đăng nhập bằng email công ty.',
    version: 'v1', is_indexed: true, updated_at: '2026-09-01T02:00:00+00:00',
    is_shared: true, can_edit: false,
  },
]

function render(label, element, seed = () => {}, entry = '/admin/settings') {
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

const seedAll = (overrides = {}) => (qc) => {
  qc.setQueryData(QUERY_KEYS.activeEvent, { ...EVENT, is_active: true, ...overrides.event })
  qc.setQueryData(QUERY_KEYS.masterData('departments'), DEPARTMENTS)
  qc.setQueryData(QUERY_KEYS.masterData('workLocations'), LOCATIONS)
  qc.setQueryData(QUERY_KEYS.masterData('teams'), TEAMS)
  qc.setQueryData(QUERY_KEYS.masterData('shifts'), overrides.shifts ?? SHIFTS)
  qc.setQueryData(QUERY_KEYS.masterData('tripLegs'), LEGS)
  qc.setQueryData(QUERY_KEYS.masterData('pickupPoints'), PICKUPS)
  qc.setQueryData(QUERY_KEYS.eventSettings(1), SETTINGS)
  qc.setQueryData(QUERY_KEYS.documents, overrides.documents ?? DOCUMENTS)
}

// --- Cấu hình kỳ ---
render('Cấu hình kỳ — Thông tin kỳ (đang là mặc định)', <SettingsPage />, seedAll(), '/admin/settings?tab=event')
render(
  'Cấu hình kỳ — Thông tin kỳ (chưa mặc định)',
  <SettingsPage />,
  seedAll({ event: { is_active: false } }),
  '/admin/settings?tab=event',
)
render('Cấu hình kỳ — Quy định', <SettingsPage />, seedAll(), '/admin/settings?tab=terms')
render('Cấu hình kỳ — Tài liệu', <SettingsPage />, seedAll(), '/admin/settings?tab=documents')
render(
  'Cấu hình kỳ — Tài liệu rỗng',
  <SettingsPage />,
  seedAll({ documents: [] }),
  '/admin/settings?tab=documents',
)
render('Cấu hình kỳ — Ca bay', <SettingsPage />, seedAll(), '/admin/settings?tab=shifts')
render(
  'Cấu hình kỳ — Ca bay rỗng (kỳ mới)',
  <SettingsPage />,
  seedAll({ shifts: [] }),
  '/admin/settings?tab=shifts',
)
render('Cấu hình kỳ — Chặng & điểm đón', <SettingsPage />, seedAll(), '/admin/settings?tab=legs')
render('Cấu hình kỳ — Trọng số & Gala', <SettingsPage />, seedAll(), '/admin/settings?tab=weights')
render('Cấu hình kỳ — tab lạ trên URL về tab đầu', <SettingsPage />, seedAll(), '/admin/settings?tab=khong-co')
render('Cấu hình kỳ — đang tải', <SettingsPage />)

// --- Master data ---
render('Master data — Phòng ban', <MasterDataPage />, seedAll(), '/admin/master-data?tab=departments')
render('Master data — Địa điểm', <MasterDataPage />, seedAll(), '/admin/master-data?tab=locations')
render('Master data — Team', <MasterDataPage />, seedAll(), '/admin/master-data?tab=teams')
render('Master data — đang tải', <MasterDataPage />, () => {}, '/admin/master-data')

// --- Bảng CRUD dùng chung ---
render(
  'Bảng CRUD — lỗi tải',
  <CrudSection
    resource="departments"
    title="Phòng ban"
    columns={[{ key: 'name', label: 'Tên' }]}
    fields={[{ name: 'name', label: 'Tên', required: true }]}
  />,
  (qc) => {
    qc.setQueryData(QUERY_KEYS.masterData('departments'), undefined)
  },
)
render(
  'Bảng CRUD — chỉ đọc (có ghi chú)',
  <CrudSection
    resource="teams"
    title="Team"
    canWrite={false}
    readOnlyNote="Chỉ định Trưởng nhóm làm ở Tổng quan."
    columns={[{ key: 'name', label: 'Tên' }]}
    fields={[{ name: 'name', label: 'Tên', required: true }]}
  />,
  seedAll(),
)
