const META = {
  live: { label: 'Cập nhật trực tiếp', dot: 'bg-emerald-500 animate-pulse', text: 'text-emerald-700' },
  connecting: { label: 'Đang kết nối…', dot: 'bg-slate-400', text: 'text-slate-500' },
  offline: { label: 'Mất kết nối — đang thử lại', dot: 'bg-amber-500', text: 'text-amber-700' },
}

/** Chỉ báo luồng cập nhật sơ đồ đang sống hay không. */
export default function LiveBadge({ status }) {
  const meta = META[status] ?? META.connecting
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${meta.text}`} role="status">
      <span className={`size-2 rounded-full ${meta.dot}`} aria-hidden="true" />
      {meta.label}
    </span>
  )
}
