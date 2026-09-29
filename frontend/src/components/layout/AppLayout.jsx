import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  BedDouble,
  Bus,
  CalendarDays,
  ClipboardList,
  LayoutDashboard,
  LogOut,
  Mail,
  Map as MapIcon,
  Menu as MenuIcon,
  PartyPopper,
  Search,
  Database,
  Settings,
  Megaphone,
  Plane,
  Users,
  UserRound,
  UserX,
  X,
} from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../context/ToastContext'
import { ROLE_LABELS } from '../../utils/constants'
import Avatar from '../common/Avatar'
import GalaTurnBanner from '../gala/GalaTurnBanner'
import ChatWidget from '../chat/ChatWidget'
import EventSwitcher from './EventSwitcher'

const EMPLOYEE_NAV = [
  {
    items: [
      { to: '/my-journey', label: 'Hành trình', icon: MapIcon },
      { to: '/register-event', label: 'Đăng ký', icon: ClipboardList },
      { to: '/schedule', label: 'Lịch trình', icon: CalendarDays },
      { to: '/gala', label: 'Gala', icon: PartyPopper },
      { to: '/profile', label: 'Hồ sơ', icon: UserRound },
    ],
  },
]

/** BTC có 8 màn hình — chia nhóm theo thứ tự công việc: chuẩn bị danh sách → phân bổ. */
const ADMIN_NAV = [
  { items: [{ to: '/admin', label: 'Tổng quan', icon: LayoutDashboard, end: true }] },
  {
    label: 'Đăng ký & CBNV',
    items: [
      { to: '/admin/registrations', label: 'Đăng ký', icon: ClipboardList },
      { to: '/admin/cancellations', label: 'Huỷ đăng ký', icon: UserX },
      { to: '/admin/users', label: 'CBNV', icon: Users },
      { to: '/admin/email-logs', label: 'Email', icon: Mail },
    ],
  },
  {
    label: 'Phân bổ',
    items: [
      { to: '/admin/flights', label: 'Chuyến bay', icon: Plane },
      { to: '/admin/buses', label: 'Xe', icon: Bus },
      { to: '/admin/rooms', label: 'Phòng', icon: BedDouble },
      { to: '/admin/gala', label: 'Gala', icon: PartyPopper },
      { to: '/admin/itinerary', label: 'Lịch trình', icon: CalendarDays },
      { to: '/admin/people', label: 'Tra cứu lộ trình', icon: Search },
      { to: '/admin/announcements', label: 'Thông báo', icon: Megaphone },
    ],
  },
  {
    label: 'Thiết lập',
    items: [
      { to: '/admin/settings', label: 'Cấu hình kỳ', icon: Settings },
      { to: '/admin/master-data', label: 'Master data', icon: Database },
    ],
  },
  {
    // BTC/Super Admin cũng là đối tượng đăng ký (tính trong "Tổng nhân sự") —
    // form dùng chung /register-event + /my-journey của CBNV, chỉ thiếu link menu.
    label: 'Tham gia của tôi',
    items: [
      { to: '/register-event', label: 'Đăng ký của tôi', icon: ClipboardList },
      { to: '/my-journey', label: 'Hành trình của tôi', icon: MapIcon },
    ],
  },
]

// Thanh dưới trên điện thoại chỉ đủ 5 ô: BTC giữ 4 màn hình hay dùng, ô cuối mở menu đầy đủ.
const ADMIN_BOTTOM = ['/admin', '/admin/registrations', '/admin/flights', '/admin/rooms']

/** Mục menu ứng với URL hiện tại — khớp dài nhất, để `/admin/flights/board` vẫn thuộc "Chuyến bay". */
function findCurrent(items, pathname) {
  return items
    .filter((item) => pathname === item.to || pathname.startsWith(`${item.to}/`))
    .sort((a, b) => b.to.length - a.to.length)[0]
}

export default function AppLayout() {
  const { user, isAdmin, logout } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  const groups = isAdmin ? ADMIN_NAV : EMPLOYEE_NAV
  const allItems = groups.flatMap((group) => group.items)
  const bottomItems = isAdmin ? allItems.filter((item) => ADMIN_BOTTOM.includes(item.to)) : allItems
  const currentLabel = findCurrent(allItems, pathname)?.label

  // Tên tab trình duyệt theo màn hình — BTC hay mở nhiều tab song song.
  useEffect(() => {
    document.title = currentLabel ? `${currentLabel} · Team Building` : 'Team Building'
  }, [currentLabel])

  // Đổi trang thì về đầu trang, không giữ vị trí cuộn của trang trước.
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])

  const closeMenu = () => setMobileMenuOpen(false)

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
      <aside className="hidden w-60 shrink-0 border-r border-hairline bg-canvas md:sticky md:top-0 md:flex md:h-screen md:flex-col lg:w-64">
        <Brand />
        <EventSwitcher />
        <SidebarNav groups={groups} />
        <UserCard user={user} onLogout={handleLogout} />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Thanh trên — chỉ mobile. Menu thả xuống gắn vào thanh nên luôn nằm trong tầm nhìn. */}
        <div className="sticky top-0 z-30 md:hidden">
          <header className="relative z-10 flex items-center justify-between border-b border-hairline bg-canvas pr-2">
            <Brand compact />
            <button
              type="button"
              onClick={() => setMobileMenuOpen((open) => !open)}
              className="grid size-11 place-items-center rounded-full text-ink-secondary hover:bg-black/5"
              aria-label={mobileMenuOpen ? 'Đóng menu' : 'Mở menu'}
              aria-expanded={mobileMenuOpen}
            >
              {mobileMenuOpen ? <X className="size-5" /> : <MenuIcon className="size-5" />}
            </button>
          </header>

          {mobileMenuOpen && (
            <>
              <button
                type="button"
                aria-label="Đóng menu"
                onClick={closeMenu}
                className="fixed inset-0 bg-black/30"
              />
              <div className="absolute inset-x-0 top-full z-10 max-h-[calc(100dvh-8rem)] overflow-y-auto border-b border-hairline bg-canvas shadow-elevated">
                <EventSwitcher compact />
                <SidebarNav groups={groups} onNavigate={closeMenu} />
                <UserCard user={user} onLogout={handleLogout} />
              </div>
            </>
          )}
        </div>

        <main className="mx-auto w-full max-w-[1600px] flex-1 px-4 py-4 pb-24 sm:px-6 md:pb-8 lg:px-8 lg:py-6">
          <GalaTurnBanner />
          <Outlet />
        </main>

        {/* Thanh dưới — mobile. CBNV tra cứu bằng một tay ở sân bay. */}
        <nav
          className="fixed inset-x-0 bottom-0 z-30 flex border-t border-hairline bg-canvas pb-[env(safe-area-inset-bottom)] md:hidden"
          aria-label="Điều hướng nhanh"
        >
          {bottomItems.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={closeMenu}
              className={({ isActive }) =>
                `flex min-h-14 flex-1 flex-col items-center justify-center gap-0.5 py-2 text-eyebrow transition ${
                  isActive ? 'text-primary' : 'text-ink-muted'
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
          {isAdmin && (
            <button
              type="button"
              onClick={() => setMobileMenuOpen((open) => !open)}
              aria-expanded={mobileMenuOpen}
              className={`flex min-h-14 flex-1 flex-col items-center justify-center gap-0.5 py-2 text-eyebrow transition ${
                mobileMenuOpen ? 'text-primary' : 'text-ink-muted'
              }`}
            >
              <MenuIcon className="size-5" aria-hidden="true" />
              Thêm
            </button>
          )}
        </nav>
      </div>

      <ChatWidget />
    </div>
  )
}

function Brand({ compact = false }) {
  return (
    <Link to="/home" className={`flex items-center gap-2.5 px-4 ${compact ? 'py-2.5' : 'py-4'}`}>
      <span className="grid size-9 place-items-center rounded-md bg-primary text-on-primary">
        <Plane className="size-5" aria-hidden="true" />
      </span>
      <span className="leading-tight">
        <span className="block text-body-md font-semibold tracking-tight text-ink">Team Building</span>
        {!compact && <span className="block text-caption text-ink-muted">Cổng thông tin nội bộ</span>}
      </span>
    </Link>
  )
}

function SidebarNav({ groups, onNavigate }) {
  return (
    <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-3" aria-label="Điều hướng chính">
      {groups.map((group, index) => (
        <div key={group.label ?? index}>
          {group.label && (
            <p className="px-4 pb-1.5 text-eyebrow text-ink-faint">
              {group.label}
            </p>
          )}
          <div className="space-y-0.5">
            {group.items.map((item) => (
              <SidebarLink key={item.to} {...item} onClick={onNavigate} />
            ))}
          </div>
        </div>
      ))}
    </nav>
  )
}

function SidebarLink({ to, label, icon: Icon, end, onClick }) {
  return (
    <NavLink
      to={to}
      end={end}
      onClick={onClick}
      className={({ isActive }) =>
        `relative flex items-center gap-3 rounded-sm px-4 py-3 text-body-sm transition ${
          isActive
            ? 'bg-canvas-soft font-medium text-ink before:absolute before:inset-y-2 before:left-0 before:w-0.5 before:rounded-full before:bg-primary'
            : 'text-ink-secondary hover:bg-black/5 hover:text-ink'
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
    <div className="flex items-center gap-3 border-t border-hairline p-3">
      <Link to="/profile" className="shrink-0" title="Hồ sơ của tôi">
        <Avatar user={user} size="sm" />
      </Link>
      <div className="min-w-0 flex-1">
        <p className="truncate text-body-sm font-medium text-ink">{user.full_name}</p>
        <p className="truncate text-caption text-ink-muted">
          {ROLE_LABELS[user.role] ?? user.role}
          {user.team ? ` · ${user.team.name}` : ''}
        </p>
      </div>
      <button
        type="button"
        onClick={onLogout}
        className="rounded-full p-2 text-ink-muted transition hover:bg-black/5 hover:text-rose-600"
        aria-label="Đăng xuất"
        title="Đăng xuất"
      >
        <LogOut className="size-4" />
      </button>
    </div>
  )
}
