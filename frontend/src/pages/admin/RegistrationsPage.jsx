import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ChevronLeft, ChevronRight, ClipboardList, Search, X } from 'lucide-react'
import { useRegistrationFormOptions, useRegistrationList } from '../../hooks/useRegistration'
import { REGISTRATION_STATUS_META } from '../../utils/constants'
import { formatDateTime, formatNumber } from '../../utils/format'
import Alert from '../../components/common/Alert'
import Badge from '../../components/common/Badge'
import Button from '../../components/common/Button'
import Card from '../../components/common/Card'
import EmptyState from '../../components/common/EmptyState'
import Input from '../../components/common/Input'
import PageHeader from '../../components/common/PageHeader'
import Select from '../../components/common/Select'
import Spinner from '../../components/common/Spinner'

const PAGE_SIZE = 20
const FILTER_KEYS = ['q', 'team_id', 'shift_id', 'status', 'is_participating', 'missing_documents']

/**
 * Danh sách đăng ký cho BTC.
 *
 * Bộ lọc nằm trên URL (`?missing_documents=true`) để dashboard và checklist dẫn thẳng tới
 * đúng nhóm người cần xử lý, và BTC gửi link cho nhau được.
 */
export default function RegistrationsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const page = Math.max(Number(searchParams.get('page')) || 1, 1)
  const filters = Object.fromEntries(
    FILTER_KEYS.map((key) => [key, searchParams.get(key)]).filter(([, value]) => value),
  )
  const params = { ...filters, page, page_size: PAGE_SIZE }

  const { data: options } = useRegistrationFormOptions()
  const { data, isLoading, isFetching, error } = useRegistrationList(params)

  function update(changes) {
    const next = new URLSearchParams(searchParams)
    for (const [key, value] of Object.entries(changes)) {
      if (value === null || value === undefined || value === '') next.delete(key)
      else next.set(key, String(value))
    }
    // Đổi bộ lọc thì về trang 1, nếu không dễ đứng ở trang 5 của một danh sách chỉ còn 1 trang.
    if (!('page' in changes)) next.delete('page')
    setSearchParams(next, { replace: true })
  }

  const totalPages = data ? Math.max(Math.ceil(data.total / PAGE_SIZE), 1) : 1
  const hasFilters = Object.keys(filters).length > 0

  return (
    <>
      <PageHeader
        title="Danh sách đăng ký"
        description={data ? `${formatNumber(data.total)} đăng ký khớp bộ lọc` : undefined}
      />

      <div className="flex flex-col gap-4">
        <Card>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
            <div className="sm:col-span-2">
              <SearchBox key={filters.q ?? ''} initial={filters.q ?? ''} onSearch={(q) => update({ q })} />
            </div>
            <Select
              label="Team"
              placeholder="Tất cả team"
              value={filters.team_id ?? ''}
              onChange={(changeEvent) => update({ team_id: changeEvent.target.value })}
              options={(options?.teams ?? []).map((team) => ({ value: team.id, label: team.name }))}
            />
            <Select
              label="Ca bay"
              placeholder="Tất cả ca"
              value={filters.shift_id ?? ''}
              onChange={(changeEvent) => update({ shift_id: changeEvent.target.value })}
              options={(options?.shifts ?? []).map((shift) => ({ value: shift.id, label: shift.name }))}
            />
            <Select
              label="Tham gia"
              placeholder="Tất cả"
              value={filters.is_participating ?? ''}
              onChange={(changeEvent) => update({ is_participating: changeEvent.target.value })}
              options={[
                { value: 'true', label: 'Có tham gia' },
                { value: 'false', label: 'Không tham gia' },
              ]}
            />
            <Select
              label="Trạng thái"
              placeholder="Tất cả"
              value={filters.status ?? ''}
              onChange={(changeEvent) => update({ status: changeEvent.target.value })}
              options={Object.entries(REGISTRATION_STATUS_META).map(([value, meta]) => ({
                value,
                label: meta.label,
              }))}
            />
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3">
            <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1 text-sm text-slate-700 ring-1 ring-slate-200 ring-inset hover:bg-slate-50">
              <input
                type="checkbox"
                className="size-4 accent-brand-600"
                checked={filters.missing_documents === 'true'}
                onChange={(changeEvent) =>
                  update({ missing_documents: changeEvent.target.checked ? 'true' : null })
                }
              />
              Chỉ người thiếu CCCD / ngày sinh
            </label>
            {hasFilters && (
              <Button
                variant="ghost"
                size="sm"
                icon={X}
                onClick={() => setSearchParams(new URLSearchParams(), { replace: true })}
              >
                Xoá bộ lọc
              </Button>
            )}
            {isFetching && !isLoading && <span className="text-xs text-slate-400">Đang cập nhật…</span>}
          </div>
        </Card>

        {isLoading ? (
          <Spinner label="Đang tải danh sách…" />
        ) : error ? (
          <Alert tone="error" title="Không tải được danh sách đăng ký">
            {error.message}
          </Alert>
        ) : data.items.length === 0 ? (
          <Card>
            <EmptyState
              icon={ClipboardList}
              title="Không có đăng ký nào"
              description={hasFilters ? 'Thử bỏ bớt bộ lọc.' : 'Chưa CBNV nào gửi đăng ký.'}
            />
          </Card>
        ) : (
          <Card bodyClassName="p-0">
            <RegistrationTable rows={data.items} />
            <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 px-4 py-2.5">
              <p className="text-xs text-slate-500">
                Trang {page}/{totalPages} · {formatNumber(data.total)} đăng ký
              </p>
              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  icon={ChevronLeft}
                  disabled={page <= 1}
                  onClick={() => update({ page: page - 1 })}
                >
                  Trước
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => update({ page: page + 1 })}
                >
                  Sau
                  <ChevronRight className="size-4" aria-hidden="true" />
                </Button>
              </div>
            </footer>
          </Card>
        )}
      </div>
    </>
  )
}

/** Tìm khi bấm Enter hoặc nút — không gọi API theo từng phím gõ. */
function SearchBox({ initial, onSearch }) {
  const [value, setValue] = useState(initial)

  return (
    <form
      role="search"
      className="flex items-end gap-2"
      onSubmit={(submitEvent) => {
        submitEvent.preventDefault()
        onSearch(value.trim())
      }}
    >
      <div className="min-w-0 flex-1">
        <Input
          label="Tìm kiếm"
          type="search"
          placeholder="Tên, email, mã nhân viên"
          value={value}
          onChange={(changeEvent) => setValue(changeEvent.target.value)}
        />
      </div>
      <Button type="submit" variant="secondary" icon={Search} aria-label="Tìm">
        <span className="sr-only sm:not-sr-only">Tìm</span>
      </Button>
    </form>
  )
}

function RegistrationTable({ rows }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[820px] text-sm">
        <thead>
          <tr className="border-b border-slate-100 text-left text-xs tracking-wide text-slate-400 uppercase">
            <th scope="col" className="px-4 py-2 font-medium">CBNV</th>
            <th scope="col" className="px-3 py-2 font-medium">Team</th>
            <th scope="col" className="px-3 py-2 font-medium">Tham gia</th>
            <th scope="col" className="px-3 py-2 font-medium">Ca</th>
            <th scope="col" className="px-3 py-2 font-medium">Xe BTC</th>
            <th scope="col" className="px-3 py-2 font-medium">Giấy tờ</th>
            <th scope="col" className="px-3 py-2 font-medium">Trạng thái</th>
            <th scope="col" className="px-4 py-2 font-medium">Gửi lúc</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((row) => {
            const statusMeta = REGISTRATION_STATUS_META[row.status] ?? { label: row.status, tone: 'slate' }
            const busLegs = row.bus_needs.filter((need) => need.needs_bus)
            const participating = row.status === 'submitted' && row.is_participating

            return (
              <tr key={row.id} className="align-top hover:bg-slate-50/60">
                <td className="px-4 py-2.5">
                  <p className="font-medium text-slate-900">{row.user.full_name}</p>
                  <p className="text-xs text-slate-500">
                    {[row.user.employee_code, row.user.email].filter(Boolean).join(' · ')}
                  </p>
                </td>
                <td className="px-3 py-2.5 text-slate-700">{row.user.team_name ?? '—'}</td>
                <td className="px-3 py-2.5">
                  {row.is_participating ? (
                    <Badge tone="emerald">Có</Badge>
                  ) : (
                    <span title={row.not_participating_reason ?? undefined}>
                      <Badge tone="slate">Không</Badge>
                    </span>
                  )}
                </td>
                <td className="px-3 py-2.5 text-slate-700">{row.shift?.code ?? '—'}</td>
                <td className="px-3 py-2.5 text-slate-700">
                  {busLegs.length ? (
                    <span title={busLegs.map((need) => need.trip_leg_name).join(', ')}>
                      {busLegs.length}/{row.bus_needs.length} chặng
                    </span>
                  ) : (
                    '—'
                  )}
                </td>
                <td className="px-3 py-2.5">
                  {!participating ? (
                    <span className="text-slate-400">—</span>
                  ) : row.user.can_fly ? (
                    <Badge tone="emerald">Đủ</Badge>
                  ) : (
                    <Badge tone="rose">Thiếu</Badge>
                  )}
                </td>
                <td className="px-3 py-2.5">
                  <div className="flex flex-wrap gap-1">
                    <Badge tone={statusMeta.tone}>{statusMeta.label}</Badge>
                    {row.penalty_applied && <Badge tone="amber">Phí phạt</Badge>}
                  </div>
                </td>
                <td className="px-4 py-2.5 text-xs whitespace-nowrap text-slate-500">
                  {formatDateTime(row.cancelled_at ?? row.submitted_at)}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
