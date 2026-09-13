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

/**
 * Nội dung một file .ics. Giờ ghi dạng UTC (hậu tố Z) để lịch trên điện thoại tự đổi sang
 * giờ máy — không phải đoán múi giờ.
 */
export function buildIcs({ uid, title, start, end, location, description, alarmMinutes = 60 }) {
  const startDate = new Date(start)
  const endDate = end ? new Date(end) : new Date(startDate.getTime() + 60 * 60 * 1000)

  return [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//Team Building Portal//VI',
    'CALSCALE:GREGORIAN',
    'METHOD:PUBLISH',
    'BEGIN:VEVENT',
    `UID:${uid}@teambuilding-portal`,
    `DTSTAMP:${icsDate(new Date())}`,
    `DTSTART:${icsDate(startDate)}`,
    `DTEND:${icsDate(endDate)}`,
    `SUMMARY:${icsText(title)}`,
    location ? `LOCATION:${icsText(location)}` : null,
    description ? `DESCRIPTION:${icsText(description)}` : null,
    'BEGIN:VALARM',
    `TRIGGER:-PT${alarmMinutes}M`,
    'ACTION:DISPLAY',
    `DESCRIPTION:${icsText(title)}`,
    'END:VALARM',
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
