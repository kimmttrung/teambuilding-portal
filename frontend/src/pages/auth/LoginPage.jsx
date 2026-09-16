import { useEffect, useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import {
  ArrowLeft,
  Bot as BotIcon,
  ClipboardList,
  Eye,
  EyeOff,
  LogIn,
  Map as MapIcon,
  PartyPopper,
  Plane,
  ShieldCheck,
} from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { ADMIN_ROLES } from '../../utils/constants'
import Button from '../../components/common/Button'
import Input from '../../components/common/Input'
import Alert from '../../components/common/Alert'

const schema = z.object({
  email: z.string().min(1, 'Vui lòng nhập email').email('Email không hợp lệ'),
  password: z.string().min(1, 'Vui lòng nhập mật khẩu'),
})

export default function LoginPage() {
  const { login, isAuthenticated, isRestoring } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [serverError, setServerError] = useState(null)
  const [showPassword, setShowPassword] = useState(false)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(schema), defaultValues: { email: '', password: '' } })

  useEffect(() => {
    document.title = 'Đăng nhập · Team Building'
  }, [])

  if (!isRestoring && isAuthenticated) return <Navigate to="/home" replace />

  async function onSubmit({ email, password }) {
    setServerError(null)
    try {
      const user = await login(email, password)
      const target =
        location.state?.from ?? (ADMIN_ROLES.includes(user.role) ? '/admin' : '/my-journey')
      navigate(target, { replace: true })
    } catch (error) {
      setServerError(error)
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-[1.05fr_1fr]">
      {/* Cột giới thiệu — ẩn trên mobile để bàn phím không đẩy form đi */}
      <section className="relative hidden overflow-hidden bg-slate-950 text-white lg:flex lg:flex-col lg:justify-between lg:p-10">
        <div
          className="pointer-events-none absolute inset-0"
          style={{
            backgroundImage:
              'radial-gradient(600px 300px at 15% 10%, rgba(99,102,241,0.35), transparent), radial-gradient(700px 350px at 85% 25%, rgba(34,211,238,0.16), transparent), radial-gradient(500px 300px at 50% 100%, rgba(99,102,241,0.22), transparent)',
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

        <div className="relative flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="grid size-10 place-items-center rounded-xl bg-gradient-to-br from-brand-400 to-brand-700 shadow-lg shadow-brand-900/40">
              <Plane className="size-5" aria-hidden="true" />
            </span>
            <span className="leading-tight">
              <span className="block font-semibold">Team Building Portal</span>
              <span className="block text-xs text-slate-400">Cổng quản lý tập trung</span>
            </span>
          </div>
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 rounded-lg border border-white/15 bg-white/5 px-3 py-1.5 text-xs font-medium text-slate-200 transition hover:bg-white/10 hover:text-white"
          >
            <ArrowLeft className="size-3.5" aria-hidden="true" />
            Trang giới thiệu
          </Link>
        </div>

        <div className="relative max-w-md">
          <h1 className="text-3xl leading-tight font-bold text-balance">
            Một nơi duy nhất cho cả{' '}
            <span className="bg-gradient-to-r from-brand-300 via-cyan-300 to-brand-300 bg-clip-text text-transparent">
              hành trình Team Building
            </span>
          </h1>
          <p className="mt-4 leading-relaxed text-slate-300">
            Đăng ký tham gia, xem chuyến bay, xe đưa đón, phòng khách sạn, chỗ ngồi Gala Dinner và
            lịch trình — tất cả trên cùng một màn hình.
          </p>
          <ul className="mt-7 space-y-3.5 text-sm text-slate-200">
            {[
              {
                icon: ClipboardList,
                text: 'Đăng ký một lần, thông tin tự cập nhật khi BTC điều chỉnh',
              },
              {
                icon: MapIcon,
                text: 'My Journey gom bay, xe, phòng, Gala trong một màn hình',
              },
              {
                icon: BotIcon,
                text: 'Hỏi trợ lý Tibi bất cứ lúc nào về quy định và hành trình',
              },
            ].map((line) => (
              <li key={line.text} className="flex items-center gap-3">
                <span className="grid size-8 shrink-0 place-items-center rounded-lg border border-white/15 bg-white/10">
                  <line.icon className="size-4 text-brand-200" aria-hidden="true" />
                </span>
                {line.text}
              </li>
            ))}
          </ul>

          {/* Thẻ xem trước hành trình */}
          <div className="mt-8 space-y-3" aria-hidden="true">
            <div className="flex items-center gap-3 rounded-2xl border border-white/15 bg-white/5 p-4 backdrop-blur">
              <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-brand-600">
                <Plane className="size-5" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold">VN1234 · HAN → PQC</p>
                <p className="text-xs text-slate-400">06:30 – 08:40 · Ghế 12A · Ca 1 bay sáng</p>
              </div>
              <span className="shrink-0 rounded-full bg-emerald-400/15 px-2.5 py-1 text-[11px] font-semibold text-emerald-300">
                Đã công bố
              </span>
            </div>
            <div className="ml-8 flex items-center gap-3 rounded-2xl border border-white/15 bg-white/5 p-4 backdrop-blur">
              <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-fuchsia-600">
                <PartyPopper className="size-5" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold">Gala Dinner · Bàn B07 — Ghế 3</p>
                <p className="text-xs text-slate-400">Sảnh Pearl · 18:30 đón khách</p>
              </div>
            </div>
          </div>
        </div>

        <p className="relative flex items-center gap-2 text-xs text-slate-400">
          <ShieldCheck className="size-4 text-slate-500" aria-hidden="true" />
          Hệ thống nội bộ. Tài khoản do Ban tổ chức cấp.
        </p>
      </section>

      {/* Cột form */}
      <section className="relative flex items-center justify-center overflow-hidden bg-slate-50 px-5 py-10">
        <div
          className="pointer-events-none absolute inset-0"
          style={{
            backgroundImage:
              'radial-gradient(500px 260px at 50% -5%, rgba(99,102,241,0.14), transparent), radial-gradient(400px 220px at 90% 100%, rgba(34,211,238,0.10), transparent)',
          }}
          aria-hidden="true"
        />
        <div className="relative w-full max-w-sm">
          <div className="mb-6 flex items-center justify-between lg:hidden">
            <div className="flex items-center gap-3">
              <span className="grid size-10 place-items-center rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-md shadow-brand-600/25">
                <Plane className="size-5" aria-hidden="true" />
              </span>
              <span className="leading-tight">
                <span className="block font-semibold text-slate-900">Team Building Portal</span>
                <span className="block text-xs text-slate-500">Cổng quản lý tập trung</span>
              </span>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xl shadow-slate-900/5 sm:p-7">
            <p className="inline-flex items-center gap-1.5 rounded-full bg-brand-50 px-2.5 py-1 text-[11px] font-semibold text-brand-700">
              <span className="size-1.5 rounded-full bg-emerald-500" aria-hidden="true" />
              Hệ thống đang hoạt động
            </p>
            <h2 className="mt-3 text-2xl font-bold text-slate-900">Đăng nhập</h2>
            <p className="mt-1.5 text-sm text-slate-500">
              Dùng email công ty và mật khẩu Ban tổ chức đã cấp.
            </p>

            {serverError && (
              <Alert tone="error" className="mt-5">
                {serverError.message}
                {serverError.code === 'ACCOUNT_LOCKED' && (
                  <p className="mt-1">Thử lại sau 15 phút hoặc liên hệ BTC để mở khoá.</p>
                )}
                {serverError.code === 'TOO_MANY_ATTEMPTS' && (
                  <p className="mt-1">
                    Nếu bạn quên mật khẩu, liên hệ BTC để được cấp lại thay vì thử tiếp.
                  </p>
                )}
              </Alert>
            )}

            <form onSubmit={handleSubmit(onSubmit)} className="mt-6 flex flex-col gap-4" noValidate>
              <Input
                label="Email công ty"
                type="email"
                autoComplete="username"
                placeholder="ten.ban@company.vn"
                required
                error={errors.email?.message}
                {...register('email')}
              />

              <div className="relative">
                <Input
                  label="Mật khẩu"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  placeholder="••••••••"
                  required
                  className="pr-11"
                  error={errors.password?.message}
                  {...register('password')}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((visible) => !visible)}
                  className="absolute top-8.5 right-3 rounded p-1 text-slate-400 hover:text-slate-600"
                  aria-label={showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                >
                  {showPassword ? <EyeOff className="size-4.5" /> : <Eye className="size-4.5" />}
                </button>
              </div>

              <Button type="submit" size="lg" fullWidth loading={isSubmitting} icon={LogIn}>
                Đăng nhập
              </Button>
            </form>

            <p className="mt-5 text-center text-xs leading-relaxed text-slate-500">
              Quên mật khẩu hoặc chưa có tài khoản? Liên hệ Ban tổ chức qua{' '}
              <a href="mailto:btc@company.vn" className="font-medium text-brand-700 hover:underline">
                btc@company.vn
              </a>
            </p>
          </div>

          <Link
            to="/"
            className="mt-5 inline-flex w-full items-center justify-center gap-1.5 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-600 shadow-sm transition hover:bg-slate-100 hover:text-slate-900"
          >
            <ArrowLeft className="size-4" aria-hidden="true" />
            Về trang giới thiệu
          </Link>
        </div>
      </section>
    </div>
  )
}
