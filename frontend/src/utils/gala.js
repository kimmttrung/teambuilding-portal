/** Tiện ích dùng chung cho màn hình Gala. */

/**
 * Kiểu hiển thị của một ghế. Mỗi trạng thái khác nhau cả hình dạng (viền đứt, tô kín, sọc),
 * không chỉ màu — người mù màu vẫn phân biệt được (docs/07 §6).
 */
export function seatVisual(state, { selected = false, teamColor } = {}) {
  if (selected && state === 'available') {
    return { className: 'bg-brand-600 text-white ring-2 ring-brand-300', style: {} }
  }
  switch (state) {
    case 'held_by_me':
      return { className: 'border-2 border-dashed border-blue-500 bg-blue-50 text-blue-800', style: {} }
    case 'held_by_other':
      return { className: 'border-2 border-dashed border-amber-500 bg-amber-50 text-amber-800', style: {} }
    case 'taken':
      return { className: 'text-white', style: { backgroundColor: teamColor || '#475569' } }
    case 'unavailable':
      return {
        className: 'text-slate-400 line-through ring-1 ring-slate-300',
        style: { background: 'repeating-linear-gradient(45deg,#e2e8f0 0 3px,#f8fafc 3px 6px)' },
      }
    default:
      return { className: 'bg-white text-slate-600 ring-1 ring-slate-300', style: {} }
  }
}

/** Giờ server − giờ máy tại lúc tải dữ liệu, để đồng hồ đếm ngược khớp hạn backend dùng. */
export function serverOffset(serverTime, fetchedAt) {
  const server = Date.parse(serverTime)
  return Number.isNaN(server) || !fetchedAt ? 0 : server - fetchedAt
}
