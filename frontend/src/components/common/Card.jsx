export default function Card({ title, description, action, children, className = '', bodyClassName = '' }) {
  return (
    <section className={`rounded-xl border border-slate-200 bg-white shadow-xs ${className}`}>
      {(title || action) && (
        <header className="flex items-center justify-between gap-3 border-b border-slate-100 px-4 py-2.5">
          <div className="min-w-0">
            {title && <h2 className="truncate text-sm font-semibold text-slate-900">{title}</h2>}
            {description && <p className="mt-0.5 truncate text-xs text-slate-500">{description}</p>}
          </div>
          {action}
        </header>
      )}
      <div className={`px-4 py-3.5 ${bodyClassName}`}>{children}</div>
    </section>
  )
}
