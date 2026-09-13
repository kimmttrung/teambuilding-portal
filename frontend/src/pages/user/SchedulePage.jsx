import { useMyJourney } from '../../hooks/useJourney'
import { formatDate } from '../../utils/format'
import Alert from '../../components/common/Alert'
import PageHeader from '../../components/common/PageHeader'
import Spinner from '../../components/common/Spinner'
import ItineraryPanel from './journey/ItineraryPanel'

/**
 * Lịch trình của riêng người đăng nhập: mục chung + mục của team + mục của ca được xếp.
 * Lấy từ `/journey/me` — backend đã lọc sẵn, frontend không tự đoán ca.
 */
export default function SchedulePage() {
  const { data: journey, isLoading, error } = useMyJourney()

  if (isLoading) return <Spinner label="Đang tải lịch trình…" />
  if (error) {
    return (
      <Alert tone="warning" title="Chưa xem được lịch trình">
        {error.message}
      </Alert>
    )
  }

  const { event } = journey

  return (
    <>
      <PageHeader
        title="Lịch trình chương trình"
        description={`${event.name} · ${formatDate(event.start_date)} – ${formatDate(event.end_date)}`}
      />
      {!event.is_published && (
        <Alert tone="info" className="mb-4">
          Hoạt động riêng theo ca bay sẽ hiện thêm khi BTC công bố kết quả phân bổ.
        </Alert>
      )}
      <ItineraryPanel items={journey.itinerary} variant="full" />
    </>
  )
}
