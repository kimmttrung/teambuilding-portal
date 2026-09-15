import { Check } from 'lucide-react'
import { EVENT_LIFECYCLE } from '../../../utils/constants'

/** Kỳ đang ở bước nào trong 7 bước — thay cho badge trạng thái lặp lại ở hai nơi. */
export default function LifecycleStepper({ status, statusLabel }) {
  const current = Math.max(
    EVENT_LIFECYCLE.findIndex((step) => step.status === status),
    0,
  )

  return (
    <nav aria-label="Vòng đời chương trình">
      {/* Điện thoại: 7 nhãn không vừa một hàng, chỉ cần biết đang ở bước mấy */}
      <div className="sm:hidden">
        <div className="flex items-baseline justify-between gap-3 text-sm">
          <span className="font-semibold text-slate-900">{statusLabel}</span>
          <span className="text-xs text-slate-500 tabular-nums">
            Bước {current + 1}/{EVENT_LIFECYCLE.length}
          </span>
        </div>
        <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-slate-100">
          <div
            className="h-full rounded-full bg-brand-600"
            style={{ width: `${((current + 1) / EVENT_LIFECYCLE.length) * 100}%` }}
          />
        </div>
      </div>

      <ol className="hidden items-center gap-2 sm:flex">
        {EVENT_LIFECYCLE.map((step, index) => {
          const done = index < current
          const active = index === current
          return (
            <li key={step.status} className="flex min-w-0 flex-1 items-center gap-2 last:flex-none">
              <span className="flex min-w-0 items-center gap-1.5" aria-current={active ? 'step' : undefined}>
                <span
                  className={`grid size-5 shrink-0 place-items-center rounded-full text-[11px] font-semibold ${
                    done
                      ? 'bg-emerald-500 text-white'
                      : active
                        ? 'bg-brand-600 text-white ring-4 ring-brand-100'
                        : 'bg-slate-100 text-slate-400'
                  }`}
                >
                  {done ? <Check className="size-3" strokeWidth={3} aria-hidden="true" /> : index + 1}
                </span>
                <span
                  className={`truncate text-xs ${
                    active ? 'font-semibold text-brand-700' : done ? 'text-slate-600' : 'text-slate-400'
                  }`}
                >
                  {step.label}
                </span>
              </span>
              {index < EVENT_LIFECYCLE.length - 1 && (
                <span
                  className={`h-0.5 min-w-2 flex-1 rounded-full ${done ? 'bg-emerald-300' : 'bg-slate-200'}`}
                  aria-hidden="true"
                />
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
