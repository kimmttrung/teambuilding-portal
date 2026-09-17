import { api } from './client'

/** Gợi ý người theo tên / email / mã NV. Backend bỏ dấu khi so, gõ "nguyen van a" vẫn ra "Nguyễn Văn A". */
export async function searchPeople(q) {
  const { data } = await api.get('/admin/people/search', { params: { q } })
  return data
}

/** Vị trí chính xác của một người: ca, bay đi/về, xe từng chặng, phòng, ghế Gala. */
export async function fetchPersonLocation(userId) {
  const { data } = await api.get(`/admin/people/${userId}/location`)
  return data
}
