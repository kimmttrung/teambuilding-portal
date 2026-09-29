import { AlertTriangle, CheckCircle2, Info, XCircle } from 'lucide-react'

/*
 * Thông báo trong trang — dáng ex-toast của design-notion (nền surface, bo rounded-xl, padding sm/md,
 * chữ body-sm). Loại thông báo chỉ thể hiện ở vạch trái + icon, không tô cả khối.
 */
const TONES = {
  info: { bar: 'border-l-primary', icon: 'text-primary', Icon: Info },
  success: { bar: 'border-l-emerald-600', icon: 'text-emerald-600', Icon: CheckCircle2 },
  warning: { bar: 'border-l-amber-500', icon: 'text-amber-600', Icon: AlertTriangle },
  error: { bar: 'border-l-rose-600', icon: 'text-rose-600', Icon: XCircle },
}

export default function Alert({ tone = 'info', title, children, className = '' }) {
  const { bar, icon, Icon } = TONES[tone] ?? TONES.info
  return (
    <div
      className={`flex items-start gap-3 rounded-xl border border-l-4 border-hairline bg-surface px-4 py-3
        text-ink-secondary ${bar} ${className}`}
    >
      <Icon className={`mt-0.5 size-5 shrink-0 ${icon}`} aria-hidden="true" />
      <div className="flex-1 text-body-sm leading-relaxed">
        {title && <p className="font-semibold text-ink">{title}</p>}
        {children}
      </div>
    </div>
  )
}
