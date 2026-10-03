import { useEffect, useState } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useRecipientPreview, useSaveAnnouncement } from '../../../hooks/useAnnouncements'
import { useBuses } from '../../../hooks/useBuses'
import { useFlights } from '../../../hooks/useFlights'
import { useRegistrationFormOptions } from '../../../hooks/useRegistration'
import { useUsers } from '../../../hooks/useUsers'
import { useToast } from '../../../context/ToastContext'
import { ANNOUNCEMENT_SEVERITY_META, ANNOUNCEMENT_TARGET_LABELS } from '../../../utils/constants'
import { formatShortDateTime } from '../../../utils/format'
import { announcementSchema } from '../../../utils/schemas'
import { ERROR_CLASS, LABEL_CLASS } from '../../../components/common/fieldStyles'
import Input from '../../../components/common/Input'
import MarkdownText from '../../../components/common/MarkdownText'
import SearchBox from '../../../components/common/SearchBox'
import Select from '../../../components/common/Select'
import Spinner from '../../../components/common/Spinner'
import Textarea from '../../../components/common/Textarea'

const EMPTY = {
  title: '',
  content: '',
  severity: 'info',
  target_type: 'all',
  target_id: '',
}

/**
 * Ô soạn thông báo (Figma v2 · B11), dùng chung cho thẻ "Thông báo mới" trên trang và hộp thoại sửa.
 * Đối tượng cụ thể lấy từ dữ liệu thật (team, chuyến, xe, CBNV) để không gửi nhầm — backend vẫn chặn
 * lại lần nữa nếu id không thuộc kỳ.
 *
 * Nút bấm nằm ngoài form (chân thẻ / chân hộp thoại) và trỏ về qua `form={formId}`. Nút nào có
 * `value="publish"` thì lưu xong gọi `onSaved(item, 'publish')` để trang mở tiếp bước đăng.
 */
export default function AnnouncementForm({ formId, item = null, active = true, onSaved, onPendingChange, onPreview }) {
  const toast = useToast()
  const { mutateAsync: save, isPending } = useSaveAnnouncement()
  const { data: options } = useRegistrationFormOptions()
  const { data: flights } = useFlights()
  const { data: buses } = useBuses()
  const [userQuery, setUserQuery] = useState('')

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    control,
    formState: { errors },
  } = useForm({ resolver: zodResolver(announcementSchema), defaultValues: EMPTY, mode: 'onTouched' })

  const targetType = useWatch({ control, name: 'target_type' })
  const targetId = useWatch({ control, name: 'target_id' })
  const severity = useWatch({ control, name: 'severity' })
  const content = useWatch({ control, name: 'content' })

  // Tìm cá nhân theo tên/email — danh sách CBNV dài, không đổ hết vào ô chọn.
  const { data: usersPage, isLoading: loadingUsers } = useUsers(
    { q: userQuery || undefined, page_size: 20 },
    { enabled: active && targetType === 'user' },
  )

  useEffect(() => {
    if (!active) return
    reset(item ? toFormValues(item) : EMPTY)
    setUserQuery('')
  }, [item, reset, active])

  useEffect(() => {
    onPendingChange?.(isPending)
  }, [isPending, onPendingChange])

  const { data: preview } = useRecipientPreview({ targetType, targetId: targetId || null, enabled: active })

  // Cho thẻ soạn biết đang gửi tới bao nhiêu người để ghi lên nút "Đăng cho N người".
  useEffect(() => {
    onPreview?.(preview ?? null)
  }, [preview, onPreview])

  const teams = (options?.teams ?? []).filter((team) => team.is_active)
  const targetOptions = targetOptionsFor(targetType, { teams, flights: flights ?? [], buses: buses ?? [] })

  async function onSubmit(values, submitEvent) {
    const intent = submitEvent?.nativeEvent?.submitter?.value === 'publish' ? 'publish' : 'draft'
    try {
      const saved = await save({ itemId: item?.id, payload: toPayload(values) })
      if (intent === 'draft') toast.success(item ? 'Đã cập nhật thông báo.' : 'Đã lưu bản nháp.')
      if (!item) reset(EMPTY)
      onSaved?.(saved, intent)
    } catch (error) {
      toast.error(error.message)
    }
  }

  return (
    <form id={formId} onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-3.5" noValidate>
      <fieldset>
        <legend className={LABEL_CLASS}>Gửi tới</legend>
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {Object.entries(ANNOUNCEMENT_TARGET_LABELS).map(([value, label]) => {
            const selected = targetType === value
            return (
              <button
                key={value}
                type="button"
                aria-pressed={selected}
                onClick={() => {
                  setValue('target_type', value, { shouldDirty: true })
                  setValue('target_id', '')
                }}
                className={`inline-flex min-h-11 items-center rounded-sm px-3 text-eyebrow whitespace-nowrap transition sm:min-h-8 ${
                  selected ? 'bg-primary text-on-primary' : 'border border-hairline bg-surface text-ink hover:bg-canvas-soft'
                }`}
              >
                {label}
              </button>
            )
          })}
        </div>
      </fieldset>

      {targetType !== 'all' &&
        (targetType === 'user' ? (
          <>
            <SearchBox label="Tìm CBNV" placeholder="Tên, email hoặc mã NV…" onSearch={setUserQuery} />
            {loadingUsers ? (
              <Spinner label="Đang tìm CBNV…" />
            ) : (
              <Select
                label="Cá nhân nhận"
                required
                placeholder="Chọn người nhận"
                options={(usersPage?.items ?? []).map((user) => ({
                  value: String(user.id),
                  label: `${user.full_name}${user.team ? ` · ${user.team.name}` : ''}`,
                }))}
                error={errors.target_id?.message}
                {...register('target_id')}
              />
            )}
          </>
        ) : (
          <Select
            aria-label="Đối tượng cụ thể"
            required
            placeholder={`Chọn ${ANNOUNCEMENT_TARGET_LABELS[targetType]?.toLowerCase() ?? 'đối tượng'}`}
            options={targetOptions}
            error={errors.target_id?.message}
            {...register('target_id')}
          />
        ))}

      {preview && (
        <p className="text-caption text-ink-muted">
          Sẽ gửi tới <strong className="font-semibold text-ink">{preview.total} người</strong> ·{' '}
          {preview.target_label}.{!preview.email_enabled && ' Email đang tắt — đăng xong vẫn hiện trong My Journey.'}
        </p>
      )}

      <fieldset>
        <legend className={LABEL_CLASS}>Loại</legend>
        {/* Thanh chọn 3 mức như Figma: nền xám nhạt, mức đang chọn nổi lên nền trắng. */}
        <div className="mt-1.5 flex rounded-full bg-black/5 p-1">
          {Object.entries(ANNOUNCEMENT_SEVERITY_META).map(([value, meta]) => (
            <button
              key={value}
              type="button"
              aria-pressed={severity === value}
              onClick={() => setValue('severity', value, { shouldDirty: true })}
              className={`min-h-11 flex-1 rounded-full text-caption transition sm:min-h-8 ${
                severity === value ? 'bg-surface font-semibold text-ink shadow-soft' : 'font-medium text-ink-muted'
              }`}
            >
              {meta.label}
            </button>
          ))}
        </div>
        {errors.severity && <p className={ERROR_CLASS}>{errors.severity.message}</p>}
      </fieldset>

      <Input
        label="Tiêu đề"
        required
        placeholder="Ví dụ: Có mặt tại sân bay trước 05:00"
        error={errors.title?.message}
        {...register('title')}
      />
      <Textarea
        label="Nội dung"
        required
        rows={4}
        placeholder="In đậm **giờ mới**, gạch đầu dòng - cho từng ý…"
        hint="Viết được markdown. Lưu là bản nháp — CBNV chỉ thấy sau khi đăng."
        error={errors.content?.message}
        {...register('content')}
      />
      {content?.trim() && (
        <div className="rounded-md bg-canvas-soft px-3 py-2.5">
          <p className="mb-1 text-eyebrow text-ink-faint">Xem trước như CBNV thấy</p>
          <MarkdownText content={content} />
        </div>
      )}
    </form>
  )
}

function targetOptionsFor(targetType, { teams, flights, buses }) {
  if (targetType === 'team') {
    return teams.map((team) => ({ value: String(team.id), label: `Team ${team.name}` }))
  }
  if (targetType === 'flight') {
    return flights.map((flight) => ({
      value: String(flight.id),
      label: [
        flight.flight_code,
        flight.direction === 'outbound' ? 'chiều đi' : 'chiều về',
        flight.departure_time && formatShortDateTime(flight.departure_time),
      ]
        .filter(Boolean)
        .join(' · '),
    }))
  }
  if (targetType === 'bus') {
    return buses.map((bus) => ({ value: String(bus.id), label: `${bus.bus_code}` }))
  }
  return []
}

function toFormValues(item) {
  return {
    title: item.title ?? '',
    content: item.content ?? '',
    severity: item.severity ?? 'info',
    target_type: item.target_type ?? 'all',
    target_id: item.target_id != null ? String(item.target_id) : '',
  }
}

/** Ô trống thành null cho khớp `extra="forbid"` của backend; id chọn thành số. */
function toPayload(values) {
  return {
    title: values.title.trim(),
    content: values.content.trim(),
    severity: values.severity,
    target_type: values.target_type,
    target_id: values.target_type === 'all' || !values.target_id ? null : Number(values.target_id),
  }
}
