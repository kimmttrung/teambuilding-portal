import { AlertTriangle, CheckCircle2, Info, XCircle } from 'lucide-react'

const TONES = {
  info: { cls: 'border-blue-200 bg-blue-50 text-blue-900', Icon: Info },
  success: { cls: 'border-emerald-200 bg-emerald-50 text-emerald-900', Icon: CheckCircle2 },
  warning: { cls: 'border-amber-200 bg-amber-50 text-amber-900', Icon: AlertTriangle },
  error: { cls: 'border-rose-200 bg-rose-50 text-rose-900', Icon: XCircle },
}

export default function Alert({ tone = 'info', title, children, className = '' }) {
  const { cls, Icon } = TONES[tone] ?? TONES.info
  return (
    <div className={`flex items-start gap-3 rounded-lg border p-3 ${cls} ${className}`}>
      <Icon className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
      <div className="flex-1 text-sm leading-relaxed">
        {title && <p className="font-semibold">{title}</p>}
        {children}
      </div>
    </div>
  )
}
