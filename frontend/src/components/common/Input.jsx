import { forwardRef, useId } from 'react'

/** Ô nhập có nhãn, gợi ý và thông báo lỗi. Dùng chung cho mọi form. */
const Input = forwardRef(function Input(
  { label, error, hint, required, className = '', ...props },
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
      <input
        {...props}
        id={id}
        ref={ref}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined}
        className={`rounded-lg border px-3 py-2.5 text-sm text-slate-900 transition
          placeholder:text-slate-400 disabled:bg-slate-100 disabled:text-slate-500
          ${error ? 'border-rose-400 bg-rose-50' : 'border-slate-300 bg-white'} ${className}`}
      />
      {error ? (
        <p id={`${id}-error`} className="text-sm text-rose-600">{error}</p>
      ) : (
        hint && <p id={`${id}-hint`} className="text-xs text-slate-500">{hint}</p>
      )}
    </div>
  )
})

export default Input
