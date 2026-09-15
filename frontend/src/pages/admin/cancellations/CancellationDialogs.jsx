import { useState } from 'react'
import { Ban, CheckCircle2, XCircle } from 'lucide-react'
import { useApproveCancellation, useCancelOnBehalf, useRejectCancellation } from '../../../hooks/useCancellations'
import { useParticipants } from '../../../hooks/useRegistration'
import { useToast } from '../../../context/ToastContext'
import { formatDateTime } from '../../../utils/format'
import Alert from '../../../components/common/Alert'
import Button from '../../../components/common/Button'
import Modal from '../../../components/common/Modal'
import Select from '../../../components/common/Select'
import Spinner from '../../../components/common/Spinner'
import Textarea from '../../../components/common/Textarea'

const MIN_TEXT = 3

// Nhắc lại đúng câu trong quy định CBNV đã đồng ý — BTC quyết theo đó.
const PENALTY_RULE =
  'Huỷ sau hạn đăng ký: CBNV chịu chi phí vé máy bay và phòng đã đặt, trừ bất khả kháng có xác nhận của quản lý trực tiếp.'

const RELEASE_WARNING =
  'Hệ thống gỡ vé máy bay, xe, phòng, ghế Gala và vai trò Trưởng xe (nếu có) của người này, rồi email báo CBNV. Không hoàn tác được — cần đi lại thì CBNV phải đăng ký và được xếp lại.'

function Person({ item }) {
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 rounded-lg bg-slate-50 px-3 py-2.5 text-sm">
      <dt className="text-slate-500">CBNV</dt>
      <dd className="font-medium text-slate-900">
        {item.user.full_name}
        {item.user.employee_code && <span className="font-normal text-slate-500"> · {item.user.employee_code}</span>}
      </dd>
      <dt className="text-slate-500">Team</dt>
      <dd className="text-slate-700">{item.user.team_name ?? 'Chưa gán team'}</dd>
      <dt className="text-slate-500">Gửi lúc</dt>
      <dd className="text-slate-700">
        {formatDateTime(item.requested_at)} · {item.event_status_label}
      </dd>
      <dt className="text-slate-500">Lý do</dt>
      <dd className="text-slate-900">“{item.reason}”</dd>
    </dl>
  )
}

function PenaltyFields({ applied, note, afterDeadline, onApplied, onNote }) {
  return (
    <div className="flex flex-col gap-2.5 rounded-lg border border-slate-200 px-3 py-2.5">
      <label className="flex cursor-pointer items-start gap-2.5 text-sm text-slate-800">
        <input
          type="checkbox"
          className="mt-0.5 size-4 accent-brand-600"
          checked={applied}
          onChange={(changeEvent) => onApplied(changeEvent.target.checked)}
        />
        <span>
          <span className="font-medium">Áp dụng phí phạt</span>
          <span className="block text-xs text-slate-500">
            {afterDeadline ? 'Người này huỷ sau hạn đăng ký. ' : 'Người này huỷ trong hạn đăng ký. '}
            {PENALTY_RULE}
          </span>
        </span>
      </label>
      {applied && (
        <Textarea
          label="Mức phí / ghi chú phí phạt"
          rows={2}
          maxLength={512}
          counterValue={note}
          value={note}
          onChange={(changeEvent) => onNote(changeEvent.target.value)}
          placeholder="Ví dụ: chịu vé máy bay chiều đi và 2 đêm phòng"
        />
      )}
    </div>
  )
}

/** Duyệt yêu cầu huỷ: BTC quyết phí phạt, hệ thống gỡ mọi chỗ đã xếp. */
export function ApproveCancellationDialog({ item, onClose }) {
  const toast = useToast()
  const { mutateAsync, isPending } = useApproveCancellation()
  const [penalty, setPenalty] = useState(item.after_deadline)
  const [penaltyNote, setPenaltyNote] = useState('')
  const [decisionNote, setDecisionNote] = useState('')

  async function submit() {
    try {
      await mutateAsync({
        id: item.id,
        penalty_applied: penalty,
        penalty_note: penalty ? penaltyNote.trim() || null : null,
        decision_note: decisionNote.trim() || null,
      })
      toast.success(`Đã duyệt huỷ đăng ký của ${item.user.full_name}. Chỗ đã được giải phóng.`)
      onClose()
    } catch (error) {
      toast.error(error.message)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Duyệt huỷ đăng ký?"
      description="CBNV nhận email kết quả kèm quyết định phí phạt"
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="sm" onClick={onClose}>
            Để sau
          </Button>
          <Button variant="danger" size="sm" icon={CheckCircle2} loading={isPending} onClick={submit}>
            Duyệt huỷ
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-3.5">
        <Person item={item} />
        <Alert tone="warning" title="Không hoàn tác được">
          {RELEASE_WARNING}
        </Alert>
        <PenaltyFields
          applied={penalty}
          note={penaltyNote}
          afterDeadline={item.after_deadline}
          onApplied={setPenalty}
          onNote={setPenaltyNote}
        />
        <Textarea
          label="Ghi chú gửi CBNV"
          rows={2}
          maxLength={1000}
          counterValue={decisionNote}
          value={decisionNote}
          onChange={(changeEvent) => setDecisionNote(changeEvent.target.value)}
          hint="Không bắt buộc. Hiện trong email kết quả."
        />
      </div>
    </Modal>
  )
}

/** Từ chối: đăng ký giữ nguyên, bắt buộc nêu lý do để CBNV hiểu vì sao vẫn phải đi. */
export function RejectCancellationDialog({ item, onClose }) {
  const toast = useToast()
  const { mutateAsync, isPending } = useRejectCancellation()
  const [note, setNote] = useState('')

  async function submit() {
    try {
      await mutateAsync({ id: item.id, decisionNote: note.trim() })
      toast.success(`Đã từ chối yêu cầu huỷ của ${item.user.full_name}.`)
      onClose()
    } catch (error) {
      toast.error(error.message)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Từ chối yêu cầu huỷ?"
      description="Đăng ký và mọi chỗ đã xếp giữ nguyên"
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="sm" onClick={onClose}>
            Để sau
          </Button>
          <Button
            size="sm"
            icon={XCircle}
            loading={isPending}
            disabled={note.trim().length < MIN_TEXT}
            onClick={submit}
          >
            Từ chối
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-3.5">
        <Person item={item} />
        <Textarea
          label="Lý do từ chối"
          required
          rows={3}
          maxLength={1000}
          counterValue={note}
          value={note}
          onChange={(changeEvent) => setNote(changeEvent.target.value)}
          placeholder="Ví dụ: vé đã xuất và không hoàn được, vui lòng liên hệ BTC để trao đổi"
          hint="Bắt buộc — gửi kèm email cho CBNV."
        />
      </div>
    </Modal>
  )
}

/**
 * BTC huỷ thay CBNV: trường hợp ngoại lệ (chương trình đã bắt đầu, CBNV báo qua điện thoại…).
 * Chỉ liệt kê người đang xác nhận tham gia — họ mới có vé, xe, phòng cần gỡ.
 */
export function CancelOnBehalfDialog({ onClose }) {
  const toast = useToast()
  const { data, isLoading } = useParticipants()
  const { mutateAsync, isPending } = useCancelOnBehalf()
  const [registrationId, setRegistrationId] = useState('')
  const [reason, setReason] = useState('')
  const [penalty, setPenalty] = useState(false)
  const [penaltyNote, setPenaltyNote] = useState('')

  const people = (data?.items ?? [])
    .map((item) => ({
      value: item.id,
      label: [item.user.full_name, item.user.employee_code, item.user.team_name].filter(Boolean).join(' · '),
    }))
    .sort((a, b) => a.label.localeCompare(b.label, 'vi'))

  async function submit() {
    try {
      const result = await mutateAsync({
        registration_id: Number(registrationId),
        reason: reason.trim(),
        penalty_applied: penalty,
        penalty_note: penalty ? penaltyNote.trim() || null : null,
      })
      toast.success(`Đã huỷ đăng ký của ${result.user.full_name}.`)
      onClose()
    } catch (error) {
      toast.error(error.message)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Huỷ đăng ký thay CBNV"
      description="Dùng cho trường hợp ngoại lệ — ghi nhật ký và email báo CBNV"
      size="lg"
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="sm" onClick={onClose}>
            Để sau
          </Button>
          <Button
            variant="danger"
            size="sm"
            icon={Ban}
            loading={isPending}
            disabled={!registrationId || reason.trim().length < MIN_TEXT}
            onClick={submit}
          >
            Huỷ đăng ký
          </Button>
        </div>
      }
    >
      {isLoading ? (
        <Spinner label="Đang tải danh sách người tham gia…" />
      ) : (
        <div className="flex flex-col gap-3.5">
          <Select
            label="Người tham gia"
            required
            placeholder="Chọn CBNV"
            value={registrationId}
            onChange={(changeEvent) => setRegistrationId(changeEvent.target.value)}
            options={people}
          />
          <Textarea
            label="Lý do"
            required
            rows={3}
            maxLength={512}
            counterValue={reason}
            value={reason}
            onChange={(changeEvent) => setReason(changeEvent.target.value)}
            placeholder="Ví dụ: nhập viện ngày 15/10, có giấy xác nhận"
          />
          <Alert tone="warning" title="Không hoàn tác được">
            {RELEASE_WARNING}
          </Alert>
          <PenaltyFields
            applied={penalty}
            note={penaltyNote}
            afterDeadline={false}
            onApplied={setPenalty}
            onNote={setPenaltyNote}
          />
        </div>
      )}
    </Modal>
  )
}
