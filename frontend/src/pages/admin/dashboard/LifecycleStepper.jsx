import { Check } from 'lucide-react'
import { EVENT_LIFECYCLE } from '../../../utils/constants'

/**
 * Dải 7 bước của kỳ: bước đã qua xanh lá có dấu tích, bước hiện tại primary, bước sau chỉ có viền.
 * `action` là các nút chuyển trạng thái, nằm ở hàng riêng phía trên để không lẫn với nhãn các bước.
 */
export default function LifecycleStepper({ status, statusLabel, action }) {
  const current = Math.max(
    EVENT_LIFECYCLE.findIndex((step) => step.status === status),
    0,
  )

  return (
    <nav aria-label="Vòng đời chương trình" className="rounded-lg border border-hairline bg-surface p-5">
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
        <div className="min-w-0">
          <p className="text-eyebrow text-ink-muted">
            Trạng thái kỳ · bước {current + 1}/{EVENT_LIFECYCLE.length}
          </p>
          <p className="mt-0.5 text-heading-3 text-ink">{statusLabel}</p>
        </div>
        {action}
      </div>

      {/* Điện thoại: 7 nhãn không vừa một hàng, chỉ cần biết đang ở bước mấy */}
      <div className="mt-4 flex gap-1.5 lg:hidden" aria-hidden="true">
        {EVENT_LIFECYCLE.map((step, index) => (
          <span
            key={step.status}
            className={`h-2 flex-1 rounded-full ${
              index < current ? 'bg-accent-green' : index === current ? 'bg-primary' : 'bg-hairline'
            }`}
          />
        ))}
      </div>

      <ol className="mt-5 hidden min-w-0 items-center lg:flex">
        {EVENT_LIFECYCLE.map((step, index) => {
          const done = index < current
          const active = index === current
          return (
            <li key={step.status} className="flex min-w-0 flex-1 items-center last:flex-none">
              <span
                className={`flex items-center gap-2.5 text-body-sm whitespace-nowrap ${
                  active ? 'font-semibold text-ink' : done ? 'text-ink-secondary' : 'text-ink-faint'
                }`}
                aria-current={active ? 'step' : undefined}
              >
                <span
                  className={`grid size-8 shrink-0 place-items-center rounded-full text-caption font-semibold ${
                    done
                      ? 'bg-accent-green text-on-primary'
                      : active
                        ? 'bg-primary text-on-primary ring-4 ring-primary/15'
                        : 'border-2 border-input-border'
                  }`}
                >
                  {done ? <Check className="size-4" strokeWidth={3} aria-hidden="true" /> : index + 1}
                </span>
                {step.label}
              </span>
              {index < EVENT_LIFECYCLE.length - 1 && (
                <span
                  className={`mx-3 h-1 min-w-3 flex-1 rounded-full ${done ? 'bg-accent-green' : 'bg-hairline'}`}
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
