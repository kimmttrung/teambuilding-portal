/**
 * Tiện ích cho hành trình: thêm vào lịch (.ics), mở bản đồ, gọi điện.
 *
 * Không dùng thư viện: file .ics chỉ là vài dòng văn bản theo RFC 5545.
 */

/** 2026-10-15T06:30:00+00:00 -> 20261015T063000Z */
function icsDate(value) {
  return new Date(value).toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z')
}

function icsText(value) {
  return String(value ?? '')
    .replace(/\\/g, '\\\\')
    .replace(/;/g, '\\;')
    .replace(/,/g, '\\,')
    .replace(/\r?\n/g, '\\n')
}

function icsDay(value) {
  const match = String(value ?? '').match(/^(\d{4})-(\d{2})-(\d{2})/)
  return match ? `${match[1]}${match[2]}${match[3]}` : null
}

function nextDay(value) {
  const date = new Date(`${value}T00:00:00Z`)
  if (Number.isNaN(date.getTime())) return null
  date.setUTCDate(date.getUTCDate() + 1)
  return date.toISOString().slice(0, 10)
}

/**
 * Nội dung một file .ics. Giờ ghi dạng UTC (hậu tố Z) để lịch trên điện thoại tự đổi sang
 * giờ máy — không phải đoán múi giờ.
 */
export function buildIcs({ uid, title, start, end, location, description, alarmMinutes = 60, allDay = false }) {
  const startDay = allDay ? icsDay(start) : null
  const endDay = allDay ? icsDay(end || nextDay(start)) : null
  const startDate = new Date(start)
  const endDate = end ? new Date(end) : new Date(startDate.getTime() + 60 * 60 * 1000)

  if (allDay && (!startDay || !endDay)) return ''

  return [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//Team Building Portal//VI',
    'CALSCALE:GREGORIAN',
    'METHOD:PUBLISH',
    'BEGIN:VEVENT',
    `UID:${uid}@teambuilding-portal`,
    `DTSTAMP:${icsDate(new Date())}`,
    allDay ? `DTSTART;VALUE=DATE:${startDay}` : `DTSTART:${icsDate(startDate)}`,
    allDay ? `DTEND;VALUE=DATE:${endDay}` : `DTEND:${icsDate(endDate)}`,
    `SUMMARY:${icsText(title)}`,
    location ? `LOCATION:${icsText(location)}` : null,
    description ? `DESCRIPTION:${icsText(description)}` : null,
    alarmMinutes == null ? null : 'BEGIN:VALARM',
    alarmMinutes == null ? null : `TRIGGER:-PT${alarmMinutes}M`,
    alarmMinutes == null ? null : 'ACTION:DISPLAY',
    alarmMinutes == null ? null : `DESCRIPTION:${icsText(title)}`,
    alarmMinutes == null ? null : 'END:VALARM',
    'END:VEVENT',
    'END:VCALENDAR',
  ]
    .filter(Boolean)
    .join('\r\n')
}

export function downloadIcs(filename, event) {
  const blob = new Blob([buildIcs(event)], { type: 'text/calendar;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename.endsWith('.ics') ? filename : `${filename}.ics`
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

/**
 * Link bản đồ cho một địa điểm. Chỉ tin `map_url` dạng http(s): link do BTC nhập, nhưng
 * `javascript:` trong href là lỗ XSS dù người nhập là ai.
 */
export function mapsUrl(place) {
  if (!place) return null
  if (place.map_url && /^https?:\/\//i.test(place.map_url)) return place.map_url
  const query = [place.name, place.address].filter(Boolean).join(', ')
  return query ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}` : null
}

/** "0912 345 678" -> "tel:0912345678" */
export function telHref(phone) {
  const digits = String(phone ?? '').replace(/[^\d+]/g, '')
  return digits ? `tel:${digits}` : null
}
