import { useState } from 'react'
import { Link } from 'react-router-dom'
import { KeyRound, LockOpen, ShieldCheck, UserCheck, UserX } from 'lucide-react'
import {
  useChangeUserRole,
  useResetUserPassword,
  useSetUserStatus,
  useUnlockUser,
} from '../../../hooks/useUsers'
import { useToast } from '../../../context/ToastContext'
import { ROLE_LABELS, ROLE_TONES, ROLES } from '../../../utils/constants'
import { formatDateTime, formatRelative } from '../../../utils/format'
import Alert from '../../../components/common/Alert'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Input from '../../../components/common/Input'
import Select from '../../../components/common/Select'
import Textarea from '../../../components/common/Textarea'
import TemporaryPasswordNotice from './TemporaryPasswordNotice'

const ROLE_OPTIONS = Object.entries(ROLE_LABELS).map(([value, label]) => ({ value, label }))

/**
 * Tài khoản đăng nhập của một CBNV: khoá/mở, đặt lại mật khẩu, gỡ khoá tạm, đổi vai trò.
 *
 * Nút nào hiện ra khớp đúng luật backend: không tự khoá / tự đặt lại mật khẩu / tự đổi vai trò;
 * tài khoản Ban tổ chức chỉ quản trị hệ thống thao tác được; đổi vai trò chỉ quản trị hệ thống.
 */
export default function UserAccountPanel({ user, me, canManage }) {
  const toast = useToast()
  const { mutateAsync: changeRole, isPending: changingRole } = useChangeUserRole()
  const { mutateAsync: setStatus, isPending: changingStatus } = useSetUserStatus()
  const { mutateAsync: resetPassword, isPending: resetting } = useResetUserPassword()
  const { mutateAsync: unlock, isPending: unlocking } = useUnlockUser()

  const [role, setRole] = useState(user.role)
  const [roleReason, setRoleReason] = useState('')
  const [statusReason, setStatusReason] = useState('')
  const [confirmReset, setConfirmReset] = useState(false)
  const [temporaryPassword, setTemporaryPassword] = useState(null)

  const isSelf = me?.id === user.id
  const isSuperAdmin = me?.role === ROLES.SUPER_ADMIN
  const locked = Boolean(user.locked_until && new Date(user.locked_until) > new Date())

  async function run(action, success) {
    try {
      const result = await action()
      if (success) toast.success(success)
      return result
    } catch (actionError) {
      toast.error(actionError.message)
      return null
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {temporaryPassword && <TemporaryPasswordNotice password={temporaryPassword} email={user.email} />}

      <dl className="grid gap-x-4 gap-y-2.5 text-sm sm:grid-cols-2">
        <Field label="Trạng thái">
          <span className="flex flex-wrap gap-1.5">
            {user.is_active ? <Badge tone="emerald">Đang hoạt động</Badge> : <Badge tone="rose">Đã khoá</Badge>}
            {locked && <Badge tone="amber">Bị khoá tạm đăng nhập</Badge>}
            {user.must_change_password && <Badge tone="slate">Chờ đổi mật khẩu</Badge>}
          </span>
        </Field>
        <Field label="Vai trò">
          <Badge tone={ROLE_TONES[user.role] ?? 'slate'}>{ROLE_LABELS[user.role] ?? user.role}</Badge>
        </Field>
        <Field label="Đăng nhập gần nhất">
          {user.last_login_at ? (
            <span title={formatDateTime(user.last_login_at)}>{formatRelative(user.last_login_at)}</span>
          ) : (
            'Chưa từng đăng nhập'
          )}
        </Field>
        <Field label="Tạo tài khoản">{formatDateTime(user.created_at)}</Field>
      </dl>

      <Link
        to={`/admin/registrations?q=${encodeURIComponent(user.employee_code || user.email)}`}
        className="self-start text-sm font-medium text-brand-700 hover:underline"
      >
        Xem đăng ký của người này
      </Link>

      {!canManage && (
        <Alert tone="info" title="Tài khoản Ban tổ chức">
          Chỉ quản trị hệ thống mới khoá, đặt lại mật khẩu hoặc sửa hồ sơ tài khoản này được.
        </Alert>
      )}
      {canManage && isSelf && (
        <Alert tone="info">Đây là tài khoản của bạn — đổi mật khẩu và hồ sơ ở trang Hồ sơ cá nhân.</Alert>
      )}

      {canManage && locked && (
        <Section icon={LockOpen} title="Đang bị khoá tạm vì nhập sai mật khẩu nhiều lần">
          <p className="text-sm text-slate-600">Tự mở lúc {formatDateTime(user.locked_until)}. Gỡ ngay nếu đã xác minh đúng người.</p>
          <Button
            size="sm"
            variant="secondary"
            icon={LockOpen}
            loading={unlocking}
            onClick={() => run(() => unlock(user.id), 'Đã gỡ khoá đăng nhập.')}
          >
            Gỡ khoá đăng nhập
          </Button>
        </Section>
      )}

      {canManage && !isSelf && (
        <Section icon={KeyRound} title="Đặt lại mật khẩu">
          <p className="text-sm text-slate-600">
            Sinh mật khẩu tạm mới, đăng xuất người này khỏi mọi thiết bị và bắt đổi mật khẩu ở lần đăng nhập tới.
          </p>
          {confirmReset ? (
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant="secondary" onClick={() => setConfirmReset(false)}>
                Huỷ
              </Button>
              <Button
                size="sm"
                icon={KeyRound}
                loading={resetting}
                onClick={async () => {
                  const result = await run(() => resetPassword(user.id), 'Đã đặt lại mật khẩu.')
                  setConfirmReset(false)
                  if (result) setTemporaryPassword(result.temporary_password)
                }}
              >
                Xác nhận đặt lại
              </Button>
            </div>
          ) : (
            <Button size="sm" variant="secondary" icon={KeyRound} onClick={() => setConfirmReset(true)}>
              Đặt lại mật khẩu
            </Button>
          )}
        </Section>
      )}

      {canManage && !isSelf && (
        <Section icon={user.is_active ? UserX : UserCheck} title={user.is_active ? 'Khoá tài khoản' : 'Mở lại tài khoản'}>
          <p className="text-sm text-slate-600">
            {user.is_active
              ? 'Người này không đăng nhập được nữa và bị đăng xuất khỏi mọi thiết bị. Đăng ký và phân bổ vẫn giữ nguyên.'
              : 'Người này đăng nhập lại được bằng mật khẩu hiện có.'}
          </p>
          <Textarea
            label="Lý do"
            required
            rows={2}
            maxLength={500}
            value={statusReason}
            counterValue={statusReason}
            onChange={(changeEvent) => setStatusReason(changeEvent.target.value)}
            hint="Ghi vào nhật ký thay đổi, tối thiểu 3 ký tự"
          />
          <Button
            size="sm"
            variant={user.is_active ? 'danger' : 'primary'}
            icon={user.is_active ? UserX : UserCheck}
            loading={changingStatus}
            disabled={statusReason.trim().length < 3}
            onClick={async () => {
              const result = await run(
                () => setStatus({ userId: user.id, isActive: !user.is_active, reason: statusReason.trim() }),
                user.is_active ? 'Đã khoá tài khoản.' : 'Đã mở lại tài khoản.',
              )
              if (result) setStatusReason('')
            }}
          >
            {user.is_active ? 'Khoá tài khoản' : 'Mở lại tài khoản'}
          </Button>
        </Section>
      )}

      <Section icon={ShieldCheck} title="Vai trò">
        {isSuperAdmin && !isSelf ? (
          <>
            <div className="grid gap-3 sm:grid-cols-2">
              <Select label="Vai trò mới" options={ROLE_OPTIONS} value={role} onChange={(changeEvent) => setRole(changeEvent.target.value)} />
              <Input
                label="Lý do"
                value={roleReason}
                maxLength={500}
                onChange={(changeEvent) => setRoleReason(changeEvent.target.value)}
                placeholder="Ví dụ: trưởng nhóm mới của team"
              />
            </div>
            <Button
              size="sm"
              variant="secondary"
              icon={ShieldCheck}
              loading={changingRole}
              disabled={role === user.role}
              onClick={async () => {
                const result = await run(
                  () => changeRole({ userId: user.id, role, reason: roleReason.trim() }),
                  `Đã đổi vai trò thành ${ROLE_LABELS[role]}.`,
                )
                if (result) setRoleReason('')
              }}
            >
              Đổi vai trò
            </Button>
          </>
        ) : (
          <p className="text-sm text-slate-600">
            {isSelf ? 'Không tự đổi vai trò của chính mình.' : 'Chỉ quản trị hệ thống đổi được vai trò.'}
          </p>
        )}
      </Section>
    </div>
  )
}

function Section({ icon: Icon, title, children }) {
  return (
    <section className="flex flex-col gap-2.5 rounded-lg border border-slate-200 p-3">
      <h3 className="inline-flex items-center gap-1.5 text-sm font-semibold text-slate-900">
        <Icon className="size-4 text-slate-400" aria-hidden="true" />
        {title}
      </h3>
      {children}
    </section>
  )
}

function Field({ label, children }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="mt-0.5 text-slate-900">{children}</dd>
    </div>
  )
}
