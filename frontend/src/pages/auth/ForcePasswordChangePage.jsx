import { useNavigate } from 'react-router-dom'
import { LogOut, ShieldCheck } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../context/ToastContext'
import ChangePasswordForm from '../../components/profile/ChangePasswordForm'

/**
 * Màn hình duy nhất của tài khoản đang dùng mật khẩu do BTC cấp (vừa được tạo hoặc vừa được đặt lại).
 *
 * `ProtectedRoute` vẽ thẳng trang này thay cho mọi route, và backend cũng từ chối mọi API khác
 * (`PASSWORD_CHANGE_REQUIRED`), nên không có menu hay liên kết nào ở đây ngoài Đăng xuất.
 * Đổi xong, `useChangePassword` cập nhật user (cờ `must_change_password` tắt) và route đang mở hiện ra.
 */
export default function ForcePasswordChangePage() {
  const { user, logout } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()

  async function handleLogout() {
    try {
      await logout()
      navigate('/login')
    } catch {
      toast.error('Không đăng xuất được. Vui lòng thử lại.')
    }
  }

  return (
    <div className="grid min-h-dvh place-items-center bg-canvas-soft px-4 py-10">
      <div className="w-full max-w-md rounded-xl bg-surface p-6 shadow-elevated sm:p-8">
        <span className="grid size-11 place-items-center rounded-md bg-primary text-on-primary">
          <ShieldCheck className="size-5" aria-hidden="true" />
        </span>
        <h1 className="mt-4 text-heading-2 text-ink">Đổi mật khẩu để tiếp tục</h1>
        <p className="mt-2 text-body-sm text-ink-muted">
          Chào {user.full_name}. Mật khẩu Ban tổ chức cấp chỉ dùng cho lần đăng nhập đầu. Hãy đặt mật
          khẩu của riêng bạn trước khi xem hành trình hay đăng ký.
        </p>

        <div className="mt-6">
          <ChangePasswordForm currentLabel="Mật khẩu Ban tổ chức cấp" submitFullWidth />
        </div>

        <button
          type="button"
          onClick={handleLogout}
          className="mt-5 inline-flex items-center gap-1.5 text-caption font-medium text-ink-muted hover:text-ink"
        >
          <LogOut className="size-4" aria-hidden="true" />
          Đăng xuất
        </button>
      </div>
    </div>
  )
}
