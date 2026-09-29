/** Tiêu đề trang: heading-2 (26px/700) trên màn rộng, hạ về heading-3 trên điện thoại. */
export default function PageHeader({ title, description, action, className = '' }) {
  return (
    <header className={`mb-6 flex flex-wrap items-center justify-between gap-x-4 gap-y-3 ${className}`}>
      <div className="min-w-0">
        <h1 className="text-heading-3 text-balance text-ink sm:text-heading-2">{title}</h1>
        {description && <p className="mt-1 text-body-sm text-ink-muted">{description}</p>}
      </div>
      {action}
    </header>
  )
}
