import { useState } from 'react'
import { Trash2 } from 'lucide-react'
import { useActiveEvent, useDeleteEvent } from '../../hooks/useEvent'
import { useToast } from '../../context/ToastContext'
import Alert from '../common/Alert'
import Button from '../common/Button'
import Input from '../common/Input'
import Modal from '../common/Modal'

/**
 * Xoá một kỳ. Bắt gõ đúng mã kỳ vì thao tác không hoàn tác được.
 * Kỳ mặc định cũng xoá được: còn kỳ khác thì kỳ đó được đặt làm mặc định.
 */
export default function DeleteEventDialog({ event, onClose }) {
  const toast = useToast()
  const { data: current } = useActiveEvent()
  const { mutateAsync, isPending } = useDeleteEvent()
  const [code, setCode] = useState('')
  const matches = code.trim() === event.code

  async function submit() {
    try {
      await mutateAsync({ eventId: event.id, viewing: current?.id === event.id })
      toast.success(`Đã xoá kỳ ${event.code}.`)
      onClose()
    } catch (error) {
      toast.error(error.message)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={`Xoá kỳ ${event.code}`}
      description={
        event.is_active
          ? 'Đây là kỳ mặc định. Nếu còn kỳ khác, kỳ tạo sau cùng sẽ thành kỳ mặc định.'
          : 'Đăng ký, chuyến bay, xe, phòng và lịch trình của kỳ này sẽ mất.'
      }
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="sm" onClick={onClose}>
            Để sau
          </Button>
          <Button size="sm" variant="danger" icon={Trash2} loading={isPending} disabled={!matches} onClick={submit}>
            Xoá kỳ
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-3.5">
        <Alert tone="warning" title="Không hoàn tác được">
          Xoá đăng ký, chuyến bay, xe, phòng, Gala và lịch trình của kỳ này. Tài khoản, phòng ban, địa điểm
          và team vẫn giữ.
        </Alert>
        <Input
          label={`Gõ mã kỳ ${event.code} để xác nhận`}
          value={code}
          onChange={(changeEvent) => setCode(changeEvent.target.value)}
          autoComplete="off"
        />
      </div>
    </Modal>
  )
}
