import { api } from './client'

/** Toàn bộ lựa chọn cho form đăng ký trong một request. */
export async function fetchRegistrationFormOptions() {
  const { data } = await api.get('/master-data/registration-form')
  return data
}

export async function fetchTeams() {
  const { data } = await api.get('/master-data/teams')
  return data
}

/**
 * CRUD master data. Sáu tài nguyên dùng chung một khuôn endpoint nên gom về một bảng đường dẫn
 * thay vì viết 18 hàm gần giống nhau — thêm loại mới chỉ cần thêm một dòng.
 *
 * `departments` · `work-locations` · `teams` dùng chung cho mọi kỳ.
 * `shifts` · `trip-legs` · `pickup-points` gắn với kỳ đang chọn (backend đọc `X-Event-Id`).
 */
export const MASTER_DATA_PATHS = {
  departments: '/master-data/departments',
  workLocations: '/master-data/work-locations',
  teams: '/master-data/teams',
  shifts: '/master-data/shifts',
  tripLegs: '/master-data/trip-legs',
  pickupPoints: '/master-data/pickup-points',
}

export async function fetchMasterData(resource) {
  const { data } = await api.get(MASTER_DATA_PATHS[resource])
  return data
}

/** `itemId` rỗng = tạo mới. */
export async function saveMasterData(resource, { itemId, payload }) {
  const base = MASTER_DATA_PATHS[resource]
  const { data } = itemId
    ? await api.patch(`${base}/${itemId}`, payload)
    : await api.post(base, payload)
  return data
}

export async function deleteMasterData(resource, itemId) {
  await api.delete(`${MASTER_DATA_PATHS[resource]}/${itemId}`)
}
