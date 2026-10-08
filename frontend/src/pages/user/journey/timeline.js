import { format, parseISO } from 'date-fns'
import { vi } from 'date-fns/locale'
import { formatTime } from '../../../utils/format'

/**
 * Một dòng thời gian cho CBNV: lịch trình là xương sống, vé cá nhân gắn vào mốc
 * cùng việc. Vé không khớp mốc nào thành một bước riêng, để không mất thông tin
 * và cũng không hiện hai lần.
 */

function clock(value) {
  if (!value) return null
  const date = parseISO(value)
  if (Number.isNaN(date.getTime())) return null
  return { date: format(date, 'yyyy-MM-dd'), time: format(date, 'HH:mm') }
}

function minutes(value) {
  const match = String(value ?? '').match(/^(\d{2}):(\d{2})/)
  if (!match) return null
  return Number(match[1]) * 60 + Number(match[2])
}

function closest(steps, time) {
  if (!steps.length) return null
  const target = minutes(time)
  if (target == null) return steps[0]
  return [...steps].sort(
    (a, b) => Math.abs((minutes(a.time) ?? 0) - target) - Math.abs((minutes(b.time) ?? 0) - target),
  )[0]
}

function onDate(steps, date, predicate) {
  return steps.filter((step) => (!date || step.date === date) && predicate(step))
}

function dayNumber(start, date) {
  if (!start || !date) return null
  const diff = Date.parse(date) - Date.parse(start)
  if (Number.isNaN(diff)) return null
  const number = Math.round(diff / 86400000) + 1
  return number > 0 ? number : null
}

function dayLabel(date) {
  const parsed = parseISO(date)
  if (Number.isNaN(parsed.getTime())) return date
  const label = format(parsed, 'EEEE, dd/MM', { locale: vi })
  return label.charAt(0).toUpperCase() + label.slice(1)
}

export function actionLine(step) {
  if (step.bus) {
    const bus = step.bus
    const where = bus.pickup_point?.name || step.location
    const gather = bus.gather_time ? formatTime(bus.gather_time) : step.time
    const depart = bus.departure_time ? formatTime(bus.departure_time) : null
    const parts = []
    if (where && gather && gather !== '—') parts.push(`Có mặt tại ${where} lúc ${gather}`)
    else if (where) parts.push(`Có mặt tại ${where}`)
    else if (gather && gather !== '—') parts.push(`Có mặt lúc ${gather}`)
    if (bus.bus_code) parts.push(`· Xe ${bus.bus_code}`)
    if (depart && depart !== '—' && depart !== gather) parts.push(`· xe chạy ${depart}`)
    if (bus.dropoff_point) parts.push(`· xuống tại ${bus.dropoff_point}`)
    return parts.join(' ')
  }
  if (step.flight) {
    const flight = step.flight
    const parts = [`Bay ${flight.departure_airport} → ${flight.arrival_airport}`]
    if (flight.flight_code) parts.push(`· ${flight.flight_code}`)
    if (flight.seat_number) parts.push(`· ghế ${flight.seat_number}`)
    const arrival = flight.arrival_time ? formatTime(flight.arrival_time) : null
    if (arrival && arrival !== '—') parts.push(`· đến ${arrival}`)
    return parts.join(' ')
  }
  if (step.hotel) {
    const stay = step.hotel
    const room = stay.room_number ? `Phòng ${stay.room_number}` : 'Nhận phòng'
    return [room, stay.hotel_name].filter(Boolean).join(' · ')
  }
  if (step.gala) {
    const gala = step.gala
    const seat = [`Bàn ${gala.table_code || '—'}`, gala.seat_number != null ? `ghế ${gala.seat_number}` : null]
      .filter(Boolean)
      .join(' · ')
    return [seat, gala.venue].filter(Boolean).join(' · ')
  }
  return step.description || (step.location ? `Tại ${step.location}` : '')
}

function blankStep(extra) {
  return {
    endTime: '',
    location: '',
    description: '',
    tripLegId: null,
    kind: 'activity',
    bus: null,
    flight: null,
    hotel: null,
    gala: null,
    ...extra,
  }
}

export function buildTimeline(journey) {
  const steps = (journey?.itinerary ?? []).map((item, index) => blankStep({
    key: `it-${item.id ?? index}`,
    date: item.day_date,
    time: item.start_time || '',
    endTime: item.end_time || '',
    title: item.title,
    location: item.location || '',
    description: item.description || '',
    tripLegId: item.trip_leg_id ?? null,
  }))

  for (const bus of journey?.buses ?? []) {
    const when = clock(bus.gather_time || bus.departure_time)
    const date = when?.date || bus.trip_leg?.leg_date || null
    const byLeg = steps.find((step) => step.tripLegId && step.tripLegId === bus.trip_leg?.id && !step.bus)
    const byTitle = closest(
      onDate(steps, date, (step) => !step.bus && /tập trung|điểm đón|ra sân bay|theo xe/i.test(step.title)),
      when?.time,
    )
    const hit = byLeg || byTitle
    if (hit) {
      hit.bus = bus
      hit.kind = 'bus'
      if (bus.pickup_point?.name) hit.location = bus.pickup_point.name
    } else if (date || bus.bus_code) {
      steps.push(blankStep({
        key: `bus-${bus.bus_id ?? bus.bus_code}`,
        date,
        time: when?.time || '',
        title: bus.trip_leg?.name || 'Xe đưa đón',
        location: bus.pickup_point?.name || '',
        kind: 'bus',
        bus,
      }))
    }
  }

  for (const flight of [journey?.flights?.outbound, journey?.flights?.return].filter(Boolean)) {
    const when = clock(flight.departure_time)
    const named = flight.arrival_airport
      ? onDate(steps, when?.date, (step) => !step.flight && /bay|chuyến/i.test(step.title) && step.title.includes(flight.arrival_airport))
      : []
    const titled = onDate(steps, when?.date, (step) => !step.flight && /bay|chuyến/i.test(step.title))
    const hit = closest(named, when?.time) || closest(titled, when?.time)
    if (hit) {
      hit.flight = flight
      hit.kind = 'flight'
    } else {
      steps.push(blankStep({
        key: `flight-${flight.flight_code}-${flight.direction || ''}`,
        date: when?.date || null,
        time: when?.time || '',
        title: `Chuyến bay ${flight.flight_code || ''}`.trim(),
        location: flight.departure_airport || '',
        kind: 'flight',
        flight,
      }))
    }
  }

  const stay = journey?.accommodation
  if (stay) {
    const when = clock(stay.check_in_at)
    const hit = closest(
      onDate(steps, when?.date, (step) => !step.hotel && /nhận phòng/i.test(step.title)),
      when?.time,
    ) || steps.find((step) => !step.hotel && /nhận phòng/i.test(step.title))
    if (hit) {
      hit.hotel = stay
      hit.kind = hit.kind === 'activity' ? 'hotel' : hit.kind
    } else {
      steps.push(blankStep({
        key: 'hotel-checkin',
        date: when?.date || null,
        time: when?.time || '',
        title: 'Nhận phòng',
        location: stay.hotel_name || '',
        kind: 'hotel',
        hotel: stay,
      }))
    }
    const checkout = clock(stay.check_out_at)
    const checkoutStep = closest(
      onDate(steps, checkout?.date, (step) => /trả phòng/i.test(step.title)),
      checkout?.time,
    )
    if (checkoutStep) checkoutStep.checkout = stay
  }

  const gala = journey?.gala
  if (gala) {
    const when = clock(gala.starts_at)
    const hit = closest(
      onDate(steps, when?.date, (step) => !step.gala && /gala/i.test(step.title)),
      when?.time,
    ) || steps.find((step) => !step.gala && /gala/i.test(step.title))
    if (hit) {
      hit.gala = gala
      if (hit.kind === 'activity') hit.kind = 'gala'
    } else {
      steps.push(blankStep({
        key: 'gala',
        date: when?.date || null,
        time: when?.time || '',
        title: gala.name || 'Gala Dinner',
        location: gala.venue || '',
        kind: 'gala',
        gala,
      }))
    }
  }

  steps.sort((a, b) => {
    const byDate = String(a.date || '9999').localeCompare(String(b.date || '9999'))
    if (byDate) return byDate
    return (a.time || '99:99').localeCompare(b.time || '99:99')
  })

  const start = journey?.event?.start_date
  const days = []
  for (const step of steps) {
    const date = step.date || 'unknown'
    let day = days.find((item) => item.date === date)
    if (!day) {
      day = {
        date,
        number: dayNumber(start, step.date),
        label: step.date ? dayLabel(step.date) : 'Chưa rõ ngày',
        steps: [],
      }
      days.push(day)
    }
    day.steps.push(step)
  }
  return { days, steps }
}

export function stepMoment(step) {
  if (!step?.date) return null
  const time = step.time && /^\d{2}:\d{2}/.test(step.time) ? step.time : '00:00'
  const date = new Date(`${step.date}T${time}:00`)
  return Number.isNaN(date.getTime()) ? null : date
}

export function nextTimelineStep(days, now = new Date()) {
  const steps = (days ?? []).flatMap((day) => day.steps)
  const upcoming = steps.find((step) => {
    const moment = stepMoment(step)
    return moment && moment >= now
  })
  return upcoming || steps[0] || null
}
