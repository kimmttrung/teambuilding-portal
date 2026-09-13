/** Thư đang thật sự trên đường gửi (không tính dòng chỉ ghi log vì EMAIL_ENABLED=false). */
export function isInFlight(log) {
  return log.status === 'queued' && !log.is_dev_only
}

/**
 * Backend ghi lỗi dạng "<lỗi thô> | <cách sửa>". Tách ra để hiện cách sửa trước —
 * "535 BadCredentials" không nói gì với BTC, "cần App Password" thì có.
 */
export function splitEmailError(message) {
  if (!message) return { detail: null, hint: null }
  const [detail, ...rest] = message.split(' | ')
  return { detail, hint: rest.join(' | ') || null }
}
