/*
 * design-notion › badge-pill: bo rounded-full, chữ eyebrow (12px/600), padding 4px 8px.
 * `brand` là đúng badge-pill của skill (nền surface, chữ primary). Các tone còn lại là màu trạng thái
 * của ứng dụng (skill không có bảng màu lỗi/thành công), nên chỉ tô nền nhạt, không tô đậm.
 */
const TONES = {
  slate: 'bg-canvas-soft text-ink-muted ring-hairline',
  emerald: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  amber: 'bg-amber-50 text-amber-800 ring-amber-200',
  rose: 'bg-rose-50 text-rose-700 ring-rose-200',
  blue: 'bg-brand-50 text-primary ring-brand-200',
  brand: 'bg-surface text-primary ring-hairline',
}

export default function Badge({ tone = 'slate', children, className = '' }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-1 text-eyebrow whitespace-nowrap
        ring-1 ring-inset ${TONES[tone] ?? TONES.slate} ${className}`}
    >
      {children}
    </span>
  )
}
