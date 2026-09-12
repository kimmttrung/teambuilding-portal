/**
 * Ô chọn dạng thẻ (radio). Vùng bấm rộng — CBNV điền form này trên điện thoại,
 * radio tròn mặc định quá nhỏ để bấm chính xác.
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
      className={`flex items-start gap-3 rounded-xl border-2 p-3.5 transition
        ${checked ? 'border-brand-600 bg-brand-50' : 'border-slate-200 bg-white hover:border-slate-300'}
        ${disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'}`}
    >
      <input
        type="radio"
        name={name}
        value={value}
        checked={checked}
        disabled={disabled}
        onChange={() => onChange?.(value)}
        className="mt-0.5 size-4 shrink-0 accent-brand-600"
      />
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-2">
          {Icon && <Icon className="size-4 shrink-0 text-slate-400" aria-hidden="true" />}
          <span className="text-sm font-semibold text-slate-900">{title}</span>
        </span>
        {description && (
          <span className="mt-1 block text-xs leading-relaxed text-slate-500">{description}</span>
        )}
        {meta && <span className="mt-1.5 block text-xs font-medium text-brand-700">{meta}</span>}
      </span>
    </label>
  )
}
