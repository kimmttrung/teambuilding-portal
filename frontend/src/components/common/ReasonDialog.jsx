import { useId } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { moveReasonSchema } from '../../utils/schemas'
import { REASON_DIALOG_LABELS } from '../../utils/constants'
import Alert from './Alert'
import Button from './Button'
import Modal from './Modal'
import Textarea from './Textarea'

/** Xác nhận thao tác cần lý do; lỗi server giữ ngay trong form, không làm mất nội dung. */
export default function ReasonDialog({
  title,
  description,
  children,
  confirmLabel,
  onConfirm,
  onClose,
  pending = false,
}) {
  const formId = useId()
  const {
    register,
    handleSubmit,
    control,
    setError,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: zodResolver(moveReasonSchema),
    defaultValues: { reason: '' },
    mode: 'onTouched',
  })
  const reason = useWatch({ control, name: 'reason' })
  async function submit(values) {
    try {
      await onConfirm(values.reason)
    } catch (error) {
      setError('root', { message: error.message })
    }
  }
  return (
    <Modal
      open
      onClose={onClose}
      title={title}
      description={description}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            {REASON_DIALOG_LABELS.cancel}
          </Button>
          <Button
            variant="danger"
            type="submit"
            form={formId}
            loading={pending || isSubmitting}
          >
            {confirmLabel}
          </Button>
        </div>
      }
    >
      <form
        id={formId}
        onSubmit={handleSubmit(submit)}
        className="flex flex-col gap-4"
        noValidate
      >
        {children}
        {errors.root && <Alert tone="error">{errors.root.message}</Alert>}
        <Textarea
          label={REASON_DIALOG_LABELS.reason}
          required
          rows={3}
          maxLength={500}
          counterValue={reason}
          error={errors.reason?.message}
          hint="Lưu vào nhật ký thay đổi, tối thiểu 3 ký tự"
          {...register('reason')}
        />
      </form>
    </Modal>
  )
}
