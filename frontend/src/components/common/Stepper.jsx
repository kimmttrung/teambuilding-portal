import { Check } from 'lucide-react'

/**
 * Thanh tiến trình của form nhiều bước.
 *
 * Chỉ cho bấm quay lại bước đã đi qua: nhảy tới bước chưa đi qua sẽ bỏ qua
 * validate của các bước giữa, mà bước sau phụ thuộc dữ liệu bước trước.
 */
export default function Stepper({ steps, currentIndex, visitedCount, skipIndexes = [], onStepClick }) {
  return (
    <nav aria-label="Các bước đăng ký">
      {/* Mobile: chỉ cần biết đang ở bước mấy và tên bước */}
      <div className="sm:hidden">
        <div className="flex items-baseline justify-between">
          <p className="text-body-sm font-semibold text-ink">{steps[currentIndex]?.label}</p>
          <p className="text-caption text-ink-muted tabular-nums">
            Bước {currentIndex + 1}/{steps.length}
          </p>
        </div>
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-hairline">
          <div
            className="h-full rounded-full bg-primary transition-all"
            style={{ width: `${((currentIndex + 1) / steps.length) * 100}%` }}
          />
        </div>
      </div>

      {/* Desktop: thấy hết các bước để biết còn bao nhiêu việc */}
      <ol className="hidden items-center gap-1.5 sm:flex">
        {steps.map((step, index) => {
          const done = index < currentIndex
          const active = index === currentIndex
          // Bước bị bỏ qua (ví dụ: không tham gia thì không chọn ca) không cho bấm vào.
          const skipped = skipIndexes.includes(index)
          const reachable = index <= visitedCount && !skipped

          return (
            <li key={step.id} className="flex min-w-0 flex-1 items-center gap-1.5">
              <button
                type="button"
                onClick={() => reachable && onStepClick?.(index)}
                disabled={!reachable}
                aria-current={active ? 'step' : undefined}
                className={`flex min-w-0 flex-1 items-center gap-2 rounded-sm px-2 py-1.5 text-left transition
                  ${reachable ? 'hover:bg-black/5' : 'cursor-default'}`}
              >
                <span
                  className={`grid size-6 shrink-0 place-items-center rounded-full text-xs font-semibold
                    ${
                      skipped
                        ? 'bg-canvas-soft text-ink-faint'
                        : done
                          ? 'bg-accent-green text-on-primary'
                          : active
                            ? 'bg-primary text-on-primary'
                            : 'bg-hairline text-ink-muted'
                    }`}
                >
                  {done && !skipped ? <Check className="size-3.5" strokeWidth={3} aria-hidden="true" /> : index + 1}
                </span>
                <span
                  className={`truncate text-caption font-medium ${
                    active ? 'text-primary' : done ? 'text-ink-secondary' : 'text-ink-faint'
                  } ${skipped ? 'line-through' : ''}`}
                >
                  {step.label}
                </span>
              </button>
              {index < steps.length - 1 && (
                <span className={`h-px w-4 shrink-0 ${done ? 'bg-accent-green' : 'bg-hairline'}`} />
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
