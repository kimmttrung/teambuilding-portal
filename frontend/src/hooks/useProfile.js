import { useMutation } from '@tanstack/react-query'
import { changePassword, updateProfile, uploadAvatar } from '../api/auth'
import { useAuth } from '../context/AuthContext'

/**
 * Cập nhật hồ sơ. Ba endpoint đều trả về UserSelf đầy đủ, nên đẩy thẳng vào
 * AuthContext thay vì gọi lại /auth/me — sidebar và form thấy dữ liệu mới ngay.
 */
export function useUpdateProfile() {
  const { setUser } = useAuth()

  return useMutation({
    mutationFn: (patch) => updateProfile(patch),
    onSuccess: (user) => setUser(user),
  })
}

export function useUploadAvatar() {
  const { setUser } = useAuth()

  return useMutation({
    mutationFn: (file) => uploadAvatar(file),
    onSuccess: (user) => setUser(user),
  })
}

/**
 * Đổi mật khẩu thu hồi mọi phiên cũ và trả cặp token + hồ sơ mới cho thiết bị này.
 */
export function useChangePassword() {
  const { setUser } = useAuth()

  return useMutation({
    mutationFn: ({ current_password, new_password }) =>
      changePassword(current_password, new_password),
    onSuccess: (data) => setUser(data.user),
  })
}
