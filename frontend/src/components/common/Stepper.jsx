import { BusFront, Check, Heart, Plane, ShieldCheck, UserRound } from 'lucide-react'

const STEP_ICONS = [UserRound, ShieldCheck, Plane, BusFront, Heart]
const STEP_COLORS = [
  ['bg-primary', 'text-primary'],
  ['bg-accent-teal', 'text-accent-teal'],
  ['bg-amber-400', 'text-amber-600'],
  ['bg-accent-orange', 'text-accent-orange'],
  ['bg-accent-purple', 'text-accent-purple-deep'],
]

export default function Stepper({ steps, currentIndex, visitedCount, completedIndexes = [], skipIndexes = [], onStepClick }) {
  return (
    <nav aria-label="Các bước đăng ký">
      <div className="sm:hidden">
        <div className="flex items-baseline justify-between gap-3">
          <p className="text-eyebrow font-semibold text-primary uppercase">Bước {currentIndex + 1}</p>
          <p className="text-caption text-ink-muted tabular-nums">{steps[currentIndex]?.label}</p>
        </div>
        <div className="mt-2 flex gap-1" aria-hidden="true">
          {steps.map((step, index) => <span key={step.id} className={`h-1 flex-1 rounded-full ${index <= currentIndex ? 'bg-primary' : 'bg-hairline'}`} />)}
        </div>
      </div>

      <ol className="hidden items-start sm:flex">
        {steps.map((step, index) => {
          const done = completedIndexes.includes(index) && index !== currentIndex
          const active = index === currentIndex
          const skipped = skipIndexes.includes(index)
          const reachable = index <= visitedCount && !skipped
          const Icon = STEP_ICONS[index] ?? UserRound
          const [circle, color] = STEP_COLORS[index] ?? STEP_COLORS[0]
          const status = skipped ? 'Bỏ qua' : done ? 'Xong' : active ? 'Đang làm' : ''

          return (
            <li key={step.id} className="flex min-w-0 flex-1 items-start">
              <button
                type="button"
                onClick={() => reachable && onStepClick?.(index)}
                disabled={!reachable}
                aria-current={active ? 'step' : undefined}
                className={`flex min-w-0 flex-1 flex-col items-center text-center ${reachable ? 'cursor-pointer' : 'cursor-default'}`}
              >
                <span className={`grid size-10 place-items-center rounded-full text-white shadow-soft transition ${skipped ? 'bg-hairline text-ink-faint' : active ? `${circle} ring-3 ring-primary/15` : done ? circle : 'bg-accent-purple/35 text-accent-purple-deep'}`}>
                  {done && !skipped ? <Check className="size-4" strokeWidth={3} aria-hidden="true" /> : <Icon className="size-4" aria-hidden="true" />}
                </span>
                <span className={`mt-1.5 whitespace-nowrap text-[10px] leading-tight font-semibold ${skipped ? 'text-ink-faint' : active || done ? color : 'text-ink-faint'}`}>
                  Bước {index + 1}{status && ` · ${status}`}
                </span>
                <span className={`mt-0.5 max-w-[120px] text-[11px] leading-tight font-medium ${active ? 'text-ink' : done ? 'text-ink-secondary' : 'text-ink-muted'}`}>
                  {step.label}
                </span>
              </button>
              {index < steps.length - 1 && (
                <span className={`mt-5 h-0.5 min-w-4 flex-1 ${done ? 'bg-accent-teal' : 'bg-hairline'}`} aria-hidden="true" />
              )}
            </li>
          )
        })}
      </ol>
      <div className="mt-3 hidden items-center justify-center gap-1.5 border-t border-hairline pt-2 text-[11px] text-ink-faint sm:flex">
        <Check className="size-3 text-accent-green" aria-hidden="true" />
        Tự lưu nháp · nội dung được lưu tự động
      </div>
    </nav>
  )
}
