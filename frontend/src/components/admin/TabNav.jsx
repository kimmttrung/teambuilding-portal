/**
 * Thanh tab cho màn hình nhiều mục (Cấu hình kỳ, Master data).
 *
 * Tab đang mở nằm trong URL (`?tab=`) chứ không phải state: BTC gửi link cho nhau, bấm Back phải quay
 * lại đúng tab trước đó, và F5 không được nhảy về tab đầu. Cùng cách `/admin/rooms` đang làm.
 */
export default function TabNav({ tabs, current, onChange }) {
  return (
    <div className="-mx-1 overflow-x-auto">
      <div className="flex gap-1 border-b border-slate-200 px-1" role="tablist">
        {tabs.map(({ id, label, icon: Icon }) => {
          const active = id === current
          return (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => onChange(id)}
              className={`flex shrink-0 items-center gap-1.5 border-b-2 px-3 py-2 text-sm whitespace-nowrap transition ${
                active
                  ? 'border-brand-600 font-medium text-brand-700'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              {Icon && <Icon className="size-4 shrink-0" aria-hidden="true" />}
              {label}
            </button>
          )
        })}
      </div>
    </div>
  )
}
