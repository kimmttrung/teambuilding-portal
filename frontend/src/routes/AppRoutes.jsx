import { Link, Navigate, Route, Routes } from 'react-router-dom'
import { FileQuestion, House } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { ADMIN_ROLES } from '../utils/constants'
import ProtectedRoute from './ProtectedRoute'
import AppLayout from '../components/layout/AppLayout'
import LandingPage from '../pages/public/LandingPage'
import LoginPage from '../pages/auth/LoginPage'
import MyJourneyPage from '../pages/user/MyJourneyPage'
import RegisterEventPage from '../pages/user/RegisterEventPage'
import ProfilePage from '../pages/user/ProfilePage'
import SchedulePage from '../pages/user/SchedulePage'
import DashboardPage from '../pages/admin/DashboardPage'
import RegistrationsPage from '../pages/admin/RegistrationsPage'
import CancellationsPage from '../pages/admin/CancellationsPage'
import EmailLogsPage from '../pages/admin/EmailLogsPage'
import BusesPage from '../pages/admin/BusesPage'
import ItineraryPage from '../pages/admin/ItineraryPage'
import AnnouncementsPage from '../pages/admin/AnnouncementsPage'
import SettingsPage from '../pages/admin/SettingsPage'
import MasterDataPage from '../pages/admin/MasterDataPage'
import RoomsPage from '../pages/admin/RoomsPage'
import UsersPage from '../pages/admin/UsersPage'
import FlightsPage from '../pages/admin/FlightsPage'
import FlightBoardPage from '../pages/admin/FlightBoardPage'
import GalaAdminPage from '../pages/admin/GalaAdminPage'
import GalaPage from '../pages/gala/GalaPage'
import Button from '../components/common/Button'
import Card from '../components/common/Card'
import EmptyState from '../components/common/EmptyState'

export default function AppRoutes() {
  return (
    <Routes>
      {/* Trang giới thiệu public — taskbar có nút Đăng nhập dẫn tới /login. */}
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/home" element={<HomeRedirect />} />

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
            <Route path="admin/cancellations" element={<CancellationsPage />} />
            <Route path="admin/email-logs" element={<EmailLogsPage />} />
            <Route path="admin/buses" element={<BusesPage />} />
            <Route path="admin/itinerary" element={<ItineraryPage />} />
            <Route path="admin/announcements" element={<AnnouncementsPage />} />
            <Route path="admin/rooms" element={<RoomsPage />} />
            <Route path="admin/flights" element={<FlightsPage />} />
            <Route path="admin/flights/board" element={<FlightBoardPage />} />
            <Route path="admin/users" element={<UsersPage />} />
            <Route path="admin/gala" element={<GalaAdminPage />} />
            <Route path="admin/settings" element={<SettingsPage />} />
            <Route path="admin/master-data" element={<MasterDataPage />} />
          </Route>

          <Route path="*" element={<NotFound />} />
        </Route>
      </Route>
    </Routes>
  )
}

/** Vào "/home" thì đưa mỗi vai trò về màn hình chính của họ. */
function HomeRedirect() {
  const { user } = useAuth()
  return <Navigate to={ADMIN_ROLES.includes(user.role) ? '/admin' : '/my-journey'} replace />
}

function NotFound() {
  return (
    <Card>
      <EmptyState
        icon={FileQuestion}
        title="Không tìm thấy trang"
        description="Đường dẫn này không tồn tại hoặc đã được đổi."
        action={
          <Link to="/home">
            <Button size="sm" icon={House}>
              Về trang chính
            </Button>
          </Link>
        }
      />
    </Card>
  )
}
