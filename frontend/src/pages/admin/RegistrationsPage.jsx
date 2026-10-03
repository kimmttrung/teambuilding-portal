import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  ArrowLeft,
  BedDouble,
  BusFront,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  PartyPopper,
  Phone,
  Plane,
  Search,
  Send,
  X,
} from 'lucide-react'
import { useRegistrationFormOptions, useRegistrationList } from '../../hooks/useRegistration'
import { useJourneyOf } from '../../hooks/useJourney'
import { GENDER_LABELS, REGISTRATION_STATUS_META } from '../../utils/constants'
import { formatDateTime, formatNumber, formatPhone, formatShortDateTime, formatTime } from '../../utils/format'
import { teamDotClass } from '../../utils/rooms'
import Alert from '../../components/common/Alert'
import Badge from '../../components/common/Badge'
import Button from '../../components/common/Button'
import Card from '../../components/common/Card'
import EmptyState from '../../components/common/EmptyState'
import ExportButton from '../../components/common/ExportButton'
import Modal from '../../components/common/Modal'
import PageHeader from '../../components/common/PageHeader'
import Spinner from '../../components/common/Spinner'
import ReminderDialog from '../../components/admin/ReminderDialog'

const PAGE_SIZE = 20
const FILTER_KEYS = ['q', 'team_id', 'work_location_id', 'shift_id', 'status', 'is_participating', 'missing_documents']

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
  const locations = options?.work_locations ?? []
  const exportButton = (props) => (
    <ExportButton
      url="/registrations/export"
      fallbackName="dang-ky.xlsx"
      title="Toàn bộ đăng ký của kỳ, kèm sheet người chưa đăng ký — không theo bộ lọc"
      {...props}
    />
  )

  return (
    <>
      <PageHeader
        title="Đăng ký"
        description={
          data
            ? `${formatNumber(data.total)} đăng ký · ${options?.teams?.length ?? 0} team · ${locations.length} nơi làm việc`
            : undefined
        }
        className="mb-6 max-md:hidden"
        action={exportButton({ children: 'Xuất Excel' })}
      />

      <div className="mb-4 flex items-center gap-3 md:hidden">
        <Link to="/admin" className="grid size-8 place-items-center text-ink" aria-label="Quay lại"><ArrowLeft className="size-5" /></Link>
        <h1 className="text-page-title text-ink">Đăng ký <span className="ml-1 text-body-sm font-normal text-ink-faint">{data ? formatNumber(data.total) : '—'}</span></h1>
        {exportButton({ size: 'sm', className: 'ml-auto', children: 'Xuất' })}
      </div>

      <div className="flex flex-col gap-4 max-md:gap-3">
        <div className="flex flex-col gap-2 md:flex-row md:flex-wrap md:items-center">
          <SearchField key={filters.q ?? ''} initial={filters.q ?? ''} onSearch={(q) => update({ q })} />
          {/* Điện thoại: một hàng cuộn ngang, không xuống dòng chiếm nửa màn hình. */}
          <div className="flex gap-2 max-md:-mx-4 max-md:overflow-x-auto max-md:px-4 max-md:pb-1 md:flex-wrap md:items-center">
            <FilterSelect
              label="Trạng thái"
              value={filters.status ?? ''}
              onChange={(value) => update({ status: value })}
              options={Object.entries(REGISTRATION_STATUS_META).map(([value, meta]) => ({ value, label: meta.label }))}
            />
            <FilterSelect
              label="Team"
              value={filters.team_id ?? ''}
              onChange={(value) => update({ team_id: value })}
              options={(options?.teams ?? []).map((team) => ({ value: team.id, label: team.name }))}
            />
            <FilterSelect
              label="Nơi làm việc"
              value={filters.work_location_id ?? ''}
              onChange={(value) => update({ work_location_id: value })}
              options={locations.map((location) => ({ value: location.id, label: location.name }))}
            />
            <FilterSelect
              label="Ca đi"
              value={filters.shift_id ?? ''}
              onChange={(value) => update({ shift_id: value })}
              options={(options?.shifts ?? []).map((shift) => ({ value: shift.id, label: shift.name }))}
            />
            <FilterSelect
              label="Giấy tờ"
              value={filters.missing_documents === 'true' ? 'true' : ''}
              onChange={(value) => update({ missing_documents: value })}
              options={[{ value: 'true', label: 'Thiếu giấy tờ' }]}
            />
            {hasFilters && (
              <Button variant="ghost" size="sm" icon={X} className="shrink-0" onClick={() => setSearchParams(new URLSearchParams(), { replace: true })}>
                Xoá lọc
              </Button>
            )}
          </div>
        </div>

        {filters.missing_documents === 'true' && data?.total ? (
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-body-sm text-amber-900">
            <span>Đang lọc CBNV thiếu CCCD / ngày sinh.</span>
            <Button size="sm" icon={Send} onClick={() => setReminding(true)}>Gửi nhắc</Button>
          </div>
        ) : null}

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
              <RegistrationTable rows={data.items} locations={locations} selectedId={selected?.id} onSelect={setSelected} />
            </div>
            <div className="md:hidden">
              <MobileRegistrationList rows={data.items} onSelect={setSelected} />
            </div>
            <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-hairline px-4 py-2.5">
              <p className="text-caption text-ink-muted">
                Trang {page}/{totalPages} · {formatNumber(data.total)} đăng ký
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

      {selected && (
        <RegistrationDetailModal
          row={selected}
          journey={journey}
          isLoading={journeyLoading}
          error={journeyError}
          onRemind={() => setReminding(true)}
          onClose={() => setSelected(null)}
        />
      )}

      {reminding && <ReminderDialog kind="missing_documents" onClose={() => setReminding(false)} />}
    </>
  )
}

/** Nhãn trạng thái của một dòng: đã gửi nhưng báo không đi thì ghi rõ "Không đi". */
function statusOf(row) {
  if (row.status === 'submitted' && !row.is_participating) return { label: 'Không đi', tone: 'slate' }
  return REGISTRATION_STATUS_META[row.status] ?? { label: row.status, tone: 'slate' }
}

function Initial({ row, className }) {
  return (
    <span className={`grid shrink-0 place-items-center rounded-full font-semibold text-white ${teamDotClass(row.user.team_id)} ${className}`} aria-hidden="true">
      {row.user.full_name?.trim().slice(0, 1)}
    </span>
  )
}

function MobileRegistrationList({ rows, onSelect }) {
  return (
    <ul className="divide-y divide-hairline">
      {rows.map((row) => {
        const status = statusOf(row)
        return (
          <li key={row.id}>
            <button type="button" onClick={() => onSelect(row)} className="flex w-full items-center gap-3 px-4 py-3.5 text-left">
              <Initial row={row} className="size-9 text-caption" />
              <span className="min-w-0 flex-1">
                <span className="flex items-center justify-between gap-2">
                  <span className="truncate text-body-sm font-semibold text-ink">{row.user.full_name}</span>
                  <Badge tone={status.tone}>{status.label}</Badge>
                </span>
                <span className="mt-0.5 block truncate text-caption text-ink-muted">
                  {[row.user.team_name ?? 'Chưa gán team', row.shift?.name].filter(Boolean).join(' · ')}
                </span>
              </span>
              <ChevronRight className="size-4 shrink-0 text-ink-faint" aria-hidden="true" />
            </button>
          </li>
        )
      })}
    </ul>
  )
}

function RegistrationTable({ rows, locations, selectedId, onSelect }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[880px] text-body-sm">
        <thead>
          <tr className="border-b border-hairline bg-canvas-soft text-left text-eyebrow text-ink-muted">
            <th scope="col" className="px-4 py-3">Họ tên</th>
            <th scope="col" className="px-3 py-3">Team</th>
            <th scope="col" className="px-3 py-3">Nơi làm</th>
            <th scope="col" className="px-3 py-3">Trạng thái</th>
            <th scope="col" className="px-3 py-3">Ca</th>
            <th scope="col" className="px-3 py-3">Xe</th>
            <th scope="col" className="px-3 py-3">Giấy tờ</th>
            <th scope="col" className="w-10 px-3 py-3"><span className="sr-only">Mở chi tiết</span></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-hairline">
          {rows.map((row) => {
            const busLegs = row.bus_needs.filter((need) => need.needs_bus)
            const status = statusOf(row)
            const location = locations.find((item) => item.id === row.user.work_location_id)

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
                className={`cursor-pointer align-middle transition hover:bg-canvas-soft focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary ${selectedId === row.id ? 'bg-brand-50' : ''}`}
              >
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2.5">
                    <Initial row={row} className="size-7 text-eyebrow" />
                    <div className="min-w-0">
                      <p className="truncate font-semibold text-ink">{row.user.full_name}</p>
                      <p className="text-caption text-ink-faint">
                        {[row.user.employee_code, GENDER_LABELS[row.user.gender]].filter(Boolean).join(' · ') || row.user.email}
                      </p>
                    </div>
                  </div>
                </td>
                <td className="px-3 py-3">{row.user.team_name ?? '—'}</td>
                <td className="px-3 py-3 text-ink-secondary">{location?.name ?? '—'}</td>
                <td className="px-3 py-3"><Badge tone={status.tone}>{status.label}</Badge></td>
                <td className="px-3 py-3 text-ink-secondary">{row.shift?.code ?? '—'}</td>
                <td className="px-3 py-3 text-ink-secondary">{busLegs.length ? `${busLegs.length}/${row.bus_needs.length} chặng` : '—'}</td>
                <td className="px-3 py-3">{row.user.can_fly ? <span className="text-ink-muted">Đủ</span> : <Badge tone="amber">Thiếu</Badge>}</td>
                <td className="px-3 py-3 text-right"><ChevronRight className="inline size-4 text-ink-faint" aria-hidden="true" /></td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

/** Chi tiết một người, mở giữa màn hình: bên trái là đăng ký, bên phải là chỗ đang được xếp. */
function RegistrationDetailModal({ row, journey, isLoading, error, onRemind, onClose }) {
  const status = statusOf(row)
  const flights = [journey?.flights?.outbound, journey?.flights?.return].filter(Boolean)
  const buses = journey?.buses ?? []
  const nothingAssigned = !flights.length && !buses.length && !journey?.accommodation && !journey?.gala

  return (
    <Modal
      open
      size="xl"
      onClose={onClose}
      title={row.user.full_name}
      description={[row.user.team_name ?? 'Chưa gán team', row.user.employee_code, GENDER_LABELS[row.user.gender]].filter(Boolean).join(' · ')}
    >
      <div className="grid gap-x-8 gap-y-6 lg:grid-cols-2">
        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <Initial row={row} className="size-12 text-title" />
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={status.tone}>{status.label}</Badge>
              {row.shift && <Badge tone="slate">{row.shift.name}</Badge>}
              {row.is_participating && <Badge tone={row.user.can_fly ? 'emerald' : 'amber'}>{row.user.can_fly ? 'Đủ giấy tờ' : 'Thiếu giấy tờ'}</Badge>}
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {row.user.phone ? (
              <a href={`tel:${row.user.phone}`} className="inline-flex min-h-9 items-center gap-1.5 rounded-md border border-hairline px-3 text-caption font-medium text-ink hover:bg-canvas-soft">
                <Phone className="size-3.5" aria-hidden="true" /> {formatPhone(row.user.phone)}
              </a>
            ) : (
              <span className="inline-flex min-h-9 items-center text-caption text-ink-faint">Chưa có số điện thoại</span>
            )}
            {row.is_participating && !row.user.can_fly && (
              <Button variant="secondary" size="sm" icon={Send} onClick={onRemind}>Nhắc bổ sung giấy tờ</Button>
            )}
          </div>

          <section className="mt-6">
            <h3 className="mb-3 text-body-md font-semibold text-ink">Lịch sử đăng ký</h3>
            <div className="flex flex-col gap-4 border-l-2 border-hairline pl-4 text-body-sm">
              {row.submitted_at && <TimelineItem icon={ClipboardList} title="Gửi đăng ký" time={formatDateTime(row.submitted_at)} />}
              {row.cancelled_at && <TimelineItem icon={X} title="Đã huỷ đăng ký" time={formatDateTime(row.cancelled_at)} />}
              {!row.submitted_at && !row.cancelled_at && <p className="text-ink-muted">Chưa có lịch sử.</p>}
            </div>
          </section>
        </div>

        <div className="min-w-0">
          <section>
            <h3 className="mb-3 text-body-md font-semibold text-ink">Đang được xếp</h3>
            {isLoading ? (
              <div className="rounded-xl border border-hairline bg-canvas-soft px-4 py-6 text-body-sm text-ink-muted">Đang tải hành trình…</div>
            ) : error ? (
              <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-4 text-body-sm text-rose-700">Không tải được hành trình: {error.message}</div>
            ) : (
              <div className="overflow-hidden rounded-xl border border-hairline">
                {flights.map((flight) => (
                  <JourneyAssignment key={`${flight.direction}-${flight.flight_code}`} icon={Plane} sticker="bg-accent-sky" label={flight.direction === 'outbound' ? 'Chuyến bay đi' : 'Chuyến bay về'} value={`${flight.flight_code} · ${formatShortDateTime(flight.departure_time)}`} detail={`${flight.departure_airport} → ${flight.arrival_airport}`} />
                ))}
                {buses.map((bus) => (
                  <JourneyAssignment key={`${bus.bus_id}-${bus.trip_leg.id}`} icon={BusFront} sticker="bg-accent-green" label={bus.trip_leg.name} value={`${bus.bus_code}${bus.pickup_point ? ` · ${bus.pickup_point.name}` : ''}`} detail={bus.gather_time ? `Tập trung ${formatTime(bus.gather_time)}` : 'Chưa có giờ tập trung'} />
                ))}
                {journey?.accommodation && (
                  <JourneyAssignment icon={BedDouble} sticker="bg-accent-purple-deep" label="Phòng" value={`${journey.accommodation.room_number} · ${journey.accommodation.hotel_name}`} detail={journey.accommodation.roommates?.length ? `Ở cùng ${journey.accommodation.roommates.map((roommate) => roommate.full_name).join(', ')}` : 'Chưa có người ở cùng'} />
                )}
                {journey?.gala && (
                  <JourneyAssignment icon={PartyPopper} sticker="bg-accent-pink" label="Gala" value={`Bàn ${journey.gala.table_code} · Ghế ${journey.gala.seat_number}`} detail={journey.gala.name} />
                )}
                {nothingAssigned && (
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
        </div>
      </div>
    </Modal>
  )
}

function JourneyAssignment({ icon: Icon, sticker, label, value, detail }) {
  return (
    <div className="flex items-center gap-3 border-b border-hairline px-4 py-3.5 last:border-b-0">
      {/* Sticker màu chỉ để phân loại bốn mảng phân bổ, cùng màu với trang "Phân bổ". */}
      <span className={`grid size-9 shrink-0 place-items-center rounded-md text-on-primary ${sticker}`}><Icon className="size-4.5" aria-hidden="true" /></span>
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

function SearchField({ initial = '', onSearch }) {
  const [value, setValue] = useState(initial)
  return (
    <form className="relative min-w-0 md:w-[280px]" role="search" onSubmit={(event) => { event.preventDefault(); onSearch(value.trim()) }}>
      <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-faint" aria-hidden="true" />
      <input
        type="search"
        aria-label="Tìm tên, mã NV, email"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="Tìm tên, mã NV, email"
        className="h-11 w-full rounded-md border border-hairline bg-surface pl-9 pr-3 text-base text-ink outline-none placeholder:text-ink-faint focus:border-primary focus:ring-2 focus:ring-primary/10 md:h-9 md:text-body-sm"
      />
    </form>
  )
}

/** Ô lọc: chưa chọn thì trắng, đã chọn thì nền primary để nhìn lướt là biết đang lọc theo gì. */
function FilterSelect({ label, value, onChange, options }) {
  const selected = options.find((option) => String(option.value) === String(value))
  return (
    <div className={`relative h-11 shrink-0 rounded-md border px-3 md:h-9 ${value ? 'border-primary bg-primary text-on-primary' : 'border-hairline bg-surface text-ink-secondary'}`}>
      <select
        aria-label={label}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="absolute inset-0 z-10 h-full w-full cursor-pointer appearance-none opacity-0"
      >
        <option value="">Tất cả</option>
        {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
      <span className="inline-flex h-full items-center gap-2 whitespace-nowrap text-caption font-medium">
        {selected ? `${label}: ${selected.label}` : label}
        <ChevronDown className={`size-3.5 ${value ? 'text-on-primary/70' : 'text-ink-faint'}`} aria-hidden="true" />
      </span>
    </div>
  )
}
