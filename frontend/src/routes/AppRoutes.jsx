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
import SchedulePage from '../pages/user/SchedulePage'
import DashboardPage from '../pages/admin/DashboardPage'
import RegistrationsPage from '../pages/admin/RegistrationsPage'
import EmailLogsPage from '../pages/admin/EmailLogsPage'
import BusesPage from '../pages/admin/BusesPage'
import RoomsPage from '../pages/admin/RoomsPage'
import UsersPage from '../pages/admin/UsersPage'
import FlightsPage from '../pages/admin/FlightsPage'
import FlightBoardPage from '../pages/admin/FlightBoardPage'
import GalaAdminPage from '../pages/admin/GalaAdminPage'
import GalaPage from '../pages/gala/GalaPage'
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
          <Route path="schedule" element={<SchedulePage />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="gala" element={<GalaPage />} />

          {/* BTC */}
          <Route element={<ProtectedRoute roles={ADMIN_ROLES} />}>
            <Route path="admin" element={<DashboardPage />} />
            <Route path="admin/registrations" element={<RegistrationsPage />} />
            <Route path="admin/email-logs" element={<EmailLogsPage />} />
            <Route path="admin/buses" element={<BusesPage />} />
            <Route path="admin/rooms" element={<RoomsPage />} />
            <Route path="admin/flights" element={<FlightsPage />} />
            <Route path="admin/flights/board" element={<FlightBoardPage />} />
            <Route path="admin/users" element={<UsersPage />} />
            <Route path="admin/gala" element={<GalaAdminPage />} />
            <Route path="admin/announcements" element={<Placeholder title="Thông báo" step={25} />} />
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
