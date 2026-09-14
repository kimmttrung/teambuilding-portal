import { useNow } from '../../hooks/useGala'

/**
 * Đếm ngược tới `endsAt` (ISO UTC). `offsetMs` = giờ server − giờ máy, để máy chạy lệch giờ
 * vẫn đếm đúng với hạn backend đang dùng.
 */
export default function Countdown({ endsAt, offsetMs = 0, className = '', expiredText = 'Hết giờ' }) {
  const now = useNow()
  if (!endsAt) return null
  const remaining = Math.max(Date.parse(endsAt) - (now + offsetMs), 0)
  const totalSeconds = Math.ceil(remaining / 1000)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  const urgent = totalSeconds <= 30

  return (
    <span
      role="timer"
      aria-live="off"
      className={`font-mono tabular-nums ${urgent ? 'text-rose-600' : ''} ${className}`}
    >
      {remaining === 0 ? expiredText : `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`}
    </span>
  )
}
