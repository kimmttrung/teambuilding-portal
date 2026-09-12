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
          <p className="text-sm font-semibold text-slate-900">{steps[currentIndex]?.label}</p>
          <p className="text-xs text-slate-500 tabular-nums">
            Bước {currentIndex + 1}/{steps.length}
          </p>
        </div>
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-200">
          <div
            className="h-full rounded-full bg-brand-600 transition-all"
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
                className={`flex min-w-0 flex-1 items-center gap-2 rounded-lg px-2 py-1.5 text-left transition
                  ${reachable ? 'hover:bg-slate-100' : 'cursor-default'}`}
              >
                <span
                  className={`grid size-6 shrink-0 place-items-center rounded-full text-xs font-semibold
                    ${
                      skipped
                        ? 'bg-slate-100 text-slate-400'
                        : done
                          ? 'bg-emerald-500 text-white'
                          : active
                            ? 'bg-brand-600 text-white'
                            : 'bg-slate-200 text-slate-500'
                    }`}
                >
                  {done && !skipped ? <Check className="size-3.5" strokeWidth={3} aria-hidden="true" /> : index + 1}
                </span>
                <span
                  className={`truncate text-xs font-medium ${
                    active ? 'text-brand-700' : done ? 'text-slate-700' : 'text-slate-400'
                  } ${skipped ? 'line-through' : ''}`}
                >
                  {step.label}
                </span>
              </button>
              {index < steps.length - 1 && (
                <span className={`h-px w-4 shrink-0 ${done ? 'bg-emerald-300' : 'bg-slate-200'}`} />
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
