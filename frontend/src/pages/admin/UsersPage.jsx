import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ChevronLeft, ChevronRight, Download, Plus, Upload, Users, X } from 'lucide-react'
import { useUsers } from '../../hooks/useUsers'
import { useRegistrationFormOptions } from '../../hooks/useRegistration'
import { useAuth } from '../../context/AuthContext'
import { ROLE_LABELS, ROLE_TONES, ROLES, USER_REGISTRATION_FILTERS } from '../../utils/constants'
import { formatDateTime, formatNumber, formatRelative } from '../../utils/format'
import Alert from '../../components/common/Alert'
import Badge from '../../components/common/Badge'
import Button from '../../components/common/Button'
import Card from '../../components/common/Card'
import EmptyState from '../../components/common/EmptyState'
import PageHeader from '../../components/common/PageHeader'
import SearchBox from '../../components/common/SearchBox'
import Select from '../../components/common/Select'
import Spinner from '../../components/common/Spinner'
import UserCreateModal from './users/UserCreateModal'
import UserDetailModal from './users/UserDetailModal'
import UserExportModal from './users/UserExportModal'
import UserImportModal from './users/UserImportModal'

const PAGE_SIZE = 25
const FILTER_KEYS = ['q', 'team_id', 'role', 'registration', 'is_active', 'missing_documents']

/**
 * Quản lý CBNV: tìm, lọc, xem hồ sơ đầy đủ, tạo tài khoản, khoá/mở, đặt lại mật khẩu.
 * Bộ lọc nằm trên URL để BTC gửi link cho nhau và F5 không mất chỗ đang làm.
 */
export default function UsersPage() {
  const { user: me } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const page = Math.max(Number(searchParams.get('page')) || 1, 1)
  const filters = Object.fromEntries(
    FILTER_KEYS.map((key) => [key, searchParams.get(key)]).filter(([, value]) => value),
  )
  const params = { ...filters, page, page_size: PAGE_SIZE }

  const { data: options } = useRegistrationFormOptions()
  const { data, isLoading, isFetching, error } = useUsers(params)
  const [creating, setCreating] = useState(false)
  const [importing, setImporting] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [openUserId, setOpenUserId] = useState(null)

  function update(changes) {
    const next = new URLSearchParams(searchParams)
    for (const [key, value] of Object.entries(changes)) {
      if (value === null || value === undefined || value === '') next.delete(key)
      else next.set(key, String(value))
    }
    if (!('page' in changes)) next.delete('page')
    setSearchParams(next, { replace: true })
  }

  const totalPages = data ? Math.max(Math.ceil(data.total / PAGE_SIZE), 1) : 1
  const hasFilters = Object.keys(filters).length > 0

  return (
    <>
      <PageHeader
        title="Quản lý CBNV"
        description={data ? `${formatNumber(data.total)} tài khoản khớp bộ lọc` : undefined}
        action={
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" icon={Upload} onClick={() => setImporting(true)}>
              Import Excel
            </Button>
            <Button variant="secondary" icon={Download} onClick={() => setExporting(true)}>
              Xuất Excel
            </Button>
            <Button icon={Plus} onClick={() => setCreating(true)}>
              Thêm CBNV
            </Button>
          </div>
        }
      />

      <div className="flex flex-col gap-4">
        <Card>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
            <div className="sm:col-span-2">
              <SearchBox
                key={filters.q ?? ''}
                initial={filters.q ?? ''}
                placeholder="Tên, email, mã nhân viên"
                onSearch={(q) => update({ q })}
              />
            </div>
            <Select
              label="Team"
              placeholder="Tất cả team"
              value={filters.team_id ?? ''}
              onChange={(changeEvent) => update({ team_id: changeEvent.target.value })}
              options={(options?.teams ?? []).map((team) => ({ value: team.id, label: team.name }))}
            />
            <Select
              label="Vai trò"
              placeholder="Tất cả"
              value={filters.role ?? ''}
              onChange={(changeEvent) => update({ role: changeEvent.target.value })}
              options={Object.entries(ROLE_LABELS).map(([value, label]) => ({ value, label }))}
            />
            <Select
              label="Đăng ký kỳ này"
              placeholder="Tất cả"
              value={filters.registration ?? ''}
              onChange={(changeEvent) => update({ registration: changeEvent.target.value })}
              options={Object.entries(USER_REGISTRATION_FILTERS).map(([value, label]) => ({ value, label }))}
            />
            <Select
              label="Tài khoản"
              placeholder="Tất cả"
              value={filters.is_active ?? ''}
              onChange={(changeEvent) => update({ is_active: changeEvent.target.value })}
              options={[
                { value: 'true', label: 'Đang hoạt động' },
                { value: 'false', label: 'Đã khoá' },
              ]}
            />
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3">
            <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1 text-sm text-slate-700 ring-1 ring-slate-200 ring-inset hover:bg-slate-50">
              <input
                type="checkbox"
                className="size-4 accent-brand-600"
                checked={filters.missing_documents === 'true'}
                onChange={(changeEvent) => update({ missing_documents: changeEvent.target.checked ? 'true' : null })}
              />
              Chỉ người thiếu CCCD / ngày sinh
            </label>
            {hasFilters && (
              <Button variant="ghost" size="sm" icon={X} onClick={() => setSearchParams(new URLSearchParams(), { replace: true })}>
                Xoá bộ lọc
              </Button>
            )}
            {isFetching && !isLoading && <span className="text-xs text-slate-400">Đang cập nhật…</span>}
          </div>
        </Card>

        {isLoading ? (
          <Spinner label="Đang tải danh sách CBNV…" />
        ) : error ? (
          <Alert tone="error" title="Không tải được danh sách CBNV">
            {error.message}
          </Alert>
        ) : data.items.length === 0 ? (
          <Card>
            <EmptyState
              icon={Users}
              title="Không có CBNV nào"
              description={hasFilters ? 'Thử bỏ bớt bộ lọc.' : 'Thêm từng người hoặc import danh sách từ Excel.'}
            />
          </Card>
        ) : (
          <Card bodyClassName="p-0">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[920px] text-sm">
                <thead>
                  <tr className="border-b border-slate-100 text-left text-xs tracking-wide text-slate-400 uppercase">
                    <th scope="col" className="px-4 py-2 font-medium">CBNV</th>
                    <th scope="col" className="px-3 py-2 font-medium">Team / Phòng ban</th>
                    <th scope="col" className="px-3 py-2 font-medium">Vai trò</th>
                    <th scope="col" className="px-3 py-2 font-medium">Đăng ký kỳ này</th>
                    <th scope="col" className="px-3 py-2 font-medium">Giấy tờ</th>
                    <th scope="col" className="px-3 py-2 font-medium">Tài khoản</th>
                    <th scope="col" className="px-3 py-2 font-medium">Đăng nhập</th>
                    <th scope="col" className="px-4 py-2">
                      <span className="sr-only">Thao tác</span>
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data.items.map((row) => (
                    <UserRow key={row.id} row={row} isMe={row.id === me?.id} onOpen={() => setOpenUserId(row.id)} />
                  ))}
                </tbody>
              </table>
            </div>
            <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 px-4 py-2.5">
              <p className="text-xs text-slate-500">
                Trang {page}/{totalPages} · {formatNumber(data.total)} tài khoản
              </p>
              <div className="flex gap-2">
                <Button variant="secondary" size="sm" icon={ChevronLeft} disabled={page <= 1} onClick={() => update({ page: page - 1 })}>
                  Trước
                </Button>
                <Button variant="secondary" size="sm" disabled={page >= totalPages} onClick={() => update({ page: page + 1 })}>
                  Sau
                  <ChevronRight className="size-4" aria-hidden="true" />
                </Button>
              </div>
            </footer>
          </Card>
        )}
      </div>

      {creating && (
        <UserCreateModal
          options={options}
          canCreateOrganizers={me?.role === ROLES.SUPER_ADMIN}
          onClose={() => setCreating(false)}
        />
      )}
      {openUserId && <UserDetailModal userId={openUserId} options={options} onClose={() => setOpenUserId(null)} />}
      {importing && <UserImportModal onClose={() => setImporting(false)} />}
      {exporting && <UserExportModal onClose={() => setExporting(false)} />}
    </>
  )
}

function UserRow({ row, isMe, onOpen }) {
  return (
    <tr className={`align-top hover:bg-slate-50/60 ${row.is_active ? '' : 'bg-slate-50 text-slate-500'}`}>
      <td className="px-4 py-2.5">
        <p className="font-medium text-slate-900">
          {row.full_name}
          {isMe && <span className="ml-1.5 text-xs font-normal text-slate-500">(bạn)</span>}
        </p>
        <p className="text-xs text-slate-500">{[row.employee_code, row.email].filter(Boolean).join(' · ')}</p>
      </td>
      <td className="px-3 py-2.5">
        <p className="text-slate-700">{row.team_name ?? '—'}</p>
        {row.department_name && <p className="text-xs text-slate-500">{row.department_name}</p>}
      </td>
      <td className="px-3 py-2.5">
        <Badge tone={ROLE_TONES[row.role] ?? 'slate'}>{ROLE_LABELS[row.role] ?? row.role}</Badge>
      </td>
      <td className="px-3 py-2.5">
        <RegistrationBadge row={row} />
      </td>
      <td className="px-3 py-2.5">{row.can_fly ? <Badge tone="emerald">Đủ</Badge> : <Badge tone="rose">Thiếu</Badge>}</td>
      <td className="px-3 py-2.5">
        <div className="flex flex-wrap gap-1">
          {row.is_active ? <Badge tone="emerald">Hoạt động</Badge> : <Badge tone="rose">Đã khoá</Badge>}
          {row.is_locked && <Badge tone="amber">Khoá tạm</Badge>}
          {row.must_change_password && <Badge tone="slate">Chờ đổi mật khẩu</Badge>}
        </div>
      </td>
      <td className="px-3 py-2.5 text-xs whitespace-nowrap text-slate-500">
        {row.last_login_at ? (
          <span title={formatDateTime(row.last_login_at)}>{formatRelative(row.last_login_at)}</span>
        ) : (
          'Chưa từng'
        )}
      </td>
      <td className="px-4 py-2.5 text-right">
        <Button variant="ghost" size="sm" onClick={onOpen}>
          Chi tiết
        </Button>
      </td>
    </tr>
  )
}

function RegistrationBadge({ row }) {
  if (!row.registration_status || row.registration_status === 'draft') return <Badge tone="slate">Chưa đăng ký</Badge>
  if (row.registration_status === 'cancelled') return <Badge tone="rose">Đã huỷ</Badge>
  return row.is_participating ? <Badge tone="emerald">Tham gia</Badge> : <Badge tone="slate">Không tham gia</Badge>
}
