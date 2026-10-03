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
    accent: 'sky',
  },
  {
    icon: UserX,
    title: 'Huỷ đăng ký',
    description: 'CBNV tự huỷ trước công bố, gửi yêu cầu sau công bố, BTC duyệt có ghi phạt.',
    accent: 'pink',
  },
  {
    icon: Users,
    title: 'Quản lý CBNV',
    description: 'Tạo tài khoản, đặt lại mật khẩu, khoá/mở, import Excel tất cả-hoặc-không.',
    accent: 'teal',
  },
  {
    icon: Plane,
    title: 'Chuyến bay',
    description: 'CRUD chuyến bay, phân bổ tự động giữ nguyên team, kéo-thả bảng bay.',
    accent: 'sky',
  },
  {
    icon: Bus,
    title: 'Xe đưa đón',
    description: 'Phân xe theo chặng và điểm đón, Trưởng xe xem được hành khách xe mình.',
    accent: 'orange',
  },
  {
    icon: BedDouble,
    title: 'Khách sạn & phòng',
    description: 'Xếp phòng tự động không trộn giới tính, sơ đồ theo tầng, import Excel.',
    accent: 'green',
  },
  {
    icon: PartyPopper,
    title: 'Gala Dinner',
    description: 'Bốc thăm có seed, chọn ghế theo lượt, chốt realtime qua SSE.',
    accent: 'purple',
  },
  {
    icon: CalendarDays,
    title: 'Lịch trình',
    description: 'Mốc thời gian từng ngày, gắn địa điểm bản đồ, hiện trong My Journey.',
    accent: 'teal',
  },
  {
    icon: Mail,
    title: 'Email & nhắc việc',
    description: 'Gửi nhắc thiếu giấy tờ, nhật ký gửi lại thư lỗi, chống gửi trùng 24h.',
    accent: 'brown',
  },
  {
    icon: LayoutDashboard,
    title: 'Tổng quan BTC',
    description: 'Tiến độ bay/xe/phòng, checklist trước công bố, việc cần làm theo giai đoạn.',
    accent: 'purple',
  },
]

const JOURNEY_STEPS = [
  {
    step: '01',
    title: 'Đăng ký 5 bước',
    description:
      'CBNV xác nhận tham gia, chọn ca bay, điểm đón từng chặng và đồng ý quy định — sửa được tới khi BTC đóng đăng ký.',
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

/*
 * Màu icon tile lấy từ bảng sticker của design-notion — chỉ để phân loại/trang trí,
 * không bao giờ tô nút hay nền bố cục (Do's and Don'ts).
 */
const TILES = {
  sky: 'bg-accent-sky/15 text-accent-sky',
  purple: 'bg-accent-purple/40 text-accent-purple-deep',
  pink: 'bg-accent-pink/12 text-accent-pink',
  orange: 'bg-accent-orange/10 text-accent-orange',
  teal: 'bg-accent-teal/12 text-accent-teal',
  green: 'bg-accent-green/12 text-accent-green',
  brown: 'bg-accent-brown/10 text-accent-brown',
}

/** Chấm sao trong dải hero "ban đêm" — sticker-constellation field của skill. */
const STARS = [
  { top: '12%', left: '8%', size: 'size-2', color: 'bg-accent-sky' },
  { top: '22%', left: '46%', size: 'size-1.5', color: 'bg-accent-purple' },
  { top: '70%', left: '5%', size: 'size-1.5', color: 'bg-accent-pink' },
  { top: '84%', left: '40%', size: 'size-2', color: 'bg-accent-teal' },
  { top: '8%', left: '88%', size: 'size-1.5', color: 'bg-accent-orange' },
  { top: '60%', left: '94%', size: 'size-2', color: 'bg-accent-green' },
  { top: '40%', left: '28%', size: 'size-1', color: 'bg-white/70' },
  { top: '54%', left: '60%', size: 'size-1', color: 'bg-white/60' },
  { top: '30%', left: '70%', size: 'size-1', color: 'bg-white/50' },
]

const CONTAINER = 'mx-auto w-full max-w-[1200px] px-4 sm:px-6'

export default function LandingPage() {
  const { isAuthenticated, isRestoring, user } = useAuth()
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    document.title = 'Team Building Portal — Cổng quản lý tập trung'
  }, [])

  const homePath = !isRestoring && isAuthenticated ? (ADMIN_ROLES.includes(user?.role) ? '/home' : '/my-journey') : '/login'
  const ctaLabel = !isRestoring && isAuthenticated ? 'Vào hệ thống' : 'Đăng nhập'

  return (
    <div className="min-h-screen scroll-smooth bg-canvas-soft font-sans text-ink">
      {/* ===== nav-bar: nền canvas, chữ body-sm, dính trên cùng ===== */}
      <header className="sticky top-0 z-50 border-b border-hairline bg-canvas/95 backdrop-blur">
        <div className={`${CONTAINER} flex h-16 items-center justify-between gap-4`}>
          <a href="#top" className="flex items-center gap-2.5">
            <span className="grid size-9 place-items-center rounded-md bg-primary text-on-primary">
              <Plane className="size-5" aria-hidden="true" />
            </span>
            <span className="leading-tight">
              <span className="block text-body-sm font-semibold text-ink">Team Building Portal</span>
              <span className="block text-eyebrow font-normal text-ink-muted">Cổng quản lý tập trung</span>
            </span>
          </a>

          <nav className="hidden items-center gap-1 lg:flex" aria-label="Điều hướng giới thiệu">
            {NAV_LINKS.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className="rounded-sm px-3 py-2 text-body-sm text-ink-secondary transition hover:bg-black/5 hover:text-ink"
              >
                {link.label}
              </a>
            ))}
          </nav>

          <div className="flex items-center gap-2">
            {/* button-utility: nút ở thanh điều hướng, bo 8px, viền hairline */}
            <Link
              to={homePath}
              className="hidden items-center gap-2 rounded-md border border-hairline bg-surface px-3.5 py-1 text-button text-ink transition hover:bg-canvas-soft sm:inline-flex"
            >
              <LogIn className="size-4" aria-hidden="true" />
              {ctaLabel}
            </Link>
            <button
              type="button"
              onClick={() => setMenuOpen((open) => !open)}
              className="grid size-11 place-items-center rounded-full text-ink-secondary hover:bg-black/5 lg:hidden"
              aria-label={menuOpen ? 'Đóng menu' : 'Mở menu'}
              aria-expanded={menuOpen}
            >
              {menuOpen ? <X className="size-5" /> : <MenuIcon className="size-5" />}
            </button>
          </div>
        </div>

        {menuOpen && (
          <nav className="border-t border-hairline bg-canvas px-4 py-3 lg:hidden" aria-label="Điều hướng giới thiệu mobile">
            <div className="flex flex-col gap-1">
              {NAV_LINKS.map((link) => (
                <a
                  key={link.href}
                  href={link.href}
                  onClick={() => setMenuOpen(false)}
                  className="rounded-sm px-3 py-3 text-body-sm text-ink-secondary transition hover:bg-black/5"
                >
                  {link.label}
                </a>
              ))}
              <Link
                to={homePath}
                className="mt-2 inline-flex min-h-11 items-center justify-center gap-2 rounded-full bg-primary px-4 py-2.5 text-button text-on-primary"
              >
                <LogIn className="size-4" aria-hidden="true" />
                {ctaLabel}
              </Link>
            </div>
          </nav>
        )}
      </header>

      {/* ===== hero-band: dải "ban đêm" secondary — mảng tối DUY NHẤT của trang ===== */}
      <section id="top" className="relative overflow-hidden bg-secondary text-on-primary">
        {STARS.map((star) => (
          <span
            key={`${star.top}-${star.left}`}
            className={`pointer-events-none absolute rounded-full ${star.size} ${star.color}`}
            style={{ top: star.top, left: star.left }}
            aria-hidden="true"
          />
        ))}

        <div className={`${CONTAINER} relative grid items-center gap-10 pt-14 pb-14 lg:grid-cols-2 lg:pt-20 lg:pb-20`}>
          <Reveal>
            <p className="inline-flex items-center gap-1.5 rounded-full bg-surface px-2 py-1 text-eyebrow text-primary">
              <Sparkles className="size-3.5" aria-hidden="true" />
              Cổng nội bộ — một nơi duy nhất cho cả kỳ team building
            </p>
            <h1 className="mt-5 text-heading-1 text-balance sm:text-display-2 xl:text-display-1">
              Quản lý team building tập trung, từ đăng ký tới Gala
            </h1>
            <p className="mt-5 max-w-xl text-body-md text-white/80">
              CBNV đăng ký một lần rồi xem toàn bộ hành trình — chuyến bay, xe đưa đón, phòng khách
              sạn, ghế Gala Dinner — trên cùng một màn hình. BTC phân bổ tự động, theo dõi tiến độ
              realtime và được trợ lý ảo Tibi đỡ việc trả lời câu hỏi lặp lại.
            </p>
            {/* Cặp CTA pill: button-primary + button-secondary */}
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link
                to={homePath}
                className="inline-flex min-h-12 items-center gap-2 rounded-full bg-primary px-6 py-2.5 text-button text-on-primary transition hover:bg-primary-active active:scale-[0.97]"
              >
                <LogIn className="size-4" aria-hidden="true" />
                {ctaLabel}
                <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
              <a
                href="#video"
                className="inline-flex min-h-12 items-center gap-2 rounded-full bg-surface px-6 py-2.5 text-button text-ink shadow-soft transition hover:bg-canvas-soft active:scale-[0.97]"
              >
                <Play className="size-4" aria-hidden="true" />
                Xem video demo
              </a>
            </div>
            <dl className="mt-10 grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-4">
              {STATS.map((stat) => (
                <div key={stat.label}>
                  <dt className="sr-only">{stat.label}</dt>
                  <dd className="text-heading-2">{stat.value}</dd>
                  <dd className="mt-1 text-caption text-white/70">{stat.label}</dd>
                </div>
              ))}
            </dl>
          </Reveal>

          <Reveal delay={120}>
            <div className="overflow-hidden rounded-xl bg-surface shadow-elevated">
              <div className="flex items-center gap-1.5 border-b border-hairline px-4 py-2.5">
                <span className="size-2.5 rounded-full bg-accent-pink" />
                <span className="size-2.5 rounded-full bg-accent-orange" />
                <span className="size-2.5 rounded-full bg-accent-green" />
                <span className="ml-2 text-eyebrow font-normal text-ink-muted">video_intro.mp4 — demo sản phẩm</span>
              </div>
              <video controls playsInline preload="metadata" src="/video_intro.mp4" className="aspect-video w-full bg-black">
                Trình duyệt của bạn không phát được video. Mở file{' '}
                <a href="/video_intro.mp4" className="underline">
                  video_intro.mp4
                </a>
                .
              </video>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ===== Dự án này là gì ===== */}
      <section id="gioi-thieu" className="scroll-mt-20">
        <div className={`${CONTAINER} py-16 lg:py-24`}>
          <SectionHeading
            eyebrow="Dự án này là gì"
            title="Ba mảnh ghép của một kỳ team building"
            description="Trước đây danh sách nằm rải rác Excel, email và tin nhắn. Portal gom mọi thứ vào một luồng duy nhất: CBNV cung cấp thông tin → BTC phân bổ → CBNV nhận hành trình."
          />

          <div className="mt-10 grid gap-4 md:grid-cols-3">
            {[
              {
                icon: ClipboardList,
                tile: 'sky',
                title: 'CBNV đăng ký',
                description:
                  'Form 5 bước theo ca bay, nhu cầu xe từng chặng, đồng ý quy định có kiểm tra đã đọc hết. Sửa được tới khi đóng đăng ký.',
              },
              {
                icon: LayoutDashboard,
                tile: 'purple',
                title: 'BTC phân bổ',
                description:
                  'Thuật toán xếp bay giữ nguyên team trong mili-giây, phân xe theo điểm đón, xếp phòng đúng giới tính, bốc thăm ghế Gala có seed.',
              },
              {
                icon: MapIcon,
                tile: 'teal',
                title: 'CBNV xem hành trình',
                description:
                  'Một request duy nhất trả cả chuyến đi. Chưa công bố thì ghi rõ đang chờ gì — không còn cảnh đoán già đoán non.',
              },
            ].map((card, index) => (
              <Reveal key={card.title} delay={index * 90}>
                <FeatureCard icon={card.icon} tile={card.tile} title={card.title} description={card.description} />
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ===== Thành phần quản lý ===== */}
      <section id="tinh-nang" className="scroll-mt-20 border-t border-hairline bg-canvas">
        <div className={`${CONTAINER} py-16 lg:py-24`}>
          <SectionHeading
            eyebrow="Thành phần quản lý"
            title="BTC điều hành cả kỳ trên 10 phân hệ"
            description="Mỗi phân hệ là một màn hình riêng trong sidebar BTC, chia nhóm theo đúng thứ tự công việc: chuẩn bị danh sách trước, phân bổ sau."
          />

          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {MODULES.map((module, index) => (
              <Reveal key={module.title} delay={(index % 3) * 80}>
                <FeatureCard icon={module.icon} tile={module.accent} title={module.title} description={module.description} />
              </Reveal>
            ))}
            <Reveal delay={160}>
              {/* pricing-plan-card-featured: nổi lên bằng nền canvas-soft, không bằng viền màu */}
              <div className="flex h-full flex-col justify-between rounded-lg border border-hairline bg-canvas-soft p-6">
                <div>
                  <span className={`grid size-10 place-items-center rounded-md ${TILES.pink}`}>
                    <BotIcon className="size-5" aria-hidden="true" />
                  </span>
                  <h3 className="mt-4 text-title">Trợ lý Tibi + đa kỳ</h3>
                  <p className="mt-2 text-body-sm text-ink-muted">
                    Chatbot RAG trả lời từ tài liệu công khai, bộ chọn kỳ chạy song song nhiều mùa
                    team building trên cùng một hệ thống.
                  </p>
                </div>
                <Link
                  to={homePath}
                  className="mt-5 inline-flex items-center gap-1.5 text-body-sm font-medium text-primary hover:text-primary-active"
                >
                  Đăng nhập để trải nghiệm <ArrowRight className="size-4" aria-hidden="true" />
                </Link>
              </div>
            </Reveal>
          </div>
        </div>
      </section>

      {/* ===== Video demo ===== */}
      <section id="video" className="scroll-mt-20">
        <div className={`${CONTAINER} py-16 lg:py-24`}>
          <div className="grid items-center gap-10 lg:grid-cols-5">
            <div className="lg:col-span-2">
              <SectionHeading
                eyebrow="Video demo"
                title="Xem portal chạy thật trong vài phút"
                description="Video walkthrough từ màn hình đăng ký của CBNV, các bước phân bổ của BTC cho tới My Journey và đêm Gala — đúng luồng dữ liệu thật của hệ thống."
              />
              <ul className="mt-6 space-y-3 text-body-sm text-ink-secondary">
                {[
                  'Đăng ký 5 bước và trang hồ sơ cá nhân',
                  'Màn hình BTC: bay, xe, phòng, Gala, email',
                  'My Journey: một màn hình cho cả hành trình',
                ].map((line) => (
                  <li key={line} className="flex gap-2.5">
                    <Check className="mt-0.5 size-4 shrink-0 text-accent-green" aria-hidden="true" />
                    {line}
                  </li>
                ))}
              </ul>
            </div>
            <Reveal delay={120} className="lg:col-span-3">
              <div className="overflow-hidden rounded-xl border border-hairline bg-surface shadow-soft">
                <video controls playsInline preload="metadata" src="/video_intro.mp4" className="aspect-video w-full bg-black">
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
      <section id="hanh-trinh" className="scroll-mt-20 border-t border-hairline bg-canvas">
        <div className={`${CONTAINER} py-16 lg:py-24`}>
          <SectionHeading eyebrow="Dịch vụ cho CBNV" title="Từ lúc đăng ký tới đêm Gala: bốn bước" />
          <ol className="mt-10 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {JOURNEY_STEPS.map((item, index) => (
              <Reveal key={item.step} delay={index * 90}>
                <li className="relative h-full overflow-hidden rounded-lg border border-hairline bg-surface p-6">
                  <span
                    className="pointer-events-none absolute -top-1 right-3 text-display-2 text-canvas-soft select-none"
                    aria-hidden="true"
                  >
                    {item.step}
                  </span>
                  <p className="relative text-eyebrow text-primary">BƯỚC {item.step}</p>
                  <h3 className="relative mt-2 text-title">{item.title}</h3>
                  <p className="relative mt-2 text-body-sm text-ink-muted">{item.description}</p>
                </li>
              </Reveal>
            ))}
          </ol>

          {/* Vòng đời kỳ */}
          <Reveal className="mt-10">
            <div className="rounded-lg border border-hairline bg-canvas-soft p-6">
              <div className="flex flex-wrap items-center gap-3">
                <h3 className="text-title">Vòng đời một kỳ</h3>
                <span className="rounded-full bg-surface px-2 py-1 text-eyebrow text-primary ring-1 ring-hairline">
                  BTC chuyển trạng thái có xác nhận, chặn nhảy cóc
                </span>
              </div>
              <ol className="mt-4 flex flex-wrap items-center gap-2">
                {LIFECYCLE.map((stage, index) => (
                  <li key={stage} className="flex items-center gap-2">
                    <span className="rounded-sm border border-hairline bg-surface px-3 py-1.5 text-body-sm font-medium text-ink-secondary">
                      {stage}
                    </span>
                    {index < LIFECYCLE.length - 1 && (
                      <ArrowRight className="size-4 text-ink-faint" aria-hidden="true" />
                    )}
                  </li>
                ))}
              </ol>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ===== Cam kết vận hành ===== */}
      <section>
        <div className={`${CONTAINER} grid gap-4 py-16 md:grid-cols-3 lg:py-20`}>
          {[
            {
              icon: ShieldCheck,
              tile: 'green',
              title: 'Phân quyền 3 lớp',
              description:
                'CBNV chỉ thấy hành trình của mình, Trưởng xe chỉ thấy xe mình phụ trách, tên ghế Gala chỉ BTC và team mình đọc được.',
            },
            {
              icon: Bell,
              tile: 'orange',
              title: 'Không lỡ thông báo',
              description:
                'Email nhắc thiếu giấy tờ, báo lượt chọn ghế Gala, banner lượt chọn hiện trên mọi trang khi tới lượt team bạn.',
            },
            {
              icon: BotIcon,
              tile: 'pink',
              title: 'Tibi trực 24/7',
              description:
                'Hỏi quy định, giờ giấc, địa điểm bất cứ lúc nào. Trích nguồn rõ ràng, từ chối khéo câu hỏi ngoài tài liệu.',
            },
          ].map((card, index) => (
            <Reveal key={card.title} delay={index * 90}>
              <div className="flex h-full gap-4 rounded-lg border border-hairline bg-surface p-6">
                <span className={`grid size-10 shrink-0 place-items-center rounded-md ${TILES[card.tile]}`}>
                  <card.icon className="size-5" aria-hidden="true" />
                </span>
                <div>
                  <h3 className="text-body-md font-semibold">{card.title}</h3>
                  <p className="mt-1.5 text-body-sm text-ink-muted">{card.description}</p>
                </div>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ===== FAQ ===== */}
      <section id="faq" className="scroll-mt-20 border-t border-hairline bg-canvas">
        <div className="mx-auto w-full max-w-3xl px-4 py-16 sm:px-6 lg:py-24">
          <SectionHeading eyebrow="Hỏi đáp" title="Những câu hỏi gặp nhiều nhất" />
          <div className="mt-10 space-y-3">
            {FAQS.map((faq, index) => (
              <Reveal key={faq.q} delay={index * 60}>
                <details className="group rounded-lg border border-hairline bg-surface px-5 py-4 open:shadow-soft">
                  <summary className="cursor-pointer list-none text-body-md font-medium [&::-webkit-details-marker]:hidden">
                    <span className="flex items-center justify-between gap-4">
                      {faq.q}
                      <span className="grid size-7 shrink-0 place-items-center rounded-full bg-black/5 text-ink-muted transition group-open:rotate-45 group-open:bg-primary group-open:text-on-primary">
                        <span className="text-lg leading-none" aria-hidden="true">
                          +
                        </span>
                      </span>
                    </span>
                  </summary>
                  <p className="mt-3 text-body-sm text-ink-muted">{faq.a}</p>
                </details>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ===== CTA — feature-card-elevated trên nền giấy, không thêm mảng tối thứ hai ===== */}
      <section>
        <div className={`${CONTAINER} py-16 lg:py-20`}>
          <Reveal>
            <div className="flex flex-col items-start gap-6 rounded-xl border border-hairline bg-surface p-6 shadow-soft sm:p-10 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <h2 className="text-heading-3 text-balance sm:text-heading-2">
                  Sẵn sàng cho kỳ team building tiếp theo?
                </h2>
                <p className="mt-2 max-w-xl text-body-md text-ink-muted">
                  Đăng nhập bằng tài khoản BTC đã cấp để đăng ký, theo dõi hành trình và nhận thông báo
                  mới nhất của kỳ.
                </p>
              </div>
              <Link
                to={homePath}
                className="inline-flex min-h-12 shrink-0 items-center gap-2 rounded-full bg-primary px-6 py-2.5 text-button text-on-primary transition hover:bg-primary-active active:scale-[0.97]"
              >
                <LogIn className="size-4" aria-hidden="true" />
                {ctaLabel}
                <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ===== footer: nền canvas-soft, chữ caption ink-secondary ===== */}
      <footer className="border-t border-hairline bg-canvas-soft text-ink-secondary">
        <div className={`${CONTAINER} flex flex-col gap-4 py-8 md:flex-row md:items-center md:justify-between`}>
          <div className="flex items-center gap-2.5">
            <span className="grid size-8 place-items-center rounded-md bg-primary text-on-primary">
              <Plane className="size-4" aria-hidden="true" />
            </span>
            <div className="text-caption">
              <p className="font-semibold text-ink">Team Building Portal</p>
              <p>Hệ thống nội bộ. Tài khoản do Ban tổ chức cấp.</p>
            </div>
          </div>
          <p className="text-caption">
            Cần hỗ trợ? Liên hệ BTC qua{' '}
            <a href="mailto:btc@company.vn" className="font-medium text-primary hover:underline">
              btc@company.vn
            </a>
          </p>
        </div>
      </footer>
    </div>
  )
}

/** Tiêu đề mỗi section: badge-pill (eyebrow) + heading-1 + mô tả body-md. */
function SectionHeading({ eyebrow, title, description }) {
  return (
    <Reveal className="max-w-2xl">
      <p className="inline-flex rounded-full bg-surface px-2 py-1 text-eyebrow text-primary ring-1 ring-hairline">
        {eyebrow}
      </p>
      <h2 className="mt-3 text-heading-2 text-balance sm:text-heading-1">{title}</h2>
      {description && <p className="mt-4 text-body-md text-ink-muted">{description}</p>}
    </Reveal>
  )
}

/** feature-card: surface, hairline, rounded-lg, padding lg, phẳng; hover chỉ nhấc nhẹ bằng bóng Level 1. */
function FeatureCard({ icon: Icon, tile, title, description }) {
  return (
    <div className="h-full rounded-lg border border-hairline bg-surface p-6 transition hover:shadow-soft">
      <span className={`grid size-10 place-items-center rounded-md ${TILES[tile] ?? TILES.sky}`}>
        <Icon className="size-5" aria-hidden="true" />
      </span>
      <h3 className="mt-4 text-body-md font-semibold">{title}</h3>
      <p className="mt-2 text-body-sm text-ink-muted">{description}</p>
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
