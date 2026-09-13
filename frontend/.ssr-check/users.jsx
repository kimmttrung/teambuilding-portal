import { renderToString } from 'react-dom/server'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { ToastProvider } from '../src/context/ToastContext'
import { QUERY_KEYS } from '../src/utils/constants'
import UsersPage from '../src/pages/admin/UsersPage'
import UserAccountPanel from '../src/pages/admin/users/UserAccountPanel'
import UserCreateModal from '../src/pages/admin/users/UserCreateModal'
import UserDetailModal from '../src/pages/admin/users/UserDetailModal'
import TemporaryPasswordNotice from '../src/pages/admin/users/TemporaryPasswordNotice'
import UserExportModal from '../src/pages/admin/users/UserExportModal'
import UserImportModal from '../src/pages/admin/users/UserImportModal'
import ExportButton from '../src/components/common/ExportButton'
import { filenameFromDisposition } from '../src/api/downloads'
import { buildCsv } from '../src/utils/files'
import { OPTIONS } from './fixtures.js'

const STAMP = '2026-09-12T04:00:00+00:00'

const row = (id, name, extra = {}) => ({
  id, employee_code: `NV${String(id).padStart(3, '0')}`, full_name: name, email: `nv${id}@company.vn`, phone: null,
  gender: 'male', role: 'employee', job_title: null, team_id: 1, team_name: 'Team Alpha', department_id: 1,
  department_name: 'Công nghệ', work_location_id: 1, work_location_name: 'Hà Nội', is_active: true,
  must_change_password: false, is_locked: false, last_login_at: STAMP, can_fly: true,
  registration_status: 'submitted', is_participating: true, ...extra,
})

const USERS = {
  items: [
    row(1, 'Nguyễn Văn Trung'),
    row(2, 'Lê Hữu Nam', { can_fly: false, registration_status: null, is_participating: null, last_login_at: null, must_change_password: true }),
    row(3, 'Trần Khoá', { is_active: false, is_locked: true, registration_status: 'cancelled', is_participating: null, team_name: null, department_name: null }),
    row(4, 'Ban Tổ Chức', { role: 'admin', registration_status: 'submitted', is_participating: false }),
  ],
  total: 4, page: 1, page_size: 25,
}

const DETAIL = {
  id: 5, full_name: 'Phạm Thu Hà', display_name: null, avatar_url: null, job_title: 'Kế toán',
  team: { id: 1, code: 'T1', name: 'Team Alpha', color: '#4f46e5' }, email: 'ha@company.vn', employee_code: 'NV005',
  role: 'employee', phone: '0912000005', personal_email: null, gender: 'female', date_of_birth: '1994-04-04',
  address: null, department_id: 1, work_location_id: 1, join_date: '2020-01-01', id_card_number: '001094000005',
  id_card_type: 'cccd', id_card_issue_date: null, id_card_issue_place: null, shirt_size: 'M',
  dietary_restriction: null, health_note: 'Hen suyễn', emergency_contact_name: null, emergency_contact_phone: null,
  must_change_password: true, can_fly: true, is_active: true, last_login_at: null,
  locked_until: '2099-01-01T00:00:00+00:00', created_at: STAMP, team_id: 1,
}

function render(label, element, seed = () => {}, entry = '/admin/users') {
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

const seedOptions = (qc) => qc.setQueryData(QUERY_KEYS.formOptions, OPTIONS)

render('Quản lý CBNV — danh sách', <UsersPage />, (qc) => {
  seedOptions(qc)
  qc.setQueryData(QUERY_KEYS.users({ page: 1, page_size: 25 }), USERS)
})
render(
  'Quản lý CBNV — lọc chưa đăng ký, trống',
  <UsersPage />,
  (qc) => {
    seedOptions(qc)
    qc.setQueryData(QUERY_KEYS.users({ registration: 'none', page: 1, page_size: 25 }), { items: [], total: 0, page: 1, page_size: 25 })
  },
  '/admin/users?registration=none',
)
render('Thêm CBNV', <UserCreateModal options={OPTIONS} onClose={() => {}} />)
render('Hồ sơ CBNV (tab hồ sơ)', <UserDetailModal userId={5} options={OPTIONS} onClose={() => {}} />, (qc) => {
  qc.setQueryData(QUERY_KEYS.user(5), DETAIL)
})
render('Hồ sơ CBNV — đang tải', <UserDetailModal userId={6} options={OPTIONS} onClose={() => {}} />)
render('Tài khoản — quản trị hệ thống xem CBNV bị khoá tạm', <UserAccountPanel user={DETAIL} me={{ id: 1, role: 'super_admin' }} canManage />)
render('Tài khoản — BTC xem tài khoản BTC khác', <UserAccountPanel user={{ ...DETAIL, role: 'admin', locked_until: null }} me={{ id: 1, role: 'admin' }} canManage={false} />)
render('Mật khẩu tạm', <TemporaryPasswordNotice password="aB3dE5fG7hJ9" email="ha@company.vn" />)

// --- Bước 21: import / export Excel ---
render('Import CBNV — chưa chọn file', <UserImportModal onClose={() => {}} />)
render('Xuất CBNV — chọn mức dữ liệu', <UserExportModal onClose={() => {}} />)
render('Nút xuất Excel', <ExportButton url="/rooms/export" fallbackName="phan-phong.xlsx" />)

function check(label, ok) {
  console.log(`${label}: ${ok ? 'OK' : 'LỖI'}`)
}
check(
  'Tên file từ Content-Disposition',
  filenameFromDisposition(`attachment; filename="dang-ky.xlsx"; filename*=UTF-8''%C4%91%C4%83ng-k%C3%BD.xlsx`) === 'đăng-ký.xlsx' &&
    filenameFromDisposition('attachment; filename="phan-phong-tb2026.xlsx"') === 'phan-phong-tb2026.xlsx' &&
    filenameFromDisposition(null) === null,
)
const csv = buildCsv(['Họ tên', 'Mật khẩu'], [['=HYPERLINK("x")', 'aB3,"q'], ['Lê An', null]])
check(
  'CSV có BOM, chặn công thức, bọc dấu phẩy/nháy',
  csv === '﻿Họ tên,Mật khẩu\r\n"\'=HYPERLINK(""x"")","aB3,""q"\r\nLê An,',
)
