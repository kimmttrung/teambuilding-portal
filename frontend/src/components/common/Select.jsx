import { forwardRef, useId } from 'react'
import { ChevronDown } from 'lucide-react'

/**
 * Dropdown có nhãn và thông báo lỗi, dùng chung như Input.
 *
 * `options` là mảng { value, label }. Mọi dropdown trong hệ thống lấy dữ liệu từ
 * master data (docs/03-data-model.md) nên không nhận danh sách cứng trong component.
 */
const Select = forwardRef(function Select(
  { label, error, hint, required, options = [], placeholder, className = '', children, ...props },
  ref,
) {
  const generatedId = useId()
  const id = props.id || generatedId

  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label htmlFor={id} className="text-sm font-medium text-slate-700">
          {label}
          {required && <span className="ml-0.5 text-rose-600" aria-hidden="true">*</span>}
        </label>
      )}
      <div className="relative">
        <select
          {...props}
          id={id}
          ref={ref}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined}
          className={`w-full appearance-none rounded-lg border py-2.5 pr-9 pl-3 text-sm text-slate-900
            transition disabled:bg-slate-100 disabled:text-slate-500
            ${error ? 'border-rose-400 bg-rose-50' : 'border-slate-300 bg-white'} ${className}`}
        >
          {placeholder !== undefined && <option value="">{placeholder}</option>}
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
          {children}
        </select>
        <ChevronDown
          className="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-slate-400"
          aria-hidden="true"
        />
      </div>
      {error ? (
        <p id={`${id}-error`} className="text-sm text-rose-600">{error}</p>
      ) : (
        hint && <p id={`${id}-hint`} className="text-xs text-slate-500">{hint}</p>
      )}
    </div>
  )
})

export default Select
