export const FAKE_USER = {
  id: 1, full_name: 'Nguyễn Văn Trung', display_name: null, avatar_url: null,
  job_title: 'Dev', team: { id: 1, code: 'T1', name: 'Team Alpha', color: '#4f46e5' },
  email: 'trungb001@company.vn', employee_code: 'NV001', role: 'employee',
  phone: '0915409396', personal_email: null, gender: 'male', date_of_birth: '1985-10-07',
  address: null, department_id: 1, work_location_id: 1, join_date: '2020-01-01',
  id_card_number: null, id_card_type: null, id_card_issue_date: null, id_card_issue_place: null,
  shirt_size: null, dietary_restriction: null, health_note: null,
  emergency_contact_name: null, emergency_contact_phone: null,
  must_change_password: false, can_fly: false,
}
export const STUB = `
import { FAKE_USER } from '/.ssr-check/stub-auth.js'
export function AuthProvider({ children }) { return children }
export function useAuth() {
  return {
    user: FAKE_USER, isRestoring: false, isAuthenticated: true, isAdmin: false,
    login: async () => FAKE_USER, logout: async () => {},
    refreshUser: async () => FAKE_USER, setUser: () => {},
  }
}
`
