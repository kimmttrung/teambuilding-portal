export const DIRECTION_TABS = { outbound: 'Chiều đi', return: 'Chiều về' }

export function boardPeople(data) {
  const assignments = new Map((data?.assignments ?? []).map((a) => [a.registration_id, a]))
  return (data?.participants ?? []).map((person) => {
    const assignment = assignments.get(person.registration_id)
    return { ...person, ...assignment, assignment_id: assignment?.id ?? null }
  })
}

export function groupTeams(people) {
  const groups = new Map()
  for (const person of people) {
    // Người chưa có team là từng nhóm độc lập, giống quy tắc của allocator.
    const key = person.team_id ?? `person-${person.registration_id}`
    if (!groups.has(key))
      groups.set(key, {
        key,
        name: person.team_name ?? person.full_name,
        color: person.team_color,
        people: [],
      })
    groups.get(key).people.push(person)
  }
  return [...groups.values()].sort((a, b) => b.people.length - a.people.length)
}

export function boardStats(people, flights) {
  const assigned = people.filter((p) => p.flight_id != null)
  const teams = groupTeams(people).filter((t) => t.people[0].team_id != null)
  const split = teams.filter(
    (t) => new Set(t.people.filter((p) => p.flight_id).map((p) => p.flight_id)).size > 1,
  ).length
  const requested = assigned.filter((p) => p.requested_shift_id != null)
  const mismatch = requested.filter((p) => p.shift_mismatch).length
  return {
    assigned: assigned.length,
    total: people.length,
    split,
    mismatch,
    unassigned: people.length - assigned.length,
    manual: assigned.filter((p) => p.assignment_mode === 'manual').length,
    satisfaction: requested.length ? (requested.length - mismatch) / requested.length : 1,
    overloaded: flights.filter((f) => f.remaining_slots < 0).length,
  }
}

export function allocationDiff(people, preview, flights) {
  const proposals = new Map((preview.assignments ?? []).map((a) => [a.registration_id, a]))
  const byFlight = new Map(flights.map((f) => [f.id, f]))
  return people
    .map((person) => {
      const proposed = proposals.get(person.registration_id)
      const before = person.flight_id ?? null
      const after = proposed?.flight_id ?? null
      const kind =
        before === after ? 'keep' : before == null ? 'add' : after == null ? 'remove' : 'move'
      const flag = preview.flags.find(
        (f) => f.registration_id === person.registration_id && f.type === 'SHIFT_NOT_SATISFIED',
      )
      return {
        person,
        before: byFlight.get(before),
        after: byFlight.get(after),
        kind,
        reason: proposed?.pinned
          ? 'Giữ nguyên · BTC chỉnh tay'
          : (flag?.message ??
            (kind === 'remove'
              ? 'Chưa có chỗ phù hợp'
              : kind === 'keep'
                ? 'Giữ nguyên'
                : 'Theo ưu tiên team và ca đăng ký')),
        pinned: proposed?.pinned ?? false,
      }
    })
    .sort(
      (a, b) =>
        ['add', 'move', 'remove', 'keep'].indexOf(a.kind) -
        ['add', 'move', 'remove', 'keep'].indexOf(b.kind),
    )
}

/** Chỉ nhận màu phân loại do API cung cấp, không nhận chuỗi CSS tùy ý. */
export function teamColor(color) {
  return /^#[\da-f]{6}$/i.test(color ?? '') ? color : 'var(--color-ink-faint)'
}

/** Gom những người cùng team và cùng thay đổi; vẫn mở được từng hành khách. */
export function groupDiff(rows) {
  const groups = new Map()
  for (const row of rows) {
    const key =
      row.kind !== 'add' && row.person.team_id != null
        ? JSON.stringify([
            row.person.team_id,
            row.before?.id,
            row.after?.id,
            row.kind,
            row.pinned,
            row.reason,
          ])
        : `person-${row.person.registration_id}`
    if (!groups.has(key)) groups.set(key, { ...row, key, rows: [] })
    groups.get(key).rows.push(row)
  }
  return [...groups.values()]
}
