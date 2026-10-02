import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ChevronLeft, ChevronRight, Download, FileInput, Plus, Search, Users, X } from 'lucide-react'
import { useUsers } from '../../hooks/useUsers'
import { useRegistrationFormOptions } from '../../hooks/useRegistration'
import { useAuth } from '../../context/AuthContext'
import { GENDER_LABELS, ROLE_LABELS, ROLES, USER_REGISTRATION_FILTERS } from '../../utils/constants'
import { formatDateTime, formatNumber, formatRelative } from '../../utils/format'
import Alert from '../../components/common/Alert'
import Button from '../../components/common/Button'
import EmptyState from '../../components/common/EmptyState'
import Spinner from '../../components/common/Spinner'
import UserCreateModal from './users/UserCreateModal'
import UserDetailModal from './users/UserDetailModal'
import UserExportModal from './users/UserExportModal'
import UserImportModal from './users/UserImportModal'
import '../../components/profile/F1Surface.css'

const PAGE_SIZE = 25
const FILTER_KEYS = ['q', 'team_id', 'work_location_id', 'role', 'registration', 'is_active', 'missing_documents']
const AVATAR_COLORS = ['#391c57', '#2a9d99', '#dd5b00', '#d6b6f6', '#ff64c8', '#523410', '#62aef0', '#1aae39']

export default function UsersPage() {
  const { user: me } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const page = Math.max(Number(searchParams.get('page')) || 1, 1)
  const filters = Object.fromEntries(FILTER_KEYS.map((key) => [key, searchParams.get(key)]).filter(([, value]) => value))
  const { data: options } = useRegistrationFormOptions()
  const { data, isLoading, isFetching, error } = useUsers({ ...filters, page, page_size: PAGE_SIZE })
  const [creating, setCreating] = useState(false)
  const [importing, setImporting] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [openUserId, setOpenUserId] = useState(null)
  const [selected, setSelected] = useState([])
  const rows = data?.items ?? []
  const selectedRows = rows.filter((row) => selected.includes(row.id))
  const totalPages = data ? Math.max(Math.ceil(data.total / PAGE_SIZE), 1) : 1
  const hasFilters = Object.keys(filters).length > 0

  function update(changes) {
    const next = new URLSearchParams(searchParams)
    for (const [key, value] of Object.entries(changes)) {
      if (value === null || value === undefined || value === '') next.delete(key)
      else next.set(key, String(value))
    }
    if (!('page' in changes)) next.delete('page')
    setSelected([])
    setSearchParams(next, { replace: true })
  }
  function toggle(id) { setSelected((ids) => ids.includes(id) ? ids.filter((value) => value !== id) : [...ids, id]) }

  return (
    <div className="f1-surface f1-users">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[32px] leading-[42px] font-bold tracking-[-0.7px]">Đăng ký & CBNV</h1>
          <p className="mt-1 text-[15px] leading-[22px] text-ink-muted">
            {data ? `${formatNumber(data.total)} người` : 'Danh sách CBNV'}
            {options && ` · ${options.teams?.length ?? 0} team · ${options.work_locations?.length ?? 0} nơi làm việc`}
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <Button variant="secondary" size="sm" icon={FileInput} onClick={() => setImporting(true)}>Import</Button>
          <Button variant="secondary" size="sm" icon={Download} onClick={() => setExporting(true)}>Xuất Excel</Button>
          <Button size="sm" shape="pill" icon={Plus} onClick={() => setCreating(true)}>Thêm người</Button>
        </div>
      </header>

      <div className="f1-users-toolbar">
        <UserSearch key={filters.q ?? ''} initial={filters.q ?? ''} onSearch={(q) => update({ q })} />
        <FilterSelect label="Trạng thái" value={filters.registration ?? ''} active options={Object.entries(USER_REGISTRATION_FILTERS).map(([value, label]) => ({ value, label }))} onChange={(value) => update({ registration: value })} />
        <FilterSelect label="Team" value={filters.team_id ?? ''} options={(options?.teams ?? []).map((item) => ({ value: item.id, label: item.name }))} onChange={(value) => update({ team_id: value })} />
        <FilterSelect label="Nơi làm việc" value={filters.work_location_id ?? ''} options={(options?.work_locations ?? []).map((item) => ({ value: item.id, label: item.name }))} onChange={(value) => update({ work_location_id: value })} />
        <FilterSelect label="Giấy tờ" value={filters.missing_documents ?? ''} options={[{ value: 'true', label: 'Thiếu giấy tờ' }, { value: 'false', label: 'Đủ giấy tờ' }]} onChange={(value) => update({ missing_documents: value })} />
        <FilterSelect label="Vai trò" value={filters.role ?? ''} options={Object.entries(ROLE_LABELS).map(([value, label]) => ({ value, label }))} onChange={(value) => update({ role: value })} />
        <FilterSelect label="Tài khoản" value={filters.is_active ?? ''} options={[{ value: 'true', label: 'Hoạt động' }, { value: 'false', label: 'Đã khoá' }]} onChange={(value) => update({ is_active: value })} />
        {hasFilters && <button type="button" onClick={() => { setSelected([]); setSearchParams(new URLSearchParams(), { replace: true }) }} aria-label="Xoá bộ lọc" className="p-2 text-ink-muted"><X className="size-4" /></button>}
        {isFetching && !isLoading && <span className="text-xs text-ink-faint">Đang cập nhật…</span>}
      </div>

      {selectedRows.length > 0 && <div className="mb-3 flex min-h-14 flex-wrap items-center justify-between gap-3 rounded-[10px] bg-[#15130f] px-[14px] py-2.5 text-[14px] text-white">
        <p><strong>Đã chọn {selectedRows.length}</strong><span className="ml-3 text-white/60">người</span></p>
        <div className="flex gap-3">
          <button type="button" onClick={() => setSelected([])} className="rounded-full bg-white/10 px-4 py-2">Bỏ chọn</button>
          <button type="button" onClick={() => setExporting(true)} title="API hiện xuất toàn bộ danh sách, không chỉ người đã chọn" className="rounded-full bg-white px-4 py-2 text-[#15130f]">Xuất Excel (toàn bộ)</button>
        </div>
      </div>}

      {isLoading ? <Spinner label="Đang tải danh sách CBNV…" /> : error ?
        <Alert tone="error" title="Không tải được danh sách CBNV">{error.message}</Alert> : rows.length === 0 ?
          <div className="f1-panel"><EmptyState icon={Users} title="Không có CBNV nào" description={hasFilters ? 'Thử bỏ bớt bộ lọc.' : 'Thêm từng người hoặc import danh sách từ Excel.'} /></div> :
          <div className="overflow-hidden rounded-[12px] border border-hairline">
            <div className="overflow-x-auto">
              <table className="f1-table">
                <thead><tr>
                  <th scope="col"><input type="checkbox" aria-label="Chọn tất cả trên trang" checked={rows.length > 0 && selectedRows.length === rows.length} onChange={(event) => setSelected(event.target.checked ? rows.map((row) => row.id) : [])} /></th>
                  {['Họ tên', 'Team', 'Nơi làm', 'Trạng thái', 'Vai trò', 'Tài khoản', 'Giấy tờ'].map((label) => <th key={label} scope="col">{label}</th>)}
                  <th scope="col"><span className="sr-only">Chi tiết</span></th>
                </tr></thead>
                <tbody>{rows.map((row, index) => <UserRow key={row.id} row={row} index={index} isMe={row.id === me?.id} selected={selected.includes(row.id)} onSelect={() => toggle(row.id)} onOpen={() => setOpenUserId(row.id)} />)}</tbody>
              </table>
            </div>
            <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-hairline bg-surface px-4 py-3 text-xs text-ink-muted">
              <p>Trang {page}/{totalPages} · {formatNumber(data.total)} tài khoản</p>
              <div className="flex gap-2"><Button variant="secondary" size="sm" icon={ChevronLeft} disabled={page <= 1} onClick={() => update({ page: page - 1 })}>Trước</Button><Button variant="secondary" size="sm" disabled={page >= totalPages} onClick={() => update({ page: page + 1 })}>Sau<ChevronRight className="size-4" /></Button></div>
            </footer>
          </div>}
      {creating && <UserCreateModal options={options} canCreateOrganizers={me?.role === ROLES.SUPER_ADMIN} onClose={() => setCreating(false)} />}
      {openUserId && <UserDetailModal userId={openUserId} options={options} onClose={() => setOpenUserId(null)} />}
      {importing && <UserImportModal onClose={() => setImporting(false)} />}
      {exporting && <UserExportModal onClose={() => setExporting(false)} />}
    </div>
  )
}

function FilterSelect({ label, value, options, active, onChange }) {
  return <div className={`f1-filter ${active || value ? 'f1-filter-active' : ''}`}><select aria-label={label} value={value} onChange={(event) => onChange(event.target.value)}>
    <option value="">{label}{active ? ': Tất cả' : ''}</option>{options.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
  </select></div>
}

function UserSearch({ initial, onSearch }) {
  const [value, setValue] = useState(initial)
  return <form role="search" className="relative w-[280px] max-w-full" onSubmit={(event) => { event.preventDefault(); onSearch(value.trim()) }}>
    <button type="submit" aria-label="Tìm tên, mã NV, email" className="absolute inset-y-0 left-0 z-10 grid w-9 place-items-center text-ink-faint"><Search className="size-[14px]" /></button>
    <input aria-label="Tìm tên, mã NV, email" type="search" value={value} onChange={(event) => setValue(event.target.value)} placeholder="Tìm tên, mã NV, email" className="f1-user-search w-full border border-input-border bg-surface !py-1.5 !pl-9 outline-none" />
  </form>
}

function UserRow({ row, index, isMe, selected, onSelect, onOpen }) {
  return <tr data-selected={selected}>
    <td><input type="checkbox" aria-label={`Chọn ${row.full_name}`} checked={selected} onChange={onSelect} /></td>
    <td><button type="button" onClick={onOpen} className="flex items-center gap-2.5 text-left">
      <span aria-hidden="true" className="grid size-[26px] shrink-0 place-items-center rounded-full text-[11px] font-bold text-white" style={{ background: AVATAR_COLORS[index % AVATAR_COLORS.length] }}>{row.full_name.trim().split(/\s+/).at(-1)?.[0]}</span>
      <span><span className="block text-[14px] font-semibold">{row.full_name}{isMe && <span className="ml-1 text-xs font-normal text-ink-muted">(bạn)</span>}</span>
        <span className="mt-0.5 block text-xs text-ink-faint">{[row.employee_code, GENDER_LABELS[row.gender]].filter(Boolean).join(' · ') || row.email}</span></span>
    </button></td>
    <td><span className="inline-flex items-center gap-1.5"><span className="size-2 rounded-full bg-primary" />{row.team_name ?? '—'}</span></td>
    <td className="whitespace-nowrap">{row.work_location_name ?? '—'}</td>
    <td><RegistrationBadge row={row} /></td>
    <td className="text-[13px] text-ink-muted">{ROLE_LABELS[row.role] ?? row.role}</td>
    <td><span className={`f1-badge ${row.is_active ? 'f1-badge-neutral' : 'f1-badge-red'}`}>{row.is_locked ? 'Khoá tạm' : row.is_active ? 'Hoạt động' : 'Đã khoá'}</span>
      <span title={row.last_login_at ? formatDateTime(row.last_login_at) : undefined} className="mt-1 block text-xs text-ink-faint">{row.must_change_password ? 'Chờ đổi mật khẩu' : row.last_login_at ? formatRelative(row.last_login_at) : 'Chưa đăng nhập'}</span></td>
    <td>{row.can_fly ? <span className="text-ink-faint">Đủ</span> : <span className="f1-badge f1-badge-orange">Thiếu</span>}</td>
    <td><button type="button" onClick={onOpen} aria-label={`Chi tiết ${row.full_name}`} className="grid size-8 place-items-center text-ink-faint hover:text-primary"><ChevronRight className="size-4" /></button></td>
  </tr>
}

function RegistrationBadge({ row }) {
  if (!row.registration_status || row.registration_status === 'draft') return <span className="f1-badge f1-badge-orange">Chưa phản hồi</span>
  if (row.registration_status === 'cancelled') return <span className="f1-badge f1-badge-red">Đã huỷ</span>
  return row.is_participating ? <span className="f1-badge f1-badge-green">Đã đăng ký</span> : <span className="f1-badge f1-badge-neutral">Không đi</span>
}
