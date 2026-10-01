import { formatDate } from '../../../utils/format'
import { DIRECTION_TABS } from './boardData'

export default function DirectionTabs({ value, onChange, event, disabled = false }) {
  return (
    <div className="inline-flex flex-wrap gap-1 rounded-md bg-black/5 p-1" aria-label="Chiều bay">
      {Object.entries(DIRECTION_TABS).map(([direction, label]) => (
        <button
          key={direction}
          type="button"
          aria-pressed={direction === value}
          disabled={disabled}
          onClick={() => onChange(direction)}
          className={`min-h-11 rounded-sm px-3 text-caption font-medium transition disabled:opacity-50 sm:min-h-8 ${direction === value ? 'bg-surface text-ink shadow-soft' : 'text-ink-muted hover:text-ink'}`}
        >
          {label}
          {event &&
            ` · ${formatDate(direction === 'outbound' ? event.start_date : event.end_date).slice(0, 5)}`}
        </button>
      ))}
    </div>
  )
}
