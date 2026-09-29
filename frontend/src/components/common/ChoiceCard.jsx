/**
 * Ô chọn dạng thẻ (radio). Vùng bấm rộng — CBNV điền form này trên điện thoại,
 * radio tròn mặc định quá nhỏ để bấm chính xác.
 *
 * design-notion: thẻ surface viền hairline bo rounded-lg; đang chọn thì viền primary
 * (primary là tín hiệu "đang chọn" duy nhất), không đổi màu nền.
 */
export default function ChoiceCard({
  name,
  value,
  checked,
  onChange,
  title,
  description,
  meta,
  icon: Icon,
  disabled = false,
}) {
  return (
    <label
      className={`flex items-start gap-3 rounded-lg border bg-surface p-4 transition
        ${checked ? 'border-primary ring-1 ring-primary' : 'border-hairline hover:border-input-border'}
        ${disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'}`}
    >
      <input
        type="radio"
        name={name}
        value={value}
        checked={checked}
        disabled={disabled}
        onChange={() => onChange?.(value)}
        className="mt-0.5 size-4 shrink-0 accent-primary"
      />
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-2">
          {Icon && <Icon className="size-4 shrink-0 text-ink-faint" aria-hidden="true" />}
          <span className="text-body-sm font-semibold text-ink">{title}</span>
        </span>
        {description && (
          <span className="mt-1 block text-caption leading-relaxed text-ink-muted">{description}</span>
        )}
        {meta && <span className="mt-1.5 block text-caption font-medium text-primary">{meta}</span>}
      </span>
    </label>
  )
}
