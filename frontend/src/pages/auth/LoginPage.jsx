import { useEffect, useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { ArrowLeft, LockKeyhole, Ticket } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { ADMIN_ROLES } from '../../utils/constants'
import Button from '../../components/common/Button'
import Input from '../../components/common/Input'
import ticket from '../../components/profile/assets/login-ticket.svg'
import gala from '../../components/profile/assets/login-gala.svg'
import tibi from '../../components/profile/assets/tibi.png'
import '../../components/profile/F1Surface.css'

const schema = z.object({
  email: z.string().trim().min(1, 'Vui lòng nhập email').email('Email không hợp lệ'),
  password: z.string().min(1, 'Vui lòng nhập mật khẩu'),
})

export default function LoginPage() {
  const { login, isAuthenticated, isRestoring } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [serverError, setServerError] = useState(null)
  const [showPassword, setShowPassword] = useState(false)
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm({
    resolver: zodResolver(schema), defaultValues: { email: '', password: '' },
  })

  useEffect(() => { document.title = 'Đăng nhập · Team Building' }, [])

  if (!isRestoring && isAuthenticated) return <Navigate to="/home" replace />

  async function onSubmit({ email, password }) {
    setServerError(null)
    try {
      const user = await login(email, password)
      const target = user.must_change_password ? '/profile' :
        location.state?.from ?? (ADMIN_ROLES.includes(user.role) ? '/admin' : '/my-journey')
      navigate(target, { replace: true })
    } catch (error) { setServerError(error) }
  }

  const locked = ['ACCOUNT_LOCKED', 'TOO_MANY_ATTEMPTS'].includes(serverError?.code)

  return (
    <div className="f1-surface f1-login">
      <section className="f1-login-hero">
        <Link to="/" className="f1-login-brand flex items-center gap-2.5 text-base font-bold">
          <span className="grid size-[30px] place-items-center rounded-md bg-primary text-on-primary">
            <Ticket className="size-4" aria-hidden="true" />
          </span>
          Teambuilding
        </Link>
        <p className="mb-4 text-xs font-semibold leading-[18px] text-ink-muted">Cổng Team Building nội bộ</p>
        <h1 className="max-w-[640px] text-[64px] leading-[64px] font-bold tracking-[-2.125px]">
          Một tấm vé<br />cho cả chuyến đi.
        </h1>
        <p className="mt-6 max-w-[480px] text-[18px] leading-[26px] text-ink-muted">
          Chuyến bay, xe, phòng, ghế Gala và lịch trình của bạn<br className="hidden xl:block" />
          {' '}— ở cùng một chỗ, cập nhật ngay khi BTC thay đổi.
        </p>
        <div className="f1-login-art" aria-hidden="true">
          <img src={ticket} alt="" className="f1-login-ticket" />
          <img src={gala} alt="" className="f1-login-gala" />
          <img src={tibi} alt="" className="f1-login-tibi" />
        </div>
      </section>

      <section className="f1-login-right">
        <div className="f1-login-form">
          <Link to="/" aria-label="Về trang giới thiệu" className="mb-7 inline-flex size-8 items-center lg:hidden">
            <ArrowLeft className="size-[18px]" />
          </Link>
          <h2 className="text-[30px] leading-[38px] font-bold tracking-[-0.625px] lg:text-[26px]">Đăng nhập</h2>
          <p className="mt-1 text-[15px] leading-[22px] text-ink-muted">
            <span className="hidden lg:inline">Dùng tài khoản công ty của bạn.</span>
            <span className="lg:hidden">Email công ty và mật khẩu được BTC cấp.</span>
          </p>

          <form onSubmit={handleSubmit(onSubmit)} className="mt-7 flex flex-col gap-4" noValidate>
            <Input label="Email công ty" type="email" autoComplete="username" placeholder="ten.ban@congty.vn"
              error={errors.email?.message} {...register('email')} />
            <div className="relative">
              <Input label="Mật khẩu" type={showPassword ? 'text' : 'password'} autoComplete="current-password"
                placeholder="••••••••" className="pr-16" error={errors.password?.message || (!locked ? serverError?.message : undefined)}
                {...register('password')} />
              <button type="button" onClick={() => setShowPassword((value) => !value)}
                aria-label={showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                className="absolute top-[30px] right-2 min-h-10 px-1.5 text-[13px] text-ink-muted lg:opacity-0 lg:focus:opacity-100 lg:hover:opacity-100">
                {showPassword ? 'Ẩn' : 'Hiện'}
              </button>
            </div>
            <Button type="submit" fullWidth loading={isSubmitting} className="f1-login-submit mt-2 font-medium">Đăng nhập</Button>
          </form>
          <p className="mt-4 hidden text-[13px] text-ink-faint lg:block">Sai 5 lần liên tiếp sẽ tạm khoá 15 phút.</p>
          <p className="mt-4 text-center text-caption text-ink-muted lg:text-left">Quên mật khẩu? Liên hệ Ban tổ chức để được đặt lại.</p>
          {locked && <div role="alert" className="mt-8 flex gap-3 rounded-lg bg-rose-50 p-4 text-caption text-rose-700">
            <LockKeyhole className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            <div>{serverError.message}<p className="mt-1">Thử lại sau 15 phút hoặc liên hệ BTC để mở khoá.</p></div>
          </div>}
        </div>
      </section>
    </div>
  )
}
