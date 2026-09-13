import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { ShieldAlert } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import Spinner from '../components/common/Spinner'
import EmptyState from '../components/common/EmptyState'

/**
 * Chặn theo đăng nhập và vai trò.
 *
 * Đây chỉ là lớp ẩn/hiện giao diện cho gọn. Quyền THẬT nằm ở backend
 * (docs/09-security.md §2) — sửa localStorage không lấy được dữ liệu gì thêm.
 */
export default function ProtectedRoute({ roles }) {
  const { isAuthenticated, isRestoring, user } = useAuth()
  const location = useLocation()

  // Đang khôi phục phiên từ token cũ: chờ, đừng đá về trang đăng nhập.
  if (isRestoring) return <Spinner label="Đang kiểm tra phiên đăng nhập…" />

  if (!isAuthenticated) {
    // Nhớ trang đang muốn vào để đăng nhập xong quay lại đúng chỗ.
    return <Navigate to="/login" state={{ from: location.pathname }} replace />
  }

  // Tài khoản đang dùng mật khẩu do BTC cấp (tạo mới, đặt lại): bắt đổi trước khi dùng hệ thống.
  // Trang Hồ sơ có ô đổi mật khẩu, và backend xoá cờ ngay khi đổi xong.
  if (user.must_change_password && location.pathname !== '/profile') {
    return <Navigate to="/profile" replace />
  }

  if (roles && !roles.includes(user.role)) {
    return (
      <EmptyState
        icon={ShieldAlert}
        title="Bạn không có quyền xem trang này"
        description="Trang này dành cho Ban tổ chức. Nếu cần truy cập, vui lòng liên hệ BTC."
      />
    )
  }

  return <Outlet />
}
