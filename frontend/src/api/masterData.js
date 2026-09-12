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
