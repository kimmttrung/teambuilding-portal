/** Tiện ích dùng chung cho màn hình Gala. */

/**
 * Kiểu hiển thị của một ghế. Mỗi trạng thái khác nhau cả hình dạng (viền đứt, tô kín, sọc),
 * không chỉ màu — người mù màu vẫn phân biệt được (docs/07 §6).
 */
export function seatVisual(state, { selected = false, mine = false, teamId = null } = {}) {
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
        className: `${galaTeamVisual(teamId)} ${mine ? 'ring-2 ring-primary ring-offset-2' : ''}`,
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

// Màu danh mục dùng token của design system; ghế và chấm team luôn cùng màu.
const TEAM_COLORS = [
  ['bg-accent-orange', 'text-ink'],
  ['bg-accent-purple', 'text-accent-purple-deep'],
  ['bg-accent-teal', 'text-ink'],
  ['bg-accent-green', 'text-ink'],
  ['bg-accent-sky', 'text-ink'],
  ['bg-accent-brown', 'text-on-primary'],
  ['bg-accent-pink', 'text-ink'],
  ['bg-accent-purple-deep', 'text-on-primary'],
]
function teamColor(teamId) {
  return teamId == null
    ? ['bg-ink-secondary', 'text-on-primary']
    : TEAM_COLORS[Math.abs(Number(teamId)) % TEAM_COLORS.length]
}
export function galaTeamDot(teamId) {
  return teamColor(teamId)[0]
}
export function galaTeamVisual(teamId) {
  return teamColor(teamId).join(' ')
}

/** Chỉ chọn trong đúng sơ đồ/lượt và không giữ danh sách cũ khi quota giảm. */
export function availablePicks(view, selection) {
  const team = view?.my_team
  const scope = `${view?.layout.id}:${team?.team_id}:${team?.turn_ends_at}`
  if (view?.draw.paused_at || !team?.is_leader || !team.is_my_turn || selection.scope !== scope) return []
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

/** Bán kính đủ chỗ cho vòng ghế, dùng chung khi đo và vẽ sơ đồ. */
export function galaTableRadius(seatCount) {
  return Math.max(62, (seatCount * 32) / (2 * Math.PI))
}

/** Giữ thứ tự/toạ độ bàn, nới từng hàng và cột theo bàn lớn nhất để vòng ghế không chồng nhau. */
export function galaFloorGeometry(tables) {
  if (!tables.length) return { width: 320, height: 160, positions: {} }
  const seatSize = 24
  const gap = 32
  const padding = 16
  function axis(field) {
    const sizes = new Map()
    for (const table of tables) {
      const diameter = galaTableRadius(table.seat_count) * 2 + seatSize
      sizes.set(table[field], Math.max(sizes.get(table[field]) ?? 0, diameter))
    }
    const coordinates = [...sizes.keys()].sort((a, b) => a - b)
    const centers = new Map()
    let edge = padding
    let previous = coordinates[0]
    for (const coordinate of coordinates) {
      edge += Math.max(0, coordinate - previous - 1) * 64
      centers.set(coordinate, edge + sizes.get(coordinate) / 2)
      edge += sizes.get(coordinate) + gap
      previous = coordinate
    }
    return { centers, size: edge - gap + padding }
  }
  const columns = axis('pos_x')
  const rows = axis('pos_y')
  return {
    width: Math.max(320, columns.size),
    height: rows.size,
    positions: Object.fromEntries(tables.map((table) => [table.id, {
      x: columns.centers.get(table.pos_x),
      y: rows.centers.get(table.pos_y),
    }])),
  }
}
