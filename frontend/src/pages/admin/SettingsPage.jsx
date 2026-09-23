import { Link, useSearchParams } from 'react-router-dom'
import { BookOpen, CalendarDays, FileText, Info, Plane, Route, SlidersHorizontal } from 'lucide-react'
import { useActiveEvent } from '../../hooks/useEvent'
import { useMasterData } from '../../hooks/useMasterData'
import { FLIGHT_DIRECTION_LABELS, NOTIFY_HINTS } from '../../utils/constants'
import Alert from '../../components/common/Alert'
import CrudSection from '../../components/admin/CrudSection'
import NotifyToggle from '../../components/admin/NotifyToggle'
import PageHeader from '../../components/common/PageHeader'
import Spinner from '../../components/common/Spinner'
import TabNav from '../../components/admin/TabNav'
import DocumentsTab from './settings/DocumentsTab'
import EventInfoTab from './settings/EventInfoTab'
import TermsTab from './settings/TermsTab'
import WeightsTab from './settings/WeightsTab'

/**
 * Cấu hình kỳ Team Building — mọi thứ trước đây phải làm bằng Swagger hoặc seed (docs/13 task 4).
 *
 * Chỉ chứa dữ liệu **gắn với kỳ đang chọn**. Phòng ban / địa điểm / team dùng chung mọi kỳ nên nằm ở
 * `/admin/master-data`; lịch trình có màn hình riêng vì nó là bảng dài, thao tác kéo thứ tự.
 */
const TABS = [
  { id: 'event', label: 'Thông tin kỳ', icon: Info },
  { id: 'terms', label: 'Quy định', icon: BookOpen },
  { id: 'documents', label: 'Tài liệu', icon: FileText },
  { id: 'shifts', label: 'Ca bay', icon: Plane },
  { id: 'legs', label: 'Chặng & điểm đón', icon: Route },
  { id: 'weights', label: 'Trọng số & Gala', icon: SlidersHorizontal },
]

export default function SettingsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { data: event, isLoading, error } = useActiveEvent()
  const { data: legs } = useMasterData('tripLegs', { enabled: true })
  const { data: locations } = useMasterData('workLocations')

  const tab = TABS.some((item) => item.id === searchParams.get('tab'))
    ? searchParams.get('tab')
    : TABS[0].id

  if (isLoading) return <Spinner label="Đang tải cấu hình kỳ…" />
  if (error) {
    return (
      <>
        <PageHeader title="Cấu hình kỳ" />
        <Alert tone="error" title="Không tải được kỳ">
          {error.message}
        </Alert>
      </>
    )
  }

  return (
    <>
      <PageHeader
        title="Cấu hình kỳ"
        description={`${event.name} · ${event.status_label}`}
        action={<NotifyToggle hint={NOTIFY_HINTS.config} />}
      />

      <TabNav
        tabs={TABS}
        current={tab}
        onChange={(next) => setSearchParams({ tab: next }, { replace: true })}
      />

      <div className="mt-4 grid gap-4 xl:grid-cols-12">
        <div className="min-w-0 xl:col-span-12">
          {tab === 'event' && <EventInfoTab event={event} />}
          {tab === 'terms' && <TermsTab event={event} />}
          {tab === 'documents' && <DocumentsTab />}

          {tab === 'shifts' && (
            <CrudSection
              resource="shifts"
              title="Ca bay"
              description="CBNV chọn ca khi đăng ký; thuật toán phân bổ cố gắng đáp ứng đúng ca"
              emptyTitle="Kỳ này chưa có ca bay nào"
              emptyHint="Chưa có ca thì CBNV không gửi được đăng ký tham gia."
              columns={[
                { key: 'code', label: 'Mã' },
                { key: 'name', label: 'Tên ca' },
                { key: 'earliest_departure', label: 'Bay sớm nhất' },
                { key: 'display_order', label: 'Thứ tự' },
              ]}
              fields={[
                { name: 'code', label: 'Mã ca', required: true, immutable: true, placeholder: 'CA1' },
                { name: 'name', label: 'Tên ca', required: true, placeholder: 'Ca 1 – bay sáng' },
                { name: 'description', label: 'Mô tả' },
                {
                  name: 'earliest_departure',
                  label: 'Giờ bay sớm nhất',
                  type: 'time',
                  hint: 'Giờ Việt Nam. Bỏ trống nếu không ràng buộc',
                },
                { name: 'display_order', label: 'Thứ tự hiển thị', type: 'number', defaultValue: 0 },
              ]}
            />
          )}

          {tab === 'legs' && (
            <div className="grid gap-4">
              <CrudSection
                resource="tripLegs"
                title="Chặng di chuyển"
                description="Mỗi chặng là một lần đi xe; CBNV khai nhu cầu xe theo từng chặng"
                emptyTitle="Kỳ này chưa có chặng nào"
                columns={[
                  { key: 'code', label: 'Mã' },
                  { key: 'name', label: 'Tên chặng' },
                  {
                    key: 'direction',
                    label: 'Chiều',
                    render: (row) => FLIGHT_DIRECTION_LABELS[row.direction] ?? row.direction,
                  },
                  { key: 'leg_date', label: 'Ngày' },
                ]}
                fields={[
                  {
                    name: 'code', label: 'Mã chặng', required: true, immutable: true,
                    placeholder: 'CITY_TO_AIRPORT',
                  },
                  { name: 'name', label: 'Tên chặng', required: true, placeholder: 'HN/HCM → Sân bay' },
                  {
                    name: 'direction',
                    label: 'Chiều',
                    type: 'select',
                    required: true,
                    placeholder: '— Chọn chiều —',
                    options: Object.entries(FLIGHT_DIRECTION_LABELS).map(([value, label]) => ({
                      value,
                      label,
                    })),
                  },
                  { name: 'leg_date', label: 'Ngày đi chặng này', type: 'date' },
                  { name: 'is_airport_linked', label: 'Gắn với chuyến bay', type: 'checkbox' },
                  { name: 'display_order', label: 'Thứ tự hiển thị', type: 'number', defaultValue: 0 },
                ]}
              />

              <CrudSection
                resource="pickupPoints"
                title="Điểm đón / trả"
                description="CBNV chọn điểm đón khi đăng ký; xe gom người theo điểm đón"
                emptyTitle="Kỳ này chưa có điểm đón nào"
                columns={[
                  { key: 'name', label: 'Tên' },
                  { key: 'address', label: 'Địa chỉ' },
                  {
                    key: 'trip_leg_id',
                    label: 'Chặng',
                    render: (row) =>
                      (legs ?? []).find((leg) => leg.id === row.trip_leg_id)?.name ?? '—',
                  },
                  {
                    key: 'work_location_id',
                    label: 'Nơi làm việc',
                    render: (row) =>
                      (locations ?? []).find((item) => item.id === row.work_location_id)?.name ?? '—',
                  },
                ]}
                fields={[
                  { name: 'name', label: 'Tên điểm đón', required: true, placeholder: 'Toà nhà Keangnam' },
                  { name: 'address', label: 'Địa chỉ' },
                  {
                    name: 'trip_leg_id',
                    label: 'Thuộc chặng',
                    type: 'select',
                    numeric: true,
                    options: (legs ?? []).map((leg) => ({ value: leg.id, label: leg.name })),
                  },
                  {
                    name: 'work_location_id',
                    label: 'Dành cho nơi làm việc',
                    type: 'select',
                    numeric: true,
                    options: (locations ?? []).map((item) => ({ value: item.id, label: item.name })),
                  },
                  { name: 'map_url', label: 'Link Google Maps' },
                  { name: 'display_order', label: 'Thứ tự hiển thị', type: 'number', defaultValue: 0 },
                ]}
              />
            </div>
          )}

          {tab === 'weights' && <WeightsTab event={event} />}

          <Alert tone="info" className="mt-4">
            <span className="flex flex-wrap items-center gap-1">
              <CalendarDays className="size-4 shrink-0" aria-hidden="true" />
              Lịch trình chương trình quản lý ở màn hình riêng:
              <Link to="/admin/itinerary" className="font-medium underline">
                Mở Lịch trình
              </Link>
            </span>
          </Alert>
        </div>
      </div>
    </>
  )
}
