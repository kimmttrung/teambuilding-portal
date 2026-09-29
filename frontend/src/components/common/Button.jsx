import { Loader2 } from 'lucide-react'

/*
 * design-notion › Buttons.
 * - primary: button-primary (nền primary, nhấn → primary-active). Mỗi vùng màn hình chỉ MỘT nút primary.
 * - secondary: button-utility (nền surface, viền hairline 1px).
 * - ghost: hành động phụ trong bảng/toolbar, không nền.
 * - danger: skill không có màu lỗi; chỉ dùng để xác nhận xoá/huỷ.
 * Trong ứng dụng bo `rounded-md` (8px, button-utility). `shape="pill"` = rounded-full cho CTA kiểu
 * marketing (trang Landing), đúng "pill CTA đối lập với nút utility 8px".
 */
const VARIANTS = {
  primary: 'bg-primary text-on-primary hover:bg-primary-active active:bg-primary-active disabled:opacity-50',
  secondary:
    'border border-hairline bg-surface text-ink hover:bg-canvas-soft disabled:text-ink-faint',
  danger: 'bg-rose-600 text-on-primary hover:bg-rose-700 disabled:opacity-50',
  ghost: 'text-ink-secondary hover:bg-black/5 disabled:text-ink-faint',
}

const SIZES = {
  sm: 'min-h-8 px-3.5 py-1 text-caption gap-1.5',
  md: 'min-h-10 px-4 py-1.5 text-button gap-2 max-sm:min-h-11',
  lg: 'min-h-12 px-5 py-2.5 text-button gap-2',
}

const SHAPES = {
  default: 'rounded-md',
  pill: 'rounded-full',
}

export default function Button({
  variant = 'primary',
  size = 'md',
  shape = 'default',
  loading = false,
  icon: Icon,
  fullWidth = false,
  className = '',
  children,
  disabled,
  ...props
}) {
  return (
    <button
      {...props}
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center font-medium transition active:scale-[0.97]
        disabled:cursor-not-allowed disabled:active:scale-100 ${VARIANTS[variant] ?? VARIANTS.primary}
        ${SIZES[size] ?? SIZES.md} ${SHAPES[shape] ?? SHAPES.default} ${fullWidth ? 'w-full' : ''} ${className}`}
    >
      {loading ? (
        <Loader2 className="size-4 animate-spin" aria-hidden="true" />
      ) : (
        Icon && <Icon className="size-4" aria-hidden="true" />
      )}
      {children}
    </button>
  )
}
