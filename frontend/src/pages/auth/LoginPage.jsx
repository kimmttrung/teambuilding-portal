import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Eye, EyeOff, LogIn, Plane } from 'lucide-react'
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

  if (!isRestoring && isAuthenticated) return <Navigate to="/" replace />

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
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* Cột giới thiệu — ẩn trên mobile để bàn phím không đẩy form đi */}
      <section className="hidden flex-col justify-between bg-brand-700 p-10 text-white lg:flex">
        <div className="flex items-center gap-3">
          <span className="grid size-10 place-items-center rounded-lg bg-white/15">
            <Plane className="size-5" aria-hidden="true" />
          </span>
          <span className="font-semibold">Team Building Portal</span>
        </div>

        <div className="max-w-md">
          <h1 className="text-3xl leading-tight font-bold text-balance">
            Một nơi duy nhất cho cả hành trình Team Building
          </h1>
          <p className="mt-4 leading-relaxed text-brand-100">
            Đăng ký tham gia, xem chuyến bay, xe đưa đón, phòng khách sạn, chỗ ngồi Gala Dinner
            và lịch trình — tất cả trên cùng một màn hình.
          </p>
          <ul className="mt-8 space-y-2.5 text-sm text-brand-100">
            {[
              'Đăng ký một lần, thông tin tự cập nhật khi BTC điều chỉnh',
              'Nhận thông báo khi có thay đổi chuyến bay hoặc lịch trình',
              'Hỏi trợ lý ảo bất cứ lúc nào về quy định và hành trình của bạn',
            ].map((line) => (
              <li key={line} className="flex gap-2.5">
                <span className="mt-2 size-1.5 shrink-0 rounded-full bg-brand-300" />
                {line}
              </li>
            ))}
          </ul>
        </div>

        <p className="text-xs text-brand-200">
          Hệ thống nội bộ. Tài khoản do Ban tổ chức cấp.
        </p>
      </section>

      {/* Cột form */}
      <section className="flex items-center justify-center px-5 py-10">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <span className="grid size-10 place-items-center rounded-lg bg-brand-600 text-white">
              <Plane className="size-5" aria-hidden="true" />
            </span>
            <span className="font-semibold text-slate-900">Team Building Portal</span>
          </div>

          <h2 className="text-2xl font-bold text-slate-900">Đăng nhập</h2>
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

          <p className="mt-6 text-center text-xs leading-relaxed text-slate-500">
            Quên mật khẩu hoặc chưa có tài khoản? Liên hệ Ban tổ chức qua{' '}
            <a href="mailto:btc@company.vn" className="font-medium text-brand-700 hover:underline">
              btc@company.vn
            </a>
          </p>
        </div>
      </section>
    </div>
  )
}
