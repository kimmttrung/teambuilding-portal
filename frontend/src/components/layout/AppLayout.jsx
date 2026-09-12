import { useState } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import {
  CalendarDays,
  ClipboardList,
  LayoutDashboard,
  LogOut,
  Map,
  Megaphone,
  Menu,
  Plane,
  Users,
  UserRound,
  X,
} from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../context/ToastContext'
import { ROLE_LABELS } from '../../utils/constants'
import { initials } from '../../utils/format'

const EMPLOYEE_NAV = [
  { to: '/my-journey', label: 'Hành trình', icon: Map },
  { to: '/register-event', label: 'Đăng ký', icon: ClipboardList },
  { to: '/schedule', label: 'Lịch trình', icon: CalendarDays },
  { to: '/profile', label: 'Hồ sơ', icon: UserRound },
]

const ADMIN_NAV = [
  { to: '/admin', label: 'Tổng quan', icon: LayoutDashboard, end: true },
  { to: '/admin/registrations', label: 'Đăng ký', icon: ClipboardList },
  { to: '/admin/flights', label: 'Chuyến bay', icon: Plane },
  { to: '/admin/users', label: 'CBNV', icon: Users },
  { to: '/admin/announcements', label: 'Thông báo', icon: Megaphone },
]

export default function AppLayout() {
  const { user, isAdmin, logout } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  const navItems = isAdmin ? ADMIN_NAV : EMPLOYEE_NAV

  async function handleLogout() {
    try {
      await logout()
      toast.success('Đã đăng xuất.')
      navigate('/login')
    } catch {
      toast.error('Không đăng xuất được. Vui lòng thử lại.')
    }
  }

  return (
    <div className="min-h-screen md:flex">
      {/* Sidebar — chỉ hiện trên màn hình rộng */}
      <aside className="hidden w-56 shrink-0 border-r border-slate-200 bg-white md:sticky md:top-0 md:flex md:h-screen md:flex-col lg:w-60">
        <Brand />
        <nav className="flex-1 space-y-0.5 p-2.5">
          {navItems.map((item) => (
            <SidebarLink key={item.to} {...item} />
          ))}
        </nav>
        <UserCard user={user} onLogout={handleLogout} />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Thanh trên — chỉ mobile */}
        <header className="sticky top-0 z-30 flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3 md:hidden">
          <Brand compact />
          <button
            type="button"
            onClick={() => setMobileMenuOpen((open) => !open)}
            className="rounded-lg p-2 text-slate-600 hover:bg-slate-100"
            aria-label={mobileMenuOpen ? 'Đóng menu' : 'Mở menu'}
            aria-expanded={mobileMenuOpen}
          >
            {mobileMenuOpen ? <X className="size-5" /> : <Menu className="size-5" />}
          </button>
        </header>

        {mobileMenuOpen && (
          <div className="border-b border-slate-200 bg-white p-3 md:hidden">
            <UserCard user={user} onLogout={handleLogout} />
          </div>
        )}

        <main className="mx-auto w-full max-w-[1600px] flex-1 px-4 py-4 pb-24 sm:px-6 lg:px-8 lg:py-6 md:pb-8">
          <Outlet />
        </main>

        {/* Thanh dưới — mobile. CBNV tra cứu bằng một tay ở sân bay. */}
        <nav className="fixed inset-x-0 bottom-0 z-30 flex border-t border-slate-200 bg-white md:hidden">
          {navItems.slice(0, 4).map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex flex-1 flex-col items-center gap-0.5 py-2 text-xs transition ${
                  isActive ? 'text-brand-700' : 'text-slate-500'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon className={`size-5 ${isActive ? 'stroke-[2.5]' : ''}`} aria-hidden="true" />
                  {label}
                </>
              )}
            </NavLink>
          ))}
        </nav>
      </div>
    </div>
  )
}

function Brand({ compact = false }) {
  return (
    <Link to="/" className="flex items-center gap-2.5 px-4 py-3.5">
      <span className="grid size-9 place-items-center rounded-lg bg-brand-600 text-white">
        <Plane className="size-5" aria-hidden="true" />
      </span>
      <span className="leading-tight">
        <span className="block font-semibold text-slate-900">Team Building</span>
        {!compact && <span className="block text-xs text-slate-500">Cổng thông tin nội bộ</span>}
      </span>
    </Link>
  )
}

function SidebarLink({ to, label, icon: Icon, end }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
          isActive ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100'
        }`
      }
    >
      <Icon className="size-4.5" aria-hidden="true" />
      {label}
    </NavLink>
  )
}

function UserCard({ user, onLogout }) {
  if (!user) return null
  return (
    <div className="flex items-center gap-3 border-t border-slate-100 p-3">
      {user.avatar_url ? (
        <img
          src={user.avatar_url}
          alt=""
          className="size-9 shrink-0 rounded-full object-cover"
        />
      ) : (
        <span className="grid size-9 shrink-0 place-items-center rounded-full bg-slate-200 text-sm font-semibold text-slate-600">
          {initials(user.full_name)}
        </span>
      )}
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-slate-900">{user.full_name}</p>
        <p className="truncate text-xs text-slate-500">
          {ROLE_LABELS[user.role] ?? user.role}
          {user.team ? ` · ${user.team.name}` : ''}
        </p>
      </div>
      <button
        type="button"
        onClick={onLogout}
        className="rounded-lg p-2 text-slate-500 transition hover:bg-slate-100 hover:text-rose-600"
        aria-label="Đăng xuất"
        title="Đăng xuất"
      >
        <LogOut className="size-4" />
      </button>
    </div>
  )
}
