/**
 * Ứng viên Trưởng nhóm: thành viên team đang xác nhận tham gia (danh sách từ `useParticipants`),
 * trừ một người (người đang giữ chức hoặc người đang huỷ). Backend kiểm tra lại đúng luật này.
 */
export function teamLeaderOptions(items = [], teamId, excludeUserId) {
  return items
    .filter((item) => item.user.team_id === teamId && item.user.id !== excludeUserId)
    .map((item) => ({
      value: item.user.id,
      label: [item.user.full_name, item.user.employee_code].filter(Boolean).join(' · '),
    }))
    .sort((a, b) => a.label.localeCompare(b.label, 'vi'))
}
