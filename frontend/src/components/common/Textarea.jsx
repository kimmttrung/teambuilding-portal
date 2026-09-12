import { forwardRef, useId } from 'react'

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
        <label htmlFor={id} className="text-sm font-medium text-slate-700">
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
        className={`resize-y rounded-lg border px-3 py-2.5 text-sm text-slate-900 transition
          placeholder:text-slate-400 disabled:bg-slate-100 disabled:text-slate-500
          ${error ? 'border-rose-400 bg-rose-50' : 'border-slate-300 bg-white'} ${className}`}
      />
      <div className="flex items-start justify-between gap-3">
        {error ? (
          <p id={`${id}-error`} className="text-sm text-rose-600">{error}</p>
        ) : (
          hint && <p id={`${id}-hint`} className="text-xs text-slate-500">{hint}</p>
        )}
        {showCounter && (
          <p className="ml-auto shrink-0 text-xs text-slate-400 tabular-nums">
            {counterValue.length}/{props.maxLength}
          </p>
        )}
      </div>
    </div>
  )
})

export default Textarea
