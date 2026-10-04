import { forwardRef, useId } from 'react'
import { ERROR_CLASS, FIELD_BASE, FIELD_BORDER, HINT_CLASS, LABEL_CLASS } from './fieldStyles'

/** Ô nhập nhiều dòng. Có bộ đếm ký tự khi truyền `maxLength` và `value`. */
const Textarea = forwardRef(function Textarea(
  { label, error, hint, required, rows = 3, counterValue, className = '', ...props },
  ref,
) {
  const generatedId = useId()
  const id = props.id || generatedId
  const showCounter = props.maxLength && typeof counterValue === 'string'

  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label htmlFor={id} className={LABEL_CLASS}>
          {label}
          {required && <span className="ml-0.5 text-rose-600" aria-hidden="true">*</span>}
        </label>
      )}
      <textarea
        {...props}
        id={id}
        ref={ref}
        rows={rows}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined}
        className={`${FIELD_BASE} resize-y leading-relaxed ${error ? FIELD_BORDER.error : FIELD_BORDER.normal} ${className}`}
      />
      <div className="flex items-start justify-between gap-3">
        {error ? (
          <p id={`${id}-error`} className={ERROR_CLASS}>{error}</p>
        ) : (
          hint && <p id={`${id}-hint`} className={HINT_CLASS}>{hint}</p>
        )}
        {showCounter && (
          <p className="ml-auto shrink-0 text-caption text-ink-faint tabular-nums">
            {counterValue.length}/{props.maxLength}
          </p>
        )}
      </div>
    </div>
  )
})

export default Textarea
