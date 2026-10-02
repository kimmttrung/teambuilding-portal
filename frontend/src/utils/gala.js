/** Tiện ích dùng chung cho màn hình Gala. */

/**
 * Kiểu hiển thị của một ghế. Mỗi trạng thái khác nhau cả hình dạng (viền đứt, tô kín, sọc),
 * không chỉ màu — người mù màu vẫn phân biệt được (docs/07 §6).
 */
export function seatVisual(state, { selected = false, mine = false } = {}) {
  if (selected && state === 'available') {
    return { className: 'bg-primary text-on-primary ring-2 ring-primary/25', style: {} }
  }
  switch (state) {
    case 'held_by_me':
      return { className: 'bg-primary text-on-primary', style: {} }
    case 'held_by_other':
      return {
        className:
          'border border-dashed border-accent-orange bg-accent-orange/10 text-accent-orange-deep',
        style: {},
      }
    case 'taken':
      return {
        className: mine
          ? 'bg-accent-pink text-ink ring-2 ring-accent-pink/25'
          : 'bg-ink-secondary text-on-primary',
        style: {},
      }
    case 'unavailable':
      return {
        className:
          'bg-hairline text-ink-faint line-through [background-image:repeating-linear-gradient(45deg,transparent_0_3px,var(--color-canvas-soft)_3px_6px)]',
        style: {},
      }
    default:
      return { className: 'border border-input-border bg-surface text-ink-secondary', style: {} }
  }
}

const TEAM_DOTS = [
  'bg-accent-orange',
  'bg-accent-purple',
  'bg-accent-teal',
  'bg-accent-green',
  'bg-accent-sky',
  'bg-accent-brown',
]
export function galaTeamDot(teamId) {
  return teamId == null ? 'bg-ink-faint' : TEAM_DOTS[Math.abs(Number(teamId)) % TEAM_DOTS.length]
}

/** Chỉ chọn trong đúng sơ đồ/lượt và không giữ danh sách cũ khi quota giảm. */
export function availablePicks(view, selection) {
  const team = view?.my_team
  const scope = `${view?.layout.id}:${team?.team_id}:${team?.turn_ends_at}`
  if (!team?.is_leader || !team.is_my_turn || selection.scope !== scope) return []
  const free = new Set(
    view.tables.flatMap((table) =>
      table.seats.filter((seat) => seat.state === 'available').map((seat) => seat.id),
    ),
  )
  return selection.ids.filter((id) => free.has(id)).slice(0, Math.min(team.remaining, 30))
}

/** Giờ server − giờ máy tại lúc tải dữ liệu, để đồng hồ đếm ngược khớp hạn backend dùng. */
export function serverOffset(serverTime, fetchedAt) {
  const server = Date.parse(serverTime)
  return Number.isNaN(server) || !fetchedAt ? 0 : server - fetchedAt
}

/** Khung bao bàn/ghế thực tế: bỏ lưới trống và chừa biên kể cả bàn 24 ghế. */
export function galaFloorGeometry(tables) {
  const circles = tables.map((table) => ({
    id: table.id,
    x: (table.pos_x + 0.5) * 64,
    y: (table.pos_y + 0.5) * 64,
    radius: Math.max(62, (table.seat_count * 30) / (2 * Math.PI)),
  }))
  if (!circles.length) return { width: 320, height: 160, left: 0, top: 0 }
  const left = Math.min(...circles.map((c) => c.x - c.radius - 12)) - 16
  const top = Math.min(...circles.map((c) => c.y - c.radius - 12)) - 16
  const right = Math.max(...circles.map((c) => c.x + c.radius + 12)) + 16
  const bottom = Math.max(...circles.map((c) => c.y + c.radius + 12)) + 16
  return { width: Math.max(320, right - left), height: bottom - top, left, top }
}
