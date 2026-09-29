import { forwardRef, useId } from 'react'
import { ChevronDown } from 'lucide-react'
import { ERROR_CLASS, FIELD_BASE, FIELD_BORDER, HINT_CLASS, LABEL_CLASS } from './fieldStyles'

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
        <label htmlFor={id} className={LABEL_CLASS}>
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
          className={`${FIELD_BASE} appearance-none pr-9 ${error ? FIELD_BORDER.error : FIELD_BORDER.normal} ${className}`}
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
          className="pointer-events-none absolute top-1/2 right-2.5 size-4 -translate-y-1/2 text-ink-faint"
          aria-hidden="true"
        />
      </div>
      {error ? (
        <p id={`${id}-error`} className={ERROR_CLASS}>{error}</p>
      ) : (
        hint && <p id={`${id}-hint`} className={HINT_CLASS}>{hint}</p>
      )}
    </div>
  )
})

export default Select
