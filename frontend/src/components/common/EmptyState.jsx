/** design-notion › ex-empty-state-card: nền canvas-soft, bo rounded-xl, padding xxl, chữ body-md. */
export default function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl bg-canvas-soft px-4 py-8 text-center sm:px-8">
      {Icon && (
        <span className="grid size-12 place-items-center rounded-full bg-surface text-ink-faint ring-1 ring-hairline">
          <Icon className="size-6" aria-hidden="true" />
        </span>
      )}
      <div>
        <h3 className="text-body-md font-semibold text-ink">{title}</h3>
        {description && <p className="mt-1 max-w-sm text-body-md text-ink-muted">{description}</p>}
      </div>
      {action}
    </div>
  )
}
