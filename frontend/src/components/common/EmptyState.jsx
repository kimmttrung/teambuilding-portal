export default function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <div className="flex flex-col items-center gap-3 px-4 py-10 text-center">
      {Icon && (
        <span className="grid size-12 place-items-center rounded-full bg-slate-100 text-slate-400">
          <Icon className="size-6" aria-hidden="true" />
        </span>
      )}
      <div>
        <h3 className="font-semibold text-slate-900">{title}</h3>
        {description && <p className="mt-1 max-w-sm text-sm text-slate-500">{description}</p>}
      </div>
      {action}
    </div>
  )
}
