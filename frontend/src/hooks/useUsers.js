import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  changeUserRole,
  createUser,
  fetchUser,
  fetchUsers,
  importUsers,
  resetUserPassword,
  setUserStatus,
  unlockUser,
  updateUser,
} from '../api/users'
import { QUERY_KEYS } from '../utils/constants'

export function useUsers(params) {
  return useQuery({
    queryKey: QUERY_KEYS.users(params),
    queryFn: () => fetchUsers(params),
    placeholderData: keepPreviousData,
  })
}

export function useUser(userId, { enabled = true } = {}) {
  return useQuery({
    queryKey: QUERY_KEYS.user(userId),
    queryFn: () => fetchUser(userId),
    enabled: Boolean(userId) && enabled,
  })
}

/**
 * Sửa hồ sơ hay trạng thái CBNV làm cũ cả danh sách đăng ký (tên, giấy tờ) và dashboard
 * (số thiếu giấy tờ) — xoá cache cả ba nhóm.
 */
function useUserInvalidator() {
  const queryClient = useQueryClient()
  return () => {
    queryClient.invalidateQueries({ queryKey: ['users'] })
    queryClient.invalidateQueries({ queryKey: ['registrations'] })
    queryClient.invalidateQueries({ queryKey: ['admin'] })
  }
}

export function useCreateUser() {
  const invalidate = useUserInvalidator()
  return useMutation({ mutationFn: (payload) => createUser(payload), onSuccess: invalidate })
}

export function useUpdateUser() {
  const invalidate = useUserInvalidator()
  return useMutation({
    mutationFn: ({ userId, payload }) => updateUser(userId, payload),
    onSuccess: invalidate,
  })
}

export function useChangeUserRole() {
  const invalidate = useUserInvalidator()
  return useMutation({
    mutationFn: ({ userId, role, reason }) => changeUserRole(userId, { role, reason }),
    onSuccess: invalidate,
  })
}

export function useSetUserStatus() {
  const invalidate = useUserInvalidator()
  return useMutation({
    mutationFn: ({ userId, isActive, reason }) => setUserStatus(userId, { isActive, reason }),
    onSuccess: invalidate,
  })
}

export function useResetUserPassword() {
  const invalidate = useUserInvalidator()
  return useMutation({ mutationFn: (userId) => resetUserPassword(userId), onSuccess: invalidate })
}

/** Chỉ lần ghi thật mới làm cũ cache; kiểm tra thử không đổi gì. */
export function useImportUsers() {
  const invalidate = useUserInvalidator()
  return useMutation({
    mutationFn: ({ file, dryRun }) => importUsers(file, { dryRun }),
    onSuccess: (data) => {
      if (data.committed) invalidate()
    },
  })
}

export function useUnlockUser() {
  const invalidate = useUserInvalidator()
  return useMutation({ mutationFn: (userId) => unlockUser(userId), onSuccess: invalidate })
}
