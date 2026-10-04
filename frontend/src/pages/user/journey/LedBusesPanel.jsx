import { useLedBuses } from '../../../hooks/useBuses'
import { BUS_LABELS } from '../../../utils/constants'
import Alert from '../../../components/common/Alert'
import Button from '../../../components/common/Button'
import Spinner from '../../../components/common/Spinner'
import LedBusCard from './LedBusCard'

/** Độc lập /journey/me: Trưởng xe không đăng ký vẫn thấy xe được chỉ định. */
export default function LedBusesPanel({
  event,
  representedBusIds = [],
  onOpenPassengers,
}) {
  const query = useLedBuses({ enabled: Boolean(event?.is_published) })
  if (!event?.is_published) return null
  if (query.isLoading) return <Spinner label="Đang tải xe bạn phụ trách…" />
  if (query.error)
    return (
      <Alert tone="error" title="Không tải được xe bạn phụ trách">
        {query.error.message}
        <Button variant="secondary" onClick={() => query.refetch()}>
          {BUS_LABELS.retry}
        </Button>
      </Alert>
    )
  const buses = (query.data ?? []).filter(
    (bus) => !representedBusIds.includes(bus.id),
  )
  if (!buses.length) return null
  return (
    <section aria-label={BUS_LABELS.ledBuses} className="flex flex-col gap-4">
      <h2 className="text-title font-semibold">{BUS_LABELS.ledBuses}</h2>
      {buses.map((bus) => (
        <LedBusCard
          key={bus.id}
          bus={bus}
          onOpenPassengers={onOpenPassengers}
        />
      ))}
    </section>
  )
}
