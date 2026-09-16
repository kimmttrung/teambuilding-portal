import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { Eye, Save } from 'lucide-react'
import { useUpdateEvent } from '../../../hooks/useEvent'
import { useToast } from '../../../context/ToastContext'
import Alert from '../../../components/common/Alert'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import Input from '../../../components/common/Input'
import MarkdownText from '../../../components/common/MarkdownText'
import Textarea from '../../../components/common/Textarea'

/**
 * Quy định chương trình — văn bản CBNV phải cuộn hết rồi tick đồng ý khi đăng ký.
 *
 * Bẫy ở đây là `terms_version`: bản đồng ý CBNV đã ký được lưu kèm số phiên bản. Sửa nội dung mà giữ
 * nguyên version thì chữ ký cũ trỏ tới một văn bản đã khác — backend chặn bằng `TERMS_VERSION_REQUIRED`
 * khi đã có người đồng ý. Màn hình nói trước điều đó thay vì để BTC bấm Lưu rồi mới ăn lỗi.
 */
export default function TermsTab({ event }) {
  const toast = useToast()
  const { mutateAsync: save, isPending } = useUpdateEvent()
  const [preview, setPreview] = useState(false)

  const {
    register,
    handleSubmit,
    reset,
    watch,
    formState: { errors, isDirty },
  } = useForm({
    defaultValues: { terms_version: event.terms_version ?? 'v1', terms_content: event.terms_content ?? '' },
    mode: 'onTouched',
  })

  useEffect(() => {
    reset({ terms_version: event.terms_version ?? 'v1', terms_content: event.terms_content ?? '' })
  }, [event, reset])

  const content = watch('terms_content')
  const versionChanged = watch('terms_version') !== event.terms_version

  async function onSubmit(values) {
    try {
      await save({
        eventId: event.id,
        payload: {
          terms_version: values.terms_version.trim(),
          terms_content: values.terms_content,
        },
      })
      toast.success('Đã lưu quy định chương trình.')
    } catch (error) {
      toast.error(error.message)
    }
  }

  return (
    <Card
      title="Quy định & phí phạt"
      description="CBNV phải cuộn hết văn bản này rồi mới tick đồng ý được"
      action={
        <div className="flex gap-2">
          <Button
            type="button"
            size="sm"
            variant="secondary"
            icon={Eye}
            onClick={() => setPreview((open) => !open)}
          >
            {preview ? 'Soạn thảo' : 'Xem trước'}
          </Button>
          <Button type="submit" form="terms-form" size="sm" icon={Save} loading={isPending} disabled={!isDirty}>
            Lưu quy định
          </Button>
        </div>
      }
    >
      <Alert tone={versionChanged ? 'success' : 'warning'} className="mb-4">
        {versionChanged ? (
          <>Đã đổi phiên bản — bản đồng ý cũ vẫn trỏ đúng văn bản cũ, CBNV sẽ được hỏi đồng ý lại.</>
        ) : (
          <>
            Sửa nội dung thì phải đặt <strong>phiên bản mới</strong> (ví dụ {nextVersion(event.terms_version)}).
            Giữ nguyên phiên bản khi đã có người đồng ý sẽ bị từ chối, vì chữ ký cũ sẽ trỏ tới một văn bản
            đã khác.
          </>
        )}
      </Alert>

      <form id="terms-form" noValidate onSubmit={handleSubmit(onSubmit)} className="grid gap-3.5">
        <div className="sm:max-w-xs">
          <Input
            label="Phiên bản quy định"
            required
            placeholder="v2"
            error={errors.terms_version?.message}
            {...register('terms_version', { required: 'Nhập phiên bản quy định' })}
          />
        </div>

        {preview ? (
          <div className="rounded-lg border border-slate-200 p-4">
            {content?.trim() ? (
              <MarkdownText content={content} />
            ) : (
              <p className="text-sm text-slate-500">Chưa có nội dung quy định.</p>
            )}
          </div>
        ) : (
          <Textarea
            label="Nội dung (markdown)"
            rows={18}
            placeholder="# Quy định chương trình…"
            error={errors.terms_content?.message}
            {...register('terms_content')}
          />
        )}
      </form>
    </Card>
  )
}

/** v1 -> v2. Không đoán nổi thì để BTC tự gõ. */
function nextVersion(current) {
  const match = /^v(\d+)$/.exec(current ?? '')
  return match ? `v${Number(match[1]) + 1}` : 'v2'
}
