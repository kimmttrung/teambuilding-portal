import { Navigate, Route, Routes } from 'react-router-dom'
import { FileQuestion } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { ADMIN_ROLES } from '../utils/constants'
import ProtectedRoute from './ProtectedRoute'
import AppLayout from '../components/layout/AppLayout'
import LoginPage from '../pages/auth/LoginPage'
import MyJourneyPage from '../pages/user/MyJourneyPage'
import RegisterEventPage from '../pages/user/RegisterEventPage'
import ProfilePage from '../pages/user/ProfilePage'
import DashboardPage from '../pages/admin/DashboardPage'
import FlightsPage from '../pages/admin/FlightsPage'
import FlightBoardPage from '../pages/admin/FlightBoardPage'
import ComingSoon from '../components/common/ComingSoon'
import EmptyState from '../components/common/EmptyState'
import PageHeader from '../components/common/PageHeader'

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route index element={<HomeRedirect />} />

          {/* CBNV */}
          <Route path="my-journey" element={<MyJourneyPage />} />
          <Route path="register-event" element={<RegisterEventPage />} />
          <Route path="schedule" element={<Placeholder title="Lịch trình chương trình" step={17} />} />
          <Route path="profile" element={<ProfilePage />} />

          {/* BTC */}
          <Route element={<ProtectedRoute roles={ADMIN_ROLES} />}>
            <Route path="admin" element={<DashboardPage />} />
            <Route path="admin/registrations" element={<Placeholder title="Danh sách đăng ký" step={18} />} />
            <Route path="admin/flights" element={<FlightsPage />} />
            <Route path="admin/flights/board" element={<FlightBoardPage />} />
            <Route path="admin/users" element={<Placeholder title="Quản lý CBNV" step={18} />} />
            <Route path="admin/announcements" element={<Placeholder title="Thông báo" step={18} />} />
          </Route>

          <Route path="*" element={<NotFound />} />
        </Route>
      </Route>
    </Routes>
  )
}

/** Vào "/" thì đưa mỗi vai trò về màn hình chính của họ. */
function HomeRedirect() {
  const { user } = useAuth()
  return <Navigate to={ADMIN_ROLES.includes(user.role) ? '/admin' : '/my-journey'} replace />
}

function Placeholder({ title, step }) {
  return (
    <>
      <PageHeader title={title} />
      <ComingSoon title={title} step={step} />
    </>
  )
}

function NotFound() {
  return (
    <EmptyState
      icon={FileQuestion}
      title="Không tìm thấy trang"
      description="Đường dẫn này không tồn tại hoặc đã được đổi."
    />
  )
}
