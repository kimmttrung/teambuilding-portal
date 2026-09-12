import { useRef } from 'react'
import { Camera, Upload } from 'lucide-react'
import { useUploadAvatar } from '../../hooks/useProfile'
import { useToast } from '../../context/ToastContext'
import Avatar from '../common/Avatar'
import Button from '../common/Button'

// Backend chặn ở 2MB (MAX_UPLOAD_MB) và chỉ nhận JPG/PNG/WEBP theo chữ ký file.
// Kiểm tra trước ở client để người dùng không phải chờ upload xong mới biết bị chối.
const MAX_BYTES = 2 * 1024 * 1024
const ACCEPTED = ['image/jpeg', 'image/png', 'image/webp']

/**
 * Đổi ảnh đại diện. Tải lên ngay khi chọn file — ảnh đi qua endpoint riêng
 * (`POST /auth/me/avatar`), không nằm trong form hồ sơ hay form đăng ký.
 */
export default function AvatarUploader({ user, size = 'lg', className = '' }) {
  const fileInputRef = useRef(null)
  const toast = useToast()
  const { mutateAsync: upload, isPending } = useUploadAvatar()

  async function handleFileChange(changeEvent) {
    const file = changeEvent.target.files?.[0]
    // Reset ngay để chọn lại đúng file vừa rồi vẫn kích hoạt onChange.
    changeEvent.target.value = ''
    if (!file) return

    if (!ACCEPTED.includes(file.type)) {
      toast.error('Chỉ chấp nhận ảnh JPG, PNG hoặc WEBP.')
      return
    }
    if (file.size > MAX_BYTES) {
      toast.error('Ảnh vượt quá 2MB. Hãy chọn ảnh nhỏ hơn.')
      return
    }

    try {
      await upload(file)
      toast.success('Đã cập nhật ảnh đại diện.')
    } catch (error) {
      toast.error(error.message)
    }
  }

  return (
    <div className={`flex items-center gap-4 ${className}`}>
      <div className="relative">
        <Avatar user={user} size={size} />
        <span
          className="absolute -right-1 -bottom-1 grid size-7 place-items-center rounded-full
            bg-white text-slate-500 ring-1 ring-slate-200"
          aria-hidden="true"
        >
          <Camera className="size-3.5" />
        </span>
      </div>

      <div className="min-w-0">
        <Button
          type="button"
          variant="secondary"
          size="sm"
          icon={Upload}
          loading={isPending}
          onClick={() => fileInputRef.current?.click()}
        >
          {user?.avatar_url ? 'Đổi ảnh' : 'Tải ảnh lên'}
        </Button>
        <p className="mt-1.5 text-xs text-slate-500">JPG, PNG hoặc WEBP · tối đa 2MB</p>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept={ACCEPTED.join(',')}
        onChange={handleFileChange}
        className="hidden"
        aria-label="Chọn ảnh đại diện"
      />
    </div>
  )
}
