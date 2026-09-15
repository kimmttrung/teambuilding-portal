import { Link } from 'react-router-dom'
import { AlertTriangle, BedDouble, Bus, PartyPopper, Plane } from 'lucide-react'
import { FLIGHT_DIRECTION_LABELS } from '../../../utils/constants'
import Card from '../../../components/common/Card'

/** Đã xếp bao nhiêu người so với số cần xếp, cho từng loại phân bổ. */
export default function AllocationProgress({ participants, flights, buses, rooms, gala, shiftDemand }) {
  const shifts = Object.entries(shiftDemand ?? {})

  return (
    <Card title="Tiến độ phân bổ" description="Số người đã được xếp so với số cần xếp">
      <div className="grid gap-x-8 gap-y-5 md:grid-cols-2">
        <Group title="Chuyến bay" icon={Plane} link="/admin/flights/board">
          {/* Nguyện vọng ca chỉ có ích trước khi công bố — là cơ sở để mua slot từng chuyến. */}
          {shifts.length > 0 && (
            <p className="-mt-1 text-xs text-slate-500">
              Nguyện vọng ca:{' '}
              {shifts.map(([shift, count], index) => (
                <span key={shift}>
                  {index > 0 && ' · '}
                  <span className="font-medium text-slate-700">{shift}</span> {count}
                </span>
              ))}
            </p>
          )}
          {flights.map((item) => (
            <ProgressRow
              key={item.direction}
              label={FLIGHT_DIRECTION_LABELS[item.direction] ?? item.direction}
              done={Math.max(participants - item.unassigned, 0)}
              total={participants}
              warning={
                item.flights === 0
                  ? 'Chưa khai chuyến nào'
                  : item.shortfall
                    ? `Thiếu ${item.shortfall} ghế`
                    : null
              }
            />
          ))}
        </Group>

        <Group title="Xe đưa đón" icon={Bus} link="/admin/buses">
          {buses.length === 0 ? (
            <p className="text-sm text-slate-500">Chưa khai chặng xe nào.</p>
          ) : (
            buses.map((leg) => (
              <ProgressRow
                key={leg.trip_leg_id}
                label={leg.name}
                done={leg.assigned}
                total={leg.demand}
                emptyText="Không ai cần xe"
                warning={
                  leg.demand && leg.buses === 0
                    ? 'Chưa có xe'
                    : leg.shortfall
                      ? `Thiếu ${leg.shortfall} ghế`
                      : null
                }
              />
            ))
          )}
        </Group>

        <Group title="Khách sạn" icon={BedDouble} link="/admin/rooms">
          <ProgressRow
            label="Đã có phòng"
            done={rooms.assigned}
            total={rooms.participants}
            warning={rooms.uncovered ? `${rooms.uncovered} người không còn giường hợp lệ` : null}
          />
          <p className="text-xs text-slate-500">{rooms.total_beds} giường đã khai</p>
        </Group>

        <Group title="Gala Dinner" icon={PartyPopper} link="/admin/gala">
          {gala.configured ? (
            <ProgressRow label="Ghế đã chốt" done={gala.assigned} total={gala.seats} />
          ) : (
            <p className="text-sm text-slate-500">Chưa cấu hình sơ đồ bàn.</p>
          )}
        </Group>
      </div>
    </Card>
  )
}

function Group({ title, icon: Icon, link, children }) {
  return (
    <section className="min-w-0">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="inline-flex items-center gap-1.5 text-xs font-semibold tracking-wide text-slate-500 uppercase">
          <Icon className="size-3.5" aria-hidden="true" />
          {title}
        </h3>
        {link && (
          <Link to={link} className="text-xs font-medium text-brand-700 hover:underline">
            Điều chỉnh
          </Link>
        )}
      </div>
      <div className="flex flex-col gap-3">{children}</div>
    </section>
  )
}

function ProgressRow({ label, done, total, warning, emptyText = 'Chưa có ai cần xếp' }) {
  if (!total) {
    return (
      <div className="flex items-center justify-between gap-3 text-sm">
        <span className="min-w-0 truncate text-slate-700">{label}</span>
        <span className="shrink-0 text-xs text-slate-400">{emptyText}</span>
      </div>
    )
  }

  const ratio = Math.min(done / total, 1)
  const complete = done >= total

  return (
    <div>
      <div className="flex items-baseline justify-between gap-3 text-sm">
        <span className="min-w-0 truncate text-slate-700">{label}</span>
        <span className="shrink-0 tabular-nums">
          <span className={`font-semibold ${complete ? 'text-emerald-700' : 'text-slate-900'}`}>
            {done}/{total}
          </span>
          <span className="ml-1 text-xs text-slate-400">({Math.round(ratio * 100)}%)</span>
        </span>
      </div>
      <div
        className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-100"
        role="meter"
        aria-valuenow={done}
        aria-valuemin={0}
        aria-valuemax={total}
        aria-label={`${label}: đã xếp ${done} trên ${total}`}
      >
        <div
          className={`h-full rounded-full ${complete ? 'bg-emerald-500' : 'bg-brand-500'}`}
          style={{ width: `${ratio * 100}%` }}
        />
      </div>
      {warning && (
        <p className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-amber-700">
          <AlertTriangle className="size-3" aria-hidden="true" />
          {warning}
        </p>
      )}
    </div>
  )
}
