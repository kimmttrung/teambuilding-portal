export default function PageHeader({ title, description, action, className = '' }) {
  return (
    <header className={`mb-4 flex flex-wrap items-center justify-between gap-x-4 gap-y-2 ${className}`}>
      <div className="min-w-0">
        <h1 className="text-lg font-bold text-balance text-slate-900 sm:text-xl">{title}</h1>
        {description && <p className="mt-0.5 text-sm text-slate-500">{description}</p>}
      </div>
      {action}
    </header>
  )
}
