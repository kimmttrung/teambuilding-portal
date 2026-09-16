import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createAnnouncement,
  deleteAnnouncement,
  fetchAnnouncements,
  fetchRecipientPreview,
  publishAnnouncement,
  unpublishAnnouncement,
  updateAnnouncement,
} from '../api/announcements'
import { QUERY_KEYS } from '../utils/constants'

export function useAnnouncements({ enabled = true } = {}) {
  return useQuery({
    queryKey: QUERY_KEYS.announcements,
    queryFn: fetchAnnouncements,
    enabled,
  })
}

/** Xem trước ai sẽ nhận — chỉ gọi khi đã chọn xong đối tượng. */
export function useRecipientPreview({ targetType, targetId, enabled = true } = {}) {
  const ready = Boolean(targetType) && (targetType === 'all' || Boolean(targetId))
  return useQuery({
    queryKey: QUERY_KEYS.announcementRecipients({ targetType, targetId: targetId ?? null }),
    queryFn: () => fetchRecipientPreview({ targetType, targetId }),
    enabled: enabled && ready,
  })
}

/**
 * Đăng/gỡ đổi cả My Journey của CBNV — xoá cache hành trình luôn để người đang
 * mở app thấy thông báo mới sau tối đa `staleTime`.
 */
function useAnnouncementInvalidator() {
  const queryClient = useQueryClient()
  return () => {
    queryClient.invalidateQueries({ queryKey: ['announcements'] })
    queryClient.invalidateQueries({ queryKey: ['journey'] })
  }
}

export function useSaveAnnouncement() {
  const invalidate = useAnnouncementInvalidator()
  return useMutation({
    mutationFn: ({ itemId, payload }) =>
      (itemId ? updateAnnouncement(itemId, payload) : createAnnouncement(payload)),
    onSuccess: invalidate,
  })
}

export function useDeleteAnnouncement() {
  const invalidate = useAnnouncementInvalidator()
  return useMutation({
    mutationFn: (itemId) => deleteAnnouncement(itemId),
    onSuccess: invalidate,
  })
}

export function usePublishAnnouncement() {
  const invalidate = useAnnouncementInvalidator()
  return useMutation({
    mutationFn: ({ itemId, sendEmail }) => publishAnnouncement(itemId, { sendEmail }),
    onSuccess: invalidate,
  })
}

export function useUnpublishAnnouncement() {
  const invalidate = useAnnouncementInvalidator()
  return useMutation({
    mutationFn: (itemId) => unpublishAnnouncement(itemId),
    onSuccess: invalidate,
  })
}
