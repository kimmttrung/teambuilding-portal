import { format, formatDistanceToNowStrict, parseISO } from 'date-fns'
import { vi } from 'date-fns/locale'

/**
 * Backend lưu và trả về UTC ISO-8601. Người dùng ở Việt Nam, nên mọi thứ hiển thị
 * theo giờ Việt Nam. Trình duyệt của CBNV luôn ở múi giờ VN nên dùng giờ máy là đúng;
 * nếu ai đó mở từ nước ngoài, `TIMEZONE_NOTE` giải thích mốc giờ đang xem.
 */
export const TIMEZONE_NOTE = 'Giờ Việt Nam (GMT+7)'

function toDate(value) {
  if (!value) return null
  try {
    const date = typeof value === 'string' ? parseISO(value) : value
    return Number.isNaN(date.getTime()) ? null : date
  } catch {
    return null
  }
}

/** 15/10/2026 */
export function formatDate(value) {
  const date = toDate(value)
  return date ? format(date, 'dd/MM/yyyy') : '—'
}

/** Thứ 5, 15/10/2026 — kèm thứ để tránh nhầm ngày khi xem nhanh */
export function formatDateWithWeekday(value) {
  const date = toDate(value)
  return date ? format(date, 'EEEE, dd/MM/yyyy', { locale: vi }) : '—'
}

/** 05:30 */
export function formatTime(value) {
  const date = toDate(value)
  return date ? format(date, 'HH:mm') : '—'
}

/** 15/10/2026 05:30 */
export function formatDateTime(value) {
  const date = toDate(value)
  return date ? format(date, 'dd/MM/yyyy HH:mm') : '—'
}

/** Thứ 5, 15/10/2026 · 05:30 */
export function formatFullDateTime(value) {
  const date = toDate(value)
  return date ? format(date, "EEEE, dd/MM/yyyy · HH:mm", { locale: vi }) : '—'
}

/** "3 ngày trước", "còn 12 ngày" */
export function formatRelative(value) {
  const date = toDate(value)
  if (!date) return '—'
  const distance = formatDistanceToNowStrict(date, { locale: vi })
  return date > new Date() ? `còn ${distance}` : `${distance} trước`
}

/** Số ngày còn lại tới một mốc (âm nếu đã qua). */
export function daysUntil(value) {
  const date = toDate(value)
  if (!date) return null
  const oneDay = 24 * 60 * 60 * 1000
  const startOfToday = new Date()
  startOfToday.setHours(0, 0, 0, 0)
  return Math.round((date - startOfToday) / oneDay)
}

/** 1.234 */
export function formatNumber(value) {
  return typeof value === 'number' ? value.toLocaleString('vi-VN') : '—'
}

/** 0912 345 678 — dễ đọc và dễ bấm gọi trên điện thoại */
export function formatPhone(value) {
  if (!value) return '—'
  const digits = value.replace(/\D/g, '')
  if (digits.length === 10) return `${digits.slice(0, 4)} ${digits.slice(4, 7)} ${digits.slice(7)}`
  return value
}

/** Chữ cái đầu của tên để làm avatar khi chưa có ảnh: "Nguyễn Văn A" -> "A" */
export function initials(fullName) {
  if (!fullName) return '?'
  const parts = fullName.trim().split(/\s+/)
  return parts[parts.length - 1][0].toUpperCase()
}
