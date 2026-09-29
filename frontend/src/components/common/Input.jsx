import { forwardRef, useId } from 'react'
import { ERROR_CLASS, FIELD_BASE, FIELD_BORDER, HINT_CLASS, LABEL_CLASS } from './fieldStyles'

/** Ô nhập có nhãn, gợi ý và thông báo lỗi. Dùng chung cho mọi form (design-notion › text-input). */
const Input = forwardRef(function Input(
  { label, error, hint, required, className = '', ...props },
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
      <input
        {...props}
        id={id}
        ref={ref}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined}
        className={`${FIELD_BASE} ${error ? FIELD_BORDER.error : FIELD_BORDER.normal} ${className}`}
      />
      {error ? (
        <p id={`${id}-error`} className={ERROR_CLASS}>{error}</p>
      ) : (
        hint && <p id={`${id}-hint`} className={HINT_CLASS}>{hint}</p>
      )}
    </div>
  )
})

export default Input
