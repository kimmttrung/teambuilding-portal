/** Lưu một Blob xuống máy người dùng với tên cho trước. */
export function saveBlob(blob, filename) {
  const href = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = href
  link.download = filename
  link.rel = 'noopener'
  document.body.appendChild(link)
  link.click()
  link.remove()
  // Thu hồi ngay thì một số trình duyệt huỷ lượt tải.
  setTimeout(() => URL.revokeObjectURL(href), 1000)
}

// Ô CSV bắt đầu bằng các ký tự này bị Excel coi là công thức (CSV injection).
const FORMULA_START = /^[=+\-@\t\r]/

export function csvCell(value) {
  let text = value === null || value === undefined ? '' : String(value)
  if (FORMULA_START.test(text)) text = `'${text}`
  return /[",;\n\r]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text
}

/** CSV có BOM để Excel đọc đúng tiếng Việt khi mở bằng double-click. */
export function buildCsv(headers, rows) {
  return `﻿${[headers, ...rows].map((row) => row.map(csvCell).join(',')).join('\r\n')}`
}
