import { Check } from 'lucide-react'
import { EVENT_LIFECYCLE } from '../../../utils/constants'

/**
 * Dải 7 bước của kỳ (Figma v2 · B1): bước đã qua tô đen, bước hiện tại tô primary, bước sau chỉ có viền.
 * `action` là nút chuyển trạng thái, đặt cuối dải để "đang ở đâu" và "bước kế tiếp" nằm trên một hàng.
 */
export default function LifecycleStepper({ status, statusLabel, action }) {
  const current = Math.max(
    EVENT_LIFECYCLE.findIndex((step) => step.status === status),
    0,
  )

  return (
    <nav aria-label="Vòng đời chương trình" className="flex flex-wrap items-center gap-x-5 gap-y-3">
      {/* Điện thoại: 7 nhãn không vừa một hàng, chỉ cần biết đang ở bước mấy */}
      <div className="min-w-0 flex-1 basis-full lg:hidden">
        <div className="flex items-baseline justify-between gap-3">
          <span className="text-body-sm font-semibold text-ink">{statusLabel}</span>
          <span className="text-eyebrow text-ink-muted tabular-nums">
            Bước {current + 1}/{EVENT_LIFECYCLE.length}
          </span>
        </div>
        <div className="mt-2 flex gap-1" aria-hidden="true">
          {EVENT_LIFECYCLE.map((step, index) => (
            <span
              key={step.status}
              className={`h-1 flex-1 rounded-full ${
                index < current ? 'bg-ink' : index === current ? 'bg-primary' : 'bg-hairline'
              }`}
            />
          ))}
        </div>
      </div>

      <ol className="hidden min-w-0 flex-1 items-center lg:flex">
        {EVENT_LIFECYCLE.map((step, index) => {
          const done = index < current
          const active = index === current
          return (
            <li key={step.status} className="flex min-w-0 flex-1 items-center last:flex-none">
              <span
                className={`flex items-center gap-2 text-caption whitespace-nowrap ${
                  active ? 'font-bold text-ink' : done ? 'text-ink-muted' : 'text-ink-faint'
                }`}
                aria-current={active ? 'step' : undefined}
              >
                <span
                  className={`grid size-4.5 shrink-0 place-items-center rounded-full text-[10px] font-bold ${
                    done
                      ? 'bg-ink text-on-primary'
                      : active
                        ? 'bg-primary text-on-primary'
                        : 'border-[1.5px] border-input-border'
                  }`}
                >
                  {done ? <Check className="size-2.5" strokeWidth={3.5} aria-hidden="true" /> : index + 1}
                </span>
                {step.label}
              </span>
              {index < EVENT_LIFECYCLE.length - 1 && (
                <span
                  className={`mx-3 h-px min-w-3 flex-1 ${done ? 'bg-ink' : 'bg-hairline'}`}
                  aria-hidden="true"
                />
              )}
            </li>
          )
        })}
      </ol>

      {action}
    </nav>
  )
}
