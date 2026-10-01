import { useState } from 'react'
import { useBusPassengers } from '../../../hooks/useBuses'
import { BUS_LABELS } from '../../../utils/constants'
import { formatTime } from '../../../utils/format'
import { telHref } from '../../../utils/travel'
import Alert from '../../../components/common/Alert'
import Avatar from '../../../components/common/Avatar'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import EmptyState from '../../../components/common/EmptyState'
import Modal from '../../../components/common/Modal'
import SearchBox from '../../../components/common/SearchBox'
import Spinner from '../../../components/common/Spinner'
import leaderBadge from '../../../assets/buses/leader-badge.svg'
import callIcon from '../../../assets/buses/call.svg'

/** Chỉ đọc API đã kiểm tra quyền: không có chức năng xếp xe hay dữ liệu giấy tờ cá nhân. */
export default function BusPassengersModal({ bus, onClose }) {
  const query = useBusPassengers(bus?.bus_id ?? bus?.id)
  const [search, setSearch] = useState('')
  if (!bus) return null
  const allRows = query.error ? [] : (query.data ?? [])
  const rows = allRows.filter((row) =>
    `${row.full_name} ${row.team_name ?? ''} ${row.phone ?? ''}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  )
  const gather = bus.gather_time || bus.departure_time
  function phone(row) {
    return row.phone ? (
      <a
        href={telHref(row.phone)}
        aria-label={`Gọi ${row.full_name}`}
        className="inline-flex size-11 shrink-0 items-center justify-center rounded-full bg-primary text-on-primary hover:bg-primary-active"
      >
        <img src={callIcon} alt="" />
      </a>
    ) : (
      <span className="text-caption text-ink-faint">Chưa có SĐT</span>
    )
  }
  return (
    <Modal
      open
      size="lg"
      onClose={onClose}
      title={`Hành khách xe ${bus.bus_code}`}
      description={bus.trip_leg?.name ?? bus.trip_leg_name}
    >
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between gap-3">
          <p className="text-heading-2 font-bold tabular-nums">
            {query.data && !query.error ? allRows.length : '—'}
            <span className="text-ink-faint">/{bus.capacity}</span>
            <span className="ml-2 text-caption font-normal text-ink-muted">
              hành khách
            </span>
          </p>
          <span className="inline-flex items-center gap-1 rounded-sm bg-accent-green/10 px-2 py-1 text-eyebrow text-accent-green">
            <img src={leaderBadge} alt="" />
            {BUS_LABELS.leader}
          </span>
        </div>
        <Card bodyClassName="p-0">
          <div className="grid grid-cols-2 gap-4 p-4">
            <div>
              <p className="text-heading-2 font-bold tabular-nums">
                {gather ? formatTime(gather) : '—'}
              </p>
              <p className="mt-1 text-eyebrow text-ink-muted">
                Tập trung ·{' '}
                {bus.pickup_point?.name ??
                  bus.pickup_point_name ??
                  'Chưa chốt điểm đón'}
              </p>
            </div>
            <div>
              <p className="break-words text-title font-semibold">
                {bus.plate_number ?? 'Chưa có biển số'}
              </p>
              <p className="mt-1 text-caption text-ink-muted">
                {bus.driver_name
                  ? `Tài xế: ${bus.driver_name}`
                  : 'BTC chưa chốt tài xế'}
              </p>
              {bus.driver_phone && (
                <a
                  href={telHref(bus.driver_phone)}
                  className="inline-flex min-h-11 items-center text-caption text-primary"
                >
                  {bus.driver_phone}
                </a>
              )}
            </div>
          </div>
        </Card>
        <SearchBox
          label={BUS_LABELS.search}
          placeholder="Tên, team, số điện thoại"
          onSearch={setSearch}
        />
        {query.isLoading && <Spinner label="Đang tải danh sách…" />}
        {query.error && (
          <Alert tone="error">
            {query.error.message}
            <Button variant="secondary" onClick={() => query.refetch()}>
              {BUS_LABELS.retry}
            </Button>
          </Alert>
        )}
        {query.data && !query.error && !rows.length && (
          <EmptyState
            title={
              search ? 'Không tìm thấy hành khách' : 'Chưa có ai trên xe này'
            }
            description={
              search
                ? 'Thử từ khoá khác.'
                : 'Ban tổ chức chưa xếp hành khách vào xe bạn phụ trách.'
            }
          />
        )}
        {rows.length > 0 && (
          <>
            <Card bodyClassName="p-0" className="sm:hidden">
              <ul className="divide-y divide-hairline">
                {rows.map((row) => (
                  <li
                    key={row.assignment_id}
                    className="flex items-center gap-3 p-4"
                  >
                    <Avatar size="sm" user={row} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-body-sm font-semibold">
                        {row.full_name}
                      </p>
                      <p className="mt-1 truncate text-caption text-ink-muted">
                        {row.team_name ?? 'Chưa có team'}
                      </p>
                      <p className="mt-1 break-words text-caption text-ink-muted">
                        {[row.pickup_point_name, row.phone]
                          .filter(Boolean)
                          .join(' · ') || 'Chưa có điểm đón'}
                      </p>
                    </div>
                    {phone(row)}
                  </li>
                ))}
              </ul>
            </Card>
            <table className="hidden w-full text-left text-body-sm sm:table">
              <thead className="border-b border-hairline text-caption text-ink-muted">
                <tr>
                  <th className="pb-3 pr-3 font-medium">Hành khách</th>
                  <th className="pb-3 pr-3 font-medium">Điểm đón / SĐT</th>
                  <th className="pb-3 font-medium">Liên hệ</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-hairline">
                {rows.map((row) => (
                  <tr key={row.assignment_id}>
                    <td className="py-3 pr-3">
                      <div className="flex items-center gap-3">
                        <Avatar user={row} size="sm" />
                        <div>
                          <p className="font-semibold">{row.full_name}</p>
                          <p className="mt-1 text-caption text-ink-muted">
                            {row.team_name ?? 'Chưa có team'}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="py-3 pr-3 text-caption text-ink-muted">
                      <p>{row.pickup_point_name ?? '—'}</p>
                      <p>{row.phone ?? '—'}</p>
                    </td>
                    <td className="py-3">{phone(row)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>
    </Modal>
  )
}
