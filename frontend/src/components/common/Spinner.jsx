import { Loader2 } from 'lucide-react'

export default function Spinner({ label = 'Đang tải…', className = '' }) {
  return (
    <div className={`flex flex-col items-center justify-center gap-2 py-10 text-slate-500 ${className}`}>
      <Loader2 className="size-6 animate-spin" aria-hidden="true" />
      <p className="text-sm">{label}</p>
    </div>
  )
}
