import { useEffect, useRef } from 'react'
import { X } from 'lucide-react'

const SIZES = {
  sm: 'max-w-md',
  md: 'max-w-lg',
  lg: 'max-w-2xl',
}

/**
 * Hộp thoại. Khoá scroll trang, đóng bằng Esc hoặc click nền.
 *
 * `bodyRef` + `onBodyScroll` để nơi gọi theo dõi việc cuộn hết nội dung —
 * modal quy định chương trình chỉ bật checkbox khi người dùng đã cuộn tới cuối.
 */
export default function Modal({
  open,
  onClose,
  title,
  description,
  size = 'md',
  footer,
  bodyRef,
  onBodyScroll,
  children,
}) {
  const closeButtonRef = useRef(null)

  useEffect(() => {
    if (!open) return undefined

    function handleKeyDown(keyEvent) {
      if (keyEvent.key === 'Escape') onClose?.()
    }

    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    document.addEventListener('keydown', handleKeyDown)
    closeButtonRef.current?.focus()

    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/50 p-0 sm:items-center sm:p-4"
      onClick={(clickEvent) => {
        if (clickEvent.target === clickEvent.currentTarget) onClose?.()
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`flex max-h-[92vh] w-full flex-col overflow-hidden rounded-t-2xl bg-white
          shadow-xl sm:rounded-xl ${SIZES[size] ?? SIZES.md}`}
      >
        <header className="flex items-start justify-between gap-3 border-b border-slate-100 px-4 py-3">
          <div className="min-w-0">
            <h2 className="font-semibold text-slate-900">{title}</h2>
            {description && <p className="mt-0.5 text-xs text-slate-500">{description}</p>}
          </div>
          <button
            type="button"
            ref={closeButtonRef}
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
            aria-label="Đóng"
          >
            <X className="size-4.5" />
          </button>
        </header>

        <div
          ref={bodyRef}
          onScroll={onBodyScroll}
          className="flex-1 overflow-y-auto overscroll-contain px-4 py-3.5"
        >
          {children}
        </div>

        {footer && (
          <footer className="border-t border-slate-100 bg-slate-50 px-4 py-3">{footer}</footer>
        )}
      </div>
    </div>
  )
}
