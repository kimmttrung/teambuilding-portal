import { REGISTRATION_DRAFT_PREFIX } from '../../../utils/constants'

/**
 * Bản nháp form đăng ký trong localStorage: F5 giữa form không mất dữ liệu đã điền.
 *
 * Khoá gắn cả event và user để máy dùng chung không lẫn nháp của người trước.
 * localStorage có thể ném lỗi (chế độ riêng tư, hết quota) — nháp là tiện lợi,
 * không phải dữ liệu nghiệp vụ, nên lỗi ở đây bị bỏ qua có chủ đích.
 */

/** Không cất giấy tờ và ghi chú sức khoẻ vào localStorage: dữ liệu cá nhân
 *  không nên nằm lại trên máy dùng chung sau khi CBNV đóng trình duyệt. */
const OMITTED_PROFILE_FIELDS = [
  'id_card_number',
  'id_card_issue_date',
  'id_card_issue_place',
  'health_note',
]

export function draftKey(eventId, userId) {
  return `${REGISTRATION_DRAFT_PREFIX}_${eventId}_${userId}`
}

export function loadDraft(key) {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    return parsed?.values ? parsed : null
  } catch {
    return null
  }
}

export function saveDraft(key, values, stepIndex) {
  try {
    const profile = { ...values.profile }
    for (const field of OMITTED_PROFILE_FIELDS) delete profile[field]

    localStorage.setItem(
      key,
      JSON.stringify({ savedAt: new Date().toISOString(), stepIndex, values: { ...values, profile } }),
    )
  } catch {
    // Hết chỗ hoặc bị chặn: bỏ qua, form vẫn chạy bình thường.
  }
}

export function clearDraft(key) {
  try {
    localStorage.removeItem(key)
  } catch {
    // Không xoá được cũng không ảnh hưởng: nháp sẽ bị ghi đè lần sau.
  }
}
