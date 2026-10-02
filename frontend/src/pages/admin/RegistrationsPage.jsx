import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  BedDouble,
  ArrowLeft,
  Bell,
  BusFront,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  ChevronDown,
  PartyPopper,
  Plane,
  Plus,
  Phone,
  Search,
  Send,
  Upload,
  X,
} from 'lucide-react'
import { useRegistrationFormOptions, useRegistrationList } from '../../hooks/useRegistration'
import { useJourneyOf } from '../../hooks/useJourney'
import { REGISTRATION_STATUS_META } from '../../utils/constants'
import { formatDateTime, formatNumber } from '../../utils/format'
import Alert from '../../components/common/Alert'
import Badge from '../../components/common/Badge'
import Button from '../../components/common/Button'
import Card from '../../components/common/Card'
import EmptyState from '../../components/common/EmptyState'
import ExportButton from '../../components/common/ExportButton'
import PageHeader from '../../components/common/PageHeader'
import Spinner from '../../components/common/Spinner'
import ReminderDialog from '../../components/admin/ReminderDialog'

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
  const { data, isLoading, error } = useRegistrationList(params)
  const [reminding, setReminding] = useState(false)
  const [selected, setSelected] = useState(null)
  const [checkedIds, setCheckedIds] = useState([])
  const { data: journey, isLoading: journeyLoading, error: journeyError } = useJourneyOf(selected?.user?.id)

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
        title="Đăng ký & CBNV"
        description={data ? `${formatNumber(data.total)} người · ${options?.teams?.length ?? 0} team · 2 nơi làm việc` : undefined}
        className="mb-6 max-md:hidden"
        action={
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" icon={Upload}>Import</Button>
            <ExportButton
              url="/registrations/export"
              fallbackName="dang-ky.xlsx"
              title="Toàn bộ đăng ký của kỳ, kèm sheet người chưa đăng ký — không theo bộ lọc"
            >
              Xuất Excel
            </ExportButton>
            <Button icon={Plus}>Thêm người</Button>
          </div>
        }
      />

      <div className="mb-4 flex items-center gap-3 md:hidden">
        <Link to="/admin" className="grid size-8 place-items-center text-ink" aria-label="Quay lại"><ArrowLeft className="size-5" /></Link>
        <h1 className="text-page-title text-ink">Đăng ký <span className="ml-1 text-body-sm font-normal text-ink-faint">{data ? formatNumber(data.total) : '—'} người</span></h1>
        <ExportButton url="/registrations/export" fallbackName="dang-ky.xlsx" size="sm" className="ml-auto" title="Xuất danh sách đăng ký">Xuất</ExportButton>
      </div>

      <div className="flex flex-col gap-4 max-md:gap-3">
        <div className="hidden flex-wrap items-center gap-2 md:flex">
          <AdminSearchField key={filters.q ?? ''} initial={filters.q ?? ''} onSearch={(q) => update({ q })} />
          <AdminFilterSelect
            label="Trạng thái"
            value={filters.status ?? ''}
            onChange={(value) => update({ status: value })}
            options={[{ value: '', label: 'Tất cả' }, ...Object.entries(REGISTRATION_STATUS_META).map(([value, meta]) => ({ value, label: meta.label }))]}
            active={!filters.status}
          />
          <AdminFilterSelect
            label="Team"
            value={filters.team_id ?? ''}
            onChange={(value) => update({ team_id: value })}
            options={[{ value: '', label: 'Tất cả' }, ...(options?.teams ?? []).map((team) => ({ value: team.id, label: team.name }))]}
          />
          <button type="button" className="inline-flex h-9 items-center gap-2 rounded-md border border-hairline bg-surface px-3 text-body-sm font-medium text-ink-secondary shadow-soft">
            Nơi làm việc <ChevronDown className="size-3.5 text-ink-faint" aria-hidden="true" />
          </button>
          <AdminFilterSelect
            label="Ca đi"
            value={filters.shift_id ?? ''}
            onChange={(value) => update({ shift_id: value })}
            options={[{ value: '', label: 'Tất cả' }, ...(options?.shifts ?? []).map((shift) => ({ value: shift.id, label: shift.name }))]}
          />
          <AdminFilterSelect
            label="Giấy tờ"
            value={filters.missing_documents === 'true' ? 'missing' : ''}
            onChange={(value) => update({ missing_documents: value === 'missing' ? 'true' : null })}
            options={[{ value: '', label: 'Tất cả' }, { value: 'missing', label: 'Thiếu' }]}
          />
          {hasFilters && <Button variant="ghost" size="sm" icon={X} onClick={() => setSearchParams(new URLSearchParams(), { replace: true })}>Xoá lọc</Button>}
        </div>

        <div className="flex gap-2 md:hidden">
          <AdminSearchField key={`mobile-${filters.q ?? ''}`} initial={filters.q ?? ''} onSearch={(q) => update({ q })} />
          <button type="button" className="inline-flex h-10 shrink-0 items-center gap-1.5 rounded-md border border-hairline bg-surface px-3 text-body-sm font-medium text-ink"><span aria-hidden="true">☷</span> Lọc · 2</button>
        </div>
        <div className="flex gap-2 md:hidden">
          <button type="button" className="rounded-md bg-brand-50 px-2.5 py-1 text-caption font-medium text-primary">Chưa phản hồi ×</button>
          <button type="button" className="rounded-md bg-brand-50 px-2.5 py-1 text-caption font-medium text-primary">Hà Nội ×</button>
        </div>

        {filters.missing_documents === 'true' && data?.total ? (
          <div className="flex items-center justify-between rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-body-sm text-amber-900 max-md:hidden">
            <span>Đang lọc CBNV thiếu CCCD / ngày sinh.</span>
            <Button size="sm" icon={Send} onClick={() => setReminding(true)}>Gửi nhắc</Button>
          </div>
        ) : null}

        {checkedIds.length > 0 && (
          <div className="hidden items-center justify-between rounded-lg bg-ink px-4 py-2.5 text-white shadow-soft md:flex">
            <span className="text-body-sm"><strong>Đã chọn {checkedIds.length}</strong><span className="ml-2 text-white/60">người</span></span>
            <div className="flex items-center gap-2">
              <button type="button" className="rounded-full bg-white/10 px-4 py-2 text-body-sm">Đổi team</button>
              <button type="button" className="rounded-full bg-white px-4 py-2 text-body-sm font-medium text-ink">Xuất</button>
              <button type="button" className="inline-flex items-center gap-1.5 rounded-full bg-white px-4 py-2 text-body-sm font-medium text-ink" onClick={() => setReminding(true)}><Bell className="size-4" aria-hidden="true" /> Gửi nhắc</button>
            </div>
          </div>
        )}

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
          <Card elevated bodyClassName="p-0">
            <div className="hidden md:block">
              <RegistrationTable
                rows={data.items}
                locations={options?.work_locations ?? []}
                selectedId={selected?.id}
                checkedIds={checkedIds}
                onToggle={(id) => setCheckedIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id])}
                onToggleAll={() => setCheckedIds((current) => current.length === data.items.length ? [] : data.items.map((row) => row.id))}
                onSelect={setSelected}
              />
            </div>
            <div className="md:hidden">
              <MobileRegistrationList
                rows={data.items}
                checkedIds={checkedIds}
                onToggle={(id) => setCheckedIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id])}
                onSelect={setSelected}
              />
            </div>
            <footer className="hidden flex-wrap items-center justify-between gap-2 border-t border-hairline px-4 py-2.5 md:flex">
              <p className="text-caption text-ink-muted">
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

      {selected && (
        <RegistrationDetailDrawer
          row={selected}
          journey={journey}
          isLoading={journeyLoading}
          error={journeyError}
          onClose={() => setSelected(null)}
        />
      )}

      {reminding && <ReminderDialog kind="missing_documents" onClose={() => setReminding(false)} />}
      {checkedIds.length > 0 && (
        <div className="fixed inset-x-0 bottom-14 z-20 mx-3 flex items-center justify-between rounded-2xl bg-ink px-4 py-3 text-white shadow-elevated md:hidden">
          <span className="text-body-sm font-semibold">Đã chọn {checkedIds.length} người</span>
          <div className="flex gap-2">
            <button type="button" className="rounded-full bg-white/10 px-3 py-2 text-caption">Đổi team</button>
            <button type="button" className="rounded-full bg-white px-3 py-2 text-caption font-semibold text-ink">Gửi nhắc</button>
          </div>
        </div>
      )}
    </>
  )
}

function MobileRegistrationList({ rows, checkedIds, onToggle, onSelect }) {
  return (
    <div className="flex flex-col gap-2 bg-canvas-soft p-4">
      <div className="flex items-center gap-2 px-0 py-1 text-body-sm">
        <span className="grid size-5 place-items-center rounded bg-primary text-white">✓</span>
        <strong>Đã chọn {checkedIds.length}</strong><span className="text-ink-muted">/ {rows.length} kết quả</span>
      </div>
      {rows.map((row) => {
        const statusMeta = row.status === 'submitted' ? { label: 'Đã đăng ký', tone: 'emerald' } : { label: 'Chưa', tone: 'amber' }
        const checked = checkedIds.includes(row.id)
        return (
          <button key={row.id} type="button" onClick={() => onSelect(row)} className={`flex w-full items-start gap-3 rounded-xl border px-3.5 py-3.5 text-left shadow-soft ${checked ? 'border-primary bg-brand-50' : 'border-hairline bg-surface'}`}>
            <input
              type="checkbox"
              checked={checked}
              onChange={(event) => { event.stopPropagation(); onToggle(row.id) }}
              onClick={(event) => event.stopPropagation()}
              className="mt-1 size-5 shrink-0 accent-primary"
              aria-label={`Chọn ${row.user.full_name}`}
            />
            <span className="grid size-9 shrink-0 place-items-center rounded-full bg-accent-purple-deep text-caption font-semibold text-white">{row.user.full_name?.slice(0, 1)}</span>
            <span className="min-w-0 flex-1">
              <span className="flex items-center justify-between gap-2"><span className="truncate text-body-sm font-semibold text-ink">{row.user.full_name}</span><Badge tone={statusMeta.tone}>{statusMeta.label}</Badge></span>
              <span className="mt-0.5 block truncate text-caption text-ink-muted">{row.user.team_name ?? 'Kinh doanh HN'} · {row.status === 'draft' ? 'chưa phản hồi 6 ngày' : row.shift?.name ?? 'đã đăng ký'}</span>
            </span>
            <span className="pt-1 text-ink-faint">›</span>
          </button>
        )
      })}
    </div>
  )
}

function RegistrationTable({ rows, locations, selectedId, checkedIds, onToggle, onToggleAll, onSelect }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[960px] text-sm">
        <thead>
          <tr className="border-b border-hairline bg-canvas-soft text-left text-caption font-medium text-ink-muted">
            <th scope="col" className="w-14 px-4 py-3"><input type="checkbox" checked={rows.length > 0 && checkedIds.length === rows.length} onChange={onToggleAll} className="size-4 accent-primary" aria-label="Chọn tất cả" /></th>
            <th scope="col" className="px-3 py-3">Họ tên</th>
            <th scope="col" className="px-3 py-3">Team</th>
            <th scope="col" className="px-3 py-3">Nơi làm</th>
            <th scope="col" className="px-3 py-3">Trạng thái</th>
            <th scope="col" className="px-3 py-3">Ca</th>
            <th scope="col" className="px-3 py-3">Xe</th>
            <th scope="col" className="px-3 py-3">Giấy tờ</th>
            <th scope="col" className="w-10 px-3 py-3" aria-label="Mở chi tiết" />
          </tr>
        </thead>
        <tbody className="divide-y divide-hairline">
          {rows.map((row) => {
            const busLegs = row.bus_needs.filter((need) => need.needs_bus)
            const status = row.status === 'submitted' ? { label: 'Đã đăng ký', tone: 'emerald' } : row.status === 'cancelled' ? { label: 'Xin huỷ', tone: 'rose' } : { label: 'Chưa phản hồi', tone: 'amber' }
            const location = locations.find((item) => item.id === row.user.work_location_id)
            const teamColor = ['bg-blue-500', 'bg-orange-500', 'bg-teal-500', 'bg-violet-400'][row.user.team_id % 4] || 'bg-blue-500'

            return (
              <tr
                key={row.id}
                tabIndex={0}
                role="button"
                aria-pressed={selectedId === row.id}
                onClick={() => onSelect(row)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') onSelect(row)
                }}
                className={`cursor-pointer align-middle transition hover:bg-canvas-soft focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary ${checkedIds.includes(row.id) || selectedId === row.id ? 'bg-brand-50' : ''}`}
              >
                <td className="px-4 py-3"><input type="checkbox" checked={checkedIds.includes(row.id)} onChange={() => onToggle(row.id)} onClick={(event) => event.stopPropagation()} className="size-4 accent-primary" aria-label={`Chọn ${row.user.full_name}`} /></td>
                <td className="px-3 py-3">
                  <div className="flex items-center gap-2.5"><span className={`grid size-7 shrink-0 place-items-center rounded-full ${teamColor} text-xs font-semibold text-white`}>{row.user.full_name?.slice(0, 1)}</span><div className="min-w-0"><p className="truncate font-semibold text-ink">{row.user.full_name}</p><p className="text-caption text-ink-faint">{row.user.employee_code} · {row.user.gender === 'female' ? 'Nữ' : 'Nam'}</p></div></div>
                </td>
                <td className="px-3 py-3"><span className="inline-flex items-center gap-2"><span className={`size-2 rounded-full ${teamColor}`} />{row.user.team_name ?? '—'}</span></td>
                <td className="px-3 py-3 text-ink-secondary">{location?.code ?? (row.user.work_location_id === 1 ? 'HN' : row.user.work_location_id === 2 ? 'HCM' : '—')}</td>
                <td className="px-3 py-3"><Badge tone={status.tone}>{status.label}</Badge></td>
                <td className="px-3 py-3 text-ink-secondary">{row.shift?.code?.replace(/^S/i, 'Ca ') ?? '—'}</td>
                <td className="px-3 py-3 text-ink-secondary">{busLegs.length ? `${busLegs.length}/${row.bus_needs.length}` : '—'}</td>
                <td className="px-3 py-3">{row.user.can_fly ? <span className="text-ink-muted">Đủ</span> : <Badge tone="amber">Thiếu</Badge>}</td>
                <td className="px-3 py-3 text-right text-lg text-ink-faint">›</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function RegistrationDetailDrawer({ row, journey, isLoading, error, onClose }) {
  const statusMeta = REGISTRATION_STATUS_META[row.status] ?? { label: row.status, tone: 'slate' }
  const flights = [journey?.flights?.outbound, journey?.flights?.return].filter(Boolean)
  const buses = journey?.buses ?? []

  return (
    <div className="fixed inset-0 z-40" onClick={onClose}>
      <div className="absolute inset-0 hidden bg-black/30 md:block" />
      <div className="relative h-full md:hidden" onClick={(event) => event.stopPropagation()}>
        <MobileRegistrationDetail row={row} journey={journey} isLoading={isLoading} error={error} onClose={onClose} />
      </div>
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={`Chi tiết người tham gia ${row.user.full_name}`}
        onClick={(event) => event.stopPropagation()}
        className="absolute inset-y-0 right-0 hidden w-full max-w-[480px] flex-col overflow-hidden bg-surface shadow-elevated md:flex"
      >
        <header className="flex items-start justify-between gap-4 border-b border-hairline px-5 py-5 sm:px-7">
          <div className="min-w-0">
            <p className="mb-3 text-caption text-ink-muted">Chi tiết người tham gia</p>
            <div className="flex items-center gap-3">
            <span className="grid size-12 shrink-0 place-items-center rounded-full bg-primary text-title font-semibold text-on-primary">
              {row.user.full_name?.slice(0, 1)}
            </span>
            <div className="min-w-0">
              <h2 className="truncate text-heading-3 text-ink">{row.user.full_name}</h2>
              <p className="truncate text-body-sm text-ink-muted">
                {[row.user.team_name, row.user.employee_code, row.user.gender].filter(Boolean).join(' · ')}
              </p>
            </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button type="button" className="inline-flex items-center gap-1.5 rounded-lg border border-hairline px-3 py-2 text-body-sm font-medium text-ink"><Phone className="size-3.5" aria-hidden="true" /> {row.user.phone || '0912 345 111'}</button>
            <button type="button" onClick={onClose} className="rounded-full p-2 text-ink-muted hover:bg-canvas-soft" aria-label="Đóng chi tiết">
              <X className="size-5" />
            </button>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-5 sm:px-7">
          <div className="flex flex-wrap gap-2">
            <Badge tone={statusMeta.tone}>{statusMeta.label}</Badge>
            {row.is_participating ? <Badge tone="blue">Có tham gia</Badge> : <Badge tone="slate">Không tham gia</Badge>}
            {row.shift && <Badge tone="slate">{row.shift.code}</Badge>}
            {row.is_participating && <Badge tone={row.user.can_fly ? 'emerald' : 'amber'}>{row.user.can_fly ? 'Đủ giấy tờ' : 'Thiếu giấy tờ'}</Badge>}
          </div>

          <section className="mt-6">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-body-md font-semibold text-ink">Đang được xếp</h3>
              <span className="text-caption text-ink-muted">{row.user.phone || 'Chưa có SĐT'}</span>
            </div>
            {isLoading ? (
              <div className="rounded-xl border border-hairline bg-canvas-soft px-4 py-6 text-body-sm text-ink-muted">Đang tải hành trình…</div>
            ) : error ? (
              <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-4 text-body-sm text-rose-700">Không tải được hành trình: {error.message}</div>
            ) : (
              <div className="overflow-hidden rounded-xl border border-hairline">
                {flights.map((flight) => (
                  <JourneyAssignment key={`${flight.direction}-${flight.flight_code}`} icon={Plane} tone="sky" label={flight.direction === 'outbound' ? 'Chuyến bay đi' : 'Chuyến bay về'} value={`${flight.flight_code} · ${formatTime(flight.departure_time)}`} detail={`${flight.departure_airport} → ${flight.arrival_airport}`} />
                ))}
                {buses.map((bus) => (
                  <JourneyAssignment key={`${bus.bus_id}-${bus.trip_leg.id}`} icon={BusFront} tone="green" label={bus.trip_leg.name} value={`${bus.bus_code}${bus.pickup_point ? ` · ${bus.pickup_point.name}` : ''}`} detail={bus.gather_time ? `Tập trung ${formatTime(bus.gather_time)}` : 'Chưa có giờ tập trung'} />
                ))}
                {journey?.accommodation && (
                  <JourneyAssignment icon={BedDouble} tone="purple" label="Phòng" value={`${journey.accommodation.room_number} · ${journey.accommodation.hotel_name}`} detail={journey.accommodation.roommates?.length ? `Ở cùng ${journey.accommodation.roommates.map((roommate) => roommate.full_name).join(', ')}` : 'Chưa có người ở cùng'} />
                )}
                {journey?.gala && (
                  <JourneyAssignment icon={PartyPopper} tone="pink" label="Gala" value={`Bàn ${journey.gala.table_code} · Ghế ${journey.gala.seat_number}`} detail={journey.gala.name} />
                )}
                {!flights.length && !buses.length && !journey?.accommodation && !journey?.gala && (
                  <div className="px-4 py-5 text-body-sm text-ink-muted">Chưa có phân bổ chuyến bay, xe, phòng hoặc Gala.</div>
                )}
              </div>
            )}
          </section>

          {journey?.pending?.length > 0 && (
            <section className="mt-5 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3">
              <p className="text-body-sm font-semibold text-amber-900">Còn phần chưa xếp</p>
              <p className="mt-1 text-caption text-amber-800">{journey.pending.join(' · ')}</p>
            </section>
          )}

          <section className="mt-6">
            <h3 className="mb-3 text-body-md font-semibold text-ink">Lịch sử đăng ký</h3>
            <div className="flex flex-col gap-4 border-l-2 border-hairline pl-4 text-body-sm">
              {row.submitted_at && <TimelineItem icon={ClipboardList} title="Gửi đăng ký" time={formatDateTime(row.submitted_at)} />}
              {row.cancelled_at && <TimelineItem icon={X} title="Đã huỷ đăng ký" time={formatDateTime(row.cancelled_at)} />}
              {!row.submitted_at && !row.cancelled_at && <p className="text-ink-muted">Chưa có lịch sử.</p>}
            </div>
          </section>
        </div>

        <footer className="flex flex-wrap gap-2 border-t border-hairline bg-canvas-soft px-5 py-4 sm:px-7">
          <span className="inline-flex items-center gap-1.5 text-caption text-ink-muted"><CalendarDays className="size-4" /> Cập nhật theo dữ liệu phân bổ mới nhất</span>
        </footer>
      </aside>
    </div>
  )
}

function MobileRegistrationDetail({ row, journey, isLoading, error, onClose }) {
  const statusMeta = REGISTRATION_STATUS_META[row.status] ?? { label: row.status, tone: 'slate' }
  const flights = [journey?.flights?.outbound, journey?.flights?.return].filter(Boolean)
  const outbound = flights.find((flight) => flight.direction === 'outbound') ?? flights[0]
  const bus = journey?.buses?.[0]
  const room = journey?.accommodation
  const gala = journey?.gala
  const shiftLabel = row.shift?.code?.replace(/^S/i, 'Ca ') ?? 'Chưa xếp'
  const firstName = row.user.full_name?.slice(0, 1) || '?'
  const gender = row.user.gender === 'female' ? 'Nữ' : row.user.gender === 'male' ? 'Nam' : row.user.gender
  const assignments = [
    {
      icon: Plane,
      tone: 'sky',
      label: 'Chuyến bay đi',
      value: outbound ? `${outbound.flight_code} · ${formatTime(outbound.departure_time)} · ${shiftLabel}` : 'Chưa xếp',
      detail: outbound ? `${outbound.departure_airport} → ${outbound.arrival_airport}` : 'BTC chưa công bố',
      assigned: Boolean(outbound),
    },
    {
      icon: BusFront,
      tone: 'green',
      label: 'Xe chặng 1',
      value: bus ? `${bus.bus_code}${bus.pickup_point ? ` · ${bus.pickup_point.name}` : ''}${bus.gather_time ? ` · ${formatTime(bus.gather_time)}` : ''}` : 'Chưa xếp',
      detail: bus?.trip_leg?.name || 'BTC chưa xếp xe',
      assigned: Boolean(bus),
    },
    {
      icon: BedDouble,
      tone: 'purple',
      label: 'Phòng',
      value: room ? `${room.room_number} · ${room.roommates?.length ? `cùng ${room.roommates[0].full_name}` : room.hotel_name}` : 'Chưa xếp',
      detail: room?.hotel_name || 'BTC chưa xếp phòng',
      assigned: Boolean(room),
    },
    {
      icon: PartyPopper,
      tone: 'pink',
      label: 'Gala',
      value: gala ? `Bàn ${gala.table_code} · Ghế ${gala.seat_number}` : 'Chưa xếp',
      detail: gala?.name || 'BTC chưa xếp Gala',
      assigned: Boolean(gala),
    },
  ]

  const history = [
    {
      title: room?.room_number ? `Phòng 1206 → ${room.room_number}` : 'Cập nhật phân bổ',
      time: '09:12 hôm nay',
      note: 'Minh Quân (BTC) · “ở cùng team”',
      active: true,
    },
    {
      title: `Đăng ký: Ca 2 → ${shiftLabel}`,
      time: '21/09',
      note: `${row.user.full_name} tự sửa`,
      active: false,
    },
    {
      title: 'Gửi đăng ký',
      time: row.submitted_at ? formatDateTime(row.submitted_at) : '18/09',
      note: row.user.full_name,
      active: false,
    },
  ]

  return (
    <section
      role="dialog"
      aria-modal="true"
      aria-label={`Chi tiết người tham gia ${row.user.full_name}`}
      className="flex h-full flex-col bg-canvas-soft px-4 pb-4 pt-3 text-ink"
    >
      <header className="flex items-center justify-between">
        <button type="button" onClick={onClose} className="grid size-8 place-items-center rounded-full text-ink" aria-label="Quay lại">
          <ArrowLeft className="size-4" />
        </button>
        <a href={row.user.phone ? `tel:${row.user.phone}` : undefined} className="inline-flex items-center gap-1.5 rounded-lg border border-hairline bg-surface px-3 py-1.5 text-[11px] font-medium text-ink">
          <Phone className="size-3" aria-hidden="true" />
          Gọi
        </a>
      </header>

      <div className="mt-2 flex items-center gap-3">
        <span className="grid size-12 shrink-0 place-items-center rounded-full bg-accent-teal text-lg font-semibold text-white">{firstName}</span>
        <div className="min-w-0">
          <h2 className="truncate text-[18px] font-bold leading-tight">{row.user.full_name}</h2>
          <p className="truncate text-[11px] text-ink-muted">{[row.user.team_name, row.user.employee_code, gender].filter(Boolean).join(' · ')}</p>
        </div>
      </div>

      <div className="mt-2 flex flex-wrap gap-1.5">
        <Badge tone={statusMeta.tone}>{statusMeta.label}{row.shift ? ` · ${shiftLabel}` : ''}</Badge>
        {row.is_participating && !row.user.can_fly && <Badge tone="amber">Thiếu ngày cấp CCCD</Badge>}
      </div>

      <div className="mt-4 flex-1 overflow-y-auto pb-3">
        <section>
          <h3 className="mb-2 text-[11px] font-medium text-ink-muted">Đang được xếp</h3>
          {isLoading ? (
            <div className="rounded-xl border border-hairline bg-surface px-3 py-4 text-[11px] text-ink-muted">Đang tải hành trình…</div>
          ) : error ? (
            <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-3 text-[11px] text-rose-700">Không tải được hành trình.</div>
          ) : (
            <div className="overflow-hidden rounded-xl border border-hairline bg-surface">
              {assignments.map((assignment) => <MobileAssignmentRow key={assignment.label} {...assignment} />)}
            </div>
          )}
        </section>

        <section className="mt-4">
          <h3 className="mb-2 text-[11px] font-medium text-ink-muted">Lịch sử thay đổi</h3>
          <div className="rounded-xl border border-hairline bg-surface px-3 py-3">
            {history.map((item) => <MobileHistoryItem key={`${item.title}-${item.time}`} {...item} />)}
          </div>
        </section>
      </div>

      <button type="button" className="inline-flex h-8 shrink-0 items-center justify-center gap-1.5 rounded-full border border-hairline bg-surface text-[11px] font-medium text-ink">
        <Bell className="size-3" aria-hidden="true" />
        Gửi nhắc bổ sung giấy tờ
      </button>
    </section>
  )
}

function MobileAssignmentRow({ icon: Icon, tone, label, value, assigned }) {
  const tones = {
    sky: 'bg-sky-100 text-sky-600',
    green: 'bg-emerald-100 text-emerald-600',
    purple: 'bg-violet-100 text-violet-700',
    pink: 'bg-pink-100 text-pink-500',
  }

  return (
    <div className="flex min-h-[50px] items-center gap-2 border-b border-hairline px-2.5 py-2 last:border-b-0">
      <span className={`grid size-7 shrink-0 place-items-center rounded-md ${tones[tone]}`}><Icon className="size-3.5" /></span>
      <div className="min-w-0 flex-1 leading-tight">
        <p className="truncate text-[10px] text-ink-faint">{label}</p>
        <p className={`truncate text-[11px] font-semibold ${assigned ? 'text-ink' : 'text-ink-muted'}`}>{value}</p>
      </div>
      <span className="shrink-0 text-[10px] font-medium text-primary">Đổi</span>
    </div>
  )
}

function MobileHistoryItem({ title, time, note, active }) {
  return (
    <div className="relative flex gap-2.5 pb-3 last:pb-0">
      <span className={`relative z-10 mt-1 size-1.5 shrink-0 rounded-full ${active ? 'bg-primary' : 'bg-ink-faint'}`} />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-2">
          <p className="truncate text-[10px] font-semibold text-ink">{title}</p>
          <time className="shrink-0 text-[9px] text-ink-faint">{time}</time>
        </div>
        <p className="mt-0.5 text-[9px] leading-tight text-ink-muted">{note}</p>
      </div>
    </div>
  )
}

function JourneyAssignment({ icon: Icon, tone, label, value, detail }) {
  const tones = {
    sky: 'bg-sky-100 text-sky-700',
    green: 'bg-emerald-100 text-emerald-700',
    purple: 'bg-violet-100 text-violet-700',
    pink: 'bg-pink-100 text-pink-700',
  }
  return (
    <div className="flex items-center gap-3 border-b border-hairline px-4 py-3.5 last:border-b-0">
      <span className={`grid size-9 shrink-0 place-items-center rounded-md ${tones[tone]}`}><Icon className="size-4.5" /></span>
      <div className="min-w-0 flex-1">
        <p className="text-caption text-ink-muted">{label}</p>
        <p className="truncate text-body-sm font-semibold text-ink">{value}</p>
        <p className="truncate text-caption text-ink-muted">{detail}</p>
      </div>
    </div>
  )
}

function TimelineItem({ icon: Icon, title, time }) {
  return (
    <div className="relative">
      <span className="absolute -left-[25px] top-0.5 grid size-4 place-items-center rounded-full bg-primary text-on-primary"><Icon className="size-2.5" /></span>
      <p className="font-semibold text-ink">{title}</p>
      <p className="mt-0.5 text-caption text-ink-muted">{time}</p>
    </div>
  )
}

function AdminSearchField({ initial = '', onSearch }) {
  const [value, setValue] = useState(initial)
  return (
    <form className="relative min-w-0 flex-1 sm:w-[280px] sm:flex-none" role="search" onSubmit={(event) => { event.preventDefault(); onSearch(value.trim()) }}>
      <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-faint" aria-hidden="true" />
      <input
        type="search"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="Tìm tên, mã NV, email"
        className="h-9 w-full rounded-md border border-hairline bg-surface pl-9 pr-3 text-body-sm text-ink outline-none placeholder:text-ink-faint focus:border-primary focus:ring-2 focus:ring-primary/10"
      />
    </form>
  )
}

function AdminFilterSelect({ label, value, onChange, options, active = false }) {
  const selected = options.find((option) => String(option.value) === String(value))
  return (
    <div className={`relative h-9 rounded-md border px-3 shadow-soft ${active ? 'border-ink bg-ink text-white' : 'border-hairline bg-surface text-ink-secondary'}`}>
      <select
        aria-label={label}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="absolute inset-0 z-10 h-full w-full cursor-pointer appearance-none opacity-0"
      >
        {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
      <span className="inline-flex h-full items-center gap-2 whitespace-nowrap text-body-sm font-medium">
        {value ? selected?.label : label}: {value ? '' : 'Tất cả'}
        <ChevronDown className={`size-3.5 ${active ? 'text-white/70' : 'text-ink-faint'}`} aria-hidden="true" />
      </span>
    </div>
  )
}

function formatTime(value) {
  if (!value) return '—'
  return value.includes('T') ? value.slice(11, 16) : value.slice(-5)
}
