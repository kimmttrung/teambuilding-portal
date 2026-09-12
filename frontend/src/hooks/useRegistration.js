import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchTerms } from '../api/events'
import { fetchRegistrationFormOptions } from '../api/masterData'
import {
  cancelRegistration,
  submitRegistration,
  updateRegistration,
} from '../api/registrations'
import { useAuth } from '../context/AuthContext'
import { QUERY_KEYS } from '../utils/constants'

/** Mọi dropdown của form đăng ký trong một request. */
export function useRegistrationFormOptions() {
  return useQuery({
    queryKey: QUERY_KEYS.formOptions,
    queryFn: fetchRegistrationFormOptions,
    // Master data do BTC sửa, rất ít thay đổi trong lúc CBNV đang điền form.
    staleTime: 10 * 60 * 1000,
  })
}

/** Quy định chương trình. Chỉ tải khi mở modal để không kéo nội dung dài vô ích. */
export function useTerms(eventId, { enabled = true } = {}) {
  return useQuery({
    queryKey: QUERY_KEYS.terms(eventId),
    queryFn: () => fetchTerms(eventId),
    enabled: Boolean(eventId) && enabled,
    staleTime: 10 * 60 * 1000,
  })
}

/**
 * Gửi hoặc sửa đăng ký.
 *
 * Một mutation cho cả hai vì form là một: `isEditing` quyết định gọi POST hay PATCH.
 * Cả hai endpoint đều nhận `profile_patch`, nên hồ sơ và đăng ký được ghi trong
 * cùng transaction ở backend — không có trạng thái "sửa hồ sơ xong nhưng đăng ký lỗi".
 */
export function useSaveRegistration({ isEditing = false } = {}) {
  const queryClient = useQueryClient()
  const { refreshUser } = useAuth()

  return useMutation({
    mutationFn: (payload) => (isEditing ? updateRegistration(payload) : submitRegistration(payload)),
    onSuccess: async (registration) => {
      queryClient.setQueryData(QUERY_KEYS.myRegistration, registration)
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.registrationStats })
      // profile_patch có thể đã đổi hồ sơ — đồng bộ lại user đang giữ trong context.
      await refreshUser().catch(() => {})
    },
  })
}

export function useCancelRegistration() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (reason) => cancelRegistration(reason),
    onSuccess: (registration) => {
      queryClient.setQueryData(QUERY_KEYS.myRegistration, registration)
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.registrationStats })
    },
  })
}
