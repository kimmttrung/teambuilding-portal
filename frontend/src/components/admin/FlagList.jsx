import { useState } from 'react'
import { AlertTriangle, ChevronDown, ChevronRight, Info, XCircle } from 'lucide-react'
import { ALLOCATION_FLAG_META, SEVERITY_TONES } from '../../utils/constants'
import Badge from '../common/Badge'

const SEVERITY_ICON = { error: XCircle, warning: AlertTriangle, info: Info }

/**
 * Danh sách cảnh báo của thuật toán, gom theo loại.
 *
 * Một lần chạy có thể sinh 40-50 flag `SHIFT_NOT_SATISFIED` (mỗi người một dòng). Đổ hết ra
 * phẳng thì BTC không thấy được 2 dòng `UNASSIGNED` quan trọng nằm lẫn đâu đó — nên gom theo
 * loại, lỗi lên trước, và mặc định chỉ mở nhóm lỗi.
 */
export default function FlagList({ flags = [], limit = 8, onSelect }) {
  const groups = groupByType(flags)

  if (!flags.length) {
    return (
      <p className="text-sm text-emerald-700">
        Không có cảnh báo nào — kết quả này có thể công bố.
      </p>
    )
  }

  return (
    <ul className="flex flex-col gap-2">
      {groups.map((group) => (
        <FlagGroup key={group.type} group={group} limit={limit} onSelect={onSelect} />
      ))}
    </ul>
  )
}

function FlagGroup({ group, limit, onSelect }) {
  const meta = ALLOCATION_FLAG_META[group.type] ?? { label: group.type, tone: 'slate' }
  const [open, setOpen] = useState(meta.blocking === true)
  const Icon = SEVERITY_ICON[group.severity] ?? Info
  const Chevron = open ? ChevronDown : ChevronRight
  const visible = open ? group.items.slice(0, limit) : []

  return (
    <li className="rounded-lg border border-slate-200">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center gap-2.5 px-3 py-2 text-left transition hover:bg-slate-50"
        aria-expanded={open}
      >
        <Chevron className="size-4 shrink-0 text-slate-400" aria-hidden="true" />
        <Icon
          className={`size-4 shrink-0 ${
            group.severity === 'error'
              ? 'text-rose-600'
              : group.severity === 'warning'
                ? 'text-amber-600'
                : 'text-slate-400'
          }`}
          aria-hidden="true"
        />
        <span className="min-w-0 flex-1 text-sm font-medium text-slate-900">{meta.label}</span>
        <Badge tone={SEVERITY_TONES[group.severity] ?? meta.tone}>{group.items.length}</Badge>
      </button>

      {open && (
        <ul className="divide-y divide-slate-100 border-t border-slate-100">
          {visible.map((flag, index) => (
            <li key={`${flag.type}-${flag.registration_id ?? flag.team_id ?? index}`}>
              {onSelect ? (
                <button
                  type="button"
                  onClick={() => onSelect(flag)}
                  className="w-full px-3 py-2 text-left text-xs leading-relaxed text-slate-600 transition hover:bg-slate-50 hover:text-slate-900"
                >
                  {flag.message}
                </button>
              ) : (
                <p className="px-3 py-2 text-xs leading-relaxed text-slate-600">{flag.message}</p>
              )}
            </li>
          ))}
          {group.items.length > limit && (
            <li className="px-3 py-2 text-xs text-slate-400">
              … và {group.items.length - limit} trường hợp nữa cùng loại
            </li>
          )}
        </ul>
      )}
    </li>
  )
}

const SEVERITY_ORDER = { error: 0, warning: 1, info: 2 }

function groupByType(flags) {
  const byType = new Map()
  for (const flag of flags) {
    const group = byType.get(flag.type)
    if (group) group.items.push(flag)
    else byType.set(flag.type, { type: flag.type, severity: flag.severity, items: [flag] })
  }
  return [...byType.values()].sort(
    (left, right) =>
      (SEVERITY_ORDER[left.severity] ?? 9) - (SEVERITY_ORDER[right.severity] ?? 9) ||
      right.items.length - left.items.length,
  )
}
