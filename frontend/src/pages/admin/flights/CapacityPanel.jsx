import { AlertTriangle, CheckCircle2, Plane, Users } from 'lucide-react'
import { FLIGHT_DIRECTION_LABELS } from '../../../utils/constants'
import Alert from '../../../components/common/Alert'
import Card from '../../../components/common/Card'
import SlotBar from '../../../components/admin/SlotBar'

/**
 * Tình trạng slot trước khi phân bổ.
 *
 * Điểm quan trọng: `shortfall` theo TỪNG CA, không chỉ theo chiều. Tổng ghế đủ mà một ca
 * thừa cầu thì vẫn chắc chắn có người phải đổi ca — BTC cần biết điều đó trước khi bấm
 * phân bổ, chứ không phải đọc 43 dòng cảnh báo sau khi chạy.
 */
export default function CapacityPanel({ summary, shiftCodes = {} }) {
  if (!summary) return null

  const problems = summary.directions.flatMap((direction) => [
    ...(direction.shortfall > 0
      ? [
          `${FLIGHT_DIRECTION_LABELS[direction.direction]}: thiếu ${direction.shortfall} ghế cho ${summary.participants} người tham gia.`,
        ]
      : []),
    ...direction.by_shift
      .filter((shift) => shift.shortfall > 0)
      .map(
        (shift) =>
          `${FLIGHT_DIRECTION_LABELS[direction.direction]} — ${shift.shift_name}: ${shift.requested} người muốn nhưng chỉ có ${shift.usable_capacity} ghế (thiếu ${shift.shortfall}).`,
      ),
  ])

  return (
    <Card
      title="Slot so với số người tham gia"
      description={`${summary.participants} CBNV xác nhận tham gia`}
    >
      {problems.length > 0 ? (
        <Alert tone="warning" title="Cần xử lý trước khi phân bổ">
          <ul className="mt-1 list-disc space-y-1 pl-4">
            {problems.map((problem) => (
              <li key={problem}>{problem}</li>
            ))}
          </ul>
        </Alert>
      ) : (
        <p className="flex items-center gap-2 text-sm text-emerald-700">
          <CheckCircle2 className="size-4 shrink-0" aria-hidden="true" />
          Đủ ghế cho cả hai chiều và từng ca.
        </p>
      )}

      <div className="mt-3.5 grid gap-3 sm:grid-cols-2">
        {summary.directions.map((direction) => (
          <div
            key={direction.direction}
            className="rounded-lg border border-slate-200 p-3"
          >
            <div className="flex items-baseline justify-between gap-2">
              <p className="text-sm font-semibold text-slate-900">
                {FLIGHT_DIRECTION_LABELS[direction.direction]}
              </p>
              <p className="inline-flex items-center gap-1 text-xs text-slate-500">
                <Plane className="size-3.5" aria-hidden="true" />
                {direction.flights} chuyến
              </p>
            </div>

            <SlotBar
              assigned={direction.assigned}
              usable={direction.usable_capacity}
              className="mt-2"
            />

            <p className="mt-2 text-xs text-slate-500">
              {direction.capacity} ghế · giữ lại {direction.reserved} ·{' '}
              {direction.shortfall > 0 ? (
                <span className="font-semibold text-rose-700">thiếu {direction.shortfall}</span>
              ) : (
                <span className="text-emerald-700">đủ chỗ</span>
              )}
            </p>

            <ul className="mt-2.5 flex flex-col gap-1.5 border-t border-slate-100 pt-2.5">
              {direction.by_shift.map((shift) => (
                <li
                  key={`${direction.direction}-${shift.shift_id ?? 'none'}`}
                  className="flex items-center justify-between gap-2 text-xs"
                >
                  <span className="truncate text-slate-600">
                    {shiftCodes[shift.shift_id] ?? shift.shift_code}
                  </span>
                  <span className="shrink-0 tabular-nums text-slate-500">
                    {shift.usable_capacity} ghế
                    {shift.requested > 0 && (
                      <>
                        {' · '}
                        <Users className="inline size-3 -mt-0.5" aria-hidden="true" />{' '}
                        {shift.requested} muốn
                      </>
                    )}
                    {shift.shortfall > 0 && (
                      <span className="ml-1 inline-flex items-center gap-0.5 font-semibold text-rose-700">
                        <AlertTriangle className="size-3" aria-hidden="true" />
                        thiếu {shift.shortfall}
                      </span>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </Card>
  )
}
