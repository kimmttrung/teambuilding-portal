/** Điểm đón/trả của một chặng, đúng thành phố xuất phát.

Điểm không gắn nơi làm việc dùng được cho mọi thành phố. Điểm gắn thành phố khác thì ẩn.
*/
export function pointsForLeg(points, leg, departureLocationId) {
  const cityId =
    departureLocationId === '' || departureLocationId == null ? null : Number(departureLocationId)
  return (points ?? []).filter((point) => {
    const onLeg = point.trip_leg_id == null || point.trip_leg_id === leg.id
    if (!onLeg) return false
    if (point.work_location_id == null) return true
    return cityId != null && Number(point.work_location_id) === cityId
  })
}

export function isReturnDropoff(leg) {
  return leg?.code === 'AIRPORT_TO_CITY'
}
