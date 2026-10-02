import { useState } from 'react'
import { useFormContext } from 'react-hook-form'
import { Check, ChevronRight, FileText } from 'lucide-react'
import { useAuth } from '../../../context/AuthContext'
import Button from '../../../components/common/Button'
import Input from '../../../components/common/Input'
import Textarea from '../../../components/common/Textarea'
import TermsModal from './TermsModal'
import StepIntro from './StepIntro'

/** Bước 5 — review dạng bảng một cột, giống màn “Xem lại trước khi gửi” trong Figma. */
export default function ConsentStep({ event, options = {}, onGoToStep }) {
  const { user } = useAuth()
  const [termsOpen, setTermsOpen] = useState(false)
  const {
    register,
    watch,
    setValue,
    formState: { errors },
  } = useFormContext()

  const profile = watch('profile') ?? {}
  const participating = watch('is_participating') === 'yes'
  const agreed = Boolean(watch('agreed_terms'))
  const companionCount = watch('companion_count') ?? 0
  const shift = options.shifts?.find((item) => String(item.id) === watch('shift_id'))
  const busNeeds = watch('bus_needs') ?? []
  const busCount = busNeeds.filter((item) => item.needs_bus).length
  const firstPickup = busNeeds.find((item) => item.needs_bus)?.pickup_point_id
  const pickup = options.pickup_points?.find((item) => String(item.id) === String(firstPickup))
  const personName = user?.full_name || profile.display_name || 'Theo hồ sơ cá nhân'
  const teamName = user?.team_name || user?.team?.name

  return (
    <div className="flex flex-col gap-4">
      <StepIntro
        step="5"
        eyebrow="Mong muốn & xem lại"
        title="Xem lại trước khi gửi."
        description="Kiểm tra thông tin một lần cuối. Bạn có thể sửa từng phần trước khi gửi đăng ký."
        mobileEyebrow="Gần xong rồi"
        mobileTitle="Xem lại trước khi gửi."
        mobileDescription=""
      />

      <section className="overflow-hidden rounded-xl border border-hairline bg-surface shadow-soft">
        <ReviewRow label="Thông tin cá nhân" value={[personName, teamName, profile.phone].filter(Boolean).join(' · ')} onEdit={() => onGoToStep?.(0)} />
        <ReviewRow
          label="Tham gia"
          value={participating ? `Có · ${agreed ? `đã đồng ý quy định ${event.terms_version || 'hiện hành'}` : 'chưa đồng ý quy định'}` : 'Không tham gia'}
          onEdit={() => onGoToStep?.(1)}
        />
        {participating && (
          <>
            <ReviewRow label="Ca đi" value={formatShift(shift?.name)} onEdit={() => onGoToStep?.(2)} />
            <ReviewRow
              label="Xe BTC"
              value={`${busCount}/${busNeeds.length} chặng${pickup ? ` · đón tại ${pickup.name}` : ''}`}
              onEdit={() => onGoToStep?.(3)}
            />
            <ReviewRow label="Người đi cùng" value={`${companionCount} người`} onEdit={() => document.getElementById('companion-count')?.focus()} />
          </>
        )}
      </section>

      <section>
        <label htmlFor="wish-note" className="text-body-sm font-semibold text-ink">
          Bạn có mong muốn gì cho kỳ này không?
        </label>
        <Textarea
          id="wish-note"
          className="mt-2"
          rows={3}
          maxLength={2000}
          counterValue={watch('wish_note') ?? ''}
          placeholder="Ví dụ: muốn ở cùng phòng với Hoàng Tuấn (Team Product) nếu được ạ."
          error={errors.wish_note?.message}
          {...register('wish_note')}
        />
        <p className="mt-1.5 text-caption text-ink-faint">BTC sẽ cân nhắc, nhưng không cam kết đáp ứng.</p>
        <div className="mt-4 flex items-start gap-2 rounded-lg bg-blue-50 px-3 py-3 text-body-sm leading-relaxed text-primary max-md:flex md:hidden">
          <FileText className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <span>Sau khi gửi, bạn nhận email xác nhận và vẫn sửa được tới 23:59, 01/10.</span>
        </div>
      </section>

      {participating && (
        <section className="rounded-xl border border-hairline bg-surface p-3 shadow-soft">
          <Input
            id="companion-count"
            label="Số người đi cùng"
            type="number"
            min="0"
            max="5"
            inputMode="numeric"
            hint="Nếu BTC cho phép, nhập số người thân/khách đi cùng (0–5)."
            error={errors.companion_count?.message}
            {...register('companion_count')}
          />
        </section>
      )}

      {participating && (
        <section className="rounded-xl border border-hairline bg-surface px-4 py-3 max-md:hidden">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <span className={`grid size-6 place-items-center rounded-full ${agreed ? 'bg-accent-green text-on-primary' : 'bg-canvas-soft text-ink-muted'}`}>
                <Check className="size-3.5" strokeWidth={3} aria-hidden="true" />
              </span>
              <span className="text-body-sm text-ink">Đồng ý quy định chương trình</span>
            </div>
            <Button type="button" variant="ghost" size="sm" icon={FileText} onClick={() => setTermsOpen(true)}>
              {agreed ? 'Xem lại quy định' : 'Đọc quy định'}
            </Button>
          </div>
          <label className="mt-3 flex items-start gap-2.5 text-caption text-ink-muted">
            <input
              type="checkbox"
              className="mt-0.5 size-4 accent-primary"
              disabled={!agreed}
              checked={agreed}
              onChange={(changeEvent) => setValue('agreed_terms', changeEvent.target.checked, { shouldValidate: true })}
            />
            Tôi đã đọc và đồng ý quy định huỷ tham gia và phí phạt.
          </label>
          {errors.agreed_terms && <p className="mt-2 text-caption text-rose-600">{errors.agreed_terms.message}</p>}
        </section>
      )}

      {participating && (
        <TermsModal
          event={event}
          open={termsOpen}
          onClose={() => setTermsOpen(false)}
          onAgree={(version) => {
            setValue('agreed_terms', true, { shouldValidate: true })
            setValue('agreed_terms_version', version)
          }}
        />
      )}
    </div>
  )
}

function ReviewRow({ label, value, onEdit }) {
  return (
    <div className="flex items-center gap-3 border-b border-hairline px-3.5 py-3 last:border-b-0 max-md:gap-2 max-md:px-4 max-md:py-3.5">
      <span className="w-36 shrink-0 text-body-sm text-ink-muted max-md:w-[104px]">{label}</span>
      <span className="min-w-0 flex-1 truncate text-body-sm font-semibold text-ink max-md:text-right">{value || 'Chưa chọn'}</span>
      <button type="button" className="inline-flex items-center gap-1 text-body-sm font-semibold text-primary hover:underline" onClick={onEdit}>
        Sửa <ChevronRight className="size-4" aria-hidden="true" />
      </button>
    </div>
  )
}

function formatShift(value) {
  if (!value) return 'Chưa chọn ca'
  return value.replace(' – bay sáng', ' · buổi sáng').replace(' – bay chiều', ' · buổi chiều')
}
