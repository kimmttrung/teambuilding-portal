import { Pencil, Trash2, UserCog, Users } from 'lucide-react'
import { formatTime } from '../../../utils/format'
import { BUS_LABELS, LOAD_WARNING_RATIO } from '../../../utils/constants'
import { telHref } from '../../../utils/travel'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import SlotBar from '../../../components/admin/SlotBar'
import { highlightTargets, usePersonLocation } from '../../../hooks/usePeople'
import { cardClass } from '../../../utils/highlight'
import busIcon from '../../../assets/buses/bus.svg'
import flightIcon from '../../../assets/buses/flight.svg'
import leaderIcon from '../../../assets/buses/leader.svg'
import missingLeaderIcon from '../../../assets/buses/leader-missing.svg'
import timingIcon from '../../../assets/buses/timing.svg'

/** Thẻ B7/L3: số ghế, điểm đón, giờ tập trung, chuyến bay và Trưởng xe. */
export default function BusCard({
  bus,
  onPassengers,
  onLeader,
  onEdit,
  onDelete,
}) {
  const { location } = usePersonLocation()
  const issues = bus.timing_issues ?? []
  return (
    <Card
      bodyClassName="p-0"
      className={cardClass(
        highlightTargets(location).buses.has(bus.id),
        issues.length ? 'border-rose-300' : '',
      )}
    >
      <div className="p-4">
        <div className="flex items-center gap-3">
          <span className="grid size-8 shrink-0 place-items-center rounded-md bg-accent-green">
            <img src={busIcon} alt="" />
          </span>
          <div className="min-w-0 flex-1">
            <h2 className="truncate text-body-md font-semibold">
              {bus.bus_code}
              <span className="ml-1 text-caption font-normal text-ink-muted">
                · {bus.plate_number ?? 'Chưa có biển số'}
              </span>
            </h2>
            <p className="mt-0.5 truncate text-caption text-ink-muted">
              {bus.gather_time ? formatTime(bus.gather_time) : 'Chưa có giờ'} ·{' '}
              {bus.pickup_point_name ?? 'Không cố định điểm đón'}
            </p>
          </div>
          <p className="shrink-0 text-body-md font-semibold tabular-nums">
            {bus.assigned_count}
            <span className="font-normal text-ink-faint">/{bus.capacity}</span>
          </p>
        </div>
        <SlotBar
          assigned={bus.assigned_count}
          usable={bus.capacity}
          showNumbers={false}
          className={`mt-4 ${bus.assigned_count / bus.capacity >= LOAD_WARNING_RATIO ? '[&_[role=meter]>div]:bg-accent-orange' : '[&_[role=meter]>div]:bg-ink'}`}
        />
        <div className="mt-3 flex flex-col gap-2 text-caption text-ink-muted">
          {bus.linked_flight_code && (
            <p className="flex items-center gap-2">
              <img src={flightIcon} alt="" />
              Chuyến bay {bus.linked_flight_code}
            </p>
          )}
          <div className="flex flex-wrap items-center gap-2">
            <img
              src={bus.leader_name ? leaderIcon : missingLeaderIcon}
              alt=""
            />
            {bus.leader_name ? (
              <p className="min-w-0 flex-1">
                Trưởng xe: {bus.leader_name}
                {bus.leader_phone && (
                  <a
                    href={telHref(bus.leader_phone)}
                    className="ml-1 text-primary"
                  >
                    · {bus.leader_phone}
                  </a>
                )}
              </p>
            ) : (
              <>
                <span className="flex-1 text-accent-orange">
                  {BUS_LABELS.noLeader}
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  className="min-h-11 text-primary sm:min-h-8"
                  onClick={onLeader}
                >
                  {BUS_LABELS.appoint}
                </Button>
              </>
            )}
          </div>
          {issues.map((issue) => (
            <p key={issue} className="flex items-start gap-2 text-rose-700">
              <img src={timingIcon} alt="" className="mt-1 shrink-0" />
              {issue.charAt(0).toUpperCase() + issue.slice(1)}
            </p>
          ))}
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-1 border-t border-hairline pt-2">
          <Button
            variant="ghost"
            size="sm"
            className="min-h-11 sm:min-h-8"
            icon={Users}
            onClick={onPassengers}
          >
            {BUS_LABELS.passengers}
          </Button>
          {bus.leader_name && (
            <Button
              variant="ghost"
              size="sm"
              className="min-h-11 sm:min-h-8"
              onClick={onLeader}
              icon={UserCog}
              aria-label={`Trưởng xe ${bus.bus_code}`}
              title={BUS_LABELS.leader}
            />
          )}
          <span className="ml-auto flex gap-1">
            <Button
              variant="ghost"
              size="sm"
              className="min-h-11 min-w-11 sm:min-h-8"
              icon={Pencil}
              onClick={onEdit}
              aria-label={`Sửa xe ${bus.bus_code}`}
            />
            <Button
              variant="ghost"
              size="sm"
              className="min-h-11 min-w-11 sm:min-h-8"
              icon={Trash2}
              onClick={onDelete}
              disabled={bus.assigned_count > 0}
              title={
                bus.assigned_count > 0
                  ? 'Chuyển hết hành khách trước khi xoá'
                  : 'Xoá xe'
              }
              aria-label={`Xoá xe ${bus.bus_code}`}
            />
          </span>
        </div>
      </div>
    </Card>
  )
}
