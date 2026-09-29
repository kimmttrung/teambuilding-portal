import { Loader2 } from 'lucide-react'

export default function Spinner({ label = 'Đang tải…', className = '' }) {
  return (
    <div className={`flex flex-col items-center justify-center gap-2 py-10 text-ink-muted ${className}`}>
      <Loader2 className="size-6 animate-spin text-primary" aria-hidden="true" />
      <p className="text-caption">{label}</p>
    </div>
  )
}
