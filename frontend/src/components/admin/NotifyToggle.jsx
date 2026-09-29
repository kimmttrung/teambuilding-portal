import { useEffect, useSyncExternalStore } from 'react'
import { Mail } from 'lucide-react'
import { notifyStore } from '../../api/notify'

/**
 * Ô "Gửi email cho CBNV bị ảnh hưởng" đặt ở đầu trang quản trị. Mặc định tắt, rời trang là tự tắt:
 * bật nhầm từ hôm trước rồi quên là mỗi cú kéo-thả thử nghiệm đều thành thư gửi thật.
 *
 * `hint` nói rõ ai nhận — ví dụ trang phân bổ chỉ gửi khi kỳ đã công bố (trước đó CBNV chưa thấy gì).
 */
export default function NotifyToggle({ hint }) {
  const enabled = useSyncExternalStore(notifyStore.subscribe, notifyStore.get, () => false)

  useEffect(() => () => notifyStore.set(false), [])

  return (
    <label
      title={hint}
      className={`inline-flex cursor-pointer items-center gap-2 rounded-md border px-3 py-1.5 text-body-sm transition-colors ${
        enabled
          ? 'border-amber-300 bg-amber-50 text-amber-900'
          : 'border-hairline bg-surface text-ink-secondary hover:border-input-border'
      }`}
    >
      <input
        type="checkbox"
        className="size-4 shrink-0 accent-amber-600"
        checked={enabled}
        onChange={(changeEvent) => notifyStore.set(changeEvent.target.checked)}
      />
      <Mail className="size-4 shrink-0" aria-hidden />
      <span>
        {enabled ? 'Đang bật: thay đổi sẽ gửi email CBNV bị ảnh hưởng' : 'Gửi email cho CBNV bị ảnh hưởng'}
      </span>
    </label>
  )
}
