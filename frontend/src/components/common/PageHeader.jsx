/** Tiêu đề trang dùng chung cho các màn hình trong app. */
export default function PageHeader({ title, description, action, className = '' }) {
  return (
    <header className={`mb-6 flex flex-wrap items-center justify-between gap-x-4 gap-y-3 ${className}`}>
      <div className="min-w-0">
        <h1 className="text-page-title text-balance text-ink">{title}</h1>
        {description && <p className="mt-1 text-body-sm text-ink-muted">{description}</p>}
      </div>
      {action}
    </header>
  )
}
