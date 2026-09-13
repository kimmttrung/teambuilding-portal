import { LOAD_WARNING_RATIO } from '../../utils/constants'

/**
 * Thanh lấp chỗ của một chuyến bay.
 *
 * Màu KHÔNG phải thứ duy nhất phân biệt trạng thái (docs/07-frontend.md §6): luôn kèm
 * số "đã xếp / ghế dùng được" để người không phân biệt được màu vẫn đọc được.
 */
export default function SlotBar({ assigned, usable, className = '', showNumbers = true }) {
  const ratio = usable > 0 ? assigned / usable : 0
  const full = usable > 0 && assigned >= usable
  const nearlyFull = !full && ratio >= LOAD_WARNING_RATIO

  const barColor = full ? 'bg-rose-500' : nearlyFull ? 'bg-amber-500' : 'bg-brand-600'
  const textColor = full ? 'text-rose-700' : nearlyFull ? 'text-amber-700' : 'text-slate-600'

  return (
    <div className={className}>
      {showNumbers && (
        <div className="mb-1 flex items-baseline justify-between gap-2 text-xs">
          <span className={`font-semibold tabular-nums ${textColor}`}>
            {assigned}/{usable}
          </span>
          <span className="text-slate-400">
            {full ? 'hết chỗ' : `còn ${usable - assigned}`}
          </span>
        </div>
      )}
      <div
        className="h-1.5 overflow-hidden rounded-full bg-slate-200"
        role="meter"
        aria-valuenow={assigned}
        aria-valuemin={0}
        aria-valuemax={usable}
        aria-label={`Đã xếp ${assigned} trên ${usable} ghế dùng được`}
      >
        <div
          className={`h-full rounded-full transition-all ${barColor}`}
          style={{ width: `${Math.min(ratio, 1) * 100}%` }}
        />
      </div>
    </div>
  )
}
