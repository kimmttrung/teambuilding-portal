import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowRight,
  BedDouble,
  Bell,
  Bot as BotIcon,
  Bus,
  CalendarDays,
  Check,
  ClipboardList,
  LayoutDashboard,
  LogIn,
  Mail,
  Map as MapIcon,
  Menu as MenuIcon,
  PartyPopper,
  Plane,
  Play,
  ShieldCheck,
  Sparkles,
  UserX,
  Users,
  X,
} from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { ADMIN_ROLES } from '../../utils/constants'

const NAV_LINKS = [
  { href: '#gioi-thieu', label: 'Giới thiệu' },
  { href: '#tinh-nang', label: 'Quản lý gì' },
  { href: '#video', label: 'Video demo' },
  { href: '#hanh-trinh', label: 'Hành trình CBNV' },
  { href: '#faq', label: 'Hỏi đáp' },
]

/** 10 phân hệ BTC — khớp menu trong AppLayout. */
const MODULES = [
  {
    icon: ClipboardList,
    title: 'Đăng ký tham gia',
    description: 'Form 5 bước, duyệt danh sách, lọc theo team và trạng thái qua URL.',
    accent: 'bg-brand-50 text-brand-700',
  },
  {
    icon: UserX,
    title: 'Huỷ đăng ký',
    description: 'CBNV tự huỷ trước công bố, gửi yêu cầu sau công bố, BTC duyệt có ghi phạt.',
    accent: 'bg-rose-50 text-rose-600',
  },
  {
    icon: Users,
    title: 'Quản lý CBNV',
    description: 'Tạo tài khoản, đặt lại mật khẩu, khoá/mở, import Excel tất cả-hoặc-không.',
    accent: 'bg-sky-50 text-sky-700',
  },
  {
    icon: Plane,
    title: 'Chuyến bay',
    description: 'CRUD chuyến bay, phân bổ tự động giữ nguyên team, kéo-thả bảng bay.',
    accent: 'bg-indigo-50 text-indigo-700',
  },
  {
    icon: Bus,
    title: 'Xe đưa đón',
    description: 'Phân xe theo chặng và điểm đón, Trưởng xe xem được hành khách xe mình.',
    accent: 'bg-amber-50 text-amber-700',
  },
  {
    icon: BedDouble,
    title: 'Khách sạn & phòng',
    description: 'Xếp phòng tự động không trộn giới tính, sơ đồ theo tầng, import Excel.',
    accent: 'bg-emerald-50 text-emerald-700',
  },
  {
    icon: PartyPopper,
    title: 'Gala Dinner',
    description: 'Bốc thăm có seed, chọn ghế theo lượt, chốt realtime qua SSE.',
    accent: 'bg-fuchsia-50 text-fuchsia-700',
  },
  {
    icon: CalendarDays,
    title: 'Lịch trình',
    description: 'Mốc thời gian từng ngày, gắn địa điểm bản đồ, hiện trong My Journey.',
    accent: 'bg-cyan-50 text-cyan-700',
  },
  {
    icon: Mail,
    title: 'Email & nhắc việc',
    description: 'Gửi nhắc thiếu giấy tờ, nhật ký gửi lại thư lỗi, chống gửi trùng 24h.',
    accent: 'bg-orange-50 text-orange-700',
  },
  {
    icon: LayoutDashboard,
    title: 'Tổng quan BTC',
    description: 'Tiến độ bay/xe/phòng, checklist trước công bố, việc cần làm theo giai đoạn.',
    accent: 'bg-slate-100 text-slate-700',
  },
]

const JOURNEY_STEPS = [
  {
    step: '01',
    title: 'Đăng ký 5 bước',
    description:
      'CBNV xác nhận tham gia, chọn ca bay, điểm đón từng chặng và đồng ý quy định — lưu nháp được, sửa tới khi BTC đóng đăng ký.',
  },
  {
    step: '02',
    title: 'Một màn hình hành trình',
    description:
      'Chuyến bay, xe, phòng, ghế Gala và lịch trình gom trong My Journey. Xuất file .ics, mở Google Maps, bấm gọi Trưởng xe.',
  },
  {
    step: '03',
    title: 'Gala Dinner theo lượt',
    description:
      'Trưởng nhóm bốc thăm thứ tự, chọn ghế cho thành viên trong lượt của team, xác nhận realtime.',
  },
  {
    step: '04',
    title: 'Trợ lý Tibi',
    description:
      'Chatbot trả lời quy định, lịch trình, hậu cần từ tài liệu công khai — kèm nguồn trích dẫn, không chạm dữ liệu cá nhân.',
  },
]

const LIFECYCLE = ['Nháp', 'Mở đăng ký', 'Đóng đăng ký', 'Phân bổ', 'Công bố', 'Diễn ra', 'Kết thúc']

const FAQS = [
  {
    q: 'Tôi lấy tài khoản ở đâu?',
    a: 'Tài khoản do Ban tổ chức cấp và gửi qua email công ty. Đăng nhập lần đầu bằng mật khẩu tạm, hệ thống sẽ yêu cầu đổi ngay. Quên mật khẩu thì liên hệ BTC qua btc@company.vn để được cấp lại.',
  },
  {
    q: 'Đăng ký xong sao chưa thấy chuyến bay, phòng?',
    a: 'BTC cần chạy phân bổ rồi bấm công bố, lúc đó My Journey mới hiện đầy đủ. Trước thời điểm đó màn hình sẽ ghi rõ từng phần đang chờ gì.',
  },
  {
    q: 'Muốn huỷ tham gia thì làm thế nào?',
    a: 'Trước khi công bố, bạn tự huỷ ngay trên trang Đăng ký. Sau công bố, bạn gửi yêu cầu huỷ để BTC duyệt — có thể kèm phí phạt theo quy định. Khi chương trình đã bắt đầu, liên hệ trực tiếp BTC.',
  },
  {
    q: 'Dùng điện thoại ở sân bay có ổn không?',
    a: 'Có. Giao diện ưu tiên mobile: thanh điều hướng dưới đủ 5 màn hình chính, thẻ bay/xe/phòng gọn một tay, số Trưởng xe bấm là gọi được.',
  },
  {
    q: 'Công ty tổ chức nhiều kỳ thì xem kỳ nào?',
    a: 'Bộ chọn kỳ nằm ngay sidebar. Mỗi kỳ có đăng ký, phân bổ và hành trình riêng, đổi kỳ là toàn bộ màn hình tải lại theo kỳ đó.',
  },
]

const STATS = [
  { value: '10', label: 'phân hệ quản lý cho BTC' },
  { value: '5', label: 'bước đăng ký cho CBNV' },
  { value: '7', label: 'giai đoạn vòng đời một kỳ' },
  { value: '1', label: 'màn hình cho cả hành trình' },
]

export default function LandingPage() {
  const { isAuthenticated, isRestoring, user } = useAuth()
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    document.title = 'Team Building Portal — Cổng quản lý tập trung'
  }, [])

  const homePath = !isRestoring && isAuthenticated ? (ADMIN_ROLES.includes(user?.role) ? '/home' : '/my-journey') : '/login'
  const ctaLabel = !isRestoring && isAuthenticated ? 'Vào hệ thống' : 'Đăng nhập'

  return (
    <div className="min-h-screen scroll-smooth bg-white font-sans text-slate-900">
      {/* ===== Taskbar ===== */}
      <header className="sticky top-0 z-50 border-b border-white/10 bg-slate-950/85 backdrop-blur">
        <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
          <a href="#top" className="flex items-center gap-2.5">
            <span className="grid size-9 place-items-center rounded-lg bg-gradient-to-br from-brand-400 to-brand-700 text-white shadow-lg shadow-brand-900/40">
              <Plane className="size-5" aria-hidden="true" />
            </span>
            <span className="leading-tight">
              <span className="block text-sm font-semibold text-white">Team Building Portal</span>
              <span className="block text-[11px] text-slate-400">Cổng quản lý tập trung</span>
            </span>
          </a>

          <nav className="hidden items-center gap-1 lg:flex" aria-label="Điều hướng giới thiệu">
            {NAV_LINKS.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className="rounded-lg px-3 py-2 text-sm text-slate-300 transition hover:bg-white/10 hover:text-white"
              >
                {link.label}
              </a>
            ))}
          </nav>

          <div className="flex items-center gap-2">
            <Link
              to={homePath}
              className="hidden items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-brand-900/40 transition hover:bg-brand-500 sm:inline-flex"
            >
              <LogIn className="size-4" aria-hidden="true" />
              {ctaLabel}
            </Link>
            <button
              type="button"
              onClick={() => setMenuOpen((open) => !open)}
              className="rounded-lg p-2 text-slate-300 hover:bg-white/10 lg:hidden"
              aria-label={menuOpen ? 'Đóng menu' : 'Mở menu'}
              aria-expanded={menuOpen}
            >
              {menuOpen ? <X className="size-5" /> : <MenuIcon className="size-5" />}
            </button>
          </div>
        </div>

        {menuOpen && (
          <nav
            className="border-t border-white/10 px-4 py-3 lg:hidden"
            aria-label="Điều hướng giới thiệu mobile"
          >
            <div className="flex flex-col gap-1">
              {NAV_LINKS.map((link) => (
                <a
                  key={link.href}
                  href={link.href}
                  onClick={() => setMenuOpen(false)}
                  className="rounded-lg px-3 py-2.5 text-sm text-slate-200 transition hover:bg-white/10"
                >
                  {link.label}
                </a>
              ))}
              <Link
                to={homePath}
                className="mt-2 inline-flex items-center justify-center gap-2 rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white"
              >
                <LogIn className="size-4" aria-hidden="true" />
                {ctaLabel}
              </Link>
            </div>
          </nav>
        )}
      </header>

      {/* ===== Hero ===== */}
      <section id="top" className="relative overflow-hidden bg-slate-950 text-white">
        <div
          className="pointer-events-none absolute inset-0"
          style={{
            backgroundImage:
              'radial-gradient(600px 300px at 15% 10%, rgba(99,102,241,0.35), transparent), radial-gradient(700px 350px at 85% 20%, rgba(34,211,238,0.18), transparent), radial-gradient(500px 300px at 50% 100%, rgba(99,102,241,0.22), transparent)',
          }}
          aria-hidden="true"
        />
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.15]"
          style={{
            backgroundImage:
              'linear-gradient(rgba(255,255,255,0.25) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.25) 1px, transparent 1px)',
            backgroundSize: '44px 44px',
            maskImage: 'radial-gradient(ellipse 80% 70% at 50% 30%, black, transparent)',
          }}
          aria-hidden="true"
        />

        <div className="relative mx-auto grid w-full max-w-6xl items-center gap-10 px-4 pt-14 pb-12 sm:px-6 lg:grid-cols-2 lg:pt-20 lg:pb-16">
          <Reveal>
            <p className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3.5 py-1.5 text-xs font-medium text-brand-200">
              <Sparkles className="size-3.5" aria-hidden="true" />
              Cổng nội bộ — một nơi duy nhất cho cả kỳ team building
            </p>
            <h1 className="mt-5 text-4xl leading-[1.15] font-bold text-balance sm:text-5xl">
              Quản lý team building{' '}
              <span className="bg-gradient-to-r from-brand-300 via-cyan-300 to-brand-300 bg-clip-text text-transparent">
                tập trung, từ đăng ký tới Gala
              </span>
            </h1>
            <p className="mt-5 max-w-xl leading-relaxed text-slate-300">
              CBNV đăng ký một lần rồi xem toàn bộ hành trình — chuyến bay, xe đưa đón, phòng khách
              sạn, ghế Gala Dinner — trên cùng một màn hình. BTC phân bổ tự động, theo dõi tiến độ
              realtime và được trợ lý ảo Tibi đỡ việc trả lời câu hỏi lặp lại.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link
                to={homePath}
                className="inline-flex items-center gap-2 rounded-xl bg-brand-600 px-6 py-3 text-sm font-semibold text-white shadow-xl shadow-brand-900/50 transition hover:-translate-y-0.5 hover:bg-brand-500"
              >
                <LogIn className="size-4" aria-hidden="true" />
                {ctaLabel}
                <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
              <a
                href="#video"
                className="inline-flex items-center gap-2 rounded-xl border border-white/20 bg-white/5 px-6 py-3 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-white/10"
              >
                <Play className="size-4" aria-hidden="true" />
                Xem video demo
              </a>
            </div>
            <dl className="mt-10 grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-4">
              {STATS.map((stat) => (
                <div key={stat.label}>
                  <dt className="sr-only">{stat.label}</dt>
                  <dd className="text-3xl font-bold text-white">{stat.value}</dd>
                  <dd className="mt-1 text-xs leading-relaxed text-slate-400">{stat.label}</dd>
                </div>
              ))}
            </dl>
          </Reveal>

          {/* Khung video hero */}
          <Reveal delay={120}>
            <div className="relative">
              <div
                className="absolute -inset-3 rounded-3xl bg-gradient-to-br from-brand-500/40 via-cyan-400/20 to-brand-500/40 blur-2xl"
                aria-hidden="true"
              />
              <div className="relative overflow-hidden rounded-2xl border border-white/15 bg-slate-900 shadow-2xl">
                <div className="flex items-center gap-1.5 border-b border-white/10 px-4 py-2.5">
                  <span className="size-2.5 rounded-full bg-rose-400" />
                  <span className="size-2.5 rounded-full bg-amber-300" />
                  <span className="size-2.5 rounded-full bg-emerald-400" />
                  <span className="ml-2 text-[11px] text-slate-400">video_intro.mp4 — demo sản phẩm</span>
                </div>
                <video
                  controls
                  playsInline
                  preload="metadata"
                  src="/video_intro.mp4"
                  className="aspect-video w-full bg-black"
                >
                  Trình duyệt của bạn không phát được video. Mở file{' '}
                  <a href="/video_intro.mp4" className="underline">
                    video_intro.mp4
                  </a>
                  .
                </video>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ===== Dự án này là gì ===== */}
      <section id="gioi-thieu" className="scroll-mt-20 bg-slate-50">
        <div className="mx-auto w-full max-w-6xl px-4 py-16 sm:px-6 lg:py-20">
          <Reveal className="max-w-2xl">
            <p className="text-xs font-semibold tracking-widest text-brand-600 uppercase">
              Dự án này là gì
            </p>
            <h2 className="mt-2 text-2xl font-bold text-balance sm:text-3xl">
              Ba mảnh ghép của một kỳ team building
            </h2>
            <p className="mt-3 leading-relaxed text-slate-600">
              Trước đây danh sách nằm rải rác Excel, email và tin nhắn. Portal gom mọi thứ vào một
              luồng duy nhất: CBNV cung cấp thông tin → BTC phân bổ → CBNV nhận hành trình.
            </p>
          </Reveal>

          <div className="mt-8 grid gap-4 md:grid-cols-3">
            {[
              {
                icon: ClipboardList,
                title: 'CBNV đăng ký',
                description:
                  'Form 5 bước theo ca bay, nhu cầu xe từng chặng, đồng ý quy định có kiểm tra đã đọc hết. Lưu nháp, sửa tới khi đóng đăng ký.',
              },
              {
                icon: LayoutDashboard,
                title: 'BTC phân bổ',
                description:
                  'Thuật toán xếp bay giữ nguyên team trong mili-giây, phân xe theo điểm đón, xếp phòng đúng giới tính, bốc thăm ghế Gala có seed.',
              },
              {
                icon: MapIcon,
                title: 'CBNV xem hành trình',
                description:
                  'Một request duy nhất trả cả chuyến đi. Chưa công bố thì ghi rõ đang chờ gì — không còn cảnh đoán già đoán non.',
              },
            ].map((card, index) => (
              <Reveal key={card.title} delay={index * 90}>
                <div className="h-full rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition hover:-translate-y-1 hover:shadow-lg">
                  <span className="grid size-11 place-items-center rounded-xl bg-brand-600 text-white shadow-md shadow-brand-600/25">
                    <card.icon className="size-5" aria-hidden="true" />
                  </span>
                  <h3 className="mt-4 font-semibold">{card.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-slate-600">{card.description}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ===== Thành phần quản lý ===== */}
      <section id="tinh-nang" className="scroll-mt-20 bg-white">
        <div className="mx-auto w-full max-w-6xl px-4 py-16 sm:px-6 lg:py-20">
          <Reveal className="max-w-2xl">
            <p className="text-xs font-semibold tracking-widest text-brand-600 uppercase">
              Thành phần quản lý
            </p>
            <h2 className="mt-2 text-2xl font-bold text-balance sm:text-3xl">
              BTC điều hành cả kỳ trên 10 phân hệ
            </h2>
            <p className="mt-3 leading-relaxed text-slate-600">
              Mỗi phân hệ là một màn hình riêng trong sidebar BTC, chia nhóm theo đúng thứ tự công
              việc: chuẩn bị danh sách trước, phân bổ sau.
            </p>
          </Reveal>

          <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {MODULES.map((module, index) => (
              <Reveal key={module.title} delay={(index % 3) * 80}>
                <div className="group h-full rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-1 hover:border-brand-200 hover:shadow-lg">
                  <span
                    className={`grid size-10 place-items-center rounded-xl ${module.accent}`}
                  >
                    <module.icon className="size-5" aria-hidden="true" />
                  </span>
                  <h3 className="mt-3.5 text-[15px] font-semibold">{module.title}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-slate-600">
                    {module.description}
                  </p>
                </div>
              </Reveal>
            ))}
            <Reveal delay={160}>
              <div className="flex h-full flex-col justify-between rounded-2xl bg-slate-950 p-5 text-white shadow-sm">
                <div>
                  <span className="grid size-10 place-items-center rounded-xl bg-white/10">
                    <BotIcon className="size-5" aria-hidden="true" />
                  </span>
                  <h3 className="mt-3.5 text-[15px] font-semibold">Trợ lý Tibi + đa kỳ</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-slate-300">
                    Chatbot RAG trả lời từ tài liệu công khai, bộ chọn kỳ chạy song song nhiều mùa
                    team building trên cùng một hệ thống.
                  </p>
                </div>
                <Link
                  to={homePath}
                  className="mt-4 inline-flex items-center gap-1.5 text-sm font-semibold text-brand-300 hover:text-brand-200"
                >
                  Đăng nhập để trải nghiệm <ArrowRight className="size-4" aria-hidden="true" />
                </Link>
              </div>
            </Reveal>
          </div>
        </div>
      </section>

      {/* ===== Video demo ===== */}
      <section id="video" className="scroll-mt-20 bg-slate-950 text-white">
        <div className="mx-auto w-full max-w-6xl px-4 py-16 sm:px-6 lg:py-20">
          <div className="grid items-center gap-10 lg:grid-cols-5">
            <Reveal className="lg:col-span-2">
              <p className="text-xs font-semibold tracking-widest text-brand-300 uppercase">
                Video demo
              </p>
              <h2 className="mt-2 text-2xl font-bold text-balance sm:text-3xl">
                Xem portal chạy thật trong vài phút
              </h2>
              <p className="mt-3 leading-relaxed text-slate-300">
                Video walkthrough từ màn hình đăng ký của CBNV, các bước phân bổ của BTC cho tới My
                Journey và đêm Gala — đúng luồng dữ liệu thật của hệ thống.
              </p>
              <ul className="mt-5 space-y-2.5 text-sm text-slate-300">
                {[
                  'Đăng ký 5 bước và trang hồ sơ cá nhân',
                  'Màn hình BTC: bay, xe, phòng, Gala, email',
                  'My Journey: một màn hình cho cả hành trình',
                ].map((line) => (
                  <li key={line} className="flex gap-2.5">
                    <Check
                      className="mt-0.5 size-4 shrink-0 text-emerald-400"
                      aria-hidden="true"
                    />
                    {line}
                  </li>
                ))}
              </ul>
            </Reveal>
            <Reveal delay={120} className="lg:col-span-3">
              <div className="overflow-hidden rounded-2xl border border-white/15 shadow-2xl">
                <video
                  controls
                  playsInline
                  preload="metadata"
                  src="/video_intro.mp4"
                  className="aspect-video w-full bg-black"
                >
                  Trình duyệt của bạn không phát được video. Mở file{' '}
                  <a href="/video_intro.mp4" className="underline">
                    video_intro.mp4
                  </a>
                  .
                </video>
              </div>
            </Reveal>
          </div>
        </div>
      </section>

      {/* ===== Hành trình CBNV ===== */}
      <section id="hanh-trinh" className="scroll-mt-20 bg-slate-50">
        <div className="mx-auto w-full max-w-6xl px-4 py-16 sm:px-6 lg:py-20">
          <Reveal className="max-w-2xl">
            <p className="text-xs font-semibold tracking-widest text-brand-600 uppercase">
              Dịch vụ cho CBNV
            </p>
            <h2 className="mt-2 text-2xl font-bold text-balance sm:text-3xl">
              Từ lúc đăng ký tới đêm Gala: bốn bước
            </h2>
          </Reveal>
          <ol className="mt-8 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {JOURNEY_STEPS.map((item, index) => (
              <Reveal key={item.step} delay={index * 90}>
                <li className="relative h-full overflow-hidden rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                  <span
                    className="pointer-events-none absolute -top-2 right-2 text-6xl font-bold text-slate-100 select-none"
                    aria-hidden="true"
                  >
                    {item.step}
                  </span>
                  <p className="text-xs font-bold tracking-widest text-brand-600">
                    BƯỚC {item.step}
                  </p>
                  <h3 className="mt-2 font-semibold">{item.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-slate-600">{item.description}</p>
                </li>
              </Reveal>
            ))}
          </ol>

          {/* Vòng đời kỳ */}
          <Reveal className="mt-10">
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="flex flex-wrap items-center gap-3">
                <h3 className="font-semibold">Vòng đời một kỳ</h3>
                <span className="rounded-full bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-700">
                  BTC chuyển trạng thái có xác nhận, chặn nhảy cóc
                </span>
              </div>
              <ol className="mt-4 flex flex-wrap items-center gap-2">
                {LIFECYCLE.map((stage, index) => (
                  <li key={stage} className="flex items-center gap-2">
                    <span className="rounded-full border border-slate-200 bg-slate-50 px-3.5 py-1.5 text-sm font-medium text-slate-700">
                      {stage}
                    </span>
                    {index < LIFECYCLE.length - 1 && (
                      <ArrowRight className="size-4 text-slate-300" aria-hidden="true" />
                    )}
                  </li>
                ))}
              </ol>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ===== Cam kết vận hành ===== */}
      <section className="bg-white">
        <div className="mx-auto grid w-full max-w-6xl gap-4 px-4 py-14 sm:px-6 md:grid-cols-3 lg:py-16">
          {[
            {
              icon: ShieldCheck,
              title: 'Phân quyền 3 lớp',
              description:
                'CBNV chỉ thấy hành trình của mình, Trưởng xe chỉ thấy xe mình phụ trách, tên ghế Gala chỉ BTC và team mình đọc được.',
            },
            {
              icon: Bell,
              title: 'Không lỡ thông báo',
              description:
                'Email nhắc thiếu giấy tờ, báo lượt chọn ghế Gala, banner lượt chọn hiện trên mọi trang khi tới lượt team bạn.',
            },
            {
              icon: BotIcon,
              title: 'Tibi trực 24/7',
              description:
                'Hỏi quy định, giờ giấc, địa điểm bất cứ lúc nào. Trích nguồn rõ ràng, từ chối khéo câu hỏi ngoài tài liệu.',
            },
          ].map((card, index) => (
            <Reveal key={card.title} delay={index * 90}>
              <div className="flex h-full gap-4 rounded-2xl border border-slate-200 bg-slate-50 p-5">
                <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-brand-600 text-white">
                  <card.icon className="size-5" aria-hidden="true" />
                </span>
                <div>
                  <h3 className="font-semibold">{card.title}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-slate-600">{card.description}</p>
                </div>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ===== FAQ ===== */}
      <section id="faq" className="scroll-mt-20 bg-slate-50">
        <div className="mx-auto w-full max-w-3xl px-4 py-16 sm:px-6 lg:py-20">
          <Reveal>
            <p className="text-xs font-semibold tracking-widest text-brand-600 uppercase">
              Hỏi đáp
            </p>
            <h2 className="mt-2 text-2xl font-bold text-balance sm:text-3xl">
              Những câu hỏi gặp nhiều nhất
            </h2>
          </Reveal>
          <div className="mt-8 space-y-3">
            {FAQS.map((faq, index) => (
              <Reveal key={faq.q} delay={index * 60}>
                <details className="group rounded-2xl border border-slate-200 bg-white px-5 py-4 shadow-sm open:shadow-md">
                  <summary className="cursor-pointer list-none font-medium [&::-webkit-details-marker]:hidden">
                    <span className="flex items-center justify-between gap-4">
                      {faq.q}
                      <span className="grid size-7 shrink-0 place-items-center rounded-full bg-slate-100 text-slate-500 transition group-open:rotate-45 group-open:bg-brand-600 group-open:text-white">
                        <span className="text-lg leading-none" aria-hidden="true">
                          +
                        </span>
                      </span>
                    </span>
                  </summary>
                  <p className="mt-3 text-sm leading-relaxed text-slate-600">{faq.a}</p>
                </details>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ===== CTA ===== */}
      <section className="relative overflow-hidden bg-gradient-to-br from-brand-700 via-brand-600 to-indigo-700 text-white">
        <div
          className="pointer-events-none absolute inset-0 opacity-20"
          style={{
            backgroundImage:
              'radial-gradient(500px 250px at 20% 20%, white, transparent), radial-gradient(500px 250px at 80% 80%, white, transparent)',
          }}
          aria-hidden="true"
        />
        <div className="relative mx-auto flex w-full max-w-6xl flex-col items-start gap-6 px-4 py-14 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:py-16">
          <Reveal>
            <h2 className="text-2xl font-bold text-balance sm:text-3xl">
              Sẵn sàng cho kỳ team building tiếp theo?
            </h2>
            <p className="mt-2 max-w-xl leading-relaxed text-brand-100">
              Đăng nhập bằng tài khoản BTC đã cấp để đăng ký, theo dõi hành trình và nhận thông báo
              mới nhất của kỳ.
            </p>
          </Reveal>
          <Reveal delay={100}>
            <Link
              to={homePath}
              className="inline-flex items-center gap-2 rounded-xl bg-white px-7 py-3.5 text-sm font-bold text-brand-700 shadow-xl transition hover:-translate-y-0.5 hover:shadow-2xl"
            >
              <LogIn className="size-4" aria-hidden="true" />
              {ctaLabel}
              <ArrowRight className="size-4" aria-hidden="true" />
            </Link>
          </Reveal>
        </div>
      </section>

      {/* ===== Footer ===== */}
      <footer className="bg-slate-950 text-slate-400">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-4 px-4 py-8 sm:px-6 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-2.5">
            <span className="grid size-8 place-items-center rounded-lg bg-white/10 text-white">
              <Plane className="size-4" aria-hidden="true" />
            </span>
            <div className="text-sm">
              <p className="font-semibold text-white">Team Building Portal</p>
              <p className="text-xs">Hệ thống nội bộ. Tài khoản do Ban tổ chức cấp.</p>
            </div>
          </div>
          <p className="text-xs">
            Cần hỗ trợ? Liên hệ BTC qua{' '}
            <a
              href="mailto:btc@company.vn"
              className="font-medium text-brand-300 hover:underline"
            >
              btc@company.vn
            </a>
          </p>
        </div>
      </footer>
    </div>
  )
}

/** Hiện dần khi cuộn tới — chỉ animation, nội dung luôn có sẵn cho SEO và SSR. */
function Reveal({ children, delay = 0, className = '' }) {
  const ref = useRef(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const node = ref.current
    if (!node || typeof IntersectionObserver === 'undefined') {
      setVisible(true)
      return
    }
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setVisible(true)
            observer.disconnect()
          }
        }
      },
      { threshold: 0.12 },
    )
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  return (
    <div
      ref={ref}
      style={{ transitionDelay: `${delay}ms` }}
      className={`transition-all duration-700 ease-out ${visible ? 'translate-y-0 opacity-100' : 'translate-y-6 opacity-0'} ${className}`}
    >
      {children}
    </div>
  )
}
