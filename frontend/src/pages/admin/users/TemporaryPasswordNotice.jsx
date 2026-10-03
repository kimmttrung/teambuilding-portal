import { useState } from 'react'
import { Check, Copy } from 'lucide-react'
import Alert from '../../../components/common/Alert'
import Button from '../../../components/common/Button'

/**
 * Hiện mật khẩu tạm đúng một lần. Hệ thống không lưu bản rõ, nên đóng hộp thoại là mất —
 * quên thì đặt lại mật khẩu mới chứ không "xem lại" được.
 */
export default function TemporaryPasswordNotice({ password, email }) {
  const [copied, setCopied] = useState(false)

  async function copy() {
    try {
      await navigator.clipboard.writeText(password)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }

  return (
    <Alert tone="warning" title="Mật khẩu tạm — chỉ hiện một lần">
      <p>
        Hệ thống tự động gửi thông tin đăng nhập tới <strong>{email}</strong>. Kiểm tra Nhật ký email nếu người dùng chưa nhận được thư. Bạn vẫn có thể sao chép mật khẩu để hỗ trợ. Người dùng bắt buộc đổi mật khẩu ở lần đăng nhập đầu.
      </p>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <code className="rounded-md bg-white px-3 py-1.5 font-mono text-base tracking-wider text-slate-900 ring-1 ring-amber-200 select-all">
          {password}
        </code>
        <Button type="button" size="sm" variant="secondary" icon={copied ? Check : Copy} onClick={copy}>
          {copied ? 'Đã chép' : 'Chép'}
        </Button>
      </div>
    </Alert>
  )
}
