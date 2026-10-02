import { useState } from 'react'
import { useFormContext } from 'react-hook-form'
import { Check, CircleSlash, FileText, PartyPopper } from 'lucide-react'
import { formatDate } from '../../../utils/format'
import { missingFlightFields } from '../../../utils/schemas'
import Alert from '../../../components/common/Alert'
import Textarea from '../../../components/common/Textarea'
import StepIntro from './StepIntro'
import TermsModal from './TermsModal'

export default function ParticipationStep({ event, onGoToProfile }) {
  const [termsOpen, setTermsOpen] = useState(false)
  const { register, watch, setValue, formState: { errors } } = useFormContext()
  const choice = watch('is_participating')
  const reason = watch('not_participating_reason') ?? ''
  const missing = missingFlightFields(watch('profile'))
  const agreed = Boolean(watch('agreed_terms'))

  return (
    <div className="flex flex-col gap-4">
      <StepIntro
        step="2"
        eyebrow="Tham gia & quy định"
        title="Bạn có tham gia Team Building lần này không?"
        description={`${event.name} · ${formatDate(event.start_date)} – ${formatDate(event.end_date)}`}
        mobileEyebrow="Xác nhận tham gia"
        mobileTitle="Bạn đi cùng mọi người chứ?"
        mobileDescription=""
      />

      <section className="rounded-xl border border-hairline bg-surface p-3 shadow-soft max-md:border-0 max-md:bg-transparent max-md:p-0 max-md:shadow-none">
        <p className="text-body-sm font-semibold text-ink max-md:hidden">Xác nhận tham gia</p>
        <div className="mt-3 grid gap-2.5 sm:grid-cols-2 max-md:mt-4">
          <ParticipationOption
            name="is_participating"
            value="yes"
            icon={PartyPopper}
            checked={choice === 'yes'}
            onChange={(value) => setValue('is_participating', value, { shouldValidate: true })}
            title="Có, tôi tham gia"
            description="BTC sẽ xếp chuyến bay, xe, phòng và chỗ Gala cho bạn."
          />
          <ParticipationOption
            name="is_participating"
            value="no"
            icon={CircleSlash}
            checked={choice === 'no'}
            onChange={(value) => setValue('is_participating', value, { shouldValidate: true })}
            title="Không, tôi không tham gia"
            description="Gửi xác nhận để BTC không tính suất của bạn."
          />
        </div>
        {errors.is_participating && <p className="mt-3 text-caption text-rose-600">{errors.is_participating.message}</p>}
      </section>

      {choice === 'yes' && missing.length > 0 && (
        <Alert tone="error" title="Cần bổ sung hồ sơ trước khi tham gia">
          Thiếu <strong>{missing.join(', ')}</strong>. <button type="button" onClick={onGoToProfile} className="font-semibold underline underline-offset-2">Quay lại bước 1</button>
        </Alert>
      )}

      {choice === 'yes' && (
        <section className="participation-terms rounded-xl border border-hairline bg-surface p-3 shadow-soft max-md:border-0 max-md:bg-transparent max-md:p-0 max-md:shadow-none">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-body-sm font-semibold text-ink">Quy định & phí phạt</p>
              <p className="mt-0.5 text-caption text-ink-muted max-md:hidden">Đọc hết quy định trước khi xác nhận.</p>
            </div>
            <span className="hidden text-caption text-ink-faint max-md:inline">Đã đọc {agreed ? 100 : 62}%</span>
            <button type="button" className="inline-flex items-center gap-1.5 text-body-sm font-semibold text-primary max-md:hidden" onClick={() => setTermsOpen(true)}>
              <FileText className="size-4" aria-hidden="true" /> {agreed ? 'Đã đọc' : 'Đọc quy định'}
            </button>
          </div>
          <div className="mt-3 hidden h-1 overflow-hidden rounded-full bg-hairline max-md:block"><span className="block h-full rounded-full bg-primary" style={{ width: `${agreed ? 100 : 62}%` }} /></div>
          <div className="mt-2 rounded-lg border border-hairline px-3 py-2.5 text-body-sm leading-relaxed text-ink-secondary max-md:min-h-[250px] max-md:p-3.5">
            <p><strong>1. Huỷ tham gia.</strong> Trước khi BTC công bố, bạn tự huỷ trong đúng hạn.</p>
            <p className="mt-2"><strong>2. Sau khi công bố.</strong> Bạn gửi yêu cầu huỷ cho BTC duyệt.</p>
            <p className="mt-2"><strong>3. Không đi mà không báo.</strong> Chi phí đã đặt cho bạn có thể bị tính theo quy định.</p>
          </div>
          <p className="mt-2 text-center text-caption text-ink-faint">⌄ &nbsp;Cuộn hết để xác nhận</p>
          <label className={`mt-3 flex items-start gap-2.5 text-caption ${agreed ? 'text-ink-muted' : 'text-ink-faint'}`}>
            <input type="checkbox" className="mt-0.5 size-4 accent-primary" disabled={!agreed} checked={agreed} onChange={(changeEvent) => setValue('agreed_terms', changeEvent.target.checked, { shouldValidate: true })} />
            Tôi đã đọc và đồng ý quy định, gồm phí phạt khi huỷ sai quy định.
          </label>
          {errors.agreed_terms && <p className="mt-2 text-caption text-rose-600">{errors.agreed_terms.message}</p>}
        </section>
      )}

      {choice === 'no' && (
        <section className="rounded-xl border border-hairline bg-surface p-3 shadow-soft">
          <p className="text-body-sm font-semibold text-ink">Lý do không tham gia</p>
          <p className="mt-0.5 text-caption text-ink-muted">Không bắt buộc, nhưng giúp BTC thống kê.</p>
          <Textarea
            className="mt-3"
            rows={3}
            maxLength={512}
            counterValue={reason}
            placeholder="Ví dụ: trùng lịch công tác, lý do sức khoẻ, việc gia đình…"
            error={errors.not_participating_reason?.message}
            {...register('not_participating_reason')}
          />
        </section>
      )}

      {choice === 'yes' && <TermsModal event={event} open={termsOpen} onClose={() => setTermsOpen(false)} onAgree={(version) => {
        setValue('agreed_terms', true, { shouldValidate: true })
        setValue('agreed_terms_version', version, { shouldValidate: true })
      }} />}
    </div>
  )
}

function ParticipationOption({ name, value, icon: Icon, checked, onChange, title, description }) {
  return (
    <label className={`relative flex cursor-pointer items-start gap-2.5 rounded-xl border p-3 transition max-md:min-h-[94px] max-md:items-center max-md:p-4 ${checked ? 'border-primary bg-brand-50 ring-1 ring-primary' : 'border-hairline hover:border-primary'}`}>
      <input type="radio" name={name} value={value} checked={checked} onChange={() => onChange(value)} className="sr-only" />
      <span className={`grid size-9 shrink-0 place-items-center rounded-lg max-md:hidden ${checked ? 'bg-primary text-on-primary' : 'bg-canvas-soft text-ink-muted'}`}><Icon className="size-5" aria-hidden="true" /></span>
      <span><span className="block text-body-sm font-semibold text-ink max-md:text-body-md">{title}</span><span className="mt-1 block text-caption leading-relaxed text-ink-muted max-md:hidden">{description}</span></span>
      <span className={`ml-auto hidden size-6 place-items-center rounded-full border text-white max-md:grid ${checked ? 'border-primary bg-primary' : 'border-input-border bg-surface text-transparent'}`}><Check className="size-3.5" strokeWidth={3} aria-hidden="true" /></span>
    </label>
  )
}
