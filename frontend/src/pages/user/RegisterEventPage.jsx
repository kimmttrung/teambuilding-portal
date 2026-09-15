import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { FormProvider, useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useQueryClient } from '@tanstack/react-query'
// `Map` của lucide phải đổi tên: để nguyên là nó che mất Map của JavaScript,
// và `new Map(...)` trong buildDefaults sẽ nổ -> React unmount, trang trắng.
import { ArrowLeft, ArrowRight, Lock, Map as MapIcon, RotateCcw, Send } from 'lucide-react'
import { useActiveEvent, useMyRegistration } from '../../hooks/useEvent'
import { useRegistrationFormOptions, useSaveRegistration } from '../../hooks/useRegistration'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../context/ToastContext'
import { QUERY_KEYS, REGISTRATION_STEPS } from '../../utils/constants'
import { formatDateTime, formatRelative } from '../../utils/format'
import { buildProfilePatch, missingFlightFields, registrationFormSchema } from '../../utils/schemas'
import { profileDefaults } from '../../components/profile/ProfileFields'
import Alert from '../../components/common/Alert'
import Button from '../../components/common/Button'
import Card from '../../components/common/Card'
import PageHeader from '../../components/common/PageHeader'
import Spinner from '../../components/common/Spinner'
import Stepper from '../../components/common/Stepper'
import BusStep from './registration/BusStep'
import CancellationPanel from './registration/CancellationPanel'
import CancelRegistrationModal from './registration/CancelRegistrationModal'
import ConsentStep from './registration/ConsentStep'
import ParticipationStep from './registration/ParticipationStep'
import ProfileStep from './registration/ProfileStep'
import RegistrationSuccess from './registration/RegistrationSuccess'
import RegistrationSummary from './registration/RegistrationSummary'
import ShiftStep from './registration/ShiftStep'
import WizardSidebar from './registration/WizardSidebar'
import { clearDraft, draftKey, loadDraft, saveDraft } from './registration/draft'

/** Trường cần kiểm tra trước khi rời từng bước. */
const STEP_FIELDS = [
  ['profile'],
  ['is_participating', 'not_participating_reason'],
  ['shift_id', 'departure_location_id'],
  ['bus_needs'],
  ['wish_note', 'companion_count', 'agreed_terms'],
]

/** Bước 3 và 4 chỉ dành cho người tham gia — chọn "không" là nhảy thẳng tới bước cuối. */
const PARTICIPANT_ONLY_STEPS = [2, 3]
const LAST_STEP = STEP_FIELDS.length - 1

export default function RegisterEventPage() {
  const { user } = useAuth()
  const { data: event, isLoading: loadingEvent, error: eventError } = useActiveEvent()
  const { data: options, isLoading: loadingOptions, error: optionsError } = useRegistrationFormOptions()
  const { data: registration, isLoading: loadingRegistration } = useMyRegistration()

  // Màn hình "gửi thành công" phải nằm ở đây, không nằm trong wizard: gửi xong là
  // cache đăng ký đổi, `key` của wizard đổi theo và wizard bị dựng lại từ đầu.
  const [submitted, setSubmitted] = useState(null)

  if (loadingEvent || loadingOptions || loadingRegistration) {
    return <Spinner label="Đang tải form đăng ký…" />
  }

  if (eventError) {
    return (
      <Alert tone="warning" title="Chưa có kỳ Team Building nào đang mở">
        {eventError.message}
      </Alert>
    )
  }

  if (optionsError) {
    return (
      <Alert tone="error" title="Không tải được dữ liệu form">
        {optionsError.message}
      </Alert>
    )
  }

  const isCancelled = registration?.status === 'cancelled'

  if (submitted) {
    return (
      <RegistrationSuccess
        registration={submitted}
        event={event}
        email={user.email}
        onEdit={() => setSubmitted(null)}
      />
    )
  }

  // Đăng ký đã chốt (BTC đóng đăng ký): chỉ cho xem lại; huỷ theo giai đoạn kỳ (CancellationPanel).
  if (registration && !isCancelled && !registration.can_edit) {
    return (
      <>
        <PageHeader title="Đăng ký Team Building" description={event.name} />
        <div className="grid gap-4 xl:grid-cols-12">
          <div className="xl:col-span-8">
            <RegistrationSummary registration={registration} />
          </div>
          <div className="flex flex-col gap-4 xl:col-span-4">
            <Alert tone="info" title="Đăng ký đã chốt">
              Đăng ký của bạn đã được ghi nhận và không sửa được nữa. Cần đổi ca, xe hay thông tin
              khác thì liên hệ Ban tổ chức.
            </Alert>
            <CancellationPanel event={event} registration={registration} />
            <Link to="/my-journey">
              <Button icon={MapIcon} fullWidth>
                Về trang Hành trình
              </Button>
            </Link>
          </div>
        </div>
      </>
    )
  }

  if (!event.can_register) {
    return (
      <>
        <PageHeader title="Đăng ký Team Building" description={event.name} />
        <div>
          <Card>
            <div className="flex flex-col items-center gap-3 py-6 text-center">
              <span className="grid size-12 place-items-center rounded-full bg-slate-100 text-slate-400">
                <Lock className="size-6" aria-hidden="true" />
              </span>
              <div>
                <h2 className="font-semibold text-slate-900">Chưa mở hoặc đã đóng đăng ký</h2>
                <p className="mx-auto mt-1 max-w-sm text-sm text-slate-500">
                  Trạng thái hiện tại: {event.status_label || event.status}. Liên hệ Ban tổ chức
                  nếu bạn cần đăng ký muộn.
                </p>
              </div>
              <Link to="/my-journey">
                <Button variant="secondary" icon={MapIcon}>
                  Về trang Hành trình
                </Button>
              </Link>
            </div>
          </Card>
        </div>
      </>
    )
  }

  return (
    <RegistrationWizard
      // Đổi giữa "tạo mới" và "sửa" thì dựng lại form với defaultValues mới.
      key={registration?.id ?? 'new'}
      event={event}
      options={options}
      registration={isCancelled ? null : registration}
      onSubmitted={setSubmitted}
    />
  )
}

function RegistrationWizard({ event, options, registration, onSubmitted }) {
  const { user } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const isEditing = Boolean(registration)
  const storageKey = draftKey(event.id, user.id)

  // Chỉ dùng nháp khi đăng ký lần đầu. Đang sửa thì dữ liệu trên server mới là
  // nguồn đúng — nháp cũ sẽ ghi đè thầm những gì đã gửi đi.
  const draft = useMemo(() => (isEditing ? null : loadDraft(storageKey)), [isEditing, storageKey])

  const [stepIndex, setStepIndex] = useState(draft?.stepIndex ?? 0)
  // Đang sửa thì mọi bước đã từng điền, cho nhảy tự do trên thanh tiến trình.
  const [visitedCount, setVisitedCount] = useState(
    isEditing ? LAST_STEP : (draft?.stepIndex ?? 0),
  )
  const [serverError, setServerError] = useState(null)
  const [cancelOpen, setCancelOpen] = useState(false)
  const [draftRestored, setDraftRestored] = useState(Boolean(draft))

  const defaultValues = useMemo(
    () => buildDefaults({ user, registration, options, event, draft }),
    [user, registration, options, event, draft],
  )

  const form = useForm({
    resolver: zodResolver(registrationFormSchema),
    defaultValues,
    mode: 'onTouched',
  })

  const { mutateAsync: save, isPending } = useSaveRegistration({ isEditing })

  const choice = form.watch('is_participating')
  const participating = choice === 'yes'
  const notParticipating = choice === 'no'

  // Lưu nháp mỗi khi người dùng nhập hoặc đổi bước: F5 giữa form không mất dữ liệu.
  useEffect(() => {
    if (isEditing) return undefined
    saveDraft(storageKey, form.getValues(), stepIndex)
    const subscription = form.watch((values) => saveDraft(storageKey, values, stepIndex))
    return () => subscription.unsubscribe()
  }, [form, isEditing, storageKey, stepIndex])

  function goTo(index) {
    const target = Math.min(Math.max(index, 0), LAST_STEP)
    // Không tham gia thì hai bước giữa không có gì để điền.
    if (notParticipating && PARTICIPANT_ONLY_STEPS.includes(target)) return
    setStepIndex(target)
    setVisitedCount((current) => Math.max(current, target))
  }

  async function goNext() {
    const valid = await form.trigger(STEP_FIELDS[stepIndex])
    if (!valid) {
      // Lỗi "thiếu trường bắt buộc" của bước 1 nằm ở gốc nhánh profile, không gắn vào
      // ô nào cả — không nói ra thì người dùng bấm Tiếp tục mà không hiểu vì sao đứng im.
      const missing = stepIndex === 0 ? missingFlightFields(form.getValues('profile')) : []
      toast.error(
        missing.length
          ? `Còn thiếu: ${missing.join(', ')}.`
          : 'Kiểm tra lại những ô đang báo đỏ rồi tiếp tục.',
      )
      return
    }

    if (stepIndex === 1) {
      if (!participating) {
        goTo(LAST_STEP)
        return
      }
      const missing = missingFlightFields(form.getValues('profile'))
      if (missing.length) {
        toast.error(`Bổ sung ${missing.join(', ')} ở bước 1 trước khi tiếp tục.`)
        return
      }
    }

    goTo(stepIndex + 1)
  }

  function goBack() {
    if (stepIndex === LAST_STEP && notParticipating) {
      setStepIndex(1)
      return
    }
    setStepIndex((current) => Math.max(0, current - 1))
  }

  function resetDraft() {
    clearDraft(storageKey)
    form.reset(buildDefaults({ user, registration, options, event, draft: null }))
    setStepIndex(0)
    setVisitedCount(0)
    setDraftRestored(false)
    toast.info('Đã xoá bản nháp, form trở về thông tin hồ sơ hiện tại.')
  }

  async function onSubmit(values) {
    setServerError(null)
    try {
      const saved = await save(buildPayload(values, { user, event }))
      clearDraft(storageKey)
      onSubmitted(saved)
      toast.success(isEditing ? 'Đã cập nhật đăng ký.' : 'Đã gửi đăng ký.')
    } catch (error) {
      setServerError(error)
      handleServerError(error)
    }
  }

  /** Đưa người dùng về đúng bước có lỗi — nếu không họ chỉ thấy nút bấm mà không hiện gì. */
  function onInvalid(errors) {
    const index = STEP_FIELDS.findIndex((fields) => fields.some((field) => errors[field]))
    if (index >= 0 && index !== stepIndex) {
      goTo(index)
      toast.error('Còn thông tin chưa hợp lệ, đã đưa bạn về bước cần sửa.')
    }
  }

  function handleServerError(error) {
    if (error.code === 'MISSING_PROFILE_FIELDS') {
      goTo(0)
      return
    }
    if (error.code === 'TERMS_VERSION_MISMATCH') {
      // BTC vừa sửa quy định: xoá cache bản cũ và buộc đọc lại bản mới.
      form.setValue('agreed_terms', false)
      form.setValue('agreed_terms_version', '')
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.terms(event.id) })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.activeEvent })
      goTo(LAST_STEP)
      return
    }
    if (error.code === 'REGISTRATION_CLOSED') {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.activeEvent })
    }
  }

  const stepContent = [
    <ProfileStep key="profile" />,
    <ParticipationStep key="participation" event={event} onGoToProfile={() => goTo(0)} />,
    <ShiftStep key="shift" options={options} />,
    <BusStep key="bus" options={options} />,
    <ConsentStep key="consent" event={event} />,
  ][stepIndex]

  return (
    <>
      <PageHeader
        title={isEditing ? 'Sửa đăng ký Team Building' : 'Đăng ký Team Building'}
        description={`${event.name}${
          event.registration_closes_at ? ` · hạn đăng ký ${formatRelative(event.registration_closes_at)}` : ''
        }`}
      />

      <div className="flex flex-col gap-4">
        <div className="rounded-xl border border-slate-200 bg-white px-4 py-3">
          <Stepper
            steps={REGISTRATION_STEPS}
            currentIndex={stepIndex}
            visitedCount={visitedCount}
            skipIndexes={notParticipating ? PARTICIPANT_ONLY_STEPS : []}
            onStepClick={goTo}
          />
        </div>

        {draftRestored && (
          <Alert tone="info" title="Đã phục hồi bản nháp">
            <p>
              Bạn có bản nháp lưu lúc {formatDateTime(draft.savedAt)}. Số CCCD và ghi chú sức khoẻ
              không được lưu trong nháp, hãy kiểm tra lại ở bước 1.
            </p>
            <button
              type="button"
              onClick={resetDraft}
              className="mt-1.5 inline-flex items-center gap-1.5 font-semibold underline underline-offset-2"
            >
              <RotateCcw className="size-3.5" aria-hidden="true" />
              Bỏ nháp, điền lại từ hồ sơ
            </button>
          </Alert>
        )}

        <FormProvider {...form}>
          {/* Lưới 12 cột: form bên trái, tóm tắt bên phải. Dưới 1280px thì tóm tắt
              xuống dưới form — trên điện thoại người dùng cần thấy ô nhập trước. */}
          <div className="grid gap-4 xl:grid-cols-12">
            <form
              onSubmit={form.handleSubmit(onSubmit, onInvalid)}
              className="flex flex-col gap-4 xl:col-span-8"
              noValidate
            >
              {stepContent}

              {serverError && (
                <Alert tone="error" title="Không gửi được đăng ký">
                  {serverError.message}
                </Alert>
              )}

              <div className="sticky bottom-20 z-10 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white/95 px-4 py-3 backdrop-blur md:bottom-4">
                <Button
                  type="button"
                  variant="secondary"
                  icon={ArrowLeft}
                  onClick={goBack}
                  disabled={stepIndex === 0}
                >
                  Quay lại
                </Button>

                <span className="hidden text-xs text-slate-500 sm:block">
                  Bước {stepIndex + 1}/{REGISTRATION_STEPS.length}
                  {!isEditing && ' · nội dung được lưu nháp tự động'}
                </span>

                {stepIndex === LAST_STEP ? (
                  <Button type="submit" icon={Send} loading={isPending}>
                    {isEditing ? 'Lưu thay đổi' : 'Gửi đăng ký'}
                  </Button>
                ) : (
                  <Button type="button" icon={ArrowRight} onClick={goNext}>
                    Tiếp tục
                  </Button>
                )}
              </div>
            </form>

            <aside className="flex flex-col gap-4 xl:col-span-4">
              <WizardSidebar
                event={event}
                options={options}
                isEditing={isEditing}
                onRequestCancel={() => setCancelOpen(true)}
              />
            </aside>
          </div>
        </FormProvider>
      </div>

      <CancelRegistrationModal
        open={cancelOpen}
        mode={registration?.cancel_policy === 'request' ? 'request' : 'self'}
        onClose={() => setCancelOpen(false)}
        closesAt={event.registration_closes_at}
        onDone={() => {
          clearDraft(storageKey)
          navigate('/my-journey')
        }}
      />
    </>
  )
}

/**
 * Giá trị khởi tạo của form: hồ sơ hiện tại + đăng ký đã có + nháp (nếu có).
 *
 * Mọi id thành chuỗi vì `<select>` chỉ làm việc với chuỗi; lúc gửi API mới đổi lại
 * thành số trong buildPayload.
 */
function buildDefaults({ user, registration, options, event, draft }) {
  const legs = options.trip_legs ?? []
  const pickupPoints = options.pickup_points ?? []
  const existingNeeds = new Map(
    (registration?.bus_needs ?? []).map((need) => [need.trip_leg_id, need]),
  )

  const base = {
    profile: profileDefaults(user),
    is_participating: registration ? (registration.is_participating ? 'yes' : 'no') : '',
    not_participating_reason: registration?.not_participating_reason ?? '',
    shift_id: registration?.shift?.id ? String(registration.shift.id) : '',
    departure_location_id: registration?.departure_location_id
      ? String(registration.departure_location_id)
      : '',
    bus_needs: legs.map((leg) => {
      const need = existingNeeds.get(leg.id)
      return {
        trip_leg_id: leg.id,
        needs_bus: need?.needs_bus ?? false,
        pickup_point_id: need?.pickup_point_id ? String(need.pickup_point_id) : '',
        note: need?.note ?? '',
        has_pickup_options: pickupPoints.some(
          (point) => point.trip_leg_id === null || point.trip_leg_id === leg.id,
        ),
      }
    }),
    wish_note: registration?.wish_note ?? '',
    companion_count: registration?.companion_count ?? 0,
    // Đã đồng ý đúng bản quy định hiện hành thì không phải đọc lại.
    agreed_terms: Boolean(
      registration?.agreed_terms_version &&
        registration.agreed_terms_version === event.terms_version,
    ),
    agreed_terms_version: registration?.agreed_terms_version ?? '',
  }

  if (!draft?.values) return base

  const draftValues = draft.values
  const draftNeeds = new Map(
    (draftValues.bus_needs ?? []).map((need) => [need.trip_leg_id, need]),
  )

  return {
    ...base,
    ...draftValues,
    profile: { ...base.profile, ...draftValues.profile },
    // Ghép theo trip_leg_id, không theo thứ tự: BTC có thể đã thêm/xoá chặng từ lúc lưu nháp.
    bus_needs: base.bus_needs.map((need) => {
      const drafted = draftNeeds.get(need.trip_leg_id)
      return drafted ? { ...need, needs_bus: drafted.needs_bus, pickup_point_id: drafted.pickup_point_id ?? '', note: drafted.note ?? '' } : need
    }),
    // Quy định đổi bản sau khi lưu nháp thì phải đọc lại bản mới.
    agreed_terms: Boolean(
      draftValues.agreed_terms && draftValues.agreed_terms_version === event.terms_version,
    ),
  }
}

/** Đổi giá trị form thành payload API (docs/04-api-spec.md §4). */
function buildPayload(values, { user, event }) {
  const participating = values.is_participating === 'yes'
  const trimmed = (value) => value?.trim() || null

  const payload = {
    is_participating: participating,
    not_participating_reason: participating ? null : trimmed(values.not_participating_reason),
    shift_id: participating && values.shift_id ? Number(values.shift_id) : null,
    departure_location_id: values.departure_location_id
      ? Number(values.departure_location_id)
      : null,
    bus_needs: participating
      ? values.bus_needs.map((need) => ({
          trip_leg_id: need.trip_leg_id,
          needs_bus: need.needs_bus,
          pickup_point_id:
            need.needs_bus && need.pickup_point_id ? Number(need.pickup_point_id) : null,
          note: trimmed(need.note),
        }))
      : [],
    wish_note: trimmed(values.wish_note),
    companion_count: participating ? Number(values.companion_count) || 0 : 0,
    agreed_terms_version: participating
      ? values.agreed_terms_version || event.terms_version
      : null,
  }

  const profilePatch = buildProfilePatch(values.profile, user)
  if (Object.keys(profilePatch).length > 0) payload.profile_patch = profilePatch

  return payload
}
