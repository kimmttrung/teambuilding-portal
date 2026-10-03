import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { KeyRound } from 'lucide-react'
import { useChangePassword } from '../../hooks/useProfile'
import { useToast } from '../../context/ToastContext'
import { changePasswordSchema } from '../../utils/schemas'
import Button from '../common/Button'
import Input from '../common/Input'

/**
 * Ba ô đổi mật khẩu — dùng chung cho thẻ "Bảo mật" ở trang hồ sơ và trang bắt đổi mật khẩu lần đầu,
 * để hai nơi cùng một bộ luật (`changePasswordSchema`) và cùng một câu báo lỗi.
 *
 * `onCancel` có thì hiện nút Huỷ; trang bắt đổi mật khẩu không truyền vì ở đó không có đường lui.
 */
export default function ChangePasswordForm({ currentLabel = 'Mật khẩu hiện tại', submitFullWidth = false, onDone, onCancel }) {
  const toast = useToast()
  const { mutateAsync: changePassword, isPending } = useChangePassword()
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(changePasswordSchema),
    defaultValues: { current_password: '', new_password: '', confirm_password: '' },
  })

  async function onSubmit(values) {
    try {
      await changePassword(values)
      reset()
      toast.success('Đã đổi mật khẩu. Các thiết bị khác đã bị đăng xuất.')
      onDone?.()
    } catch (error) {
      toast.error(error.message)
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
      <Input
        label={currentLabel}
        type="password"
        autoComplete="current-password"
        required
        error={errors.current_password?.message}
        {...register('current_password')}
      />
      <Input
        label="Mật khẩu mới"
        type="password"
        autoComplete="new-password"
        required
        hint="Tối thiểu 8 ký tự, có cả chữ và số"
        error={errors.new_password?.message}
        {...register('new_password')}
      />
      <Input
        label="Nhập lại mật khẩu mới"
        type="password"
        autoComplete="new-password"
        required
        error={errors.confirm_password?.message}
        {...register('confirm_password')}
      />
      <div className="flex flex-wrap gap-2">
        <Button type="submit" icon={KeyRound} loading={isPending} fullWidth={submitFullWidth}>
          Đổi mật khẩu
        </Button>
        {onCancel && (
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              reset()
              onCancel()
            }}
          >
            Huỷ
          </Button>
        )}
      </div>
    </form>
  )
}
