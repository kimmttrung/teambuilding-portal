/**
 * Người có `gender` ở được phòng `policy` không — khớp `gender_violation` ở backend.
 * Người chưa khai nam/nữ chỉ vào được phòng không giới hạn: không đoán thay họ.
 */
export function canStay(policy, gender) {
  if (policy === 'any') return true
  return gender === policy
}

/** Sắp tầng như người đọc: "2" trước "12", phòng chưa ghi tầng xuống cuối. */
export function groupByFloor(rooms) {
  const floors = new Map()
  for (const room of rooms) {
    const key = room.floor ?? ''
    const list = floors.get(key)
    if (list) list.push(room)
    else floors.set(key, [room])
  }
  return [...floors.entries()]
    .sort(([left], [right]) => {
      if (!left) return 1
      if (!right) return -1
      return left.localeCompare(right, 'vi', { numeric: true })
    })
    .map(([floor, list]) => ({
      floor,
      rooms: list.sort((a, b) =>
        a.room_number.localeCompare(b.room_number, 'vi', { numeric: true }),
      ),
    }))
}

// Màu phân loại team dùng token của design-notion; cùng team luôn cùng màu giữa các tầng.
const TEAM_DOTS = [
  'bg-accent-orange',
  'bg-accent-green',
  'bg-accent-pink',
  'bg-accent-purple',
  'bg-accent-sky',
  'bg-accent-teal',
  'bg-accent-purple-deep',
  'bg-primary',
  'bg-accent-brown',
]
export function teamDotClass(teamId) {
  return teamId == null ? 'bg-ink-faint' : TEAM_DOTS[Math.abs(Number(teamId)) % TEAM_DOTS.length]
}
