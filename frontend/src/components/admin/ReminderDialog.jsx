import { useState } from 'react'
import { MailCheck, Send } from 'lucide-react'
import { useReminderPreview, useSendReminders } from '../../hooks/useReminders'
import { useToast } from '../../context/ToastContext'
import { REMINDER_KINDS } from '../../utils/constants'
import { formatDateTime, formatRelative } from '../../utils/format'
import Alert from '../common/Alert'
import Badge from '../common/Badge'
import Button from '../common/Button'
import EmptyState from '../common/EmptyState'
import Modal from '../common/Modal'
import Spinner from '../common/Spinner'

/**
 * Gửi email nhắc việc cho một nhóm CBNV.
 *
 * Luôn xem trước danh sách rồi mới gửi. Người đã được nhắc trong khoảng chờ bị bỏ chọn và
 * khoá sẵn — muốn nhắc lại phải chủ động bật, để không ai nhận hai email giống nhau vì BTC
 * bấm hai lần.
 */
export default function ReminderDialog({ kind, onClose }) {
  const meta = REMINDER_KINDS[kind]
  const toast = useToast()
  const { data: preview, isLoading, error } = useReminderPreview(kind)
  const { mutateAsync, isPending } = useSendReminders(kind)

  const [includeRecent, setIncludeRecent] = useState(false)
  // null = lựa chọn mặc định (mọi người chọn được). Chỉ lưu khi BTC tự tích/bỏ tích.
  const [picked, setPicked] = useState(null)
  const [sendError, setSendError] = useState(null)

  const recipients = preview?.recipients ?? []
  const recentCount = recipients.filter((person) => person.recently_reminded).length
  const selectableIds = new Set(
    recipients
      .filter((person) => includeRecent || !person.recently_reminded)
      .map((person) => person.user_id),
  )
  const selected = picked
    ? new Set([...picked].filter((id) => selectableIds.has(id)))
    : selectableIds
  const canSend = Boolean(preview?.can_send) && selected.size > 0 && !isPending

  function toggle(userId) {
    const next = new Set(selected)
    if (next.has(userId)) next.delete(userId)
    else next.add(userId)
    setPicked(next)
  }

  function toggleAll() {
    setPicked(selected.size === selectableIds.size ? new Set() : new Set(selectableIds))
  }

  async function submit() {
    setSendError(null)
    try {
      const result = await mutateAsync({
        user_ids: [...selected],
        include_recently_reminded: includeRecent,
      })
      toast.success(
        result.email_enabled
          ? `Đã xếp ${result.queued} email vào hàng gửi.`
          : `Đã ghi ${result.queued} email vào nhật ký (đang tắt gửi thật).`,
      )
      onClose()
    } catch (submitError) {
      setSendError(submitError.message)
    }
  }

  return (
    <Modal
      open
      size="lg"
      onClose={onClose}
      title={meta.title}
      description={meta.description}
      footer={
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs text-slate-500">
            {preview ? `Đã chọn ${selected.size}/${recipients.length} người` : ''}
          </p>
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" onClick={onClose}>
              Huỷ
            </Button>
            <Button size="sm" icon={Send} loading={isPending} disabled={!canSend} onClick={submit}>
              Gửi {selected.size} email
            </Button>
          </div>
        </div>
      }
    >
      {isLoading ? (
        <Spinner label="Đang lấy danh sách người nhận…" />
      ) : error ? (
        <Alert tone="error" title="Không lấy được danh sách người nhận">
          {error.message}
        </Alert>
      ) : (
        <div className="flex flex-col gap-3">
          {!preview.can_send && (
            <Alert tone="warning" title="Chưa gửi được lúc này">
              {preview.blocked_reason}
            </Alert>
          )}
          {!preview.email_enabled && (
            <Alert tone="info">
              Đang tắt gửi thật (<code>EMAIL_ENABLED=false</code>): email chỉ được ghi vào nhật ký.
            </Alert>
          )}

          {recipients.length === 0 ? (
            <EmptyState
              icon={MailCheck}
              title="Không còn ai cần nhắc"
              description="Mọi người trong nhóm này đã hoàn tất."
            />
          ) : (
            <>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <button
                  type="button"
                  onClick={toggleAll}
                  disabled={selectableIds.size === 0}
                  className="text-sm font-medium text-brand-700 hover:underline disabled:text-slate-400 disabled:no-underline"
                >
                  {selected.size === selectableIds.size && selectableIds.size > 0 ? 'Bỏ chọn tất cả' : 'Chọn tất cả'}
                </button>
                {recentCount > 0 && (
                  <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-slate-700">
                    <input
                      type="checkbox"
                      className="size-4 accent-brand-600"
                      checked={includeRecent}
                      onChange={(changeEvent) => setIncludeRecent(changeEvent.target.checked)}
                    />
                    Nhắc lại {recentCount} người đã nhắc trong {preview.cooldown_hours} giờ qua
                  </label>
                )}
              </div>

              <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200">
                {recipients.map((person) => {
                  const inputId = `reminder-${kind}-${person.user_id}`
                  const locked = !selectableIds.has(person.user_id)
                  return (
                    <li key={person.user_id} className={`flex items-start gap-3 px-3 py-2.5 ${locked ? 'bg-slate-50' : ''}`}>
                      <input
                        id={inputId}
                        type="checkbox"
                        className="mt-1 size-4 shrink-0 accent-brand-600"
                        checked={selected.has(person.user_id)}
                        disabled={locked}
                        onChange={() => toggle(person.user_id)}
                      />
                      <label htmlFor={inputId} className="min-w-0 flex-1 cursor-pointer">
                        <span className="block text-sm font-medium text-slate-900">{person.full_name}</span>
                        <span className="block truncate text-xs text-slate-500">
                          {[person.employee_code, person.email, person.team_name].filter(Boolean).join(' · ')}
                        </span>
                        {person.missing_fields.length > 0 && (
                          <span className="mt-1 flex flex-wrap gap-1">
                            {person.missing_fields.map((field) => (
                              <Badge key={field} tone="rose">
                                Thiếu {field}
                              </Badge>
                            ))}
                          </span>
                        )}
                      </label>
                      {person.last_reminded_at && (
                        <span title={formatDateTime(person.last_reminded_at)} className="shrink-0">
                          <Badge tone={person.recently_reminded ? 'amber' : 'slate'}>
                            Đã nhắc {formatRelative(person.last_reminded_at)}
                          </Badge>
                        </span>
                      )}
                    </li>
                  )
                })}
              </ul>
            </>
          )}

          {sendError && <Alert tone="error">{sendError}</Alert>}
        </div>
      )}
    </Modal>
  )
}
