import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  BedDouble,
  Bell,
  Bus,
  CalendarDays,
  ChevronDown,
  ClipboardList,
  LayoutDashboard,
  LayoutGrid,
  LogOut,
  Mail,
  Map as MapIcon,
  Menu as MenuIcon,
  MessagesSquare,
  PartyPopper,
  Search,
  Database,
  Settings,
  SlidersHorizontal,
  Megaphone,
  Plane,
  UserCog,
  Users,
  UserRound,
  UserX,
  X,
} from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../context/ToastContext'
import { useActiveEvent, useEventStatusSync } from '../../hooks/useEvent'
import { ROLE_LABELS } from '../../utils/constants'
import Avatar from '../common/Avatar'
import GalaTurnBanner from '../gala/GalaTurnBanner'
import ChatWidget from '../chat/ChatWidget'
import EventSwitcher from './EventSwitcher'
import EventContextBar from './EventContextBar'

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

/**
 * Menu BTC chia nhóm theo thứ tự công việc: chuẩn bị danh sách → phân bổ → liên lạc.
 * Nhóm có `label` thì xổ/gập tại chỗ. Riêng nhóm có `to` (Phân bổ) không xổ: bấm vào mở trang gom
 * các màn hình con, còn `items` chỉ để mục đó sáng và tên tab đúng khi đang ở màn hình con.
 */
const ADMIN_NAV = [
  { items: [{ to: '/admin', label: 'Tổng quan', icon: LayoutDashboard, end: true }] },
  {
    label: 'Người tham gia',
    icon: Users,
    items: [
      { to: '/admin/registrations', label: 'Đăng ký', icon: ClipboardList },
      { to: '/admin/cancellations', label: 'Huỷ đăng ký', icon: UserX },
    ],
  },
  {
    label: 'Phân bổ',
    icon: LayoutGrid,
    to: '/admin/allocation',
    items: [
      { to: '/admin/flights', label: 'Chuyến bay', icon: Plane },
      { to: '/admin/buses', label: 'Xe', icon: Bus },
      { to: '/admin/rooms', label: 'Phòng', icon: BedDouble },
      { to: '/admin/gala', label: 'Gala', icon: PartyPopper },
      { to: '/admin/itinerary', label: 'Lịch trình', icon: CalendarDays },
    ],
  },
  {
    label: 'Liên lạc',
    icon: MessagesSquare,
    items: [
      { to: '/admin/announcements', label: 'Thông báo & email', icon: Megaphone },
      { to: '/admin/email-logs', label: 'Nhật ký email', icon: Mail },
      { to: '/admin/people', label: 'Tra cứu lộ trình', icon: Search },
    ],
  },
  {
    label: 'Thiết lập',
    icon: Settings,
    items: [
      { to: '/admin/settings', label: 'Cấu hình kỳ', icon: SlidersHorizontal },
      { to: '/admin/master-data', label: 'Master data', icon: Database },
      { to: '/admin/users', label: 'Tài khoản & vai trò', icon: UserCog },
    ],
  },
  {
    // BTC/Super Admin cũng là đối tượng đăng ký (tính trong "Tổng nhân sự") —
    // form dùng chung /register-event + /my-journey của CBNV, chỉ thiếu link menu.
    label: 'Tham gia của tôi',
    icon: UserRound,
    items: [
      { to: '/register-event', label: 'Đăng ký của tôi', icon: ClipboardList },
      { to: '/my-journey', label: 'Hành trình của tôi', icon: MapIcon },
    ],
  },
]

// Thanh dưới trên điện thoại chỉ đủ 5 ô: BTC giữ 4 màn hình hay dùng, ô cuối mở menu đầy đủ.
const ADMIN_BOTTOM = ['/admin', '/admin/registrations', '/admin/flights', '/admin/rooms']
const EMPLOYEE_BOTTOM = [
  { to: '/my-journey', label: 'Hành trình', icon: MapIcon },
  { to: '/schedule', label: 'Lịch trình', icon: CalendarDays },
  { to: '/gala', label: 'Gala', icon: PartyPopper },
  { to: '/my-journey?focus=announcements', label: 'Thông báo', icon: Bell },
  { to: '/profile', label: 'Tôi', icon: UserRound },
]

/** Mục menu ứng với URL hiện tại — khớp dài nhất, để `/admin/flights/board` vẫn thuộc "Chuyến bay". */
function findCurrent(items, pathname) {
  return items
    .filter((item) => matchesPath(item.to, pathname))
    .sort((a, b) => b.to.length - a.to.length)[0]
}

function matchesPath(to, pathname) {
  return pathname === to || pathname.startsWith(`${to}/`)
}

/** Đang ở trang gom hoặc một màn hình con của nhóm có trang gom thì trả các màn hình con để làm tab. */
function siblingTabs(groups, pathname) {
  const group = groups.find(
    (item) => item.to && (matchesPath(item.to, pathname) || item.items.some((child) => matchesPath(child.to, pathname))),
  )
  return group?.items ?? []
}

/** Mọi màn hình trong menu, kể cả trang gom của nhóm — dùng cho tên tab và thanh dưới điện thoại. */
function flattenNav(groups) {
  return groups.flatMap((group) =>
    group.to ? [{ to: group.to, label: group.label, icon: group.icon }, ...group.items] : group.items,
  )
}

export default function AppLayout() {
  const { user, isAdmin, logout } = useAuth()
  const { data: activeEvent } = useActiveEvent()
  useEventStatusSync()
  const toast = useToast()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const isRegistrationRoute = pathname.startsWith('/register-event')
  const isScheduleRoute = pathname === '/schedule'

  const groups = isAdmin ? ADMIN_NAV : EMPLOYEE_NAV
  const allItems = flattenNav(groups)
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
      <aside className={`hidden shrink-0 border-r border-hairline bg-canvas md:sticky md:top-0 md:flex md:h-screen md:flex-col ${isAdmin ? 'w-56 lg:w-60' : 'w-60 lg:w-64'}`}>
        <Brand isAdmin={isAdmin} />
        <EventSwitcher />
        <SidebarNav groups={groups} />
        <UserCard user={user} onLogout={handleLogout} />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Thanh trên — chỉ mobile. Menu thả xuống gắn vào thanh nên luôn nằm trong tầm nhìn. */}
        {!isRegistrationRoute && !isScheduleRoute && <div className="sticky top-0 z-30 md:hidden">
          <header className="relative z-10 flex h-14 items-center justify-between border-b border-hairline bg-canvas px-4">
            <Link to="/home" className="flex min-w-0 items-center gap-2.5">
              <span className="grid size-7 shrink-0 place-items-center rounded-md bg-primary text-on-primary">
                <Plane className="size-4" aria-hidden="true" />
              </span>
              <span className="truncate text-body-sm font-semibold text-ink">
                {activeEvent ? `${activeEvent.code} · ${activeEvent.destination || activeEvent.name}` : 'Teambuilding'}
              </span>
            </Link>
            <button
              type="button"
              onClick={() => setMobileMenuOpen((open) => !open)}
              className="grid size-11 place-items-center rounded-full text-ink-secondary hover:bg-black/5"
              aria-label={mobileMenuOpen ? 'Đóng menu' : 'Mở menu'}
              aria-expanded={mobileMenuOpen}
            >
              {mobileMenuOpen ? <X className="size-5" /> : <Avatar user={user} size="sm" className="bg-accent-purple-deep text-white ring-0" />}
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
        </div>}

        <EventContextBar event={activeEvent} tabs={siblingTabs(groups, pathname)} />

        <main className={`mx-auto w-full ${isRegistrationRoute ? 'max-w-[1200px]' : isAdmin ? 'max-w-[1440px]' : 'max-w-[1600px]'} flex-1 px-4 py-4 pb-24 sm:px-6 md:pb-8 lg:px-8 lg:py-6 ${isRegistrationRoute ? 'max-md:px-5 max-md:py-0 max-md:pb-[104px]' : 'max-md:px-4 max-md:py-4 max-md:pb-[88px]'}`}>
          <GalaTurnBanner />
          <Outlet />
        </main>

        {/* Thanh dưới — mobile. CBNV tra cứu bằng một tay ở sân bay. */}
        <nav
          className={`${isRegistrationRoute ? 'hidden' : 'flex'} fixed inset-x-0 bottom-0 z-30 border-t border-hairline bg-canvas pb-[env(safe-area-inset-bottom)] md:hidden`}
          aria-label="Điều hướng nhanh"
        >
          {(isAdmin ? bottomItems : EMPLOYEE_BOTTOM).map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={closeMenu}
              className={({ isActive }) =>
                `flex min-h-[72px] flex-1 flex-col items-center justify-center gap-1 py-2 text-eyebrow transition ${
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
              className={`flex min-h-[72px] flex-1 flex-col items-center justify-center gap-1 py-2 text-eyebrow transition ${
                mobileMenuOpen ? 'text-primary' : 'text-ink-muted'
              }`}
            >
              <MenuIcon className="size-5" aria-hidden="true" />
              Thêm
            </button>
          )}
        </nav>
      </div>

      {pathname !== '/my-journey' && <ChatWidget />}
    </div>
  )
}

function Brand({ compact = false, isAdmin = false }) {
  return (
    <Link to="/home" className={`flex items-center gap-2.5 px-4 ${compact ? 'py-2.5' : 'py-4'}`}>
      <span className="grid size-9 place-items-center rounded-md bg-primary text-on-primary">
        <Plane className="size-5" aria-hidden="true" />
      </span>
      <span className="leading-tight">
        <span className="flex items-center gap-2 text-body-md font-semibold tracking-tight text-ink">
          {isAdmin ? 'Teambuilding' : 'Team Building'}
          {isAdmin && <span className="rounded bg-canvas-soft px-1.5 py-0.5 text-eyebrow font-semibold text-ink-muted">BTC</span>}
        </span>
        {!compact && !isAdmin && <span className="block text-caption text-ink-muted">Cổng thông tin nội bộ</span>}
      </span>
    </Link>
  )
}

const NAV_ROW = 'relative flex w-full items-center gap-3 rounded-sm px-4 py-3 text-left text-body-sm transition'
const NAV_ROW_ACTIVE =
  'bg-canvas-soft font-medium text-ink before:absolute before:inset-y-2 before:left-0 before:w-0.5 before:rounded-full before:bg-primary'
const NAV_ROW_IDLE = 'text-ink-secondary hover:bg-black/5 hover:text-ink'

function SidebarNav({ groups, onNavigate }) {
  const { pathname } = useLocation()
  // Chỉ nhớ nhóm người dùng tự bấm; nhóm chứa trang đang xem thì mặc định mở, không cần effect.
  const [toggled, setToggled] = useState({})

  return (
    <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-3" aria-label="Điều hướng chính">
      {groups.map((group, index) => {
        const hasCurrent = group.items.some((item) => matchesPath(item.to, pathname))

        if (!group.label) {
          return group.items.map((item) => <SidebarLink key={item.to} {...item} onClick={onNavigate} />)
        }

        if (group.to) {
          const active = hasCurrent || matchesPath(group.to, pathname)
          return (
            <Link
              key={group.to}
              to={group.to}
              onClick={onNavigate}
              aria-current={active ? 'page' : undefined}
              className={`${NAV_ROW} ${active ? NAV_ROW_ACTIVE : NAV_ROW_IDLE}`}
            >
              <group.icon className="size-4.5" aria-hidden="true" />
              {group.label}
            </Link>
          )
        }

        const open = toggled[group.label] ?? hasCurrent
        const panelId = `nav-group-${index}`
        return (
          <div key={group.label}>
            <button
              type="button"
              aria-expanded={open}
              aria-controls={panelId}
              onClick={() => setToggled((current) => ({ ...current, [group.label]: !open }))}
              className={`${NAV_ROW} ${hasCurrent && !open ? 'font-medium text-ink' : NAV_ROW_IDLE}`}
            >
              <group.icon className="size-4.5" aria-hidden="true" />
              <span className="min-w-0 flex-1 truncate">{group.label}</span>
              <ChevronDown
                className={`size-4 shrink-0 text-ink-faint transition-transform ${open ? 'rotate-180' : ''}`}
                aria-hidden="true"
              />
            </button>
            {open && (
              <div id={panelId} className="ml-6 space-y-0.5 border-l border-hairline pl-2">
                {group.items.map((item) => (
                  <SidebarLink key={item.to} {...item} onClick={onNavigate} />
                ))}
              </div>
            )}
          </div>
        )
      })}
    </nav>
  )
}

function SidebarLink({ to, label, icon: Icon, end, onClick }) {
  return (
    <NavLink
      to={to}
      end={end}
      onClick={onClick}
      className={({ isActive }) => `${NAV_ROW} ${isActive ? NAV_ROW_ACTIVE : NAV_ROW_IDLE}`}
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
