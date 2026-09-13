import { useState } from 'react'
import { useUser } from '../../../hooks/useUsers'
import { useAuth } from '../../../context/AuthContext'
import { ADMIN_ROLES, ROLES, ROLE_LABELS } from '../../../utils/constants'
import Alert from '../../../components/common/Alert'
import Modal from '../../../components/common/Modal'
import Spinner from '../../../components/common/Spinner'
import UserAccountPanel from './UserAccountPanel'
import UserProfileForm from './UserProfileForm'

const TABS = [
  { key: 'profile', label: 'Hồ sơ' },
  { key: 'account', label: 'Tài khoản' },
]

/** Hồ sơ đầy đủ + tài khoản đăng nhập của một CBNV. Chỉ BTC mở được (dữ liệu có CCCD). */
export default function UserDetailModal({ userId, options, onClose }) {
  const { user: me } = useAuth()
  const { data: user, isLoading, error } = useUser(userId)
  const [tab, setTab] = useState('profile')

  // Khớp luật backend: tài khoản Ban tổ chức chỉ quản trị hệ thống sửa được.
  const canManage = user ? !ADMIN_ROLES.includes(user.role) || me?.role === ROLES.SUPER_ADMIN : false

  return (
    <Modal
      open
      size="lg"
      onClose={onClose}
      title={user ? user.full_name : 'Hồ sơ CBNV'}
      description={
        user ? [user.employee_code, user.email, ROLE_LABELS[user.role]].filter(Boolean).join(' · ') : undefined
      }
    >
      {isLoading ? (
        <Spinner label="Đang tải hồ sơ…" />
      ) : error ? (
        <Alert tone="error" title="Không tải được hồ sơ">
          {error.message}
        </Alert>
      ) : (
        <>
          <div role="tablist" aria-label="Hồ sơ CBNV" className="mb-4 flex gap-1 rounded-lg bg-slate-100 p-1">
            {TABS.map((item) => (
              <button
                key={item.key}
                type="button"
                role="tab"
                aria-selected={tab === item.key}
                onClick={() => setTab(item.key)}
                className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition ${
                  tab === item.key ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>

          {tab === 'profile' ? (
            <UserProfileForm key={user.id} user={user} options={options} readOnly={!canManage} />
          ) : (
            <UserAccountPanel key={user.id} user={user} me={me} canManage={canManage} />
          )}
        </>
      )}
    </Modal>
  )
}
