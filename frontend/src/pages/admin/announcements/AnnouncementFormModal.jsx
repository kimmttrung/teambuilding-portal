import { useEffect, useState } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Save } from 'lucide-react'
import { useRecipientPreview, useSaveAnnouncement } from '../../../hooks/useAnnouncements'
import { useBuses } from '../../../hooks/useBuses'
import { useFlights } from '../../../hooks/useFlights'
import { useRegistrationFormOptions } from '../../../hooks/useRegistration'
import { useUsers } from '../../../hooks/useUsers'
import { useToast } from '../../../context/ToastContext'
import { ANNOUNCEMENT_SEVERITY_META } from '../../../utils/constants'
import { announcementSchema } from '../../../utils/schemas'
import Button from '../../../components/common/Button'
import Input from '../../../components/common/Input'
import MarkdownText from '../../../components/common/MarkdownText'
import Modal from '../../../components/common/Modal'
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

const TARGET_TYPES = [
  { value: 'all', label: 'Tất cả CBNV' },
  { value: 'team', label: 'Một team' },
  { value: 'flight', label: 'Một chuyến bay' },
  { value: 'bus', label: 'Một xe' },
  { value: 'user', label: 'Một cá nhân' },
]

/**
 * Soạn / sửa thông báo. `item = null` là soạn mới (luôn tạo nháp, đăng ở bước riêng).
 * Đối tượng cụ thể lấy từ dữ liệu thật (team, chuyến, xe, CBNV) để không gửi nhầm —
 * backend vẫn chặn lại lần nữa nếu id không thuộc kỳ.
 */
export default function AnnouncementFormModal({ open, onClose, item }) {
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
  const content = useWatch({ control, name: 'content' })

  // Tìm cá nhân theo tên/email — danh sách CBNV dài, không đổ hết vào ô chọn.
  const { data: usersPage, isLoading: loadingUsers } = useUsers(
    { q: userQuery || undefined, page_size: 20 },
    { enabled: open && targetType === 'user' },
  )

  useEffect(() => {
    if (!open) return
    reset(item ? toFormValues(item) : EMPTY)
    setUserQuery('')
  }, [item, reset, open])

  const { data: preview } = useRecipientPreview({
    targetType,
    targetId: targetId || null,
    enabled: open,
  })

  const teams = (options?.teams ?? []).filter((team) => team.is_active)
  const targetOptions = targetOptionsFor(targetType, { teams, flights: flights ?? [], buses: buses ?? [] })

  async function onSubmit(values) {
    try {
      await save({ itemId: item?.id, payload: toPayload(values) })
      toast.success(item ? 'Đã cập nhật thông báo.' : 'Đã lưu bản nháp.')
      onClose()
    } catch (error) {
      toast.error(error.message)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="lg"
      title={item ? 'Sửa thông báo' : 'Soạn thông báo mới'}
      description="Lưu là bản nháp — chỉ hiện với CBNV sau khi bấm Đăng"
      footer={
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" size="sm" onClick={onClose}>
            Huỷ
          </Button>
          <Button type="submit" form="announcement-form" size="sm" icon={Save} loading={isPending}>
            {item ? 'Lưu thay đổi' : 'Lưu nháp'}
          </Button>
        </div>
      }
    >
      <form id="announcement-form" onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-3">
        <Input
          label="Tiêu đề"
          required
          placeholder="Ví dụ: VN1234 đổi giờ khởi hành"
          error={errors.title?.message}
          {...register('title')}
        />
        <div className="grid gap-3 sm:grid-cols-2">
          <Select
            label="Mức độ"
            required
            options={Object.entries(ANNOUNCEMENT_SEVERITY_META).map(([value, meta]) => ({
              value,
              label: meta.label,
            }))}
            error={errors.severity?.message}
            {...register('severity')}
          />
          <Select
            label="Gửi tới"
            required
            options={TARGET_TYPES}
            error={errors.target_type?.message}
            {...register('target_type', {
              onChange: () => setValue('target_id', ''),
            })}
          />
        </div>

        {targetType !== 'all' && (
          <>
            {targetType === 'user' ? (
              <>
                <SearchBox
                  label="Tìm CBNV"
                  placeholder="Tên, email hoặc mã NV…"
                  onSearch={setUserQuery}
                />
                {loadingUsers ? (
                  <Spinner label="Đang tìm CBNV…" />
                ) : (
                  <Select
                    label="Cá nhân nhận"
                    required
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
                label="Đối tượng cụ thể"
                required
                options={targetOptions}
                error={errors.target_id?.message}
                {...register('target_id')}
              />
            )}
            {preview && (
              <p className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
                Sẽ gửi tới <strong>{preview.total} người</strong> ({preview.target_label}).
                {!preview.email_enabled && ' Email đang tắt — đăng xong vẫn hiện trong My Journey.'}
              </p>
            )}
          </>
        )}

        <Textarea
          label="Nội dung (markdown)"
          required
          rows={5}
          placeholder="In đậm **giờ mới**, gạch đầu dòng - cho từng ý…"
          error={errors.content?.message}
          {...register('content')}
        />
        {content?.trim() && (
          <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
            <p className="mb-1 text-[11px] font-semibold tracking-wide text-slate-400 uppercase">
              Xem trước như CBNV thấy
            </p>
            <MarkdownText content={content} />
          </div>
        )}
      </form>
    </Modal>
  )
}

function targetOptionsFor(targetType, { teams, flights, buses }) {
  if (targetType === 'team') {
    return teams.map((team) => ({ value: String(team.id), label: `Team ${team.name}` }))
  }
  if (targetType === 'flight') {
    return flights.map((flight) => ({
      value: String(flight.id),
      label: `${flight.flight_code} · ${flight.direction === 'outbound' ? 'đi' : 'về'} ${flight.departure_time ?? ''}`,
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
