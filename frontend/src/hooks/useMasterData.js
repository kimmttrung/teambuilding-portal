import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  deleteMasterData,
  fetchMasterData,
  saveMasterData,
} from '../api/masterData'
import { QUERY_KEYS } from '../utils/constants'

/**
 * Hook dùng chung cho 6 loại master data (docs/13 task 4).
 *
 * Sáu loại có cùng khuôn endpoint nên dùng chung một hook thay vì 18 hook gần giống nhau — thêm loại
 * mới chỉ cần thêm một dòng vào `MASTER_DATA_PATHS`.
 *
 * Sửa master data làm cũ nhiều thứ khác: form đăng ký đọc ca/chặng/điểm đón, dashboard đếm theo team.
 * Vì vậy mỗi lần ghi đều dọn luôn `formOptions` và các khoá `admin` — rẻ hơn nhiều so với việc để
 * người dùng nhìn danh sách cũ rồi tưởng lưu hỏng.
 */
export function useMasterData(resource, { enabled = true } = {}) {
  return useQuery({
    queryKey: QUERY_KEYS.masterData(resource),
    queryFn: () => fetchMasterData(resource),
    enabled,
  })
}

function useMasterDataSync(resource) {
  const queryClient = useQueryClient()
  return {
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.masterData(resource) })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.formOptions })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.teams })
      queryClient.invalidateQueries({ queryKey: ['admin'] })
    },
  }
}

export function useSaveMasterData(resource) {
  return useMutation({
    mutationFn: (variables) => saveMasterData(resource, variables),
    ...useMasterDataSync(resource),
  })
}

export function useDeleteMasterData(resource) {
  return useMutation({
    mutationFn: (itemId) => deleteMasterData(resource, itemId),
    ...useMasterDataSync(resource),
  })
}
