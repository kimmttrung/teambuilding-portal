import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { CheckCircle2, Eye, History, Save } from 'lucide-react'
import { useChooseTermsVersion, useTermsVersions, useUpdateEvent } from '../../../hooks/useEvent'
import { useToast } from '../../../context/ToastContext'
import { formatFullDateTime } from '../../../utils/format'
import Alert from '../../../components/common/Alert'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import Input from '../../../components/common/Input'
import MarkdownText from '../../../components/common/MarkdownText'
import Modal from '../../../components/common/Modal'
import Textarea from '../../../components/common/Textarea'

/**
 * Quy định chương trình — văn bản CBNV phải cuộn hết rồi tick đồng ý khi đăng ký.
 *
 * Bẫy ở đây là `terms_version`: bản đồng ý CBNV đã ký được lưu kèm số phiên bản. Sửa nội dung mà giữ
 * nguyên version thì chữ ký cũ trỏ tới một văn bản đã khác — backend chặn bằng `TERMS_VERSION_REQUIRED`
 * khi đã có người đồng ý. Màn hình nói trước điều đó thay vì để BTC bấm Lưu rồi mới ăn lỗi.
 */
export default function TermsTab({ event, locked = false }) {
  const toast = useToast()
  const { mutateAsync: save, isPending } = useUpdateEvent()
  const { data: versions } = useTermsVersions(event.id)
  const { mutateAsync: choose, isPending: choosing } = useChooseTermsVersion(event.id)
  const [preview, setPreview] = useState(false)
  const [viewing, setViewing] = useState(null)

  const {
    register,
    handleSubmit,
    reset,
    watch,
    formState: { errors, isDirty },
  } = useForm({
    defaultValues: { terms_version: event.terms_version ?? 'v1', terms_content: '' },
    mode: 'onTouched',
  })

  // Nội dung quy định KHÔNG nằm trong `/events/active` (để response đó nhẹ) — lấy từ danh sách phiên
  // bản. Trước đây đọc `event.terms_content` (luôn undefined) nên ô soạn thảo trống sau mỗi lần tải.
  const current = versions?.find((item) => item.is_current)
  const loaded = Boolean(current)
  const currentVersion = current?.version ?? event.terms_version ?? 'v1'
  const currentContent = current?.content ?? ''

  useEffect(() => {
    reset({ terms_version: currentVersion, terms_content: currentContent })
  }, [currentVersion, currentContent, reset])

  const content = watch('terms_content')
  const versionChanged = watch('terms_version') !== currentVersion

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

  async function onChoose(item) {
    const message =
      `Dùng lại quy định bản ${item.version} cho chương trình?\n\n` +
      `Bản ${currentVersion} đang dùng sẽ chuyển xuống danh sách các bản trước (không mất). ` +
      'CBNV đăng ký từ giờ sẽ đọc và đồng ý bản được chọn.'
    if (!window.confirm(message)) return
    try {
      await choose(item.version)
      toast.success(`Chương trình giờ dùng quy định bản ${item.version}.`)
    } catch (error) {
      toast.error(error.message)
    }
  }

  return (
    <div className="grid gap-4">
      <Card
        title="Quy định & phí phạt"
        description={`Chương trình đang dùng bản ${currentVersion}. CBNV phải cuộn hết văn bản này rồi mới tick đồng ý được`}
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
            {!locked && (
              <Button type="submit" form="terms-form" size="sm" icon={Save} loading={isPending} disabled={!isDirty}>
                Lưu quy định
              </Button>
            )}
          </div>
        }
      >
        {!locked && (
          <Alert tone={versionChanged ? 'success' : 'warning'} className="mb-4">
            {versionChanged ? (
              <>Đã đổi phiên bản — bản đồng ý cũ vẫn trỏ đúng văn bản cũ, CBNV sẽ được hỏi đồng ý lại.</>
            ) : (
              <>
                Sửa nội dung thì phải đặt <strong>phiên bản mới</strong> (ví dụ {nextVersion(currentVersion)}).
                Giữ nguyên phiên bản khi đã có người đồng ý sẽ bị từ chối, vì chữ ký cũ sẽ trỏ tới một văn bản
                đã khác.
              </>
            )}
          </Alert>
        )}

        <form id="terms-form" noValidate onSubmit={handleSubmit(onSubmit)}>
          {/* Chưa tải xong nội dung thì khoá ô nhập: lưu lúc này là ghi đè quy định bằng ô trống. */}
          <fieldset disabled={locked || !loaded} className="grid gap-3.5">
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
          </fieldset>
        </form>
      </Card>

      {versions?.length > 0 && (
        <Card
          title="Các phiên bản quy định"
          description="Bản đang dùng và các bản đã bị thay — giữ lại để đối chiếu với phiên bản CBNV đã đồng ý"
          bodyClassName="p-0"
        >
          <ul className="divide-y divide-hairline">
            {versions.map((item) => (
              <li key={item.version} className="flex flex-wrap items-center gap-3 px-4 py-3">
                <History className="size-4 shrink-0 text-ink-muted" aria-hidden="true" />
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center gap-2 text-body-sm font-medium text-ink">
                    Bản {item.version}
                    {item.is_current && <Badge tone="green">Đang dùng</Badge>}
                  </p>
                  <p className="text-body-sm text-ink-muted">
                    {item.is_current
                      ? 'Bản CBNV đọc và đồng ý khi đăng ký'
                      : `Thay lúc ${formatFullDateTime(item.replaced_at)}`}{' '}
                    · {item.consent_count} người đã đồng ý bản này
                  </p>
                </div>
                <div className="flex shrink-0 gap-1">
                  <Button size="sm" variant="ghost" icon={Eye} onClick={() => setViewing(item)}>
                    Xem nội dung
                  </Button>
                  {!item.is_current && !locked && (
                    <Button
                      size="sm"
                      variant="secondary"
                      icon={CheckCircle2}
                      disabled={choosing}
                      onClick={() => onChoose(item)}
                    >
                      Dùng bản này
                    </Button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {viewing && (
        <Modal
          open
          size="lg"
          onClose={() => setViewing(null)}
          title={`Quy định – bản ${viewing.version}`}
          description={
            viewing.is_current
              ? 'Bản đang dùng'
              : `Chỉ xem. Đã thay lúc ${formatFullDateTime(viewing.replaced_at)}`
          }
        >
          {viewing.content.trim() ? (
            <MarkdownText content={viewing.content} />
          ) : (
            <p className="text-body-sm text-ink-muted">Bản này chưa có nội dung.</p>
          )}
        </Modal>
      )}
    </div>
  )
}

/** v1 -> v2. Không đoán nổi thì để BTC tự gõ. */
function nextVersion(current) {
  const match = /^v(\d+)$/.exec(current ?? '')
  return match ? `v${Number(match[1]) + 1}` : 'v2'
}
