import { useMemo, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { FormProvider, useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useQueryClient } from '@tanstack/react-query'
// `Map` của lucide phải đổi tên: để nguyên là nó che mất Map của JavaScript,
// và `new Map(...)` trong buildDefaults sẽ nổ -> React unmount, trang trắng.
import { ArrowLeft, ArrowRight, Lock, Map as MapIcon, Send } from 'lucide-react'
import { useActiveEvent, useMyRegistration } from '../../hooks/useEvent'
import { useRegistrationFormOptions, useSaveRegistration } from '../../hooks/useRegistration'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../context/ToastContext'
import { QUERY_KEYS, REGISTRATION_STEPS } from '../../utils/constants'
import {
  missingProfileFields,
  registrationFormSchema,
} from '../../utils/schemas'
import { PROFILE_FIELD_NAMES, profileDefaults } from '../../components/profile/ProfileFields'
import Alert from '../../components/common/Alert'
import Button from '../../components/common/Button'
import Card from '../../components/common/Card'
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
import { pointsForLeg } from './registration/pickupPoints'

/** Trường cần kiểm tra trước khi rời từng bước. */
const PROFILE_STEP_FIELDS = PROFILE_FIELD_NAMES.map((name) => `profile.${name}`)
const STEP_FIELDS = [
  PROFILE_STEP_FIELDS,
  ['is_participating', 'not_participating_reason'],
  ['shift_id', 'departure_location_id'],
  ['bus_needs'],
  ['wish_note', 'companion_count', 'agreed_terms', 'agreed_terms_version'],
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
  // Người đã huỷ được đăng ký lại tới trước khi công bố (backend trả cờ, không tự suy luật).
  const canReregister = Boolean(isCancelled && registration?.reregister_allowed)

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

  // Đã huỷ sau công bố: chặn cứng, chỉ còn đường liên hệ BTC.
  if (isCancelled && !canReregister) {
    const latest = registration?.latest_cancellation
    return (
      <>
        <div>
          <Card>
            <div className="flex flex-col items-center gap-3 py-6 text-center">
              <span className="grid size-12 place-items-center rounded-full bg-slate-100 text-slate-400">
                <Lock className="size-6" aria-hidden="true" />
              </span>
              <div>
                <h2 className="font-semibold text-slate-900">Bạn đã huỷ đăng ký</h2>
                <p className="mx-auto mt-1 max-w-sm text-sm text-slate-500">
                  {latest?.reason ? `Lý do đã ghi nhận: “${latest.reason}”. ` : ''}
                  Ban tổ chức đã công bố thông tin nên không đăng ký lại được trên hệ thống. Có
                  thay đổi, hãy liên hệ Ban tổ chức để được hỗ trợ.
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

  if (!event.can_register && !canReregister) {
    return (
      <>
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
    <>
      {canReregister && (
        <div className="mb-4">
          <Alert tone="info" title="Đăng ký lại sau khi huỷ">
            Lần huỷ trước của bạn đã được ghi nhận
            {registration?.latest_cancellation?.reason
              ? ` (lý do: “${registration.latest_cancellation.reason}”)`
              : ''}
            . Điền lại form dưới đây để tham gia — chỗ bay, xe, phòng và ghế Gala cũ không tự giữ
            lại, hệ thống xếp lại từ đầu.
          </Alert>
        </div>
      )}
      <RegistrationWizard
        // Đổi giữa "tạo mới" và "sửa" thì dựng lại form với defaultValues mới.
        key={registration?.id ?? 'new'}
        event={event}
        options={options}
        registration={isCancelled ? null : registration}
        onSubmitted={setSubmitted}
      />
    </>
  )
}

function RegistrationWizard({ event, options, registration, onSubmitted }) {
  const { user } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const location = useLocation()
  const draft = location.state?.registrationDraft
  const restored = draft?.userId === user.id && draft?.eventId === event.id &&
    draft?.registrationId === (registration?.id ?? null) ? draft : null
  const queryClient = useQueryClient()

  const isEditing = Boolean(registration)

  const [stepIndex, setStepIndex] = useState(restored?.stepIndex ?? 0)
  // `visitedCount` chỉ quyết định bước nào được phép mở; không dùng nó để kết luận bước đã xong.
  const [visitedCount, setVisitedCount] = useState(
    restored?.visitedCount ?? (isEditing ? LAST_STEP : 0),
  )
  const [completedSteps, setCompletedSteps] = useState(() =>
    restored?.completedSteps ?? (isEditing
      ? Array.from({ length: REGISTRATION_STEPS.length }, (_, index) => index)
      : []),
  )
  const [serverError, setServerError] = useState(null)
  const [cancelOpen, setCancelOpen] = useState(false)

  const defaultValues = useMemo(
    () => ({
      ...buildDefaults({ user, registration, options, event }),
      ...restored?.values,
      profile: { ...profileDefaults(user), id_card_type: user.id_card_type ?? '' },
    }),
    [user, registration, options, event, restored],
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

  function goTo(index) {
    const target = Math.min(Math.max(index, 0), LAST_STEP)
    if (target > 1 && participating && missingProfileFields(user).length) {
      setStepIndex(1)
      toast.error('Cập nhật các thông tin bắt buộc tại Hồ sơ trước khi tiếp tục.')
      return
    }
    // Không tham gia thì hai bước giữa không có gì để điền.
    if (notParticipating && PARTICIPANT_ONLY_STEPS.includes(target)) return
    setStepIndex(target)
    setVisitedCount((current) => Math.max(current, target))
  }

  function markStepComplete(indexes) {
    setCompletedSteps((current) => [...new Set([...current, ...indexes])].sort((a, b) => a - b))
  }

  function markMissingProfileFields() {
    return missingProfileFields(user)
  }

  function editProfile() {
    navigate('/profile', { state: { returnToRegistration: true, registrationDraft: {
      userId: user.id, eventId: event.id, registrationId: registration?.id ?? null,
      values: form.getValues(), stepIndex, visitedCount, completedSteps,
    } } })
  }

  function markMissingPickupPoints() {
    const needs = form.getValues('bus_needs') ?? []
    const missing = []
    needs.forEach((need, index) => {
      if (need.needs_bus && need.has_pickup_options && !need.pickup_point_id) {
        missing.push(index)
        form.setError(`bus_needs.${index}.pickup_point_id`, {
          type: 'required',
          message: 'Chọn điểm cho chặng này',
        })
      }
    })
    return missing
  }

  async function goNext(event) {
    event?.preventDefault()
    const valid = stepIndex === 0 ? true : await form.trigger(STEP_FIELDS[stepIndex])
    if (!valid) {
      toast.error('Kiểm tra lại những ô đang báo đỏ rồi tiếp tục.')
      return
    }

    if (stepIndex === 1) {
      if (!participating) {
        markStepComplete([stepIndex, ...PARTICIPANT_ONLY_STEPS])
        goTo(LAST_STEP)
        return
      }
      const profileValid = await form.trigger(PROFILE_STEP_FIELDS)
      const missing = markMissingProfileFields()
      if (!profileValid || missing.length) {
        toast.error(`Cập nhật ${missing.length ? missing.join(', ') : 'các trường đang báo lỗi'} tại Hồ sơ trước khi tiếp tục.`)
        return
      }
      if (!form.getValues('agreed_terms') || !form.getValues('agreed_terms_version')) {
        form.setError('agreed_terms', { type: 'required', message: 'Đọc hết quy định và đồng ý trước khi tiếp tục' })
        toast.error('Đọc hết quy định và đồng ý trước khi tiếp tục.')
        return
      }
    }

    if (stepIndex === 2 && participating && !form.getValues('shift_id')) {
      form.setError('shift_id', { type: 'required', message: 'Vui lòng chọn ca đi' })
      toast.error('Chọn ca đi trước khi tiếp tục.')
      return
    }

    if (stepIndex === 3 && participating && markMissingPickupPoints().length) {
      toast.error('Chọn điểm đón cho các chặng bạn đi xe BTC.')
      return
    }

    if (stepIndex === LAST_STEP && participating) {
      if (!form.getValues('agreed_terms') || !form.getValues('agreed_terms_version')) {
        form.setError('agreed_terms', { type: 'required', message: 'Phải đọc và đồng ý quy định chương trình' })
        toast.error('Đọc và đồng ý quy định trước khi gửi đăng ký.')
        return
      }
    }

    markStepComplete([stepIndex])
    goTo(stepIndex + 1)
  }

  function goBack() {
    if (stepIndex === LAST_STEP && notParticipating) {
      setStepIndex(1)
      return
    }
    setStepIndex((current) => Math.max(0, current - 1))
  }

  async function onSubmit(values) {
    setServerError(null)
    if (values.is_participating === 'yes' && markMissingProfileFields().length) {
      goTo(1)
      toast.error('Cần cập nhật Hồ sơ trước khi gửi đăng ký tham gia.')
      return
    }
    try {
      const saved = await save(buildPayload(values, { event }))
      onSubmitted(saved)
      toast.success(isEditing ? 'Đã cập nhật đăng ký.' : 'Đã gửi đăng ký.')
    } catch (error) {
      setServerError(error)
      handleServerError(error)
    }
  }

  /** Đưa người dùng về đúng bước có lỗi — nếu không họ chỉ thấy nút bấm mà không hiện gì. */
  function onInvalid(errors) {
    const hasError = (path) => path.split('.').reduce((node, key) => node?.[key], errors)
    const index = STEP_FIELDS.findIndex((fields) => fields.some(hasError))
    if (index >= 0 && index !== stepIndex) {
      goTo(index)
      toast.error('Còn thông tin chưa hợp lệ, đã đưa bạn về bước cần sửa.')
    }
  }

  function handleServerError(error) {
    if (error.code === 'MISSING_PROFILE_FIELDS' || error.code === 'INVALID_PROFILE_FIELDS') {
      goTo(0)
      return
    }
    if (error.code === 'TERMS_VERSION_MISMATCH') {
      // BTC vừa sửa quy định: xoá cache bản cũ và buộc đọc lại bản mới.
      form.setValue('agreed_terms', false)
      form.setValue('agreed_terms_version', '')
      setCompletedSteps((current) => current.filter((index) => index !== LAST_STEP))
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.terms(event.id) })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.activeEvent })
      goTo(LAST_STEP)
      return
    }
    if (error.code === 'REGISTRATION_CLOSED' || error.code === 'REGISTRATION_CANCELLED_FINAL') {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.activeEvent })
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.myRegistration })
    }
  }

  const stepContent = [
    <ProfileStep key="profile" onEditProfile={editProfile} />,
    <ParticipationStep key="participation" event={event} onGoToProfile={editProfile} />,
    <ShiftStep key="shift" event={event} options={options} />,
    <BusStep key="bus" options={options} />,
    <ConsentStep key="consent" event={event} options={options} onGoToStep={goTo} onEditProfile={editProfile} />,
  ][stepIndex]

  return (
    <>
      <RegistrationHeader
        stepIndex={stepIndex}
        onBack={stepIndex > 0 ? goBack : () => navigate('/my-journey')}
      />

      <div className="flex flex-col gap-4 max-md:gap-[14px]">
        <div className="rounded-xl border border-hairline bg-surface px-4 py-3 shadow-soft max-md:hidden sm:px-5 sm:py-4">
          <Stepper
            steps={REGISTRATION_STEPS}
            currentIndex={stepIndex}
            visitedCount={visitedCount}
            completedIndexes={completedSteps}
            skipIndexes={notParticipating ? PARTICIPANT_ONLY_STEPS : []}
            onStepClick={goTo}
          />
        </div>

        <FormProvider {...form}>
          {/* Lưới 12 cột: form bên trái, tóm tắt bên phải. Dưới 1280px thì tóm tắt
              xuống dưới form — trên điện thoại người dùng cần thấy ô nhập trước. */}
          <div className="grid gap-4 xl:grid-cols-12">
            <form
              onSubmit={form.handleSubmit(onSubmit, onInvalid)}
              className="flex flex-col gap-4 pb-0 max-md:gap-[18px] max-md:pb-4 xl:col-span-8 [&>section]:max-md:rounded-xl"
              noValidate
            >
              {stepContent}

              {serverError && (
                <Alert tone="error" title="Không gửi được đăng ký">
                  {serverError.message}
                </Alert>
              )}

              <div className="flex flex-wrap items-center gap-3 pt-0.5 max-md:fixed max-md:inset-x-0 max-md:bottom-0 max-md:z-[25] max-md:flex-nowrap max-md:gap-2 max-md:border-t max-md:border-hairline max-md:bg-surface max-md:px-5 max-md:py-3 max-md:pb-[calc(12px+env(safe-area-inset-bottom))]">
                <Button
                  type="button"
                  variant="secondary"
                  icon={ArrowLeft}
                  onClick={goBack}
                  disabled={stepIndex === 0}
                  className="max-md:shrink-0"
                >
                  Quay lại
                </Button>

                {stepIndex === LAST_STEP ? (
                  <Button key="submit-registration" type="submit" icon={Send} loading={isPending} className="max-md:flex-1">
                    {isEditing ? 'Lưu thay đổi' : 'Gửi đăng ký'}
                  </Button>
                ) : (
                  <Button key="next-step" type="button" icon={ArrowRight} onClick={goNext} className="max-md:flex-1">
                    Tiếp tục
                  </Button>
                )}
              </div>
            </form>

            <aside className="flex flex-col gap-4 max-md:hidden xl:col-span-4">
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
        onDone={() => navigate('/my-journey')}
      />
    </>
  )
}

function RegistrationHeader({ stepIndex, onBack }) {
  return (
    <header className="mb-3 flex min-h-12 flex-col items-stretch gap-2 md:hidden">
      <div className="flex w-full items-center justify-between gap-3">
        <button type="button" onClick={onBack} className="grid size-8 place-items-center rounded-full text-ink" aria-label="Quay lại">
          <ArrowLeft className="size-5" aria-hidden="true" />
        </button>
        <span className="text-body-sm font-medium text-ink">Bước {stepIndex + 1}/5</span>
        <span className="size-8" aria-hidden="true" />
      </div>
      <div className="grid w-full grid-cols-5 gap-1">
        {REGISTRATION_STEPS.map((step, index) => (
          <span
            key={step.id}
            className={`h-1 rounded-full ${index < stepIndex ? 'bg-accent-green' : index === stepIndex ? 'bg-primary' : 'bg-hairline'}`}
            aria-hidden="true"
          />
        ))}
      </div>
    </header>
  )
}

/**
 * Giá trị khởi tạo của form: hồ sơ hiện tại + đăng ký đã có.
 *
 * Mọi id thành chuỗi vì `<select>` chỉ làm việc với chuỗi; lúc gửi API mới đổi lại
 * thành số trong buildPayload.
 */
function buildDefaults({ user, registration, options, event }) {
  const legs = options.trip_legs ?? []
  const pickupPoints = options.pickup_points ?? []
  const existingNeeds = new Map(
    (registration?.bus_needs ?? []).map((need) => [need.trip_leg_id, need]),
  )

  return {
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
        has_pickup_options: pointsForLeg(pickupPoints, leg, registration?.departure_location_id).length > 0,
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

}

/** Đổi giá trị form thành payload API (docs/04-api-spec.md §4). */
function buildPayload(values, { event }) {
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

  return payload
}
