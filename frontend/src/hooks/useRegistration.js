import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchTerms } from '../api/events'
import { fetchRegistrationFormOptions } from '../api/masterData'
import {
  cancelRegistration,
  fetchRegistrations,
  requestCancellation,
  submitRegistration,
  updateRegistration,
  withdrawCancellationRequest,
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

/**
 * Danh sách CBNV xác nhận tham gia (dành cho BTC).
 *
 * Bảng điều chỉnh cần biết ai CHƯA được xếp chỗ, mà `/flight-assignments` chỉ trả người đã
 * xếp — nên phải lấy danh sách tham gia rồi trừ ra. `page_size=200` đủ cho quy mô hiện tại
 * (~120 người); nếu kỳ nào đông hơn thì cần thêm filter "chưa phân bổ" ở backend.
 */
export function useParticipants({ enabled = true } = {}) {
  const filters = { is_participating: true, status: 'submitted', page_size: 200 }
  return useQuery({
    queryKey: QUERY_KEYS.registrations(filters),
    queryFn: () => fetchRegistrations(filters),
    enabled,
  })
}

/**
 * Danh sách đăng ký có lọc + phân trang cho BTC. Giữ trang cũ trên màn hình trong lúc tải
 * trang mới để bảng không nháy trắng mỗi lần đổi bộ lọc.
 */
export function useRegistrationList(params) {
  return useQuery({
    queryKey: QUERY_KEYS.registrations(params),
    queryFn: () => fetchRegistrations(params),
    placeholderData: keepPreviousData,
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

/**
 * Ba mutation huỷ đều trả lại đăng ký mới nhất (kèm `cancel_policy`, `latest_cancellation`) — ghi
 * thẳng vào cache để màn hình đổi ngay; My Journey tải lại vì chỗ đã xếp có thể vừa được gỡ.
 */
function useApplyRegistration() {
  const queryClient = useQueryClient()
  return (registration) => {
    queryClient.setQueryData(QUERY_KEYS.myRegistration, registration)
    queryClient.invalidateQueries({ queryKey: QUERY_KEYS.registrationStats })
    queryClient.invalidateQueries({ queryKey: QUERY_KEYS.journey })
  }
}

/** Tự huỷ — trước khi BTC công bố. */
export function useCancelRegistration() {
  const apply = useApplyRegistration()
  return useMutation({ mutationFn: (reason) => cancelRegistration(reason), onSuccess: apply })
}

/** Gửi yêu cầu huỷ — sau khi BTC công bố, chờ BTC duyệt. */
export function useRequestCancellation() {
  const apply = useApplyRegistration()
  return useMutation({ mutationFn: (reason) => requestCancellation(reason), onSuccess: apply })
}

export function useWithdrawCancellation() {
  const apply = useApplyRegistration()
  return useMutation({ mutationFn: withdrawCancellationRequest, onSuccess: apply })
}
