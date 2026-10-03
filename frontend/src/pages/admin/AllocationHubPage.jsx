import { Link } from 'react-router-dom'
import { ArrowRight, CalendarDays } from 'lucide-react'
import { useDashboard } from '../../hooks/useDashboard'
import { formatNumber } from '../../utils/format'
import Alert from '../../components/common/Alert'
import PageHeader from '../../components/common/PageHeader'
import Spinner from '../../components/common/Spinner'
import { allocationOpened, buildAllocationTiles } from './dashboard/AllocationProgress'

/** Đường vào và lời mô tả của từng mảng; con số lấy từ `buildAllocationTiles` (cùng nguồn với dashboard). */
const SECTIONS = {
  flights: { to: '/admin/flights', title: 'Chuyến bay', description: 'Khai chuyến, số ghế và xếp người lên từng chuyến.' },
  buses: { to: '/admin/buses', title: 'Xe', description: 'Xe theo từng chặng, điểm đón và Trưởng xe.' },
  rooms: { to: '/admin/rooms', title: 'Phòng', description: 'Khách sạn, sơ đồ phòng theo tầng và xếp người ở.' },
  gala: { to: '/admin/gala', title: 'Gala', description: 'Sơ đồ bàn, bốc thăm lượt chọn và ghế của từng team.' },
}

/**
 * Trang gom năm màn hình phân bổ — mục "Phân bổ" trên menu dẫn tới đây thay vì xổ năm mục con.
 * Một request `/admin/dashboard`; số liệu do backend đếm.
 */
export default function AllocationHubPage() {
  const { data, isLoading, error } = useDashboard()

  if (isLoading) return <Spinner label="Đang tải tiến độ phân bổ…" />
  if (error) {
    return (
      <Alert tone="error" title="Không tải được tiến độ phân bổ">
        {error.message}
      </Alert>
    )
  }

  const tiles = buildAllocationTiles({
    status: data.event.status,
    participants: data.registrations.participating,
    flights: data.flights,
    buses: data.buses,
    rooms: data.rooms,
    gala: data.gala,
  })

  return (
    <>
      <PageHeader
        title="Phân bổ"
        description={
          allocationOpened(data.event.status)
            ? `${formatNumber(data.registrations.participating)} người tham gia cần xếp chuyến bay, xe, phòng và ghế Gala.`
            : 'Danh sách người đi còn thay đổi cho tới khi đóng đăng ký. Có thể khai trước chuyến bay, xe và phòng.'
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {tiles.map((tile) => (
          <HubCard key={tile.kind} {...tile} {...SECTIONS[tile.kind]} />
        ))}
        <HubCard
          to="/admin/itinerary"
          icon={CalendarDays}
          sticker="bg-accent-orange"
          title="Lịch trình"
          description="Các mốc của chương trình theo ngày, theo ca và theo team."
        />
      </div>
    </>
  )
}

function HubCard({ to, icon: Icon, sticker, title, description, done, total, note, emptyNote, warning }) {
  const counted = total !== undefined

  return (
    <Link
      to={to}
      className="group flex min-h-48 flex-col rounded-lg border border-hairline bg-surface p-6 transition hover:shadow-soft"
    >
      <div className="flex items-start justify-between gap-3">
        {/* Sticker màu chỉ để phân loại các mảng phân bổ (design-notion: bảng sticker là trang trí). */}
        <span className={`grid size-10 place-items-center rounded-md text-on-primary ${sticker}`}>
          <Icon className="size-5" aria-hidden="true" />
        </span>
        <ArrowRight
          className="size-5 text-ink-faint transition group-hover:translate-x-0.5 group-hover:text-primary"
          aria-hidden="true"
        />
      </div>

      <h2 className="mt-4 text-heading-3 text-ink">{title}</h2>
      <p className="mt-1 text-body-sm text-ink-muted">{description}</p>

      {counted && (
        <div className="mt-auto pt-5">
          <p className="text-heading-2 text-ink tabular-nums">
            {total ? (
              <>
                {formatNumber(done)}
                <span className="text-ink-faint">/{formatNumber(total)}</span>
                <span className="ml-2 text-caption font-normal tracking-normal text-ink-muted">đã xếp</span>
              </>
            ) : (
              <span className="text-ink-faint">—</span>
            )}
          </p>
          <p className="mt-0.5 text-caption text-ink-faint">{total ? note : emptyNote}</p>
          {warning && <p className="mt-1.5 text-caption font-medium text-amber-800">{warning}</p>}
        </div>
      )}
    </Link>
  )
}
